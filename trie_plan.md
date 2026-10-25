# Cyrano – Deterministic Trie & RAG Toggle Implementation Plan

> **Goal**  
> Build a production‑ready engine that can instantly match interview transcript fragments against a pre‑compiled Q&A bank (Trie) and, when no exact match is found, fall back to an LLM‑powered Retrieval‑Augmented Generation (RAG).  
> The result should be a lightweight WebSocket service that feeds structured JSON payloads to the Electron front‑end overlay.

---

## ⏱️ 1️⃣ Regression & Unit Test Suites

| Task | Owner | Notes |
|------|-------|-------|
| **Create `tests/test_normalizer.py`** | 👩‍💻 | Verify lowercasing, punctuation strip, stop‑word removal and token list output. |
| **Create `tests/test_trie.py`** | 👨‍💻 | Insert multi‑word triggers; test exact prefix search, partial matches, and missed lookups (`None`). |
| **Create `tests/test_router.py`** | 👩‍💻 | Test mode toggle (`retrieval_mode: "trie"` vs `"rag"`); ensure fallback runs when Trie returns `None`. |
| **Add `pytest.ini` for consistent config** | 👨‍💻 | Include markers, timeout settings. |
| **Run full test suite locally** | 👩‍💻 | Expect 100 % pass before moving on. |

> ✅ *Checked off when all three tests and the CI build succeed.*

---

## 📦 2️⃣ Structured Pydantic Schema & YAML QA Bank

| Task | Owner | Notes |
|------|-------|-------|
| **Create `app/schemas/qa.py`** | 👩‍💻 | Implement `QABankEntry` + `QABankContainer`. Add regex validator for `triggers`. |
| **Populate `docs/qa_bank.yml`** | 👨‍💻 | Add at least 5 diverse entries (competency, project, answer, hero story ref). Include a `gotcha_warning` field. |
| **Write `scripts/validate_qa.py`** | 👩‍💻 | Loads YAML and validates against the Pydantic model; prints errors with line numbers. |
| **Add as pre‑commit hook** | 👨‍💻 | Ensure QA bank passes validation on every PR. |

> ✅ *Checked off when the script reports no validation errors.*

---

## 🔧 3️⃣ Text Normalizer & In-Memory Word‑Token Trie

| Task | Owner | Notes |
|------|-------|-------|
| **Create `app/core/normalizer.py`** | 👩‍💻 | Implement `normalize_text()` (lowercase, punctuation strip, stop‑word removal). |
| **Implement `WordTokenTrie` in `app/core/trie.py`** | 👨‍💻 | Methods: `insert(trigger_phrase, payload)`, `search_prefix(transcript_text)` returning last matched data. |
| **Add unit tests for the trie** | 👩‍💻 | Covered by `tests/test_trie.py`. |

> ✅ *Checked off when Trie lookup latency is < 2 ms on a sample dataset.*

---

## ⚙️ 4️⃣ Configuration Toggle & Mode Router

| Task | Owner | Notes |
|------|-------|-------|
| **Create `app/core/config.json`** | 👩‍💻 | Include keys: `"retrieval_mode"`, `"provider"`, `"ollama_model"`, `"ollama_host"`. |
| **Implement `HybridRouter` in `app/core/router.py`** | 👨‍💻 |  - Load config. <br> - Build trie from QA bank at init.<br> - Provide async method `resolve_query(transcript_chunk)` that returns a structured dict (source, latency_ms, content). |
| **Add factory for LLM provider** (`app/ai/factory.py`) | 👩‍💻 | Returns an object with `generate_response(prompt, context)`|
| **Test router logic** | 👨‍💻 | Use fixtures to simulate Trie hit vs miss; verify correct source field and latency estimates. |

> ✅ *Checked off when both modes produce expected payloads.*

---

## 🌐 5️⃣ WebSocket Integration & UI Payload Rendering

| Task | Owner | Notes |
|------|-------|-------|
| **Create `app/core/main.py`** | 👩‍💻 | FastAPI app exposing `/ws/stream`. Accepts transcript chunks, passes to `HybridRouter`, and emits JSON back to Electron overlay. |
| **Add CORS & WebSocket middlewares** | 👨‍💻 | Ensure Electron can connect from localhost:port. |
| **Test end‑to‑end locally** | 👩‍💻 | Run the FastAPI server, simulate a transcript stream (e.g., using `websocat`), and inspect JSON payloads. |

> ✅ *Checked off when payloads match schema and latency is < 2 ms for Trie hits.*

---

## 🚀 6️⃣ Verification & Handoff Checklist

| Task | Owner | Notes |
|------|-------|-------|
| **Run full test suite** | 👩‍💻 | `pytest tests/` – expect > 99% coverage. |
| **Performance profiling** | 👨‍💻 | Use `time.perf_counter()` or `pyinstrument` to confirm Trie lookup < 2 ms, fallback ~800 ms. |
| **Dockerfile & Compose** | 👩‍💻 | Package FastAPI + Ollama (or mock LLM) into a single image; expose port 8000. |
| **GitHub Actions CI** | 👨‍💻 | Build Docker, run tests, lint (`black`, `mypy`), and upload coverage reports. |
| **Documentation** | 👩‍💻 | Generate Markdown docs (schema, API spec) with `mkdocs`. |
| **Deploy locally** | 👨‍💻 | Spin up container, connect Electron overlay, confirm real‑time responses. |
| **Handoff to product team** | 👩‍💻 | Provide a short demo video + README covering how to run and test locally. |

> ✅ *Checked off when all items above are green.*

---

## 📚 7️⃣ Optional Enhancements (Future Roadmap)

- **Adaptive Routing** – Store per‑question confidence weights; update after each session.
- **Sentiment & Confidence Meter** – Add lightweight sentiment model on the transcript buffer.
- **Analytics Dashboard** – Persist session logs to SQLite/Redis and surface metrics via a `/analytics` endpoint.
- **Observability** – Prometheus metrics (`trie_hits_total`, `llm_calls_total`) + OpenTelemetry tracing.
- **CI‑CD for Production** – Deploy Docker image to Azure/AWS ECS/EKS with automated rollback.

---

### How to Use This Plan

1. Follow the checklist in order, checking off each ✅ as you complete it.
2. Ensure tests and CI passes and the plan is verified.

Happy coding!


