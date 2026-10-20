# Interview Buddy — MVP Completion Plan

**Date:** 2026-10-15 · **Status:** Ready to execute
**Companions:** [PLAN.md](PLAN.md) (what we're building) · [ARCHITECTURE.md](ARCHITECTURE.md) (how it's designed) · [BUILD_GUIDE.md](BUILD_GUIDE.md) (task IDs referenced below)

Work top to bottom. Every step is one small action with a pass/fail check — if a check fails, fix that step before moving on. Task IDs (T0.x–T3.x) refer to BUILD_GUIDE §2 so this plan stays aligned with the original build order.

---

## Current state snapshot (verified 2026-10-15)

| Area | State | Evidence |
|------|-------|----------|
| T0.1 Fork + Electron shell | ✅ Done | `app/` runs via electron-vite; transparent/frameless/on-top/skipTaskbar/contentProtection all set in `src/main/index.ts` |
| T0.2 Core scaffold (FastAPI WS :8790) | ✅ Done | `run_interview_buddy.ps1` launches Ollama → core → shell; `/health` works |
| T0.3 `resume.md` | ✅ Done | Complete, one page, in `docs/` |
| T0.4 `04_projects.md` (7 projects) | ✅ Done | All 7 case studies + cross-project themes, in `docs/` |
| T0.5 `05_qa_bank.md` seed | 🟡 26 entries (target ≥40) | In `docs/`, high quality |
| T1.1 WASAPI loopback capture | 🟡 Implemented but **fell back to dummy device** on last run | `core_output.log`: "fallback init … unexpected keyword argument 'index'" |
| T1.2 STT + live partials | ✅ Done | faster-whisper medium FP16; partial interval 1.2 s (spec: ~0.5 s) |
| T1.3 Question gate | 🟡 Shell-side detector exists & wired to core finals; **no global hotkeys registered anywhere** | `questionDetector.ts` + `coreLink.ts`; zero `globalShortcut` matches in `src/` |
| T1.4 RAG over the brain | 🔴 **Broken right now:** brain files live in `docs/`, but `config.json` → `brain_dir: "../../"` (workspace root) → 0 chunks loaded | Last good run logged 79 chunks before the move to `docs/` |
| T1.5 Answer engine + contracts | ✅ Done | `prompts.py` has per-type contracts + `[you]`/`[gen]`; config uses `llama3:8b`, BUILD_GUIDE locks `qwen3:30b` |
| T1.6 Overlay text-only UI | 🟡 Window flags correct; fork chrome (Header buttons, panels) still visible; no `[you]`/`[gen]` styling; no latency readout; `focus()` on ready-to-show steals focus once | `App.tsx`, `AnswerPanel.tsx` |
| T1.7 Stealth layer | 🟡 Content protection + skipTaskbar done; **Teams acceptance test not yet run** (next interview is Teams per QUESTIONS Q9); no pre-flight screen | — |
| T1.8 Session logging / debrief | 🟡 Single `session.jsonl` with latency_ms; spec wants `transcript.jsonl` + `answers.jsonl` + debrief view | `main.py:log_session` |
| Phase 2 (JD intake, briefing, gap analysis) | 🔴 Not started | `job_descriptions/` has only a README |
| Latency SLO harness (`bench/`) | 🔴 Missing | Referenced by BUILD_GUIDE §3 but not created |

**Deliberate deviations from ARCHITECTURE.md we keep (do NOT rework these):**
- **In-process numpy cosine index instead of sqlite-vec/Qdrant** — documented in `brain.py`; corpus is ~80 chunks, external vector DB adds a moving part before an interview. Keep.
- **Question gate lives in the shell (`questionDetector.ts`), not core** — core streams finals; shell decides fire/no-fire and calls `ask`. Documented in `coreLink.ts`. Keep.
- **RMS endpointing instead of silero-VAD for now** — works with adaptive noise floor; silero upgrade is an optional hardening step (Phase H) only if false-fires show up in the mock call.

---

## Phase A — Realign the brain & model config (fixes T1.4, ~30 min)

The single most important fix: the RAG brain currently loads **zero** chunks because its files moved to `docs/` while `brain_dir` still points at the workspace root (the layout BUILD_GUIDE §1 specifies).

- [ ] **A1.** Move the five runtime brain files from `docs/` to the workspace root (`interview_buddy/`), next to `job_descriptions/`:
  `resume.md`, `02_work_history.md`, `03_education_and_background.md`, `04_projects.md`, `05_qa_bank.md`.
  *(Move, don't copy — one source of truth. Planning docs stay in `docs/`; the app never reads them at runtime.)*
- [ ] **A2.** Start core (`powershell -File app/run_interview_buddy.ps1` or just the uvicorn line) and check health:
  `curl http://127.0.0.1:8790/health` → **pass:** `"brain_chunks"` > 50 (last good run: 79) and `"stt": "ready"`.
- [ ] **A3.** In `app/core/config.json`: set `"llm_model": "qwen3:30b"` (the locked live default, BUILD_GUIDE §0) and delete the unused `"llm_model_quality"` key.
- [ ] **A4.** Warm-up check: ask core one question via WS (`{"t":"ask","text":"Tell me about yourself"}`) or a quick Python snippet against Ollama — **pass:** first token < 3 s warm, answer is first-person bullets with `[you]`/`[gen]` markers.

## Phase B — Fix & verify the audio path (T1.1 acceptance, ~45 min)

Last run fell back to a dummy device (`open_device(index=...)` isn't how PyAudioWPatch opens loopback), so no real audio was captured. This must be proven working before anything else.

- [ ] **B1.** In `app/core/audio_capture.py`, fix the stream open: use PyAudioWPatch's proper loopback open (`p.open(input_device_info=self._dev, ...)` with 48 kHz float32) instead of the `open_device(index=...)` attempt; keep the dummy fallback but make it log loudly.
- [ ] **B2.** Play a test tone or a recorded Zoom clip through the speakers while core runs — **pass:** core receives a continuous 16 kHz stream, RMS clearly rises during playback and returns to floor in silence (add a temporary `[audio] rms=…` debug line if needed; remove after).
- [ ] **B3.** Silence-gap check: play 5 s tone → 4 s silence → 5 s tone — **pass:** the ring buffer shows ~9 s of audio total (silence synthesized from wall-clock elapsed, per ARCHITECTURE §2.1), and endpointing fires once at the end of each tone segment.
- [ ] **B4.** Run the test suite from `interview_buddy/`: `app/core/.venv/Scripts/python -m pytest tests/test_core.py` — **pass:** all green (the loopback init test now exercises the real open path on this machine).

## Phase C — Question gate + global hotkeys (T1.3, F11, ~45 min)

- [ ] **C1.** Register global shortcuts in `src/main/index.ts` (Electron `globalShortcut`, none steal focus):
  - `Ctrl+Alt+Space` → start/stop session (`coreLink.send({t:'start'|'stop'})`)
  - `Ctrl+Alt+Q` → force-answer now (`coreLink.send({t:'trigger'})` — core already handles it)
  - `Ctrl+Alt+H` → hide/show overlay window
  - `Ctrl+Alt+C` → clear current answer (send a renderer event)
- [ ] **C2.** Live check with the app running: speak/read an actual question ("Tell me about a time you solved a difficult technical problem") — **pass:** shell detector fires, `question-detected` shows in console, core streams an answer to the overlay. Then say "hello" / "can you hear me" — **pass:** no fire (manual `Ctrl+Alt+Q` still works as override).
- [ ] **C3.** Create `app/core/fixtures/golden.jsonl`: 20 lines of realistic interview utterances (15 questions across tech/STAR/sysdesign/coding + 5 non-questions like greetings, acknowledgments, "let me think").
- [ ] **C4.** Add a tiny script `app/core/bench/gate_check.py` that runs the golden set through the same gate logic and prints fire/no-fire accuracy — **pass:** ≥ 90 % correct (T1.3 acceptance). *(If the shell regexes are the gate, port the check to a Node one-liner or test via WS; keep it under ~50 lines.)*

## Phase D — Overlay: text-only polish (T1.6, ~1 h)

- [ ] **D1.** Strip fork chrome from live view in `App.tsx`/`Header.tsx`: no visible buttons/borders/backgrounds — only the dim live-transcript line + answer bullets remain visible over whatever is behind the window. Settings/history open via hotkey or a thin invisible drag strip, not visible UI.
- [ ] **D2.** In `AnswerPanel.tsx`/`MarkdownRenderer.tsx`: render `[you]` bullets at full opacity and `[gen]` bullets dimmed with a distinct marker (ARCHITECTURE §4.3) — the model already emits these tags.
- [ ] **D3.** Add latency readout to `StatusBar.tsx`: per-question ms from the existing `answer_end.latency_ms` broadcast + running p50 for the session (the SLO number, visible in-app per PLAN §9).
- [ ] **D4.** Remove `mainWindow.focus()` on ready-to-show (`src/main/index.ts`) — overlay must never steal focus; verify by starting a session with another window focused and confirming it stays focused.

## Phase E — Stealth verification (T1.7, ~1 h)

The next real interview is **Teams** (QUESTIONS Q9), so Teams is the acceptance bar.

- [ ] **E1.** THE TEST: two Teams accounts on this machine, share full desktop, run a 5-question mock with the overlay visible to you — **pass:** overlay absent from the shared view; nothing in taskbar/Alt-Tab; far end hears zero UI sounds. (If it fails: check Zoom-style "advanced capture" settings are not needed for Teams; fallback = move overlay to the second monitor per Q10.)
- [ ] **E2.** Repeat E1 quickly on Zoom and Meet (window-share variant too) — log results in a `docs/stealth_matrix.md` table.
- [ ] **E3.** Add a pre-flight checklist screen (simple modal, normal opaque window): Ollama warm (dummy 1-token gen), STT ready, loopback device name shown, content protection on, monitor count + "put overlay on unshared monitor" hint, Zoom window-filtering note. One click → all green before the call.
- [ ] **E4.** *(Optional, Q11)* Process-disguise toggle: rename process image to an innocuous utility (Natively/CodeInterviewAssist pattern), off by default, switch in settings + pre-flight.

## Phase F — Session logging & debrief alignment (T1.8, ~30 min)

- [ ] **F1.** In `app/core/main.py`, split the single `session.jsonl` into the ARCHITECTURE §11 layout: `sessions/<ts>/transcript.jsonl` (`{t,text,final}`) and `answers.jsonl` (`{q_id,type,bullets,sources,latency_ms}`), plus per-stage timings (endpoint → STT final → first token) so the debrief can show where time went.
- [ ] **F2.** Minimal debrief view in the shell: after stop, list each question with its type, latency, and bullets; "export to markdown" button writes one `.md` file. *(Full briefing-vs-actual comparison lands with Phase G's JD files.)*

## Phase G — JD intake + briefing for the next interview (T2.1/F9/F13, ~1 h)

Required by BUILD_GUIDE §4 item 3 ("interview ready") and the highest-ROI feature in PLAN §7.

- [ ] **G1.** Create `job_descriptions/<role>_<company>.md` for the upcoming Teams interview: paste the raw JD verbatim at top. *(Core already auto-includes the newest file in this folder as JD context — no code change needed once files are at root per Phase A.)*
- [ ] **G2.** Add `app/core/bench/jd_brief.py` (or a settings-screen button): one Ollama call that parses the JD into `skills[], stack, seniority_signals` and writes them back into the file as a structured section.
- [ ] **G3.** Same script generates the **top-10 likely questions with pre-generated bullets** from the brain (resume + projects + QA bank) and appends them to the JD file — **pass:** you can review all 10 before the interview; every `[you]` bullet traceable to a doc.
- [ ] **G4.** Gap analysis section in the same file: JD skills × resume evidence → covered / adjacent / missing, with a prepared 20-second bridge for each gap (e.g., K8s ← Docker + AWS + CI/CD).

## Phase H — Latency SLO harness & tuning (T3.2 early, ~45 min)

- [ ] **H1.** Create `app/core/bench/latency_slo.py`: scripted 10-question run against the running core (WS `ask` → time to first token), prints p50/p95 per stage — **pass:** p50 ≤ 4 s, p95 ≤ 7 s on this machine (BUILD_GUIDE SLO).
- [ ] **H2.** Set `"partial_interval_s": 0.5` in `config.json` (spec: partials every ~500 ms; currently 1.2 s) and re-run H1 — live transcript should feel continuous without hurting the SLO.
- [ ] **H3.** *(Only if false-fires/misses appeared in C4 or E1)* Upgrade endpointing from RMS to silero-VAD (add `onnxruntime` + silero model to `app/core/pyproject.toml`, swap into `_session_loop`) and re-run B3/C4.
- [ ] **H4.** Top up `05_qa_bank.md` from 26 → ≥ 40 entries (T0.5 acceptance): generate candidates with the answer engine against the brain, keep/drop in one pass — mix of system design, AI/LLM deep-dive, STAR, project follow-ups.

## Phase I — Interview-ready rehearsal (BUILD_GUIDE §4 Definition of Done)

- [ ] **I1.** Full 20-minute mock Teams call (self vs self), 10 questions mixed tech/behavioral/sysdesign: SLO green on p50; STAR questions produce exactly S/T/A/R bullets 10/10; overlay invisible in shared view; nothing in taskbar/Alt-Tab; no sounds at the far end.
- [ ] **I2.** Offline test: kill Wi-Fi, repeat a 3-question run — **pass:** everything still works (local-first guarantee).
- [ ] **I3.** Update `app/README.md` as the portfolio-grade artifact (what it is, architecture diagram from ARCHITECTURE §1, setup, SLO numbers) and mark BUILD_GUIDE tasks T0.1–T1.8 done with dates.

---

## Done = all of these are true

1. `curl http://127.0.0.1:8790/health` → chunks > 50, stt ready, on `qwen3:30b`.
2. Real speaker audio flows through loopback with correct silence-gap timing (B2/B3).
3. Hotkeys work while the interview app has focus; detector fires ≥ 90 % on the golden set.
4. Overlay is text-only, `[you]`/`[gen]` styled, latency visible, never steals focus.
5. Teams full-desktop share shows no trace of the app (E1) — and Zoom/Meet logged in `docs/stealth_matrix.md`.
6. Sessions write `transcript.jsonl` + `answers.jsonl` with per-stage timings; debrief view lists them.
7. The next interview's JD file exists with parsed skills, gap report, and a reviewed top-10 briefing.
8. SLO harness reports p50 ≤ 4 s / p95 ≤ 7 s on this machine.

**Explicitly out of scope for MVP (per QUESTIONS Q12):** practice mode + TTS mock interviewer (F12), spaced repetition, coding-screenshot vision mode (F16), macOS — all Phase 3/4.
