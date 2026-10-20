# Open-Source Research — What to Clone for Interview Buddy

**Research date:** 2026-10-06 · Sources: GitHub repos, Microsoft docs, Stack Overflow, project READMEs/FAQs (links inline).

---

## 1. Market Map (why this category exists and what's free)

| Product | Price | Open source? | Notes |
|---------|-------|--------------|-------|
| Cluely | ~$20/mo | No | The original "invisible AI overlay" for interviews; had a mid-2025 breach (83k users) — the privacy argument for local-first. |
| Final Round AI | ~$149/mo | No | Taskbar icon visible to proctoring per Natively's comparison — exactly what R4 forbids. |
| LockedIn AI | $55–70/mo | No | Cloud-locked LLM, no local option. |
| Interview Coder (interviewcoder.com) | Paid | No (OSS clones exist) | Coding-interview focused; the `j4wg` repo below is its open alternative. |
| **Natively** | Free (BYOK / Ollama) | Source-available, personal-use license | See §2 — closest feature superset. |
| **Pluely** | Free core | Was MIT→GPL-3; v1 now closed source (old GPL code in git history) | Tauri-based, 10 MB, "one overlay, no tab, no trace." |
| **interview-copilot** (elias-soykat) | Free | **MIT** | See §2 — recommended clone base. |
| **CodeInterviewAssist** (j4wg) | Free | AGPL-3.0 | "99% invisible" coding-interview assistant with stealth launcher scripts. |
| OpenCluely, Specter-AI, xexamai, interviewcopilot (hariiprasad), Spectra, interview-assistant-CLI | Free | Various | Smaller OSS variants of the same idea; useful pattern references only. |

**Takeaway:** the "invisible AI interview copilot" is a proven, active category with multiple free codebases — we are not inventing anything, we're assembling the best parts and adding the RAG/personalization depth (resume + project docs + JD) that most of them treat as an afterthought.

---

## 2. Clone Candidates — Detailed Assessment

### ⭐ A. `elias-soykat/interview-copilot` — **recommended clone base**
https://github.com/elias-soykat/interview-copilot · **MIT** · ~20★, small & readable (66 commits)

- Electron + electron-vite, React 19, TypeScript, Tailwind, Zustand.
- **Already has our exact feature shape:** Start session → listen via *Microphone or System Audio* → real-time Whisper transcription → pause-based question detection ("smart linguistic heuristics") → streamed concise answers; always-on-top with opacity control (30–100%); screenshot→Vision for coding problems; resume text in settings as personalization context.
- **Screen-share protection implemented:** `setContentProtection` — README states it hides the window from Zoom, Teams, Discord screen shares on Windows; macOS uses Screen Recording permission + desktop audio streams (macOS 13+).
- Gaps vs our plan: OpenAI-API-only by default (no local Ollama path), no RAG (resume is pasted text, not retrieved context), no STAR-specific output contract, no JD intake/gap analysis, no practice mode, single-window UI.

**Why it wins as the base:** MIT license (cleanest of all candidates — fork freely, keep or drop attribution per MIT terms), small enough to fully own and modify in a week, and every gap is an *addition*, not a rewrite. Its `whisperService.ts`, `questionDetector.ts`, window manager, and IPC layout are exactly the seams where our Python core plugs in.

### B. `Natively-AI-assistant/natively-cluely-ai-assistant` — **reference implementation / "use it now" option**
https://github.com/Natively-AI-assistant/natively-cluely-ai-assistant · 2,600+★ · **"Natively Personal Use Source License v1.0"** (free for personal/educational/non-commercial use; commercial needs a written license)

- Electron 43 + **Rust native audio capture with zero-copy ABI transfers** (<500 ms claimed), React/Vite/Tailwind, SQLite + sqlite-vec local RAG.
- Feature superset of our brief: **dual-channel audio** (system audio = "what they say", mic = your voice — exactly our live/practice split), on-device STT (Moonshine-tiny/base, Whisper-large-v3-turbo, distil-large-v3, Parakeet CTC 0.6B), two-stage silence processing (adaptive RMS + WebRTC ML VAD), **stealth mode** (hide from dock/taskbar, process disguise as Terminal/Settings/Activity Monitor), BYOK any LLM **or fully local Ollama**, screenshot OCR for LeetCode/HackerRank/CoderPad, 9 built-in modes incl. technical interview / behavioral / system design, JD role insight, meeting history + RAG memory, latency tracing UI.
- Documented Zoom caveat (needs "Advanced capture with window filtering") and honest limits ("best-effort, not guaranteed — a phone camera always can").

**Assessment:** if the goal were *an interview this week*, run Natively as-is (personal use = free). As a *clone base* it's heavier: 4,000+ commits, Electron+Rust build chain, and its license is fine for personal use but less clean if Interview Buddy later becomes a public portfolio product. Best used as the **reference implementation** we consult for hard parts (audio latency engineering, stealth hardening, VAD design) — several of our ARCHITECTURE.md decisions are lifted directly from its documented approach.

### C. `j4wg/interview-coder-withoupaywall-opensource` (CodeInterviewAssist)
https://github.com/j4wg/interview-coder-withoupaywall-opensource · **AGPL-3.0**

- Electron + React + TS; "99% invisibility: undetectable window that bypasses most screen capture methods"; smart screenshot capture of question+code separately; GPT-4o analysis with complexity analysis; real-time debugging help.
- Notable artifacts to steal: `stealth-run.bat` / `invisible_launcher.vbs` (process-disguise launchers) and its documented invisibility compatibility matrix (which Zoom versions respect the flag, which don't).
- AGPL is fine for personal use; less ideal if we ever distribute.

### D. `iamsrikanthnani/pluely`
https://github.com/iamsrikanthnani/pluely · 2,700+★ · was MIT → GPL-3, **v1 now closed source** (old GPL code remains in repo history)

- Tauri-based ("native performance, just 10 MB"), transparent always-on-top overlay invisible to screen share, live transcript + file-grounded answers + follow-up chips.
- Assessment: the *current* product is no longer cloneable; only the pre-v1 GPL code is forkable from git history. Interesting as evidence that Tauri can do this too (our P2 option if Electron weight becomes a problem), but not the primary path.

### E. Pattern references (smaller repos)
- `TechyCSR/OpenCluely` — invisible overlay + smart image processing for DSA/OA/CP; multi-language.
- `umairinayat/Specter-AI` — Electron+React, transparent always-on-top overlay invisible to screen share, real-time OCR, streaming via OpenRouter (BYOK 500+ models) — good example of a BYOK provider abstraction we'll want anyway.
- `XiaoChu-1208/interview-assistant-CLI` — "hears the question and surfaces the answer you already prepared from your local Markdown knowledge base — verbatim, in milliseconds." Validates our core thesis: **prepared, grounded answers beat generated ones**; informs the `[you]`/`[general]` flag design.
- `aamitn/winhider` — minimal open-source implementation of exactly our invisibility primitives (DLL-injected `SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE)` + `WS_EX_TOOLWINDOW` taskbar hiding) — useful as a 200-line reference for the Windows stealth layer.

---

## 3. Recommendation & Fork Strategy

**Primary path (build):** fork **A (interview-copilot, MIT)** → rename to Interview Buddy → keep its window/IPC/UI skeleton and question-detection code → replace/augment:
1. Audio: swap Web-Audio mic capture for WASAPI loopback via the Python core (PyAudioWPatch) — borrow Natively's dual-channel + two-stage-VAD design.
2. STT: local faster-whisper in buddy-core; keep OpenAI API as fallback mode (their `whisperService.ts` becomes the API-mode client).
3. LLM: add Ollama provider alongside OpenAI (Specter-AI's BYOK pattern); wire streaming to their existing answer panel.
4. RAG: new — Qdrant + nomic-embed-text, content schema per ARCHITECTURE §7; their "Resume Description" settings field becomes the profile-summary slot.
5. Prompts: replace their generic answer prompt with our per-type contracts (tech / STAR / sysdesign / coding) evolved from `01_system_prompt.md`.
6. Stealth: keep `setContentProtection`; add taskbar/Alt-Tab hiding, process-disguise toggle (CodeInterviewAssist's launcher pattern), pre-flight invisibility test.

**Parallel path (use now):** install **Natively** today for the next real interview — it already covers ~80% of R1–R6 out of the box (paste resume in its context settings, use Ollama mode). This de-risks the whole project: if the build slips, the user still has a working copilot.

**License posture:** fork MIT code + personal-use reference to Natively's patterns = clean for both personal use and public portfolio display (keep MIT attribution; note Natively as inspiration in README).

---

## 4. Key Technical Facts Verified During Research

| Fact | Source(s) |
|------|-----------|
| `SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE)` (Win10 2004+) excludes a window from BitBlt, DXGI Desktop Duplication, and Windows.Graphics.Capture; Electron exposes it via `setContentProtection(true)` | Microsoft docs; Stack Overflow "exclude certain window from screen capture"; interview-copilot README; Natively FAQ; winhider repo |
| Zoom may ignore the flag unless "Advanced capture with window filtering" is enabled; Teams/Meet respect it | Natively FAQ (documented per-tool behavior) |
| WASAPI loopback captures rendered endpoint audio and **only delivers buffers while playback occurs** — silence must be synthesized from timestamps/discontinuity flags for correct timing | Microsoft "Loopback Recording"; Stack Overflow (NAudio `WasapiLoopbackCapture` thread); PyAudioWPatch examples |
| PyAudioWPatch = PyAudio fork exposing WASAPI loopback devices in Python | s0d3s/PyAudioWPatch repo + example scripts |
| Local LLM first-token latency is hardware-bound and degrades after idle (cold model/prefill) — pre-warm before the interview; public benchmark: Ollama 7B Q4 on RTX-2050 ≈ 2.6 s TTFT / ~5 tok/s vs vLLM 3B ≈ 0.19 s | Zima Space latency analysis; AdityaSinghDevs vLLM-vs-Ollama benchmark gist |
| whisper.cpp "falls behind on slow systems" — choose STT model by measured real-time factor, not vibes | ggml-org/whisper.cpp issue #1653 |
| Faster local-ASR options exist for English: Moonshine (tiny/base), Parakeet CTC 0.6B, distil-large-v3, whisper-large-v3-turbo | Natively README (on-device STT model list) |
