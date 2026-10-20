# Interview Buddy 🎙️🤖

An intelligent, local-first, real-time interview assistant and desktop overlay. Interview Buddy listens to live interview audio via system loopback, transcribes speech locally using `faster-whisper`, performs local RAG (Retrieval-Augmented Generation) against your personal experience and projects brain via Ollama, and delivers concise, speakable answers on an always-on-top transparent Electron overlay.

---

## 🌟 Key Features

- 🎧 **System Loopback Audio Capture** — Captures incoming audio directly from speaker output (WASAPI loopback on Windows) without virtual audio cables, cleanly transcribing interview questions from Zoom, Teams, Google Meet, or browser calls.
- ⚡ **Local-First & Privacy-Preserving** — Runs completely offline on your hardware using `faster-whisper` for STT and `Ollama` for embeddings (`nomic-embed-text`) and answer generation. Zero cloud dependencies.
- 🧠 **Personal Knowledge RAG Brain** — In-process vector indexing over your structured markdown files (`resume.md`, `04_projects.md`, `05_qa_bank.md`). Answers are grounded specifically in your own background, metrics, and STAR-format stories.
- 🪟 **Discreet Electron Overlay** — Fast, transparent, always-on-top UI with screen-share exclusion properties to stay invisible during video calls.
- 🚀 **One-Command Startup** — Automated PowerShell launcher (`run_interview_buddy.ps1`) manages Ollama, the Python core service, and the Electron frontend with unified lifecycle and cleanup.

---

## 🛠 Tech Stack

- **Desktop Overlay**: Electron, React 19, TypeScript, Tailwind CSS, Zustand
- **Core Backend**: Python 3.12+, FastAPI, Uvicorn, PyAudio (WASAPI loopback)
- **Speech-to-Text**: `faster-whisper` (CTranslate2)
- **LLM & Embeddings**: Local Ollama (`nomic-embed-text` + open-weight LLMs)
- **Testing**: Pytest (`tests/test_core.py`), anyio

---

## 📁 Repository Structure

```text
interview_buddy/
├── app/
│   ├── core/                  # Python core backend (FastAPI, STT, Loopback capture, RAG)
│   │   ├── audio_capture.py   # WASAPI loopback audio stream reader
│   │   ├── brain.py           # Markdown vector index & retriever
│   │   ├── main.py            # FastAPI WebSocket & REST endpoints
│   │   ├── stt.py             # faster-whisper real-time transcriber
│   │   └── config.json        # Core service settings
│   ├── src/                   # Electron main & renderer process (React UI)
│   ├── run_interview_buddy.ps1# One-click Windows launcher
│   └── package.json           # Frontend dependencies
├── docs/                      # Architecture, plans, and design notes
├── job_descriptions/          # Target job descriptions for semantic alignment
├── tests/                     # Backend test suite (audio capture, brain, endpoints)
├── 04_projects.md             # Project case studies and technical talking points
├── 05_qa_bank.md              # Scripted Q&A bank with STAR responses
├── resume.example.md          # Sample resume format for the knowledge brain
└── requirements.txt           # Python dependencies
```

---

## 🚀 Quick Start

### 1. Prerequisites

- **Node.js**: v18+ & npm / pnpm
- **Python**: 3.11+ (managed via `uv` or standard venv)
- **Ollama**: Installed and available in PATH ([ollama.ai](https://ollama.ai/))
  - Pull the embedding model:
    ```bash
    ollama pull nomic-embed-text
    ```
  - Pull your preferred reasoning model (e.g. `llama3` or configured in `app/core/config.json`):
    ```bash
    ollama pull gpt-oss:20b  # or llama3:8b
    ```

### 2. Configure Your Knowledge Brain

Create your `resume.md` at the project root based on the provided template:

```bash
cp resume.example.md resume.md
```

You can customize `resume.md`, `04_projects.md`, and `05_qa_bank.md` with your own experience and behavioral question responses.

### 3. Install Dependencies

**Frontend:**
```bash
cd app
npm install
cd ..
```

**Python Backend:**
```bash
uv sync   # or pip install -r requirements.txt
```

### 4. Run the Application

Launch everything with the one-command PowerShell script:

```powershell
powershell -ExecutionPolicy Bypass -File .\app\run_interview_buddy.ps1
```

---

## 🧪 Running Tests

To run the Python backend test suite:

```bash
uv run pytest
```

---

## 🔒 Privacy & Exclusions

This repository is configured to keep personal resume details, generated vector caches (`.cache/*.npz`), virtual environments, and build artifacts out of version control via `.gitignore`.
