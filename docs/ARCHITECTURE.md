# Interview Buddy — Technical Architecture

Companion to [PLAN.md](PLAN.md). This document specifies how each requirement is implemented, with concrete APIs, models, and contracts.

---

## 1. System Overview

```
┌─────────────────────────── USER MACHINE (Windows-first) ───────────────────────────┐
│                                                                                    │
│  Zoom / Teams / Meet ──(interviewer audio)──► speakers/headphones                  │
│        ▲                                                        │                  │
│        │ mic (user's voice — NEVER captured in live mode)       │ rendered audio   │
│        └────────────────────────────────────────────┐           ▼                  │
│                                                   │    ┌─────────────────────┐     │
│  ┌──────────────────────────┐                      │    │  WASAPI LOOPBACK    │     │
│  │  ELECTRON SHELL          │◄── WebSocket/SSE ────┼──► │  capture (Python)   │     │
│  │  • transparent overlay   │      streamed tokens │    │  PyAudioWPatch      │     │
│  │  • settings/briefing UI  │◄─────────────────────┤    └──────────┬──────────┘     │
│  │  • setContentProtection  │                      │               ▼                │
│  │  • global hotkeys        │                      │    ┌─────────────────────┐     │
│  │  • tray (optional)       │                      │    │ silero-VAD endpoint │     │
│  └──────────────────────────┘                      │    │ + question detect   │     │
│                                                   │    └──────────┬──────────┘     │
│  ┌──────────────────────────┐                      │               ▼                │
│  │  OLLAMA (local AI)       │◄──── HTTP ──────────┼────► ┌─────────────────────┐   │
│  │  • LLM: qwen2.5/llama    │                     │      │ faster-whisper /    │   │
│  │  • embed: nomic-embed    │                     │      │ whisper.cpp STT     │   │
│  └──────────────────────────┘                     │      └──────────┬──────────┘   │
│                                                   │                 ▼               │
│  ┌──────────────────────────┐                      │      ┌─────────────────────┐   │
│  │  QDRANT (local vectors)  │◄──── gRPC/HTTP ─────┼──────│  RAG ASSEMBLY       │   │
│  │  • profile collection    │                     │      │  (FastAPI core svc)  │   │
│  │  • jd collections        │                     │      │  classify + retrieve │   │
│  └──────────────────────────┘                     │      │  + prompt build      │   │
│                                                   │      └─────────────────────┘   │
│  markdown brain: resume.md · 04_projects.md · job_descriptions/ · 05_qa_bank.md    │
└────────────────────────────────────────────────────────────────────────────────────┘
```

### Stack decision (and why)

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Shell/UI | **Electron + React + TypeScript** (fork of `elias-soykat/interview-copilot`, MIT) | Transparent frameless always-on-top windows are first-class; `setContentProtection()` is the screen-share invisibility primitive; clone candidate already has the right window/IPC skeleton. Tauri is lighter but its content-protection + transparency story is younger and the best OSS clones are Electron anyway. |
| Core service | **Python 3.12+ / FastAPI** ("buddy-core"), localhost WebSocket/SSE to shell | Audio capture (PyAudioWPatch), STT (faster-whisper/whisper.cpp bindings), VAD, RAG (Qdrant client) are all Python-native; matches the user's existing stack (FastAPI appears throughout PyHoldem Pro docs). Keeps heavy ML out of the renderer process. |
| LLM | **Ollama** local-first; OpenAI/Claude/Gemini via API as fallback mode | User already runs Ollama + Qdrant in production projects — Interview Buddy dogfoods his own stack (portfolio point). |
| Vectors | **Qdrant** (user has it) or **sqlite-vec** for zero-dependency builds | Profile is small (<10k chunks); either is overkill-fast. Qdrant keeps parity with his RAG experience. |
| STT | **faster-whisper** (CTranslate2, int8) default; whisper.cpp alternative; Moonshine/Parakeet if speed wins on user's hardware | See §4 latency table. API fallback: OpenAI `gpt-4o-mini-transcribe`. |

Process model: 3 processes — Electron shell, buddy-core (Python), Ollama (already a service). All local; nothing leaves the machine in local mode except (optionally) API-mode calls.

---

## 2. Audio Pipeline (R5: hear speakers, ignore mic)

### 2.1 Capture

- **Windows:** WASAPI loopback on the *default render endpoint* via `PyAudioWPatch` (`get_loopback_device_info_generator()`). This captures exactly what is rendered to speakers/headphones — i.e., the interviewer in Zoom/Meet — and structurally ignores microphone input (the mic is a separate capture endpoint we never open in live mode).
- **Silence-gap handling (critical, known WASAPI quirk):** loopback only delivers buffers while something is playing. The core service must synthesize silence using buffer timestamps + `AUDCLNT_BUFFERFLAGS_DATA_DISCONTINUITY` so the VAD sees a continuous, correctly-timed stream. (This is the documented NAudio/PyAudioWPatch pattern; without it, endpoint timing drifts and question detection fires late.)
- **Sample rate:** capture at device native (usually 48 kHz), resample to 16 kHz mono for STT/VAD.
- **macOS (P2):** ScreenCaptureKit audio stream (macOS 13+, requires Screen Recording permission) or CoreAudio tap / BlackHole virtual device fallback.
- **Self-capture guard:** the app plays no audible UI sounds in live mode, so it can't hear itself through loopback. If a sound is ever added, route it to a non-default endpoint or subtract its known waveform.

### 2.2 Endpointing & question detection (F3)

1. **VAD:** silero-vad (ONNX, runs in-process) on the 16 kHz stream → speech segments with start/end timestamps.
2. **Endpoint trigger:** segment end + configurable post-silence threshold (default **900 ms**; interview-copilot uses 1500 ms — too slow for live use; tune in Phase 3).
3. **Linguistic gate** on the STT final text: fire only if it looks like a question or task prompt — interrogatives (`what/why/how/can you/would you/tell me about`), imperative prompts (`walk me through`, `design X`, `solve this`), or ends with `?`. Reject: < 3 words, greetings ("hi", "can you hear me"), pure acknowledgments. Confidence score logged; below threshold → wait for manual hotkey (Ctrl+Alt+Q) or next segment.
4. **Follow-up awareness:** if a new question arrives while bullets are on screen, keep the previous Q in context (the LLM sees "already suggested: …" so it doesn't repeat itself — important because we never hear the user's answer).

### 2.3 Dual-channel design (for practice mode)

The mic channel exists but is **off by default** and only enabled in Practice Mode (F12), where the app *should* hear the user. Live mode = system-audio channel only, per R5. This mirrors Natively's dual-channel architecture and keeps the "we never record you" guarantee structurally true rather than policy-based.

---

## 3. Speech-to-Text (F2)

| Option | Model | Speed (typical) | Accuracy on muffled call audio | Notes |
|--------|-------|-----------------|-------------------------------|-------|
| **faster-whisper int8, CPU** | `small.en` / `medium` | ~real-time or faster on modern 8-core CPU; medium needs a good CPU | Good (small) → Very good (medium) | Default. CTranslate2 backend, no CUDA needed. |
| faster-whisper FP16, GPU | `medium` / `large-v3-turbo` | 5–20× real-time | Excellent | If user has NVIDIA/AMD GPU with enough VRAM (see QUESTIONS Q2). |
| whisper.cpp | same models, GGUF | Similar to faster-whisper; can fall behind on weak CPUs (known issue) | Same | Alternative if we want a single C++ runtime. |
| Moonshine-base / Parakeet-CTC 0.6B | small specialized ASR | Faster than Whisper-class at similar/better EN accuracy | Very good for clean speech, weaker on heavy accents/music | Strong candidate if p50 latency misses target. |
| OpenAI API (fallback mode) | `gpt-4o-mini-transcribe` / `whisper-1` | Network-bound, ~1–3s round trip | Excellent | Toggle in settings; requires internet + key. |

**Streaming:** partial transcripts pushed to the overlay every ~500 ms (small dim line — doubles as "capture is working" feedback). Final transcript emitted at endpoint; that final text is what goes to classification/LLM.

---

## 4. Question Classification & Answer Engine (F4, F6)

### 4.1 Classification

Single LLM call does both classification and answering (cheaper than a separate classifier pass on local hardware). The prompt returns structured output:

```json
{ "type": "tech | star | sysdesign | coding | smalltalk",
  "confidence": 0.93,
  "bullets": [ ... ],          // per-type contract below
  "opener": "...",             // optional one-liner
  "closer": "..." }            // optional one-liner, e.g., offer to go deeper
```

`smalltalk` → overlay shows a dim "no action needed" state (or nothing) instead of bullets.

### 4.2 Output contracts (the heart of R6)

**Technical question** — 4–6 bullets, each ≤ ~15 words, first-person, grounded:
```
• Built X with Ollama + Qdrant for Y; cut lookup latency from A to B   [you]
• Approach I'd take here: <key design point>                          [general]
...
opener: "On my StockMaster project I ran into exactly this —"
closer:  "Happy to go deeper on the evaluation side if useful."
```

**Experience/behavioral (STAR)** — *exactly four bullets, one per letter*, drawn from `02_work_history.md` / `04_projects.md`:
```
S: <situation in ≤15 words, real project/team context>      [you]
T: <my specific task/ownership>                             [you]
A: <actions — the technical meat, 1–2 bullets' worth>       [you]
R: <result with a number where docs provide one>            [you]
```

**System design (senior/AI-eng)** — skeleton bullets: components → data flow → scaling/trade-offs → failure modes; for AI questions specifically: RAG pipeline shape, eval strategy, inference cost/latency trade-offs, when *not* to use an LLM.

**Coding** — approach outline + key algorithm steps + complexity note (no full code unless the question demands it); if screenshot mode is on (F16), the captured problem text is prepended as context.

**Global rules (inherited from `01_system_prompt.md`, kept verbatim in spirit):** first-person only; zero chat filler ("Here's your answer" never appears); spoken-word tone; total ≤ ~200 words (~90 s read-aloud cap); scannable formatting, no tables/complex symbols.

### 4.3 Grounding & confidence flags (F15)

- Retrieved chunks carry `source` metadata (`resume`, `project:stockmaster`, `project:sidekick`, `project:pyholdem`, `jd:<name>`, `qa_bank`).
- Prompt rule: a bullet may claim an experience/metric **only** if present in retrieved context → tag `[you]`; otherwise it must be generic best practice → tag `[general]`. The overlay renders `[you]` bullets at full opacity, `[general]` slightly dimmed with a different marker — the user reads "defensible" vs "safe filler" at a glance.
- Post-generation validator (cheap regex/LLM check in dev builds): every number in a `[you]` bullet must appear in the cited chunk.

---

## 5. RAG Pipeline (F5)

### 5.1 Ingestion (offline, on doc change / app start)

```
markdown brain ──► markdown-aware chunker ──► embed (nomic-embed-text via Ollama)
   │                headers = boundaries        ▼
   │                300–500 tok chunks      Qdrant collections:
   │                overlap ~50 tok         • profile  (resume + projects, stable)
   └─► JD parser: skills[], seniority,       • jd_<slug> (per interview session)
        must-have vs nice-to-have            • qa_bank  (practice mode)
```

- **Chunking:** split on markdown headers first (a "Core Engineering Challenges" section stays intact — those are the STAR gold), then size-cap. Metadata: `source`, `section_path`, `project`.
- **Embeddings:** `nomic-embed-text` via Ollama (768-dim, local). Fallback: sentence-transformers `all-MiniLM-L6-v2` in-process if we ever drop the Ollama dependency for embeddings.
- **Retrieval per question:** top-k=8 from `profile` + top-k=4 from active `jd_<slug>` (JD-weighted — answers should sound like they're aimed at *this* role), rerank by score, dedupe near-duplicates. Always prepend the **condensed profile** (~300 tokens: role, 6+ yrs full-stack, Navy ASM background, certs, one-line-per-project) so identity never depends on retrieval luck.
- **Context budget:** system prompt + profile summary + retrieved chunks ≤ ~4k tokens total → keeps local-model prefill fast (see §9 latency).

### 5.2 JD intake & gap analysis (F9/F13)

On paste: LLM extracts `skills[], stack, seniority_signals, team/domain` into structured JSON stored with the session; then a **gap report** = JD skills × resume evidence → {covered | adjacent | missing}, each "missing/adjacent" row gets a prepared 20-second bridge answer (e.g., K8s ← Docker + AWS + CI/CD depth). The briefing generator (F9) produces the top-10 likely questions for this role with pre-generated bullets — the user reviews it *before* the interview, in normal (non-overlay) UI.

---

## 6. LLM Backends & Model Selection

| Mode | Model guidance | Expected first-token (warm) |
|------|----------------|------------------------------|
| Local, GPU ≥ 8 GB VRAM | `qwen2.5:14b` or `llama3.1:8b` Q4/Q6 via Ollama | ~0.5–1.5 s |
| Local, weak/none GPU (CPU) | `qwen2.5:7b` Q4_K_M; consider 3B if p95 misses | ~1.5–3 s TTFT, ~5 tok/s (measured on RTX-2050-class hardware in public benchmarks — expect similar or better on a modern desktop CPU) |
| API fallback | `gpt-4o-mini` / Claude Haiku class via OpenAI/Anthropic/OpenRouter | ~0.3–1 s + network |

- **Streaming is mandatory:** tokens stream shell→overlay as they arrive; bullets render progressively (first bullet visible well before the rest finish).
- **Two-stage option (P1):** stage 1 = truncated generation of just the first 3 bullets with a fast/small model or `num_predict` cap; stage 2 refines/expands if time permits. Implement only if single-stage p50 misses the 4 s target.
- **Warm-up:** pre-flight warms Ollama (dummy 1-token generation) and STT engine before the call — cold first-token after idle is a documented failure mode; the user's interview must not be the warmup.

---

## 7. Content Schema (the markdown brain)

### 7.1 `resume.md` (to create in Phase 0)
One page: contact line, summary (3 lines), experience (role → bullets with metrics), skills grouped as in `02_work_history.md`, education/certs from `03_education_and_background.md`. Synthesized from existing docs — no new facts invented.

### 7.2 Project case-study template (`04_projects.md` sections; PyHoldem Pro already conforms via `05_holdem_trainer_docs/`)
```markdown
## <Project Name>
**One-liner:** <what it does, for whom>
**Stack:** <technologies>
**Role & ownership:** <solo/team, what I owned end-to-end>
### Problem & context   (why it exists; the market gap)
### Solution & impact  (tangible results — NUMBERS where possible: latency, tests, users, $)
### Architecture       (diagram + decisions with justifications)
### Hard problems      (2–4 × challenge → solution → outcome; STAR raw material)
### Metrics            (every quantifiable fact in one list — retrieval goldmine)
```
StockMaster and Sidekick LLM need this treatment before Phase 1 exit criteria.

### 7.3 `job_descriptions/<role>_<company>.md`
Raw JD verbatim + machine-generated sections: parsed skills, gap report, top-10 briefing questions with pre-generated bullets (regenerated on demand).

---

## 8. UI Specification (F7)

**Window:** Electron `BrowserWindow { transparent:true, frame:false, alwaysOnTop:true, resizable:false, skipTaskbar:true, hasShadow:false, backgroundColor:'#00000000' }`, fixed size (default 420×560, user-adjustable in settings), draggable via a thin invisible top strip. `win.setContentProtection(true)` on show (see §10). Multi-monitor: default placement = **the monitor that is NOT being shared** (user picks once in setup; per-session override hotkey Ctrl+Alt+M moves it).

**Rendering — text only:** no visible borders, buttons, or backgrounds. Dark-on-light or light-on-dark auto by a single toggle; high-contrast with soft text-shadow for readability over arbitrary content behind the window. Font size 14–20 px adjustable (Ctrl+Alt+= / -). Markdown rendered as plain bullets/lines — never tables or code fences in live mode (code mode shows pseudocode, monospace, max ~8 lines).

**States:**
| State | Overlay shows |
|-------|---------------|
| IDLE (not started) | nothing (window hidden) |
| LISTENING | dim single line: live partial transcript of interviewer + tiny "●" pulse |
| QUESTION DETECTED | brief highlight flash on the final question text |
| GENERATING → ANSWER | bullets stream in; `[you]`/`[general]` markers; opener/closer lines styled distinctively (italic, dimmer) |
| PRACTICE | same + score badge after each answer |

**Global hotkeys:** Ctrl+Alt+Space start/stop session · Ctrl+Alt+Q force-answer now · Ctrl+Alt+H hide/show overlay · Ctrl+Alt+N next bullet / expand collapsed bullet · Ctrl+Alt+C clear current answer · Ctrl+Alt+=/- font size. All registered via Electron `globalShortcut`; none steal focus.

**Non-live UI (settings, briefing, practice, debrief):** normal opaque window — invisibility only matters during the call; pre-flight tells the user to minimize it before sharing starts.

---

## 9. Latency Budget (target: first bullet ≤ 4 s after question end)

| Stage | Budget | Notes |
|-------|--------|-------|
| Post-silence endpoint threshold | 0.3–0.9 s | Tunable; the dominant "perceived" delay — keep low, rely on linguistic gate to avoid false fires |
| STT final (10 s question) | ≤ 0.5 s (GPU/turbo model) – 1.5 s (CPU int8 small/medium) | faster-whisper processes shorter than real-time on adequate hardware |
| Classification + retrieval | ≤ 0.2 s | Retrieval is local vector search; classification folded into the answer call's prefill |
| LLM prefill (~4k ctx) + first bullet | 0.5–3 s warm, by hardware tier | §6 table |
| Shell render of first token | ≤ 100 ms | WebSocket streaming |
| **Total p50 target** | **≤ 4 s** | Measured in-app (status bar shows per-question timing); p95 ≤ 7 s |

Every stage emits a timestamp to the session log → the debrief screen shows where time went, and Phase 3 tuning is data-driven.

---

## 10. Stealth / Invisibility Layer (F8) — implementation details

| Mechanism | How |
|-----------|-----|
| **Excluded from all capture APIs** | `win.setContentProtection(true)` → Windows `SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE)` (Win10 2004+; user on Win11 build 26200 ✓). Excludes the window from BitBlt, DXGI Desktop Duplication, and Windows.Graphics.Capture — i.e., Zoom/Teams/Meet full-desktop shares. Fallback flag `WDA_MONITOR` for older builds (auto-selected by Electron). |
| **Zoom caveat** | Some Zoom versions use a capture mode that ignores the flag: Settings → Share Screen → Advanced → **"Advanced capture with window filtering"**. Pre-flight UI walks through this per tool; Teams/Meet respect the flag without config. |
| **Taskbar / Alt-Tab** | `skipTaskbar:true` + (Windows) extended style `WS_EX_TOOLWINDOW`; no tray icon by default. |
| **Process disguise (optional toggle)** | Rename process image to an innocuous utility name (pattern used by Natively & CodeInterviewAssist's `stealth-run.vbs`). Off by default; on = "no evidence even in Task Manager". |
| **No focus steal / no sounds** | Overlay never calls `focus()`; zero audible UI feedback in live mode. |
| **Notifications** | App suppresses its own toasts during a session; pre-flight suggests Windows Focus Assist. |
| **Fallback placement** | Second monitor (preferred) or a virtual desktop not being shared ("Share this desktop" option in Zoom/Teams). Pre-flight auto-detects monitor count and warns if single-monitor + full-desktop share is the only option. |
| **Pre-flight test (Phase 3)** | One-click: starts a capture of the primary screen via `Windows.Graphics.Capture` *without* content protection, renders a canary frame in the overlay region, asserts the canary is absent → "invisibility verified for this tool" before the interview. |

---

## 11. Data Model & Storage (local-only)

```
~/.interview-buddy/
├── config.json            # settings: models, hotkeys, monitor, opacity, flags
├── brain/                 # symlink or copy of the markdown workspace docs
├── qdrant/                # vector store data (or external Qdrant per config)
├── sessions/<ts>_<role>/
│   ├── session.json       # meta: JD used, models, timings per stage
│   ├── transcript.jsonl   # {t, text, final} — interviewer audio only
│   └── answers.jsonl      # {q_id, type, bullets[], sources[], latency_ms}
└── practice/              # question bank state, scores, spaced-repetition queue
```

No telemetry in v1. API mode sends only prompt context (never raw audio) — and the user can see exactly what leaves the machine via a "data out" log toggle.

---

## 12. Testing Strategy

- **Unit:** chunker, JD parser, linguistic gate (30+ recorded question transcripts), STAR-contract validator (exactly 4 labeled bullets), silence-gap synthesizer (synthetic playback/silence patterns).
- **Integration:** recorded Zoom/Teams audio fixtures → full pipeline → assert endpoint timing within ±200 ms and correct classification; WASAPI loopback test with a known-tone generator.
- **Latency benchmark harness:** scripted 10-question run, p50/p95 per stage, CI on the dev machine (this is the app's core metric — treat it like an SLO).
- **Invisibility matrix:** {Zoom, Teams, Meet} × {full desktop, window share} automated screenshot diff of the overlay region + manual canary test.
- **Prompt-contract suite:** 30 golden questions per type; assert format compliance (bullet count, word caps, first-person, no filler phrases) — run against each model in the rotation before it's allowed to be default.
