# Interview Buddy — Master Plan

**Status:** Draft v1 (pending answers in [QUESTIONS.md](QUESTIONS.md))
**Date:** 2026-10-06
**Companion docs:** [ARCHITECTURE.md](ARCHITECTURE.md) · [OPEN_SOURCE_RESEARCH.md](OPEN_SOURCE_RESEARCH.md) · [QUESTIONS.md](QUESTIONS.md)

---

## 1. Vision & Problem

Interview Buddy is a **local-first, screen-share-invisible interview copilot** for high-level software engineering and AI engineering interviews. During a live video-monitored interview it:

1. **Hears only the interviewer** — by capturing audio *output to speakers* (WASAPI loopback), never the microphone, so the applicant's own voice is never processed or leaked into context.
2. **Understands the question** — real-time speech-to-text + question-type classification (technical / behavioral-STAR / system design / coding).
3. **Answers with scannable bullets** — grounded in the user's markdown resume, portfolio project docs, and the specific job description:
   - *Technical questions* → 4–6 key-point bullets tailored to the user profile + JD.
   - *Experience/behavioral questions* → exactly four bullets: **S**, **T**, **A**, **R** (STAR), drawn from real work history so every claim is defensible.
4. **Shows only text on a transparent overlay** — no chrome, no background; the user reads bullets while still seeing whatever window sits behind them.
5. **Leaves no trace** — invisible to full-screen sharing (Zoom/Teams/Meet), hidden from taskbar/Alt-Tab, silent, no focus stealing, optional process disguise.

The end goal is not just "passing" but *ace*: the app also runs a **practice loop** (mock interviewer + scoring) so the user gets faster and less dependent on it over time.

### Why this is winnable technically (research summary)

- **Invisibility to screen share is a solved problem on Windows 10 2004+ / Win11:** `SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE)` excludes a window from BitBlt, DXGI Desktop Duplication, and Windows.Graphics.Capture — the three APIs Zoom/Teams/Meet use. Electron exposes it as `win.setContentProtection(true)`. Verified working in at least two open-source projects (see [OPEN_SOURCE_RESEARCH.md](OPEN_SOURCE_RESEARCH.md)). One known caveat: some Zoom builds need "Advanced capture with window filtering" enabled; fallbacks are second-monitor placement and a different virtual desktop.
- **"Hear the speakers, not the mic" is a solved problem:** WASAPI loopback capture (Windows) records exactly what renders to the default audio endpoint — i.e., the interviewer's voice in Zoom/Meet — while ignoring microphone input entirely. Libraries: `PyAudioWPatch` (Python), NAudio (C#), or Rust crates. macOS equivalent: ScreenCaptureKit audio / CoreAudio tap.
- **Latency is achievable:** local STT (faster-whisper / whisper.cpp / Moonshine / Parakeet) runs at or faster than real-time on modern hardware; a warm local 7–8B LLM via Ollama produces first tokens in ~1–3s depending on GPU. Target: **first bullet visible ≤ 4 seconds after the interviewer finishes the question**, with bullets streaming in progressively.
- **There is free open-source code to clone:** `elias-soykat/interview-copilot` (MIT) is nearly this exact product; `Natively-AI-assistant/natively-cluely-ai-assistant` (2.6k★, personal-use license) is a feature superset. Full analysis in [OPEN_SOURCE_RESEARCH.md](OPEN_SOURCE_RESEARCH.md).

---

## 2. Product Definition

### 2.1 Target user & scenario

The user (milli) interviewing for senior/staff SWE and AI engineering roles: video call on one monitor, Interview Buddy overlay pinned to the corner of a **second monitor** (or same monitor with content protection), sharing "this screen" or full desktop. The interviewer sees only the shared window/desktop + webcam.

### 2.2 Core live-interview loop

```
Interviewer speaks ──► speaker output ──► WASAPI loopback capture
                                              │
                                    VAD endpointing (silero)
                                              │
                              question detected? (pause + heuristics)
                                              │ yes
                              STT final transcript (local Whisper-class model)
                                              │
                     classify: tech | STAR | sysdesign | coding | smalltalk
                                              │
              RAG retrieval: resume + project docs + JD chunks
                                              │
        LLM (Ollama local / API fallback) streams structured bullets
                                              │
                 transparent overlay renders text-only bullets
```

### 2.3 Non-negotiables (from the brief)

| # | Requirement |
|---|-------------|
| R1 | Context = markdown docs of all portfolio projects + markdown resume + pasted job description. No other sources of truth. |
| R2 | AI model on the back end; local-first (Ollama), API fallback allowed. |
| R3 | Transparent window, **text only visible** — user can read bullets and still see the window behind them. |
| R4 | Invisible to *entire-screen* sharing: no evidence in the shared view that Interview Buddy exists or is running. |
| R5 | Audio input = speaker output only (loopback). Microphone ignored during live mode. |
| R6 | Output = bullet lists: tech → key points grounded in profile+JD; experience → one bullet each for S, T, A, R. |

---

## 3. Feature Set & Priorities

Priority legend: **P0** = MVP must-have · **P1** = v1.5 · **P2** = later / nice-to-have.

### P0 — MVP ("get me through a real interview")

| ID | Feature | Notes |
|----|---------|-------|
| F1 | Speaker-output audio capture (WASAPI loopback) with silence-gap handling | Core of R5. Must handle "no data when silent" correctly for accurate timing. |
| F2 | Real-time STT with live partial transcript shown small on overlay | Local model default; API fallback toggle. |
| F3 | Question detection: VAD endpoint + linguistic heuristics + manual hotkey trigger | Don't fire on "hello", background music, or the user's own echoed voice (shouldn't happen — loopback only). |
| F4 | Question-type classifier → prompt routing (tech / STAR / sysdesign / coding) | Can be a zero-shot LLM step or folded into the answer prompt. |
| F5 | RAG over `resume.md`, project docs, and active JD | Local embeddings + Qdrant (or sqlite-vec). Retrieval always includes condensed profile summary. |
| F6 | Bullet answer engine with strict output contract | Tech: 4–6 bullets ≤ ~15 words each, first-person, grounded in retrieved chunks; STAR: exactly S/T/A/R bullets from real history; optional one-line opener + closer ("I'd be happy to go deeper on X"). Hard cap ≈ 200 spoken words (90s). |
| F7 | Transparent frameless always-on-top overlay, text-only rendering, adjustable font/opacity | Electron `transparent:true`, `frame:false`, `alwaysOnTop`. No visible chrome. |
| F8 | Screen-share invisibility: `setContentProtection(true)` + taskbar/Alt-Tab hiding + silent UI + no focus steal | The "no evidence" checklist in §6. |
| F9 | JD intake screen: paste JD → stored as session context; pre-interview briefing generator (top likely questions, pre-generated bullets) | Briefing = the highest-leverage feature for *acing*, not just surviving. |
| F10 | Local persistence of sessions (transcript + generated bullets + timestamps) | Enables review mode and practice scoring later. |
| F11 | Global hotkeys: start/stop, hide/show overlay, next bullet/expand, clear | Must work while the interview app has focus. |

### P1 — v1.5 ("make me better")

| ID | Feature | Notes |
|----|---------|-------|
| F12 | **Practice mode (mock interviewer):** TTS reads questions from a generated question bank; user answers via mic (mic channel enabled *only* in practice); LLM scores each answer against a rubric + STAR completeness; tracks weak areas with spaced repetition. This is the feature that actually raises pass rates over time. |
| F13 | **JD gap analysis:** parse JD skills vs resume → flag gaps ("JD wants Kubernetes; your docs don't mention it") and generate bridging answers from adjacent experience (e.g., Docker/AWS). Prevents the classic "we use X" surprise. |
| F14 | **Question bank (`05_qa_bank.md`):** auto-generate candidate questions per role from resume+JD; user marks practiced/mastered; practice mode drills unmastered ones first. |
| F15 | **Confidence flags on bullets:** each bullet tagged `[you]` (grounded in your docs) vs `[general]` (safe generic knowledge). User never says something they can't defend under follow-up. |
| F16 | **Coding-question mode:** screenshot the shared problem → vision model → approach outline + key steps + complexity note (no full code unless asked). |
| F17 | **System-design template** tuned for senior/AI-eng: architecture skeleton bullets (components, data flow, scaling trade-offs, failure modes) — this is where high-level interviews are won. |
| F18 | Post-interview **debrief screen:** what was actually asked vs the briefing; export session to markdown. |

### P2 — later

- macOS support (ScreenCaptureKit audio; `NSWindowSharingNone`), Linux (PipeWire monitor source).
- Multi-JD "role profiles" with per-company notes; follow-up-question memory ("they already heard about StockMaster's latency work — don't repeat").
- Phone-link companion (bullets on a phone propped behind the laptop as physical backup).
- Auto model management: download/quantize STT+LLM models per detected hardware.
- Packaging polish: NSIS installer, auto-update *off* during sessions, first-run wizard with the invisibility pre-flight test.

---

## 4. Phases & Milestones

> Assumes Windows-first (user is on Win11 build 26200), Electron + Python core stack per [ARCHITECTURE.md](ARCHITECTURE.md).

### Phase 0 — Foundations (Day 1–2)
- Fork `elias-soykat/interview-copilot` (MIT) as the shell skeleton; strip OpenAI-only paths. *(Decision pending Q3 in QUESTIONS.md — alternative: run Natively as-is while building.)*
- **Content pipeline:** create `resume.md` (synthesize from `02_work_history.md` + `03_education_and_background.md`), complete `04_projects.md` covering StockMaster, Sidekick LLM, and PyHoldem Pro (PyHoldem already has full docs in `05_holdem_trainer_docs/`; the other two need equivalent case-study depth — see content schema in ARCHITECTURE §7).
- Stand up: Ollama + chosen models pulled & warmed; Qdrant (or sqlite-vec) running; Python core service skeleton.
- **Exit criteria:** `resume.md` + project docs exist and read well; local model answers a test prompt in < 3s warm.

### Phase 1 — MVP live loop (Week 1–2)
- F1 audio capture → F2 STT → F3 detection → F4 classification → F6 bullets → F7 overlay, wired end-to-end with the RAG context from F5.
- F8 stealth basics: content protection on, no taskbar icon, silent UI.
- **Exit criteria (acceptance test):** run a real Zoom call between two accounts; share full desktop; ask 10 questions (mix of tech/behavioral); bullets appear ≤ 4s after each question ends, are first-person and grounded in the docs, STAR questions produce exactly S/T/A/R bullets, and the overlay is **not visible** in the shared view.

### Phase 2 — Context depth (Week 3)
- F9 JD intake + briefing generator; F10 session logging; F15 confidence flags; F17 system-design template tuned on real AI-eng questions.
- **Exit criteria:** given a pasted JD, produce a 10-question briefing with pre-generated bullets in < 60s; every bullet traceable to a source doc or flagged `[general]`.

### Phase 3 — Practice & hardening (Week 4)
- F12 practice mode + F13 gap analysis + F14 question bank; F18 debrief.
- Stealth hardening: process-disguise option, pre-flight invisibility test UI (auto-runs the Zoom/Teams check), latency tuning pass with measured p50/p95.
- **Exit criteria:** 20-minute mock interview session scored end-to-end; weak-area report generated; p50 question→first-bullet ≤ 4s on user's machine.

### Phase 4 — Polish & ship (Week 5)
- Packaging, settings UX, model management, docs/README for the app itself (portfolio-grade), optional macOS pass.

---

## 5. Content Pipeline (the markdown "brain")

Interview Buddy is only as good as its source-of-truth documents. Required files (names align with the existing `01_system_prompt.md` references):

| File | Status | Purpose |
|------|--------|---------|
| `resume.md` | **to create** (synthesize from 02/03) | One-page markdown resume; primary identity context. |
| `04_projects.md` | **to create** | Index + per-project case studies: StockMaster, Sidekick LLM, PyHoldem Pro. Schema in ARCHITECTURE §7 — must include metrics, architecture decisions, and "challenge → solution" stories (the raw material for STAR bullets). |
| `05_qa_bank.md` | **to create** (Phase 3) | Question bank with practiced/mastered flags; seeded by auto-generation from resume+JD. |
| `01_system_prompt.md` | exists — **evolve** | Split into per-mode prompt templates (tech / STAR / sysdesign / coding) keeping the existing strict rules: first-person only, zero filler, ≤ 90s spoken length, scannable formatting. Drafts in ARCHITECTURE §8. |
| `job_descriptions/<role>_<company>.md` | per interview | Pasted JD + parsed skills + gap analysis output. |

**Rule:** the app never invents experience. Anything not traceable to these docs is either flagged `[general]` or omitted. This is what makes bullets *defensible* under follow-up — the #1 way candidates get caught in monitored interviews.

---

## 6. The "No Evidence" Checklist (R4, made concrete)

What an interviewer could observe, and how each is handled:

| Evidence vector | Mitigation |
|-----------------|------------|
| Overlay visible in full-screen share | `setContentProtection(true)` → `WDA_EXCLUDEFROMCAPTURE` (Win10 2004+; user on Win11 ✓). Zoom caveat: enable "Advanced capture with window filtering" (documented in setup guide); Teams/Meet respect the flag. Fallbacks: place overlay on a monitor that isn't shared, or on a virtual desktop not being shared. |
| Window in taskbar / Alt-Tab | `skipTaskbar` + tool-window extended style; no tray icon by default (optional tiny one). |
| Focus steal when answer arrives | Overlay never takes focus; hotkeys are global but passive. |
| Audible UI sounds reaching the interviewer via their mic | **Zero audible feedback in live mode** (no chimes); visual-only state changes. Also prevents loopback self-capture. |
| Windows toast notifications on shared screen | App suppresses its own toasts during a session; pre-flight reminds user to enable Focus Assist/DND. |
| Process visible in Task Manager | Optional process disguise (rename to an innocuous utility, e.g., the pattern used by Natively/CodeInterviewAssist). Default: honest name — most interviewers never open Task Manager mid-call. |
| Fan noise / power draw from local inference during call | Pre-warm models before the call; prefer quantized 7–8B or API mode on battery; document in pre-flight. |
| Webcam catching a second monitor | Physical: angle/position overlay monitor out of frame (setup guide). |
| "Hear yourself" echo (app plays user's own voice back) | Loopback only captures *rendered* audio, not mic — but if the conferencing app is set to play the user's own mic locally, that would be captured. Pre-flight: disable self-audio in Zoom/Meet settings. |

---

## 7. Recommendations Beyond the Brief (the "what else")

Ordered by impact on *passing high-level SWE / AI-eng interviews*:

1. **Pre-interview briefing generator (F9) — highest ROI.** Live hints help, but candidates ace interviews by walking in with a plan: top-10 likely questions for *this* JD with pre-generated STAR bullets from *their* history. The live overlay then becomes recall + safety net, not the whole strategy.
2. **Practice mode with scoring (F12).** A TTS mock interviewer that asks from the question bank, listens via mic (practice only), and grades answers against a rubric (STAR completeness, specificity, metrics, 90-second discipline). Spaced repetition on weak questions. This is how the user gets *less* dependent on the overlay — which is itself a good interview story ("I built a local-first copilot to train with").
3. **JD gap analysis (F13).** Senior panels probe JD keywords. Auto-mapping JD requirements → resume evidence → gaps, with bridging answers from adjacent experience (e.g., "no K8s on resume, but Docker + AWS + CI/CD depth" → prepared 20-second bridge).
4. **System-design answer templates (F17).** High-level SWE/AI interviews are won in design rounds: provide skeleton bullets for scalable services and *AI systems* specifically (RAG pipelines, evals, inference cost/latency trade-offs, multi-agent orchestration) — directly matching the user's profile so answers sound like their own architecture work.
5. **Confidence flags `[you]` vs `[general]` (F15).** Prevents the fatal "I did X" that isn't in any doc and dies under follow-up.
6. **Two-stage answer streaming.** Emit 3 skeleton bullets fast (small/fast model or truncated generation), then refine — perceived latency drops dramatically even if full quality takes longer.
7. **Session review + debrief (F18).** Post-interview: what was asked vs briefed, timing of each question, which bullets were used. Turns every interview into training data for the next one.
8. **Coding-question screenshot mode (F16).** For OA-style or "let's solve this together" moments: capture the problem window → vision model → approach + complexity outline. (Borrowed directly from the clone candidates; it's table stakes in 2025.)
9. **Latency engineering as a first-class feature.** Live transcript of the interviewer streaming on the overlay (small, dim) does double duty: proves to *the user* that capture is working, and gives them a reading buffer while bullets generate. Measure p50/p95 question→first-bullet in every build.
10. **Keep it local-first as a story.** The app itself becomes a portfolio artifact demonstrating the exact stack the resume claims (Ollama, Qdrant, RAG, FastAPI, TypeScript) — "I built Interview Buddy" is a legitimate project to talk about *in* interviews once v1 ships.

---

## 8. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Zoom build ignores content-protection flag | Medium | High (overlay visible) | Pre-flight test per conferencing tool; second-monitor / virtual-desktop fallback; document Zoom "window filtering" setting. |
| Local LLM too slow on user's hardware | Medium | High (bullets late) | Hardware-tiered model selection (see QUESTIONS Q2); API fallback mode; two-stage streaming; pre-warm before call. |
| STT mishears muffled Zoom audio → wrong question | Medium | Medium | Live transcript visible so user can correct/confirm with a hotkey; re-ask prompt ("Could you rephrase?") as a generated closer option; API STT fallback (higher accuracy). |
| RAG hallucination → bullet claims experience the user doesn't have | Low-Med | High (caught in follow-up) | Retrieval-grounded generation + `[you]`/`[general]` flags + "never invent" rule in prompt templates. |
| WASAPI loopback silence gaps break VAD timing | Medium | Medium | Timestamp-based silence padding (known NAudio/PyAudioWPatch pattern); integration test with recorded Zoom audio. |
| Electron transparent-window quirks (no resize, GPU compositing artifacts) | Low-Med | Low | Fixed-size draggable window; `backgroundThrottling:false`; test on user's exact GPU/driver. |
| Scope creep (practice mode before live loop works) | High | Medium | Phase gates above are strict: no P1 work until Phase 1 acceptance test passes. |
| Fan noise / battery during long call with local inference | Low-Med | Low | API-mode option; quantized models; pre-flight warning. |

---

## 9. Success Metrics

- **Latency:** p50 question-end → first bullet ≤ 4s, p95 ≤ 7s on the user's machine (measured in-app, displayed in status bar).
- **Invisibility:** pass the test matrix — {Zoom, Teams, Meet} × {full-desktop share, window share of interview app} with overlay visible to user and absent from capture.
- **Grounding:** 100% of `[you]` bullets traceable to a source doc; zero invented metrics in a 20-question audit.
- **Format compliance:** STAR questions → exactly S/T/A/R bullets, every time (prompt-contract test suite with 30 recorded questions).
- **Usability:** user can run a full mock interview unaided after the first-run wizard.

---

## 10. Open Questions

See [QUESTIONS.md](QUESTIONS.md) — 12 questions with recommended defaults. The plan is executable on defaults alone; answers only change model choices, scope ordering, and content work.
