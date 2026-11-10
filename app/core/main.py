"""Interview Buddy — buddy-core service.

Pipeline: WASAPI loopback capture -> 16 kHz ring buffer -> RMS endpointing ->
faster-whisper STT (partials + finals) -> WebSocket to the Electron shell ->
(shell-side question detector fires) -> Ollama streaming answer grounded in the
markdown brain (RAG).

Run:  uv run python main.py     (from app/core/)
"""
from __future__ import annotations

import asyncio
import json
import time
from collections import deque
from contextlib import asynccontextmanager
from pathlib import Path

try:
    import webrtcvad
except ImportError:
    webrtcvad = None

import httpx
import numpy as np
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from .audio_capture import TARGET_RATE, LoopbackCapture
from .brain import Brain
from .router import HybridRouter
from .prompts import build_system_prompt
from .stt import Transcriber

try:
    from app.ai.factory import ProviderFactory
except ImportError:
    try:
        from .ai.factory import ProviderFactory
    except ImportError:
        ProviderFactory = None

CONFIG_PATH = Path(__file__).parent / "config.json"


def load_config() -> dict:
    """Load configuration from JSON file and resolve the brain directory."""
    with open(CONFIG_PATH, encoding="utf-8") as f:
        cfg = json.load(f)
    # Resolve brain_dir relative to the config file so the path is stable
    # regardless of where the process / pytest is launched from.
    brain_dir = Path(cfg["brain_dir"])
    if not brain_dir.is_absolute():
        brain_dir = (CONFIG_PATH.parent / brain_dir).resolve()
    # Fallback: if the runtime brain files aren't at the configured dir,
    # check docs/ (where they live in this repo layout).
    key_files = ("resume.md", "04_projects.md", "05_qa_bank.md")
    if not any((brain_dir / name).exists() for name in key_files):
        alt = CONFIG_PATH.parent.parent / "docs"
        if any((alt / name).exists() for name in key_files):
            brain_dir = alt
    cfg["brain_dir"] = str(brain_dir)
    return cfg


CFG = load_config()
RING_SECONDS = 30
FRAME_SAMPLES = int(0.03 * TARGET_RATE)  # 30 ms endpointing frame


def rms(x: np.ndarray | list[float]) -> float:
    """Compute Root Mean Square for endpointing signal energy."""
    if len(x) == 0:
        return 0.0
    arr = np.asarray(x, dtype=np.float32)
    return float(np.sqrt(np.mean(np.square(arr))))


class Core:
    """
    Main application core for Interview Buddy.
    
    Manages the lifecycle of the RAG brain, STT engine, and the 
    live WebSocket session loop.
    """

    def __init__(self):
        self.brain = Brain(CFG["brain_dir"], CFG["ollama_url"])
        self.transcriber: Transcriber | None = None
        self.stt_status = "loading"
        self.clients: set[WebSocket] = set()
        self.session_active = False
        self._session_task: asyncio.Task | None = None
        self._capture: LoopbackCapture | None = None
        self.last_final_text = ""
        self.session_dir: Path | None = None
        # expose brain data for tests
        self._chunks: list[str] = []
        self._vectors = None
        # Trie instant-answer state
        self._trie_answered = False
        self._trie_answered_for = ""   # normalized text the trie answered (prevents RAG dup)
        self._current_utterance_text = ""
        # RAG dedup guard — prevents double-firing on the same utterance
        self._last_rag_text = ""

        # Router and provider instances — share the Brain so embeddings are loaded only once
        self.router = HybridRouter(CFG, brain=self.brain)
        self.provider = ProviderFactory.create_provider(CFG) if ProviderFactory else None

    def load(self, force: bool = False):
        """Helper to load brain chunks and vectors for testing."""
        self.brain.load(force=force)
        self._chunks = self.brain._chunks
        self._vectors = self.brain._vectors

    def retrieve(self, query: str, k: int = 8) -> list[str]:
        """Helper to retrieve brain chunks for testing."""
        return self.brain.retrieve(query, k=k)

    # ---------------- lifecycle ----------------

    async def startup(self):
        """Initialize components during FastAPI startup."""
        # Offload brain loading to a thread to prevent blocking the FastAPI startup (which holds the port)
        # This ensures that /health remains responsive while the brain is being initialized.
        try:
            await asyncio.to_thread(self.brain.load)
        except Exception as e:
            print(f"[core] brain load failed (will retry on first ask): {e}", flush=True)

        async def _load_stt():
            try:
                self.transcriber = await asyncio.to_thread(Transcriber, CFG["stt_model"])
                self.stt_status = "ready"
            except Exception as e:
                self.stt_status = f"error: {e}"
                print(f"[core] STT load failed: {e}", flush=True)

        asyncio.create_task(_load_stt())

    # ---------------- wrappers for testing ----------------

    def load(self, force: bool = False) -> None:
        """Load brain data and expose chunks/vectors for tests."""
        self.brain.load(force=force)
        self._chunks = self.brain._chunks
        self._vectors = getattr(self.brain, "_vectors", None)

    def retrieve(self, query: str, k: int = 8) -> list[str]:
        """Retrieve relevant chunks via brain."""
        return self.brain.retrieve(query, k)

    def reload_config(self) -> dict:
        """Re-read config.json and update CFG in place (for model switching)."""
        global CFG
        new_cfg = load_config()
        CFG.clear()
        CFG.update(new_cfg)
        # Re-initialize router with new config (trie stays, config changes)
        self.router.config = CFG
        print(f"[core] config reloaded: llm_model={CFG['llm_model']}", flush=True)
        return CFG

    # ---------------- ws plumbing ----------------

    async def broadcast(self, msg: dict):
        """Broadcast a message to all connected shell clients."""
        dead: list[WebSocket] = []
        for ws in list(self.clients):
            try:
                await ws.send_text(json.dumps(msg))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.clients.discard(ws)

    def log_session(self, kind: str, **fields):
        """Log a session event to a local JSONL file."""
        if self.session_dir is None:
            return
        try:
            with open(self.session_dir / "session.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps({"t": round(time.time(), 3), "kind": kind, **fields}) + "\n")
        except Exception:
            pass

    # ---------------- session control ----------------

    async def start_session(self):
        """Initialize session storage and start the live loop."""
        if self.session_active:
            return
        ts = time.strftime("%Y%m%d-%H%M%S")
        self.session_dir = Path.home() / ".interview-buddy" / "sessions" / ts
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.session_active = True
        self._session_task = asyncio.create_task(self._session_loop())
        await self.broadcast({"t": "status", "msg": f"session started ({ts})"})

    async def stop_session(self):
        """Stop the live loop and cleanup resources."""
        if not self.session_active:
            return
        self.session_active = False
        if self._capture is not None:
            try:
                self._capture.stop()
            except Exception:
                pass
            self._capture = None
        await self.broadcast({"t": "status", "msg": "session stopped"})

    # ---------------- the live loop ----------------

    async def _session_loop(self):
        try:
            cap = LoopbackCapture()
            self._capture = cap
            ring: list[float] = []
            total_written = 0
            last_tick = time.time()
            noise_floor = 0.0025
            in_speech = False
            speech_start_total = 0
            speech_start_time = 0.0  # wall clock when continuous speech began
            silence_since: float | None = None
            last_partial_at = 0.0
            last_partial_text = ""
            stt_lock = asyncio.Lock()

            await self.broadcast({"t": "status", "msg": f"listening on {cap.device_name!r}"})

            # Initialize VAD if available - using level 1 (least aggressive) to ensure sensitivity
            vad = webrtcvad.Vad(1) if webrtcvad else None

            while self.session_active:
                samples, elapsed = await asyncio.to_thread(cap.read, 0.02)
                now = time.time()
                expected = int(elapsed * TARGET_RATE)
                if len(samples) == 0 and expected > 0:
                    samples = np.zeros(expected, dtype=np.float32)

                ring.extend(samples.tolist())
                total_written += len(samples)
                max_samples = RING_SECONDS * TARGET_RATE
                if len(ring) > max_samples:
                    excess = len(ring) - max_samples
                    del ring[:excess]
                    speech_start_total = max(0, speech_start_total - excess)
                last_tick = now

                # ---- endpointing on the newest 30 ms frame ----
                frame = np.array(ring[-FRAME_SAMPLES:], dtype=np.float32) if len(ring) >= FRAME_SAMPLES else np.zeros(0, dtype=np.float32)
                
                is_speech = False
                if vad is not None and len(frame) == FRAME_SAMPLES:
                    # webrtcvad needs 16-bit PCM mono
                    int_frame = (frame * 32767).astype(np.int16).tobytes()
                    is_speech = vad.is_speech(int_frame, TARGET_RATE)
                else:
                    # Fallback to simple RMS if VAD is missing or frame size is odd
                    r = rms(frame)
                    # Use a more sensitive fallback threshold (similar to original noise floor logic)
                    is_speech = r > 0.004

                if not in_speech and is_speech:
                    in_speech = True
                    speech_start_total = total_written - len(frame)
                    speech_start_time = now
                    silence_since = None
                    self._trie_answered = False
                    self._trie_answered_for = ""
                    self._current_utterance_text = ""
                    await self.broadcast({"t": "speech_started"})
                elif in_speech:
                    if not is_speech:
                        if silence_since is None:
                            silence_since = now
                        elif now - silence_since >= CFG["silence_ms"] / 1000.0:
                            start = max(0, speech_start_total - int(0.3 * TARGET_RATE))
                            # utterance window from the ring (ring holds last RING_SECONDS)
                            ring_start_abs = total_written - len(ring)
                            lo = max(0, start - ring_start_abs)
                            audio = np.array(ring[lo:], dtype=np.float32) if lo < len(ring) else np.zeros(0, dtype=np.float32)
                            in_speech = False
                            silence_since = None
                            speech_start_time = 0.0
                            text = ""
                            if self.transcriber is not None and len(audio) > 1600:
                                async with stt_lock:
                                    try:
                                        text = await asyncio.to_thread(self.transcriber.transcribe, audio, True)
                                    except Exception as e:
                                        print(f"[core] STT error: {e}", flush=True)
                            if text:
                                self.last_final_text = text
                                self.log_session("final", text=text)
                                await self.broadcast({"t": "final", "text": text})

                                # ---- auto-trigger RAG on final transcripts ----
                                # Fire RAG on every final utterance independent of the trie.
                                # If the trie already answered this exact question on a partial,
                                # RAG is suppressed in _answer_inner to avoid duplicate answers.
                                if (
                                    len(text.split()) >= 3
                                    and text != self._last_rag_text
                                    and text != self._trie_answered_for
                                ):
                                    self._last_rag_text = text
                                    asyncio.create_task(self.answer(text))
                    else:
                        silence_since = None
                        # Force endpoint if continuous speech exceeds max_utterance_s
                        # (interviewer keeps talking without a silence gap)
                        max_utterance_s = CFG.get("max_utterance_s", 15)
                        if speech_start_time > 0 and now - speech_start_time >= max_utterance_s:
                            start = max(0, speech_start_total - int(0.3 * TARGET_RATE))
                            ring_start_abs = total_written - len(ring)
                            lo = max(0, start - ring_start_abs)
                            audio = np.array(ring[lo:], dtype=np.float32) if lo < len(ring) else np.zeros(0, dtype=np.float32)
                            in_speech = False
                            speech_start_time = 0.0
                            text = ""
                            if self.transcriber is not None and len(audio) > 1600:
                                async with stt_lock:
                                    try:
                                        text = await asyncio.to_thread(self.transcriber.transcribe, audio, True)
                                    except Exception as e:
                                        print(f"[core] STT error: {e}", flush=True)
                            if text:
                                self.last_final_text = text
                                self.log_session("final", text=text)
                                await self.broadcast({"t": "final", "text": text})

                                if (
                                    len(text.split()) >= 3
                                    and text != self._last_rag_text
                                    and text != self._trie_answered_for
                                ):
                                    self._last_rag_text = text
                                    asyncio.create_task(self.answer(text))

                # ---- live partials (skip while a final transcription is running) ----
                if now - last_partial_at >= CFG["partial_interval_s"] and not stt_lock.locked():
                    recently_active = in_speech or (silence_since is not None and now - silence_since < 2.0)
                    if self.transcriber is not None and recently_active:
                        n = int(min(len(ring), 15.0 * TARGET_RATE))
                        if n > 4800:  # >= 0.3 s of audio in the window
                            partial_audio = np.array(ring[-n:], dtype=np.float32)
                            try:
                                text = await asyncio.to_thread(self.transcriber.transcribe, partial_audio, True)
                            except Exception:
                                text = ""
                            if text and text != last_partial_text:
                                last_partial_text = text
                                last_partial_at = now
                                await self.broadcast({"t": "partial", "text": text})

                                # ---- instant trie match on rolling partials ----
                                if not self._trie_answered:
                                    trie_hit = self.router.trie.search_prefix(text)
                                    if trie_hit:
                                        content = trie_hit.get("answer", "")
                                        self._trie_answered = True
                                        self._trie_answered_for = text
                                        await self.broadcast({"t": "answer_start", "question": text})
                                        self.log_session("answer_trie_start", question=text)
                                        await self.broadcast({"t": "token", "text": content})
                                        await self.broadcast(
                                            {
                                                "t": "answer_end",
                                                "full": content,
                                                "latency_ms": 0,
                                                "source": "trie",
                                            }
                                        )
                                        self.log_session(
                                            "answer_trie_end",
                                            question=text,
                                            full=content,
                                            latency_ms=0,
                                            source="trie",
                                        )
        except Exception as e:
            print(f"[core] Error in session loop: {e}", flush=True)
            import traceback
            traceback.print_exc()
        finally:
            if self._capture:
                try:
                    self._capture.stop()
                except Exception:
                    pass
                self._capture = None

    # ---------------- answering ----------------

    async def answer(self, question: str):
        """
        Handles the generation of an answer to an interview question.
        
        Uses the HybridRouter to decide between a deterministic Trie match
        (from the QA bank) and RAG-based generation.
        """
        t0 = time.time()

        try:
            await self._answer_inner(question, t0)
        except Exception as e:
            print(f"[core] answer failed: {e}", flush=True)
            import traceback
            traceback.print_exc()
            try:
                await self.broadcast({"t": "answer_error", "error": str(e)})
            except Exception:
                pass

    async def _answer_inner(self, question: str, t0: float):
        """Inner answer logic separated so exceptions are caught and surfaced."""
        # If the trie already answered this exact utterance on a partial, skip RAG.
        if self._trie_answered and question == self._trie_answered_for:
            return

        if not self.brain.ready:
            try:
                await asyncio.to_thread(self.brain.load)
            except Exception as e:
                print(f"[core] brain load failed: {e}", flush=True)

        # Trie first: instant scripted answer, never touches Ollama.
        # If the trie hits here (not already handled on partials), answer immediately.
        resolution = await self.router.resolve_query(question)
        if resolution.get("trie_hit"):
            content = resolution.get("content", "")
            await self.broadcast({"t": "answer_start", "question": question})
            self.log_session("answer_start", question=question)
            await self.broadcast({"t": "token", "text": content})
            latency_ms = int((time.time() - t0) * 1000)
            self.log_session("answer_end", full=content, latency_ms=latency_ms)
            await self.broadcast({"t": "answer_end", "full": content, "latency_ms": latency_ms})
            return

        # Fallback to RAG generation
        # We reuse the brain's retrieval to get the best chunks for the prompt
        print(f"[core] RAG starting for: {question[:80]}", flush=True)
        evidence = []
        try:
            evidence = await asyncio.to_thread(self.brain.retrieve, question, 8)
        except Exception as e:
            print(f"[core] retrieve failed: {e}", flush=True)
        
        print(f"[core] RAG retrieved {len(evidence)} chunks", flush=True)
        if evidence and isinstance(evidence, list):
            content = "\n".join(evidence)
            print(f"[core] RAG evidence total {len(content)} chars", flush=True)
            
        # Build system prompt with gathered evidence
        system = build_system_prompt(self.brain.profile_summary, evidence, self.brain.jd_context())
        
        await self.broadcast({"t": "answer_start", "question": question})
        self.log_session("answer_start", question=question)

        full = ""
        try:
            print(f"[core] RAG calling Ollama chat ({CFG['llm_model']})", flush=True)
            async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
                async with client.stream(
                    "POST",
                    f"{CFG['ollama_url'].rstrip('/')}/api/chat",
                    json={
                        "model": CFG["llm_model"],
                        "stream": True,
                        "keep_alive": "30m",
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": question},
                        ],
                        "options": {"temperature": 0.4, "num_predict": 200, "num_ctx": 2048},
                        "think": False,
                    },
                ) as resp:
                    if resp.status_code != 200:
                        err_body = await resp.aread()
                        raise RuntimeError(f"Ollama returned HTTP {resp.status_code}: {err_body.decode('utf-8', errors='ignore')}")
                    async for line in resp.aiter_lines():
                        if not line.strip():
                            continue
                        try:
                            obj = json.loads(line)
                        except Exception:
                            continue
                        if "error" in obj:
                            raise RuntimeError(f"Ollama error: {obj['error']}")
                        msg = obj.get("message", {})
                        # reasoning models stream a separate 'thinking' field —
                        # only stream content to the overlay.
                        tok = msg.get("content", "")
                        if tok:
                            full += tok
                            await self.broadcast({"t": "token", "text": tok})
            print(f"[core] RAG complete: {len(full)} chars in {int((time.time() - t0) * 1000)}ms", flush=True)
        except Exception as e:
            print(f"[core] LLM error: {e}", flush=True)
            await self.broadcast({"t": "answer_error", "error": str(e)})

        latency_ms = int((time.time() - t0) * 1000)
        self.log_session("answer_end", full=full, latency_ms=latency_ms)
        await self.broadcast({"t": "answer_end", "full": full, "latency_ms": latency_ms})


CORE = Core()

app = FastAPI(title="buddy-core")


@app.on_event("startup")
async def _startup():
    await CORE.startup()


@app.get("/health")
def health():
    return {
        "ok": True,
        "stt": CORE.stt_status,
        "brain_chunks": len(CORE.brain._chunks),
        "llm_model": CFG["llm_model"],
        "session_active": CORE.session_active,
    }


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    CORE.clients.add(ws)
    print("[core] shell connected", flush=True)
    try:
        while True:
            msg = json.loads(await ws.receive_text())
            t = msg.get("t")
            if t == "start":
                await CORE.start_session()
            elif t == "stop":
                await CORE.stop_session()
            elif t == "ask" and msg.get("text"):
                asyncio.create_task(CORE.answer(msg["text"]))
            elif t == "trigger" and CORE.last_final_text:
                asyncio.create_task(CORE.answer(CORE.last_final_text))
            elif t == "reload_config":
                CORE.reload_config()
                await ws.send_text(json.dumps({"t": "config_reloaded", "llm_model": CFG["llm_model"]}))
    except WebSocketDisconnect:
        pass
    finally:
        CORE.clients.discard(ws)
        print("[core] shell disconnected", flush=True)


def run():
    import uvicorn

    uvicorn.run(app, host=CFG["host"], port=int(CFG["port"]), log_level="warning")


if __name__ == "__main__":
    run()

