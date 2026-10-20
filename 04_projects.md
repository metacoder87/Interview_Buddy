# Portfolio Projects — Case Studies & STAR Source Material

Source of truth for project questions. Every metric below comes from the project's own repo/docs (paths in headers). Format per ARCHITECTURE §7.2: problem → solution/impact → architecture → hard problems → metrics.

---

## Sidekick LLM
**Repo:** `C:\Users\milli\free_offline_llm_app\sidekick_llm` · github.com/metacoder87/sidekick_llm
**One-liner:** Privacy-first desktop knowledge system for local LLMs — the durable artifact is a user-owned corpus (conversations, compounding memory, domain "AI Experts" trained on your own PDFs), not a chat window.
**Stack:** Electron 43 · React 18 + Vite · Node main process · Ollama (inference + embeddings) · SQLite (better-sqlite3, WAL) · FTS5/BM25 · TypeScript
**Role & ownership:** Solo architect/developer; full lifecycle.

### Problem & context
Chat UIs throw away the knowledge they accumulate. Sidekick inverts that: offline, zero-cost, data never leaves the machine, and the assistant *improves with use* via a persistent, de-duplicated memory of personal facts plus per-domain Expert vaults built from user documents and curated web research.

### Solution & impact
- **Federated Expert consultation:** query embedded once; each selected vault searched independently; personas combined in one prompt that is explicitly asked to *surface disagreements rather than flatten them*; every answer carries a grounding badge distinguishing cited/vault-backed answers from model-only ones.
- **Compounding memory:** facts extracted in background, de-duplicated on canonical form, recalled by relevance to the current question (not pure recency) — the system compounds instead of accumulating noise.
- **Embedding contract as load-bearing invariant:** a chunk without a valid dimension-matched vector is *invisible* to retrieval, not silently scored zero; provenance (`embedding_model`, `embedding_dim`) stored on every vector; write boundary rejects empty vectors; mismatched vectors are excluded and reported; existing vaults repairable via in-place re-indexing.
- **Resilient offline architecture:** Ollama + SQLite both local → fully offline operation; availability polling surfaces connection/DB-integrity problems instead of failing silently; long-running ops (ingest, research, re-index) report real counts and actionable failure reasons; embedding models pre-flighted before minutes of work.

### Hard problem → solution
*Silent retrieval degradation:* vector search quietly returning wrong results when embeddings drift or a model swap changes dimensions. *Solution:* the embedding contract above — provenance per vector, dimension-matched visibility rule, repair path via re-indexing, and honest reporting instead of blanket success.

### Metrics
- 100% offline operation; zero cloud dependency for inference or storage.
- Versioned SQLite schema (`PRAGMA user_version`) with transactional migrations + automatic backup-before-migrate + integrity check on open.
- FTS5 BM25 full-text search + cosine vector retrieval, both local.

---

## SYNAPSE — Systematic Yield Network for AI Placement & Strategic Employment
**Repo:** `C:\Users\milli\SYNAPSE` · github.com/metacoder87/SYNAPSE
**One-liner:** Privacy-first, zero-API-cost, human-in-the-loop job intelligence platform: normalizes six data sources, deterministic screening, semantic-fit ranking, and on-demand fact-checked company dossiers from a local three-agent AI crew.
**Stack:** FastAPI · Next.js (cyberpunk dashboard) · PostgreSQL (source of truth) · ChromaDB (vectors, same UUIDs) · sentence-transformers MiniLM embeddings · CrewAI on Ollama · Prometheus + Grafana + Phoenix tracing · Docker Compose (7 containers)
**Role & ownership:** Sole developer — requirements, architecture, implementation, testing, engineering decisions. AI coding tools used as accelerators; ownership of decomposition, tradeoffs, and validation was mine.

### Problem & context
Technical job search wastes time three ways: reviewing low-fit roles repeatedly, re-researching the same companies across scattered sources, and rewriting application material without a reliable factual boundary. Also: cloud job-search SaaS means your search history lives on someone else's servers (Cluely-style breach risk).

### Solution & impact
- **Pipeline:** six source adapters (USAJobs/Adzuna/Jooble/Greenhouse/Lever/RSS) → unified Pydantic Job model → deterministic regex kill switch (discards logged, not stored) → MiniLM embeddings → alignment score vs candidate profile → ranked queue. PostgreSQL = relational truth; ChromaDB = vectors keyed by the same job UUIDs.
- **Freshness enforced three ways:** daily deterministic expiry on closing dates, 12-hour heartbeat probing live URLs (404s / generic redirects / "position filled"), weekly purge removing stale rows from Postgres and Chroma together.
- **Deep-dive dossiers:** CrewAI crew (Scout → Networker → Fact-Checker) on local Ollama; backend retrieves company evidence, extracts/embeds chunks in a per-run in-memory index, generates structured claims, checks numeric literals *deterministically*, asks a temperature-zero verifier for supported/contradicted/insufficient verdicts — and **Python, not the model, renders the final cited dossier**.
- **Claim-gated application documents:** tailored résumé + cover letter generated only from an approved fact ledger; in-place editing with revision history; export DOCX/PDF/TXT/Markdown/ZIP.
- **Honest status (verified snapshot):** working local single-user system — backend 76 passed / 32 skipped tests, frontend 16 passing tests, production Next.js build succeeds. Careful boundary: "production-shaped architecture," not externally deployed SaaS; durable queues, tenant isolation, hosted inference, and security hardening are the explicit SaaS preconditions.

### Hard problems → solutions
*Dual-store consistency (Postgres + ChromaDB):* permanent deletion required a tombstone plus vector-cleanup retry record so the two stores can't drift. *Model overreach in generation:* claims must carry evidence references and a verification verdict; final rendering is deterministic Python — the model is inspectable and replaceable. *Threshold calibration:* `calibrate_threshold.py` shows real score distribution after first ingest instead of guessing an alignment cutoff.

### Metrics
- 6 ingestion sources, 1 unified schema; 3 independent freshness mechanisms.
- Backend: 76 passed / 32 skipped (skips = optional services/models unavailable in verification env). Frontend: 16 passing tests + green production build.
- Full observability stack: Prometheus metrics endpoint, Grafana dashboards, Phoenix agent tracing.

---

## Investment Matrix / CryptoInsight (crypto)
**Repo:** `C:\Users\milli\millionaire_miller_investments\investment_matrix` · github.com/metacoder87/investment_matrix
**One-liner:** Self-hosted quantitative market-research and automated paper-trading platform for **cryptocurrency**: multi-exchange real-time ingestion, deterministic decision engine with triple-validated entries, and a seven-agent local AI research organization that maintains a versioned strategy playbook. (Distinct from StockMaster — the equities line; this crypto system is the more advanced of the two.)
**Stack:** FastAPI · Celery + beat · Alembic · TimescaleDB/PostgreSQL hypertables · Redis Streams · Ollama (Llama 3.1 8B, JSON-contract execution) · Next.js + React + Tailwind · Docker Compose
**Role & ownership:** Solo architect/developer; full lifecycle including the agent organization design.

### Problem & context
Proprietary quant strategies leak if they run through public APIs or cloud inference, and retail tooling either black-boxes decisions or can't validate a strategy before risking capital. Goal: zero data leaves the machine, every entry is validated three ways, and losing strategies automatically size down.

### Solution & impact
- **High-throughput ingestion:** parallel WebSocket streamers (Kraken/Coinbase/Binance) → Redis Streams with crash-safe consumption (pending-message recovery + dead-letter queue) → TimescaleDB hypertables for raw ticks/quotes plus 1m/5m rollups.
- **Deterministic decision engine:** millisecond-level formula engine (VWAP, CVD, ATR, RSI) makes every live trading decision — the LLM is *off the trade path* (nightly desk analyst writing postmortems/lessons). Entries validated three ways before execution: 7-day strategy backtest → thesis-geometry simulation of the exact TP/SL being traded → guardrail stack (freshness, regime, correlation, drawdown, **fractional-Kelly sizing from realized win rates**).
- **Live trigger execution:** Redis-first sub-second price reads; intrabar high/low wick detection for entries/stops with conservative whipsaw handling; quote-derived half-spread fill simulation from stored bid/ask.
- **Self-correcting accuracy loop:** every prediction/thesis scored against realized prices; per-strategy scorecards (win rate, expectancy, direction accuracy) feed Kelly sizing — losing strategies automatically shrink.
- **Autonomous research team:** seven agents (Scout → Deep Research → Backtest Lab → Strategy Scientist, plus Note Analyst, Risk Officer, Strategy Router) on dedicated Celery queues so they can never delay trading; champion/challenger shadow evaluation with out-of-sample gates and bounded parameters; validated findings become a versioned **Strategy Playbook** (regime → strategy + params) that live trading reads. Promotions manual (tier 0) or automatic (tier 1).
- **Observability:** SSE real-time dashboard (~2s crew refresh, tick-by-tick portfolio revaluation), regime ribbon on charts, 48h replay scrubber, live ops page (writer throughput/lag sparklines, stream depths, queue depths, LLM invocation stats).

### Hard problems → solutions
*Backpressure between ingestion and storage:* Redis Streams as the isolation layer with pending-message recovery + DLQ so a slow writer never drops ticks. *LLM reliability in a trading system:* JSON-contract model execution with prompt retries and agent validation — but architecturally the LLM can never approve an entry; only the deterministic engine does.

### Metrics
- 3 exchanges, sub-second price reads, millisecond-level decision engine.
- Triple entry validation (backtest + geometry sim + guardrail stack) before any paper execution.
- 7-agent research org on isolated queues; versioned playbook with out-of-sample promotion gates.

---

## StockMaster (equities)
**Repo:** not yet provided — expand this section when the repo path is available
**One-liner:** Quantitative financial modeling and price-prediction application for **stock markets**, with autonomous AI trading crews: real-time market ingestion, quantitative backtesting, and risk-reviewed execution.
**Stack (per work history):** Python · Kraken API · quantitative backtesting infrastructure
**Role & ownership:** Solo architect/developer; designed and maintained the continuous-learning autonomous trading crews.

### Problem & context
Retail quant tooling either black-boxes signals or can't separate research from execution risk. StockMaster targets the equities side of the same problem Investment Matrix solves for crypto: model-driven price prediction with backtested, risk-reviewed execution — kept local so proprietary models never leave the machine.

### Key facts (from work history — verify/expand against repo)
- Continuous-learning autonomous AI trading crews.
- Real-time market ingestion → quantitative backtesting → risk-reviewed execution pipeline.
- Kraken API integration; Python throughout.

> NOTE for interview use: keep StockMaster and Investment Matrix/CryptoInsight as **two distinct projects** (equities vs crypto). If pressed on depth, lead with Investment Matrix — it has the fuller architecture story above.

---

## PyHoldem Pro / Holdem-Trainer
**Repo:** `C:\Users\milli\Holdem-Helper\Holdem-Trainer` · full docs in workspace `05_holdem_trainer_docs/`
**One-liner:** Quantitative Texas Hold'em training platform: concurrent CLI simulator + React dashboard with real-time EV-based coaching, Bayesian playing-style classification, and adaptive spaced-repetition drills.
**Stack:** Python 3.13 + FastAPI/Uvicorn · React 18 + TypeScript + Vite · PostgreSQL/SQLAlchemy/Alembic (JSON fallback) · Docker · Prometheus + Grafana
**Role & ownership:** Solo architect/developer; full lifecycle.

### Problem & context
Solver-grade poker software is expensive, desktop-locked, and data-hostile; basic simulators don't evaluate decisions mathematically in real time. Gap: local-first (privacy), automated per-decision EV grading, and drills that adapt to observed weaknesses.

### Solution & impact
- **Real-time automated coaching:** every human decision point evaluated against mathematical baselines; immediate EV-loss output in big blinds pinpoints costly mistakes.
- **Adaptive spaced-repetition drills:** training engine maps weaknesses ("Too Loose", "Poor Pot Odds") to focus areas and dynamically serves scenarios the player has historically struggled with.
- **Bayesian playing-style classification** with credible intervals over session history; full analytics dashboard (charts, reports, timeline).

### Hard problems → solutions (the interview gold)
*CPU-bound Monte Carlo in an ASGI event loop:* range-vs-range equity needs thousands of simulated deals — running them synchronously blocked the event loop and froze WebSockets. *Solution:* compressed lookup table + fast hand-evaluation module (`fast_eval.py`), caching of identical board/hand combos, exact enumeration preferred over Monte Carlo when cards-to-come are low → **seconds down to single-digit milliseconds**.
*Scaling ICM permutations:* 9-handed final table = 362,880 exact permutations. *Solution:* optimized recursion in `icm_calculator.py` at **O(2^n·n)** with memoized sub-state stack weights — exact indexing for n≤6, dynamic programming for 7–9 hands, **under 5 ms**.
*Client-side quiz cheating:* inspectable React state/API payloads let players bypass drill math. *Solution:* server-owned validation — frontend requests a `quiz_id`, correct answers cached privately in backend transient progress files, tolerance calculation (absolute/relative margins) executed server-side before feedback is exposed.

### Metrics
- **630+ passing tests** covering core game loops, pot distributions, side pots, Bayesian credible intervals, tournament payouts.
- Monte Carlo equity: seconds → single-digit ms; ICM 9-handed: <5 ms.
- Dockerized with Prometheus/Grafana observability overlay (API latency, game-loop performance, ASGI health).

---

## Qdrant Search Console
**Repo:** `C:\Users\milli\qdrant\qdrant-search-project` · github.com/metacoder87/qdrant-search-project
**One-liner:** Document-first semantic search console: turns chunk-level vector matches into ranked *document* results with deterministic seeding and human-feedback capture for future embedding fine-tuning.
**Stack:** Python + FastAPI · Qdrant (Docker, disk-persistent) · sentence-transformers `all-MiniLM-L6-v2` · SQLite (HITL feedback) · React + TypeScript + Vite · Tailwind/ShadCN · PDF.js
**Role & ownership:** AI Architect & Senior AI Engineer — end-to-end architecture and implementation.

### Problem & context
Raw vector search returns scattered chunks from the same document, drowning users in ML noise; and retrieval systems without structured feedback can't improve. Gap: a human-in-the-loop layer between ANN output and decision-making.

### Solution & impact
- **Intelligent hit aggregation:** custom algorithm groups chunk hits by `doc_id`, computes average similarity per document, sorts the final payload — large documents stop dominating results; raw ML output becomes a clean document-first experience.
- **Deterministic CI/CD seeding:** `qdrant_seed.py` (DEBUG-gated) drops/recreates/seeds the collection with an exact 10-point dataset spanning PDF/text/HTML → reproducible test states and trivial onboarding.
- **Strict HITL feedback loop:** captures result usefulness, but a downvote *requires* an explanation — high-quality contextual data for future embedding fine-tuning and RAG optimization.
- **Safe multi-format rendering:** PDF.js native-feeling PDFs; sanitized HTML pipeline with ≤50-word preview snippets and chunk-navigation arrows that auto-scroll to the exact semantic match (XSS-safe).

### Metrics
- Chunk→document aggregation eliminates per-chunk result flooding (design-level fix, measured in UX review load).
- Deterministic 10-point seed dataset for fully reproducible pipelines.

---

## The Learning Tree
**Repo:** `C:\Users\milli\learning_tree_ai_education\learning_tree`
**One-liner:** Local-first K-12 family-learning app built around one explorable, animated 3D tree — grades are trunk regions, subjects are limbs, learning objectives are leaves whose fall-to-spring colors reflect *evidence-based* mastery.
**Stack:** React 18 + TypeScript + Vite · React Three Fiber / Drei / Three.js (WebGL) · FastAPI + Pydantic + SQLAlchemy + Alembic + SQLite · Ed25519 signing + AES-GCM (`cryptography`) · Ollama optional (disabled by default)
**Role & ownership:** Solo architect/developer; engineering prototype with explicit release gates.

### Problem & context
K-12 learning apps either cloud-lock family data or award "mastery" for repeating a lesson five times. Goal: no-cloud Windows-first Family Edition where mastery requires real evidence, curriculum is versioned and signed, and AI stays out of the child-facing loop until reviewed.

### Solution & impact
- **Evidence-based mastery state machine (6 levels):** Unexplored → Started → Developing → Practiced → Proficient → Mastered; each level has explicit required evidence (instruction + assessment + *later scheduled reviews*); attempts, evidence, mastery events, and review schedules stored separately; open-ended responses flagged for parent review instead of exact-match graded.
- **Versioned curriculum-pack contract:** manifests with licenses/standards/objectives/units/lessons/sources/approvals; published packs reject missing sources, orphan graph references, duplicate stable IDs, drafts, and author self-approval; deterministic hashing, coverage reports, immutable review reports, **Ed25519 release signing + verification**.
- **Local family data security:** AES-GCM encrypted export/import with passphrase-derived keys preserving full progress history.
- **Resilient interface:** WebGL failure falls back to a keyboard-accessible React error-boundary navigator; `prefers-reduced-motion` and forced-colors support; only the current grade region + neighbors rendered in 3D (performance).

### Metrics
- Seeded map: 14 levels (Pre-K–Grade 12), 91 subject branches, 542 leaves; 12 canonical lesson packages authored, rest explicitly "not installed or not reviewed" — never silently substituted.
- Honest status reporting API (`/api/curriculum/status` separates installed coverage from optional tutor health).

---

## Coder Core
**Repo:** `C:\Users\milli\code_mastery\coder_core`
**One-liner:** Local-first desktop mastery system for computer-science learning and reproducible workforce-readiness measurement: cited lessons, Docker-verified drills, and a full mock-OA assessment simulator with interviewer-led and paired-coding modes.
**Stack:** Electron 43 · React 19 + strict TypeScript · sandboxed CommonJS preload bridge · Node SQLite API (attempt history) · Docker (hardened execution sandbox) · Monaco (bundled, no CDN) · Ollama (optional coaching)
**Role & ownership:** Solo architect/developer; Python Online-Assessment Core and Assessment Simulator milestones complete.

### Problem & context
Coding-practice tools either grade loosely or can't prove readiness: no deadline pressure, no evidence of what the learner actually did, and mastery estimates with no confidence bounds. Goal: reproducible, evidence-based workforce-readiness measurement that runs fully locally.

### Solution & impact
- **Assessment simulator:** online-assessment, interviewer-led, and paired-coding modes sharing one deadline; exact foreground-dwell evidence; bounded problem navigation; code/reasoning recovery; communication/collaboration rubrics for paired mode; optional human evaluation + aggregate review; SQLite-backed history. Four fixed 70-minute mock-OA blueprints with exact section budgets and distinct problem sets.
- **Content at scale, all original:** 48 prerequisite-linked skills · 48 lessons with precise university/official Python citations · 144 trace/semantics/complexity/debugging/pattern drills · 48 challenge families with visible + hidden tests, all verified in Docker.
- **Honest mastery estimation:** evidence-based estimates *with explicit confidence levels*; challenge vs retrieval mastery reported separately; drill-only readiness capped at 35% so practice can't fake assessment performance.
- **Hardened execution sandbox:** Docker-backed Python — no network, no host mounts, read-only root, non-root user, dropped capabilities, CPU/RAM/PID limits, forced timeout. Crash-safe timed-session recovery (code, assistance, timer deadline, learner notes).
- **Governed content factory:** schema-v3 ledger with immutable source records, claim-level provenance, deterministic checks, independent evaluator gates, quarantine, rollback, soft deletion.

### Metrics
- 48 skills / 48 lessons / 144 drills / 48 challenge families — all Docker-verified.
- Repeatable 12-route Electron accessibility audit (landmarks, ARIA references, focus traversal, Chromium a11y tree) including isolated simulator sessions.

---

## Cross-project themes (use for "what defines your work" questions)

1. **Local-first & privacy-preserving by architecture, not slogan:** Ollama + SQLite/Postgres/Qdrant everywhere; data-never-leaves-the-machine is a design constraint in Sidekick LLM, SYNAPSE, Investment Matrix, Learning Tree, and Coder Core.
2. **Determinism where it matters, models where they help:** regex kill switches before embedding spend (SYNAPSE), deterministic decision engine with the LLM off the trade path (Investment Matrix), Python renders the final dossier not the model (SYNAPSE), evidence-gated mastery states (Learning Tree).
3. **Honest reporting as a feature:** real counts + actionable failure reasons (Sidekick LLM), verified status snapshots and language boundaries (SYNAPSE), confidence-bounded mastery estimates with drill-only caps (Coder Core), "not reviewed" states never silently substituted (Learning Tree).
4. **Production-shaped solo systems:** Docker Compose multi-container deploys, Alembic migrations, Prometheus/Grafana/Phoenix observability, 630+ tests in one repo alone, CI-seeding utilities, accessibility audits — portfolio projects built to the standard of shipped software.
