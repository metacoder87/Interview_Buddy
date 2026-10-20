# Interview Buddy - Real-Time AI Interview Assistant
An all-in-one desktop application that listens to live interview audio, transcribes questions, and streams concise spoken answers using a local LLM. It runs completely offline (unless you enable API mode), stays invisible during screen-share sessions, and provides a stealthy always-on-top overlay for real-time assistance.

## Quick Start
1. Prerequisites
- Node.js >= 18 (npm >= 9) - for the Electron front-end
- Python 3.12+ with uv (Python package manager)
- Ollama 0.33+ with models pre-pulled:
  qwen3:30b
  qwen2.5:32b
  llama3:8b
  mistral:7b
  gpt-oss:20b
  nomic-embed-text (embedding model)
- Optional but recommended: a local Qdrant instance for vector search (the app works with SQLite-vec if none is found).

2. Installation
- Clone the repository:
  git clone https://github.com/elias-soykat/interview-copilot.git
- Install Node dependencies (inside the app folder):
  npm install
- Set up the Python core service:
  cd app/core
  uv sync               # creates a virtual environment with required packages
  uv run uvicorn main:app --port 8790   # start FastAPI backend

3. Prepare your "brain" (content)
- Create resume.md – one-page summary of experience, skills and education. Use information from 02_work_history.md, 03_education_and_background.md and your LinkedIn/portfolio; do not add invented facts.
- Add project case studies to 04_projects.md. Use a structure like:
  ## <Project Name>
  **One-liner:** …
  **Stack:** …
  **Role & ownership:** …
  ### Problem & context
  ### Solution & impact (include measurable results)
  ### Architecture
  ### Hard problems (challenge → solution → outcome, STAR format)
  ### Metrics (list all quantifiable facts)
- Place each job description in job_descriptions/ as <role>_<company>.md. Include the raw JD and optionally a brief "gap-analysis" section.

4. Launch the application
 - From the repository root (the app folder) run:
   npm run dev
- The Electron window opens with a transparent, always-on-top overlay.
- Open Settings in the app and paste your OpenAI API key (required for Whisper transcription and GPT answer generation). You may also paste the contents of resume.md here for personalized context.

5. Run a session
- Click Start. Choose System Audio (the audio that is being sent to your speakers/headphones) as the capture source – this is the loopback channel that contains the interviewer's voice.
- Adjust Opacity and Font Size in Settings if needed.
- Use hotkeys:
  - Ctrl+Alt+Space – start/stop listening
  - Ctrl+Alt+Q – force an answer now
  - Ctrl+Alt+= / Ctrl+Alt+- increase / decrease font size
  - Ctrl+Alt+H – hide/show the overlay
- The app automatically detects question pauses, transcribes them, classifies the question type and streams answer bullets. Your spoken answers can be captured in practice mode (Ctrl+Alt+P) if you want to rehearse.

## Stealth / Invisibility
- Screen-share protection: The window is marked with setContentProtection(true), which excludes it from Zoom, Microsoft Teams, Google Meet and other desktop-capture APIs. A pre-flight checklist (Phase 3) verifies that the overlay cannot be seen when you share your screen.
- Taskbar & Alt-Tab: skipTaskbar:true + WS_EX_TOOLWINDOW ensures the app does not appear in the taskbar or Alt-Tab list.
- Process disguise (optional toggle): renames the executable to a benign utility name; can be enabled in Settings → "Stealth Mode".

## Latency Target
The system aims for p50 <= 4 s from question end to first bullet, with p95 <= 7 s. All major stages (audio capture → STT → classification → LLM generation → overlay render) are timed and logged; the debrief screen shows where time is spent.

## FAQ / Troubleshooting
| Symptom | Likely cause | Fix |
|---|---|---|
- No audio is captured | Loopback device not enabled or wrong default in PyAudioWPatch | Verify Windows “Loopback” capture is enabled (SoundControl → Recording → "Stereo Mix"/"Wave Out Capture") and that the app's settings point to the correct device.
- Overlay visible during screen share | Content protection disabled or running an older OS build | Ensure setContentProtection(true) is active; on Windows 10 < 2004 you may need to enable "Advanced capture with window filtering" in Teams/Zoom and then re-enable the flag.
- Answers are delayed > 7 s (p95) | CPU-only STT model or cold LLM start | Switch to GPU-accelerated faster-whisper FP16 model, or pre-warm Ollama ollama run qwen3:30b before the interview.
- Missing bullets / wrong format | Classification confidence low; manual hotkey not used | Verify the linguistic gate threshold (default 900 ms post-silence). Use Ctrl+Alt+Q to manually trigger if needed.

## Support
For bugs, feature requests or discussion, open an issue in the GitHub repository or contact the maintainer directly.

*Interview Buddy* – your AI co-pilot for technical, behavioral and system-design interview preparation.
