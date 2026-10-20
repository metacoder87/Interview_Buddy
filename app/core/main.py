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

import httpx
import numpy as np
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from .audio_capture import TARGET_RATE, LoopbackCapture
from .brain import Brain
from .prompts import build_system_prompt
from .stt import Transcriber

CONFIG_PATH = Path(__file__).parent / "config.json"


def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        cfg = json.load(f)
    # Resolve brain_dir relative to the config file so the path is stable
    # regardless of where the process / pytest is launched from.
    brain_dir = Path(cfg["brain_dir"])
    if not brain_dir.is_absolute():
        brain_dir = (CONFIG_PATH.parent / brain_dir).resolve()
    cfg["brain_dir"] = str(brain_dir)
    return cfg


CFG = load_config()
RING_SECONDS = 30
FRAME_SAMPLES = int(0.03 * TARGET_RATE)  # 30 ms endpointing frame


class Core:
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

    # ---------------- lifecycle ----------------

    async def startup(self):
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

    # ---------------- ws plumbing ----------------

    async def broadcast(self, msg: dict):
        dead: list[WebSocket] = []
        for ws in list(self.clients):
            try:
                await ws.send_text(json.dumps(msg))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.clients.discard(ws)

    def log_session(self, kind: str, **fields):
        if self.session_dir is None:
            return
        try:
            with open(self.session_dir / "session.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps({"t": round(time.time(), 3), "kind": kind, **fields}) + "\n")
        except Exception:
            pass

    # ---------------- session control ----------------

    async def start_session(self):
        if self.session_active:
            return
        ts = time.strftime("%Y%m%d-%H%M%S")
        self.session_dir = Path.home() / ".interview-buddy" / "sessions" / ts
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.session_active = True
        self._session_task = asyncio.create_task(self._session_loop())
        await self.broadcast({"t": "status", "msg": f"session started ({ts})"})

    async def stop_session(self):
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
        cap = LoopbackCapture()
        self._capture = cap
        ring: list[float] = []
        total_written = 0
        last_tick = time.time()
        noise_floor = 0.0025
        in_speech = False
        speech_start_total = 0
        silence_since: float | None = None
        last_partial_at = 0.0
        last_partial_text = ""
        stt_lock = asyncio.Lock()

        def rms(x: np.ndarray) -> float:
            return float(np.sqrt(np.mean(np.square(x)))) if len(x) else 0.0

        await self.broadcast({"t": "status", "msg": f"listening on {cap.device_name!r}"})

        while self.session_active:
            samples, elapsed = cap.read(timeout=0.02)
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
            frame = np.array(ring[-FRAME_SAMPLES:], dtype=np.float32) if len(ring) >= FRAME_SAMPLES else np.zeros(0)
            r = rms(frame)
            if r < noise_floor * 1.6:
                noise_floor = max(0.0005, 0.97 * noise_floor + 0.03 * r)
            thr = max(noise_floor * 3.0, 0.004)

            if not in_speech and len(frame) and r > thr:
                in_speech = True
                speech_start_total = total_written - len(frame)
                silence_since = None
                await self.broadcast({"t": "speech_started"})
            elif in_speech:
                if r <= thr:
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
                else:
                    silence_since = None

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

        try:
            cap.stop()
        finally:
            self._capture = None

    # ---------------- answering ----------------

    async def answer(self, question: str):
        t0 = time.time()
        if not self.brain.ready:
            try:
                await asyncio.to_thread(self.brain.load)
            except Exception as e:
                print(f"[core] brain load failed: {e}", flush=True)

        evidence = []
        try:
            evidence = await asyncio.to_thread(self.brain.retrieve, question, 8)
        except Exception as e:
            print(f"[core] retrieve failed: {e}", flush=True)

        system = build_system_prompt(self.brain.profile_summary, evidence, self.brain.jd_context())
        await self.broadcast({"t": "answer_start", "question": question})
        self.log_session("answer_start", question=question)

        full = ""
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=10.0)) as client:
                async with client.stream(
                    "POST",
                    f"{CFG['ollama_url'].rstrip('/')}/api/chat",
                    json={
                        "model": CFG["llm_model"],
                        "stream": True,
                        # keep the model resident for the whole interview
                        "keep_alive": "30m",
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": question},
                        ],
                        "options": {"temperature": 0.4, "num_predict": 700},
                    },
                ) as resp:
                    async for line in resp.aiter_lines():
                        if not line.strip():
                            continue
                        try:
                            obj = json.loads(line)
                        except Exception:
                            continue
                        msg = obj.get("message", {})
                        # reasoning models (qwen3) stream a separate 'thinking'
                        # field — never show that on the overlay, only content.
                        tok = msg.get("content", "")
                        if tok:
                            full += tok
                            await self.broadcast({"t": "token", "text": tok})
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
