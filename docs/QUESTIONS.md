# Open Questions — Needed to Finalize the Plan

Each question lists **why it matters** and my **recommended default**. You can answer "all defaults" and Phase 0 starts immediately; any override just changes model choices, scope order, or content work.

## Platform & Hardware

**Q1. Target OS priority?**
The plan assumes Windows-first (you're on Win11 build 26200), macOS in P2.
*Why:* WASAPI loopback + `WDA_EXCLUDEFROMCAPTURE` are the most mature invisibility primitives; macOS needs ScreenCaptureKit/CoreAudio work.
**Default: Windows-only for v1–v3, macOS in Phase 4+ if wanted.**

Windows first. Mac later.

**Q2. Your machine's hardware? (GPU model + VRAM, CPU cores, RAM)**
*Why:* determines the local LLM size tier and STT engine — the single biggest driver of whether we hit the ≤4 s latency target locally.
**Default assumption:** modern desktop with a mid-range NVIDIA GPU (8 GB+ VRAM) → `qwen2.5:14b` or `llama3.1:8b` + faster-whisper FP16. If CPU-only → 7B Q4_K_M + int8 STT, and API mode becomes the recommended live setting.

Yes specific to my machine.

**Q3. Clone base confirmation:** fork `elias-soykat/interview-copilot` (MIT) as the build base, with Natively installed in parallel for immediate use?
*Why:* this is the one structural decision; it's reversible for ~2 weeks of work but shapes everything after.
**Default: yes — MIT fork + Natively-as-stopgap.**

Yes piece together what we can from what is already built to most easily build out and get the key features working. 

## AI Backends

**Q4. Local-first confirmed? Which Ollama models do you already have pulled?**
*Why:* we want zero new downloads in Phase 0 if possible, and your existing model choices tell me what your hardware has proven it can run.
**Default: local-first via Ollama; pull `qwen2.5:7b` (safe floor) + `nomic-embed-text`; upgrade to 14B after the latency benchmark on your machine.**

I have multiple Ollama models pulled and will likely use Qwen or Nemotron's latest model that will answer quickly but accurately.

**Q5. Is an API fallback acceptable for live interviews (OpenAI/Claude/Gemini key), or must live mode be fully offline?**
*Why:* API mode buys ~1 s of latency and better STT accuracy at the cost of network + a key; "fully local" is also your privacy story.
**Default: both modes, local default, one-click API fallback.**

ollama or llama-node-cpp will be fine no api needed.

## Content (the markdown brain)

**Q6. Resume:** do you have an existing resume file I should convert to `resume.md`, or synthesize it from `02_work_history.md` + `03_education_and_background.md`?
*Why:* `resume.md` is the identity anchor for every generated answer; it must match what's actually in front of interviewers.
**Default: synthesize from 02/03 (no new facts), you review once.**

I have add some docs, and you can review my online portflio and profile for deep research about me to see if anything else is needed. 

portfolio: https://gmcubedesigns.com/
linkedin: https://www.linkedin.com/in/therealgarymiller/

**Q7. Project docs:** PyHoldem Pro has full case-study docs already. For **StockMaster** and **Sidekick LLM**, where are the source repos/docs? Can I draft their `04_projects.md` sections from repo + your input, or will you write them (template in ARCHITECTURE §7.2)?
*Why:* STAR bullets for "tell me about X project" questions come *only* from these docs — thin docs = thin, generic-sounding answers exactly when the panel digs into your flagship projects.
**Default: I draft both case studies from available material using the template; you correct metrics/ownership in one pass.**

These are the paths to my portfolio projects themselves. All paths start with "C:\Users\"
SYNAPSE: "milli\SYNAPSE"
Investment Matrix: "milli\millionaire_miller_investments\investment_matrix"
Holdem Trainer: "milli\Holdem-Helper\Holdem-Trainer"
Qdrant Search: "milli\qdrant\qdrant-search-project"
Learning Tree: "milli\learning_tree_ai_education\learning_tree"
Sidekick LLM: "milli\free_offline_llm_app\sidekick_llm"
Coder Core: "milli\code_mastery\coder_core"

**Q8. Question bank seeding:** should `05_qa_bank.md` start as an auto-generated set (top questions per role type from resume+JD) that you then curate, or do you want to write it by hand first?
*Why:* practice mode (F12) drills from this file; a good seed saves a week of manual work.
**Default: auto-generate ~50 seeds across {system design, AI/LLM deep-dive, behavioral STAR, project follow-ups}, you mark keep/drop.**

There should be some prewritten seed questions and scripted answers that the model can use for on the spot answer development. 

## UX & Stealth Preferences

**Q9. Interview setup:** which conferencing tools do you actually get interviews on (Zoom / Teams / Meet), and will you use a headset or speakers during calls?
*Why:* the invisibility pre-flight is per-tool; headset vs speakers changes loopback device selection and the "hear yourself" echo check.
**Default: support all three; assume headset (loopback follows default endpoint either way).**

I get interviews on all of those Zoom, Meet, and Teams. My next interview is on Teams so if it matters it definitely needs to work on Teams.

**Q10. Monitor setup:** single monitor or multi-monitor during interviews?
*Why:* determines whether we rely on content-protection alone (multi-monitor: overlay on unshared monitor = bulletproof) or need the flag to work perfectly (single monitor + full-desktop share).
**Default: design for both; pre-flight auto-detects and warns.**

I might be able to use a second monitor with my laptop. 

**Q11. Process disguise on by default?** (rename process to an innocuous utility so even Task Manager shows nothing suspicious)
*Why:* it's the strongest "no evidence" measure but also the sneakiest — some candidates prefer honest-by-default with a toggle.
**Default: off by default, one-click toggle + explained in pre-flight.**

Yes toggle.

## Scope

**Q12. Practice mode (F12) timing:** keep it at Phase 3 as planned, or pull it earlier?
*Why:* it's the highest long-term-value feature but depends on live-loop stability; pulling it earlier risks a slower MVP.
**Default: Phase 3 as planned — MVP first, practice right after.**

Focus on MVP and getting the project interview ready ASAP.

---

### One-line answers sheet (fill in and return)

| Q | Your answer / "default" |
|---|-------------------------|
| 1 OS priority | default |
| 2 Hardware (GPU/CPU/RAM) | ____________ |
| 3 Fork MIT base + Natively stopgap? | default |
| 4 Ollama models already pulled | ____________ |
| 5 API fallback OK for live mode? | default |
| 6 Resume source file or synthesize? | default (synthesize) |
| 7 StockMaster / Sidekick doc sources | ____________ |
| 8 QA bank: auto-seed then curate? | default |
| 9 Conferencing tools + headset/speakers | ____________ |
| 10 Single or multi monitor in interviews? | ____________ |
| 11 Process disguise default on/off? | default (off) |
| 12 Practice mode phase | default (Phase 3) |
