# BUILD GUIDE — Implementation Directive

Single source of truth for build order. Every task has: **work** → **acceptance test** (must be demonstrably true before the next task). Work top to bottom; do not skip acceptance tests — they are what make this fast (no rework) instead of just quick.

---

## 0. Environment Snapshot (measured 2026-10-08, this machine)

| Item | Value | Build consequence |
|------|-------|-------------------|
| CPU / RAM | Core Ultra 9 275HX, 24 threads / **63.5 GB** | Large models viable; STT never a bottleneck |
| GPU | **RTX 5080 Laptop, 16 GB VRAM**, driver 592.02 | FP16 inference for LLM+STT fits well |
| Node / npm | v22.17.0 / 11.7.0 | Electron base runs as-is |
| Python | 3.13.5 (`py` launcher) + **uv 0.11.7** | Use `uv` for the core service env |
| Ollama | running, client 0.33.3 | Local-first confirmed (no API mode needed per Q5) |
| Models already pulled | `nomic-embed-text` ✓ · `qwen3:30b` · `qwen2.5:32b` · `llama3:8b` · `mistral:7b` · `gpt-oss:20b` + large GGUFs | **Zero new downloads needed** for MVP |
| ffmpeg | not on PATH | Fine — we feed raw PCM from the capture device, no file decoding |

### Model decisions (locked)
- **LLM live default:** `qwen3:30b` (MoE A3B — fast decode on this hardware, strong instruction following). Fallback if p95 misses SLO: `llama3:8b` (fully in VRAM).
- **Embeddings:** `nomic-embed-text` (already pulled).
- **STT:** faster-whisper `medium` FP16 on the 5080 (expect ≪ real-time); fallback `small.en` int8 CPU. No API STT needed.
- **Vector store:** Qdrant if a local instance is available, else **sqlite-vec** in-process (zero-dependency default — fewer moving parts before an interview).

### Latency SLO (the number that matters)
Question-end → first bullet on overlay: **p50 ≤ 4 s, p95 ≤ 7 s.** Measured per-question in the session log; displayed in the status bar. Every task below that touches the pipeline must keep this green.

---

## 1. Repo Layout (target state)

```
interview_buddy/                  ← workspace root (the "markdown brain" lives here)
├── PLAN.md · ARCHITECTURE.md · OPEN_SOURCE_RESEARCH.md · QUESTIONS.md · BUILD_GUIDE.md
├── resume.md                     ← T-content-1
├── 04_projects.md                ← T-content-2
├── 05_qa_bank.md                 ← T-content-3 (seed Q + scripted answers)
├── job_descriptions/             ← per-interview JD files
└── app/                          ← the application (fork of elias-soykat/interview-copilot, MIT)
    ├── src/main/ ...             ← Electron shell (overlay window, hotkeys, stealth)
    ├── src/renderer/ ...         ← React UI (text-only overlay rendering)
    └── core/                     ← NEW: Python FastAPI service ("buddy-core")
        ├── main.py               ← WS/SSE server to the shell
        ├── audio_capture.py      ← WASAPI loopback + silence-gap synthesis
        ├── vad_endpoint.py       ← silero-vad endpointing
        ├── stt.py                ← faster-whisper wrapper (streaming partials)
        ├── question_gate.py      ← linguistic gate + classification routing
        ├── rag/                  ← chunker, embedder (Ollama), store (sqlite-vec/Qdrant)
        ├── llm.py                ← Ollama streaming client + prompt templates
        └── prompts/              ← tech.md · star.md · sysdesign.md · coding.md (from 01_system_prompt rules)
```

---

## 2. Task List

### Phase 0 — Foundations
**T0.1 Clone base into `app/`** *(done when: repo cloned, `npm install` clean, `npm run dev` opens a window)*
- Fork skeleton = interview-copilot (MIT). Keep its window manager, IPC layout, settings UI.

**T0.2 Python core scaffold** *(acceptance: `uv sync` in `app/core/`; `ws://localhost:8790/ws` accepts the shell; ping→pong < 5 ms)*
- uv-managed env (py3.13): fastapi, uvicorn[standard], websockets, pyaudiowpatch, faster-whisper, onnxruntime (silero), numpy, sqlite-vec, httpx.

**T0.3 Content: `resume.md`** *(acceptance: one page; every line traceable to 02/03 docs or gmcubedesigns.com/LinkedIn; user signs off)*
- Synthesize from `02_work_history.md`, `03_education_and_background.md`, portfolio site, LinkedIn. No invented facts.

**T0.4 Content: `04_projects.md`** *(acceptance: all 7 projects documented per ARCHITECTURE §7.2 template — SYNAPSE, Investment Matrix (StockMaster), Holdem-Trainer/PyHoldem Pro, Qdrant Search, Learning Tree, Sidekick LLM, Coder Core — each with metrics + ≥1 challenge→solution story; sources = the 7 local repos + portfolio site)*
- PyHoldem Pro: reuse `05_holdem_trainer_docs/CASE_STUDY.md` (already conforms).

**T0.5 Content: `05_qa_bank.md` seed** *(acceptance: ≥40 entries, each = question + scripted first-person answer grounded in T0.3/T0.4 docs; mix: system design, AI/LLM deep-dive, behavioral STAR (S/T/A/R explicit), project follow-ups)*
- Per Q8: these are prewritten seeds the model uses for on-the-spot answer development — retrieval pulls the closest scripted answers as few-shot grounding.

### Phase 1 — MVP live loop (the interview-ready path)
**T1.1 Audio capture** *(acceptance: play a test tone / recorded Zoom clip through speakers → core receives continuous 16 kHz stream with correct timestamps across silence gaps; unit test on synthetic playback/silence patterns)*
- PyAudioWPatch WASAPI loopback, default render endpoint; silence synthesis from discontinuity flags (ARCHITECTURE §2.1).

**T1.2 STT + live transcript** *(acceptance: 30 s of interviewer audio → final text on overlay within ≤ 1 s of endpoint; partials stream every ~500 ms)*
- faster-whisper `medium` FP16 (CUDAExecutionProvider); stream partials over WS to the shell.

**T1.3 Question gate + classification** *(acceptance: golden set of 30 transcripts → correct fire/no-fire ≥ 90%; type label correct ≥ 85%)*
- silero-vad endpoint (900 ms post-silence) + linguistic gate; manual override hotkey Ctrl+Alt+Q.

**T1.4 RAG over the brain** *(acceptance: ingest resume.md + 04_projects.md + a test JD → top-k retrieval returns the right project section for 20 probe questions, ≥ 9/10 per category)*
- markdown-aware chunker; nomic-embed-text via Ollama; sqlite-vec default.

**T1.5 Answer engine + prompt contracts** *(acceptance: format suite — STAR questions → exactly S/T/A/R bullets 30/30; tech → 4–6 grounded bullets, ≤ 200 words total, first-person, zero filler; every `[you]` bullet traceable to a doc)*
- Ollama `qwen3:30b`, streaming tokens → overlay renders progressively.

**T1.6 Overlay UI (text-only)** *(acceptance: window is transparent/frameless/always-on-top; only text visible over any background behind it; states per ARCHITECTURE §8; font-size hotkeys work)*
- Reuse fork's AnswerPanel; strip chrome; add `[you]`/`[general]` styling + latency readout.

**T1.7 Stealth layer (Teams-first)** *(acceptance: THE TEST — real Teams call, two accounts, share full desktop: overlay visible to user, absent from the shared view; also pass Zoom + Meet matrix; taskbar/Alt-Tab clean; zero audible UI sounds)*
- `setContentProtection(true)`; skipTaskbar/tool-window style; process-disguise toggle (Q11); pre-flight checklist screen.

**T1.8 Session logging + debrief stub** *(acceptance: every session writes transcript.jsonl + answers.jsonl with per-stage timings; debrief view lists questions asked vs briefing)*

### Phase 2 — Context depth
**T2.1 JD intake + gap analysis + briefing generator** (F9/F13) · **T2.2 confidence flags in UI** (F15) · **T2.3 system-design prompt tuning on real AI-eng questions** (F17)

### Phase 3 — Practice & hardening
**T3.1 Practice mode** (mic channel + TTS mock interviewer + rubric scoring, F12/F14) · **T3.2 latency tuning pass to SLO with p50/p95 harness** · **T3.3 stealth hardening: pre-flight auto-capture canary test**

### Phase 4 — Ship
Packaging (electron-builder NSIS), first-run wizard, README as portfolio artifact, macOS if wanted.

---

## 3. Commands Cheat-Sheet

```bash
# core service
cd app/core && uv sync && uv run uvicorn main:app --port 8790

# shell (after T0.1)
cd app && npm install && npm run dev

# models (all already pulled — verify only)
ollama list | findstr "qwen3:30b nomic-embed-text"

# latency SLO harness (Phase 3, but usable from T1.5)
cd app/core && uv run python bench/latency_slo.py --questions fixtures/golden.jsonl
```

## 4. Definition of Done — "Interview Ready" (Teams)

1. Pre-flight screen passes on this machine: Ollama warm (`qwen3:30b` + `nomic-embed-text`), STT engine loaded, loopback device = the endpoint Teams uses, content-protection verified by canary capture test.
2. 10-question mock Teams call (self vs self): SLO green on p50; STAR format 10/10; overlay invisible in shared view; nothing in taskbar/Alt-Tab; no sounds heard by the far end.
3. `job_descriptions/<next-role>.md` exists with parsed skills + gap report + top-10 briefing reviewed by user.
4. Fallbacks known: second monitor placement ready (Q10); process-disguise toggle location known; API-free operation confirmed offline (kill Wi-Fi test).
