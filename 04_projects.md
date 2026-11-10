# Portfolio Projects — Case Studies & STAR Source Material

Source of truth for project questions. Every metric below comes from the project's own repo/docs (paths in headers). Format per ARCHITECTURE §7.2: problem → solution/impact → architecture → hard problems → metrics.

---

## Sidekick LLM

*Repo:* `C:\Users\milli\free_offline_llm_app\sidekick_llm` · [github.com/metacoder87/sidekick_llm](https://github.com/metacoder87/sidekick_llm)  
*One-liner:* Privacy-first desktop knowledge system for local LLMs — the durable artifact is a user-owned corpus (conversations, compounding memory, domain "AI Experts" trained on your own PDFs), not a chat window.  
*Stack:* Electron 43 · React 18 + Vite · Node main process · Ollama (inference + embeddings) · SQLite (better-sqlite3, WAL) · FTS5/BM25 · TypeScript  
*Role & ownership:* Solo architect/developer; full lifecycle.

### Problem & Context

Chat UIs throw away the knowledge they accumulate. Sidekick inverts that: offline, zero-cost, data never leaves the machine, and the assistant *improves with use* via a persistent, de-duplicated memory of personal facts plus per-domain Expert vaults built from user documents and curated web research.

### Solution & Architectural Impact

- **Federated Expert Consultation:** Queries are embedded once; each selected vault is searched independently; personas are combined in one prompt that is explicitly asked to *surface disagreements rather than flatten them*. Every answer carries a grounding badge distinguishing cited/vault-backed answers from model-only ones.
- **Compounding Memory Architecture:** Facts are extracted in the background, de-duplicated on canonical form, and recalled by relevance to the current question (not pure recency)—ensuring the system compounds useful knowledge rather than accumulating noise.
- **Embedding Contract as Load-Bearing Invariant:** A chunk without a valid dimension-matched vector is *invisible* to retrieval, not silently scored zero. Provenance (`embedding_model`, `embedding_dim`) is stored on every vector; write boundaries reject empty vectors; mismatched vectors are excluded and reported; existing vaults are repairable via in-place re-indexing.
- **Resilient Offline Architecture:** Ollama and SQLite both run locally for fully offline operation. Availability polling surfaces connection and DB-integrity problems instead of failing silently. Long-running operations (ingest, research, re-index) report real counts and actionable failure reasons, and embedding models are pre-flighted before minutes of work are wasted.

### Hard Problem → Solution

*Silent retrieval degradation:* Vector search quietly returns wrong results when embeddings drift or a model swap changes dimensions.  
*Solution:* The embedding contract above—provenance per vector, dimension-matched visibility rule, repair path via re-indexing, and honest reporting instead of blanket success.

### Metrics & Engineering Guardrails

- 100% offline operation; zero cloud dependency for inference or storage.
- Versioned SQLite schema (`PRAGMA user_version`) with transactional migrations, automatic backup-before-migrate, and integrity checks on open.
- Hybrid FTS5 BM25 full-text search + cosine vector retrieval, executed entirely locally.

---

## SYNAPSE — Systematic Yield Network for AI Placement & Strategic Employment

*Repo:* `C:\Users\milli\SYNAPSE` · [github.com/metacoder87/SYNAPSE](https://github.com/metacoder87/SYNAPSE)  
*One-liner:* Privacy-first, zero-API-cost, human-in-the-loop job intelligence platform: normalizes six data sources, deterministic screening, semantic-fit ranking, and on-demand fact-checked company dossiers from a local three-agent AI crew.  
*Stack:* FastAPI · Next.js (cyberpunk dashboard) · PostgreSQL (source of truth) · ChromaDB (vectors, same UUIDs) · sentence-transformers MiniLM embeddings · CrewAI on Ollama · Prometheus + Grafana + Phoenix tracing · Docker Compose (7 containers)  
*Role & ownership:* Sole developer — requirements, architecture, implementation, testing, engineering decisions. AI coding tools used as accelerators; ownership of decomposition, tradeoffs, and validation was mine.

### Problem & Context

Technical job search wastes time three ways: reviewing low-fit roles repeatedly, re-researching the same companies across scattered sources, and rewriting application material without a reliable factual boundary. Furthermore, cloud job-search SaaS means your search history lives on external servers carrying unnecessary breach risks.

### Solution & Architectural Impact

- **Ingestion & Dual-Store Pipeline:** Six source adapters (USAJobs/Adzuna/Jooble/Greenhouse/Lever/RSS) stream into a unified Pydantic Job model, passing through a deterministic regex kill switch (discards logged, not stored) before MiniLM embedding and alignment scoring. PostgreSQL acts as relational truth; ChromaDB stores vectors keyed by the exact same job UUIDs.
- **Triple-Layer Freshness Enforcement:** Daily deterministic expiry on closing dates, 12-hour heartbeat probing of live URLs (catching 404s, generic redirects, and "position filled" states), and a weekly purge removing stale rows from Postgres and Chroma simultaneously.
- **Agentic Deep-Dive Dossiers:** A CrewAI crew (`Scout` → `Networker` → `Fact-Checker`) runs on local Ollama. The backend retrieves company evidence, extracts/embeds chunks in a per-run in-memory index, generates structured claims, checks numeric literals *deterministically*, asks a temperature-zero verifier for supported/contradicted/insufficient verdicts—and *Python, not the model, renders the final cited dossier*.
- **Claim-Gated Application Documents:** Tailored résumés and cover letters are generated solely from an approved fact ledger, supporting in-place editing with revision history and multi-format exports (DOCX/PDF/TXT/Markdown/ZIP).

### Hard Problems → Solutions

- **Dual-Store Consistency (Postgres + ChromaDB):** Permanent deletion requires a tombstone plus a vector-cleanup retry record to prevent the two stores from drifting out of sync.
- **Model Overreach in Generation:** Claims must carry evidence references and a verification verdict. Final rendering is executed by deterministic Python code, ensuring the model remains inspectable and replaceable.
- **Threshold Calibration:** `calibrate_threshold.py` evaluates real score distributions after initial ingestion rather than guessing arbitrary alignment cutoffs.

### Metrics & Engineering Guardrails

- 6 ingestion sources normalized into 1 unified schema with 3 independent freshness mechanisms.
- Backend verified: 76 passed / 32 skipped tests (skips correspond to optional services/models unavailable in specific verification environments). Frontend: 16 passing tests with green production builds.
- Full observability stack: Prometheus metrics endpoint, Grafana dashboards, and Phoenix agent tracing.

---

## Investment Matrix / CryptoInsight

*Repo:* `C:\Users\milli\millionaire_miller_investments\investment_matrix` · [github.com/metacoder87/investment_matrix](https://github.com/metacoder87/investment_matrix)  
*One-liner:* Self-hosted quantitative market-research and automated paper-trading platform for cryptocurrency: multi-exchange real-time ingestion, deterministic decision engine with triple-validated entries, and a seven-agent local AI research organization maintaining a versioned strategy playbook.  
*Stack:* FastAPI · Celery + beat · Alembic · TimescaleDB/PostgreSQL hypertables · Redis Streams · Ollama (Llama 3.1 8B, JSON-contract execution) · Next.js + React + Tailwind · Docker Compose  
*Role & ownership:* Solo architect/developer; full lifecycle including agent organization design.

### Problem & Context

Proprietary quantitative strategies leak if routed through public cloud APIs or hosted LLM inference, and retail tooling either black-boxes decisions or fails to validate strategies before risking capital. Goal: 100% data sovereignty, triple-validated trade entries, and self-correcting position sizing.

### Solution & Architectural Impact

- **High-Throughput Ingestion & Backpressure Isolation:** Parallel WebSocket streamers (Kraken/Coinbase/Binance) push events to Redis Streams with crash-safe consumer groups (pending-message recovery + dead-letter queue) feeding TimescaleDB hypertables for raw ticks and 1m/5m rollups.
- **Deterministic Decision Engine (LLM Off Trade Path):** Millisecond-level formula engines (VWAP, CVD, ATR, RSI) drive live trading decisions. The LLM acts exclusively as a nightly desk analyst writing post-mortems and strategy proposals. Every entry undergoes triple validation: (1) 7-day historical backtest, (2) thesis-geometry simulation of exact TP/SL levels, and (3) a risk guardrail stack incorporating regime checks, correlation filters, drawdowns, and fractional-Kelly sizing derived from realized win rates.
- **Autonomous 7-Agent Research Organization:** Seven specialized agents operating on dedicated Celery queues (`Scout` → `Deep Research` → `Backtest Lab` → `Strategy Scientist`, plus `Note Analyst`, `Risk Officer`, `Strategy Router`) ensure research never blocks trading threads. Features a champion/challenger shadow evaluation system with out-of-sample promotion gates that feed a versioned *Strategy Playbook*.
- **Real-Time Observability & Ops:** Server-Sent Events (SSE) dashboard delivering ~2s crew updates and tick-by-tick portfolio revaluation, featuring a regime ribbon, 48-hour replay scrubber, and a live ops page tracking writer throughput, lag sparklines, and LLM invocation stats.

### Hard Problems → Solutions

- **Backpressure & Tick Loss:** Redis Streams acts as an isolation buffer between exchange websocket ingestion and database persistence, preventing slow consumer spikes from dropping market ticks.
- **LLM Reliability in Trading:** Enforced strict JSON-contract model execution with automated retries, while maintaining an uncompromised architectural boundary where the LLM can never trigger a trade execution directly.

### Metrics & Engineering Guardrails

- 3 exchange feeds with sub-second price reads and millisecond-level formula execution.
- Triple-entry validation stack executed prior to any paper order placement.
- 7-agent research organization operating on isolated queues with versioned playbooks and out-of-sample promotion gates.

---

## StockMaster (Equities)

*Repo:* *Local repository workspace*  
*One-liner:* Quantitative financial modeling and price-prediction application for stock markets with autonomous AI trading crews: real-time market ingestion, quantitative backtesting, and risk-reviewed execution.  
*Stack:* Python · Kraken API · Custom quantitative backtesting framework  
*Role & ownership:* Solo architect/developer.

### Problem & Context

Retail equities tooling lacks transparency and fails to separate exploratory research pipelines from execution risk. StockMaster tackles the equities counterpart to Investment Matrix, delivering model-driven price prediction and backtested execution entirely locally.

### Key Implementation Details

- Implemented real-time market data ingestion pipelines interfacing with exchange APIs.
- Built quantitative backtesting frameworks to validate predictive alpha models before simulation runs.
- Maintained strict separation between exploratory model training and execution risk parameters.

---

## PyHoldem Pro / Holdem-Trainer

*Repo:* `C:\Users\milli\Holdem-Helper\Holdem-Trainer`  
*One-liner:* Quantitative Texas Hold'em training platform: concurrent CLI simulator + React dashboard with real-time EV-based coaching, Bayesian playing-style classification, and adaptive spaced-repetition drills.  
*Stack:* Python 3.13 + FastAPI/Uvicorn · React 18 + TypeScript + Vite · PostgreSQL/SQLAlchemy/Alembic · Docker · Prometheus + Grafana  
*Role & ownership:* Solo architect/developer; full lifecycle.

### Problem & Context

Solver-grade poker software is prohibitively expensive, desktop-locked, and data-hostile, while basic simulators fail to evaluate human decisions mathematically in real time. Goal: local-first privacy, automated per-decision EV grading, and drills that dynamically adapt to observed player weaknesses.

### Solution & Architectural Impact

- **Real-Time Automated Coaching:** Every human decision point is evaluated against mathematical baselines, outputting immediate EV-loss figures in big blinds to highlight costly errors.
- **Adaptive Spaced-Repetition Drills:** The training engine maps weaknesses (e.g., "Too Loose", "Poor Pot Odds") to focus areas, dynamically serving scenarios targeting historical mistakes.
- **Bayesian Playing-Style Classification:** Calculates credible intervals over session histories, backed by a complete visual analytics dashboard.

### Hard Problems → Solutions (Interview Highlights)

- **CPU-Bound Monte Carlo in ASGI Event Loops:** Calculating range-vs-range equity requires thousands of simulated deals. Running them synchronously blocked the event loop and froze WebSockets. *Solution:* Built compressed lookup tables, a fast hand-evaluation module (`fast_eval.py`), memoized identical board/hand combinations, and enforced exact enumeration when cards-to-come were low—dropping execution time from seconds down to single-digit milliseconds.
- **Scaling ICM Permutations:** Evaluating 9-handed final tables requires computing 362,880 exact permutations. *Solution:* Implemented optimized recursion in `icm_calculator.py` running at $O(2^n \cdot n)$ with memoized sub-state stack weights, using exact indexing for $n \le 6$ and dynamic programming for 7–9 hands, reducing runtimes to under 5ms.
- **Client-Side Quiz Cheating:** Inspectable React state and API payloads allowed users to bypass drill math. *Solution:* Shifted validation server-side where a `quiz_id` is issued, correct answers are cached privately in transient backend progress files, and tolerance margins are evaluated on the server before releasing feedback.

### Metrics & Engineering Guardrails

- 630+ passing tests covering core game loops, pot distributions, side pots, Bayesian credible intervals, and tournament payouts.
- Monte Carlo equity reduced from seconds to single-digit milliseconds; 9-handed ICM execution in under 5ms.
- Dockerized with full Prometheus/Grafana observability tracking API latency, game-loop performance, and ASGI worker health.

---

## Qdrant Search Console

*Repo:* `C:\Users\milli\qdrant\qdrant-search-project` · [github.com/metacoder87/qdrant-search-project](https://github.com/metacoder87/qdrant-search-project)  
*One-liner:* Document-first semantic search console: turns chunk-level vector matches into ranked *document* results with deterministic seeding and human-feedback capture for future embedding fine-tuning.  
*Stack:* Python + FastAPI · Qdrant (Docker, disk-persistent) · sentence-transformers all-MiniLM-L6-v2 · SQLite (HITL feedback) · React + TypeScript + Vite · Tailwind/ShadCN · PDF.js  
*Role & ownership:* AI Architect & Senior AI Engineer — end-to-end architecture and implementation.

### Problem & Context

Raw vector search returns scattered chunks from the same document, drowning users in machine learning noise. Furthermore, retrieval systems lacking structured feedback mechanisms cannot improve over time. Goal: Establish a human-in-the-loop validation layer between ANN output and decision-making.

### Solution & Architectural Impact

- **Intelligent Hit Aggregation:** Developed a custom grouping algorithm that aggregates chunk hits by `doc_id`, computes average similarity per document, and resorts the payload. Large documents stop dominating results, converting raw vector output into a clean, document-first experience.
- **Deterministic CI/CD Seeding:** Created `qdrant_seed.py` (DEBUG-gated) to instantly drop, recreate, and seed collections with an exact 10-point dataset spanning PDF, text, and HTML formats, ensuring reproducible test states.
- **Strict HITL Feedback Loop:** Captures result usefulness, enforcing that downvotes require a structured explanation. This builds a high-quality contextual dataset for future embedding fine-tuning and RAG optimization.
- **Safe Multi-Format Rendering:** Integrated native-feeling PDF rendering via PDF.js alongside a sanitized HTML pipeline featuring 50-word preview snippets and chunk-navigation arrows that auto-scroll to exact semantic matches.

### Metrics & Engineering Guardrails

- Chunk-to-document aggregation eliminates per-chunk result flooding.
- Deterministic 10-point seed dataset guarantees 100% reproducible test pipelines.

---

## The Learning Tree

*Repo:* `C:\Users\milli\learning_tree_ai_education\learning_tree`  
*One-liner:* Local-first K-12 family-learning app built around an explorable 3D tree where grade regions represent trunks, subject branches represent limbs, and learning objectives represent leaves whose colors reflect *evidence-based* mastery.  
*Stack:* React 18 + TypeScript + Vite · React Three Fiber / Drei / Three.js (WebGL) · FastAPI + Pydantic + SQLAlchemy + Alembic + SQLite · Ed25519 signing + AES-GCM (`cryptography`) · Ollama (optional)  
*Role & ownership:* Solo architect/developer.

### Problem & Context

K-12 learning applications either cloud-lock family data or award "mastery" for repeating a lesson five times. Goal: A zero-cloud, Windows-first family edition where mastery requires genuine evidence, curriculum manifests are cryptographically signed and versioned, and AI remains strictly out of the child-facing loop until reviewed.

### Solution & Architectural Impact

- **Evidence-Based Mastery State Machine (6 Levels):** Progress moves through *Unexplored → Started → Developing → Practiced → Proficient → Mastered*. Each level enforces explicit required evidence (instruction + assessment + scheduled reviews). Attempts, evidence, mastery events, and review schedules are stored in isolated tables, and open-ended responses are flagged for parent review rather than unmonitored exact-match grading.
- **Versioned Curriculum-Pack Contracts:** Manifests define licenses, standards, objectives, units, lessons, sources, and approvals. Published packages automatically reject missing sources, orphan graph references, duplicate stable IDs, drafts, and author self-approvals. Features deterministic hashing, coverage reporting, immutable review logs, and *Ed25519 release signing and verification*.
- **Local Family Data Security:** AES-GCM encrypted export/import routines utilizing passphrase-derived keys to protect complete progress histories.
- **Resilient Interface Design:** WebGL initialization failures gracefully fall back to a keyboard-accessible React error-boundary navigator, supporting `prefers-reduced-motion`, forced colors, and performance optimizations rendering only active grade regions and immediate neighbors.

### Metrics & Engineering Guardrails

- Seeded map contains 14 levels (Pre-K–Grade 12), 91 subject branches, and 542 leaves across 12 canonical lesson packages, with unreviewed packages explicitly marked rather than silently substituted.
- Honest status reporting API (`/api/curriculum/status`) cleanly separates installed curriculum coverage from optional local AI health.

---

## Coder Core

*Repo:* `C:\Users\milli\code_mastery\coder_core`  
*One-liner:* Local-first desktop mastery system for computer-science learning and reproducible workforce-readiness measurement: cited lessons, Docker-verified drills, and a full mock-OA assessment simulator with interviewer-led and paired-coding modes.  
*Stack:* Electron 43 · React 19 + strict TypeScript · sandboxed CommonJS preload bridge · Node SQLite API · Docker (hardened execution sandbox) · Monaco editor (bundled offline) · Ollama (optional coaching)  
*Role & ownership:* Solo architect/developer.

### Problem & Context

Coding practice tools either grade too leniently or fail to prove workforce readiness under pressure: they lack deadline enforcement, capture no telemetry on learner problem-solving behavior, and provide mastery estimates without confidence bounds. Goal: Reproducible, evidence-based workforce readiness measurement running entirely locally.

### Solution & Architectural Impact

- **Comprehensive Assessment Simulator:** Supports online-assessment, interviewer-led, and paired-coding modes sharing a single strict deadline. Captures exact foreground-dwell evidence, bounded problem navigation, and code/reasoning state recovery. Features communication/collaboration rubrics for paired modes, optional human evaluation overlays, and SQLite-backed history tracking across four fixed 70-minute mock-OA blueprints.
- **Original Content Factory at Scale:** Contains 48 prerequisite-linked skills, 48 lessons citing university and official documentation, 144 trace/semantics/complexity/debugging/pattern drills, and 48 challenge families backed by comprehensive test suites verified in Docker.
- **Honest Mastery Estimation:** Reports evidence-based estimates *with explicit confidence levels*, separating challenge mastery from retrieval mastery. Drill-only readiness is strictly capped at 35% so practice repetition cannot artificially fake assessment performance.
- **Hardened Execution Sandbox:** Docker-backed Python execution environment configured with zero network access, read-only root filesystems, non-root execution users, dropped Linux capabilities, strict CPU/RAM/PID resource limits, and forced execution timeouts alongside crash-safe timed session recovery.

### Metrics & Engineering Guardrails

- 48 skills / 48 lessons / 144 drills / 48 challenge families—all fully verified in Docker.
- Repeatable 12-route Electron accessibility audit (landmarks, ARIA references, focus traversal, Chromium a11y tree) covering isolated simulator sessions.

---

## Cross-Project Architectural Themes

1. **Local-First & Privacy-Preserving by Design:** Ollama, SQLite, PostgreSQL, and Qdrant run locally everywhere; data sovereignty is a primary design constraint across Sidekick LLM, SYNAPSE, Investment Matrix, The Learning Tree, and Coder Core.
2. **Determinism Where It Matters, Models Where They Help:** Regex kill switches filter data before embedding spend in SYNAPSE; quantitative math engines drive trading decisions with LLMs strictly off the execution path in Investment Matrix; Python code renders final dossiers rather than unvalidated models in SYNAPSE; evidence-gated state machines govern progression in The Learning Tree.
3. **Honest Reporting as a Core Feature:** Real counts and actionable failure reasons in Sidekick LLM, verified status snapshots in SYNAPSE, confidence-bounded mastery estimates with drill caps in Coder Core, and explicit "not reviewed" states in The Learning Tree.
4. **Production-Shaped Solo Systems:** Docker Compose multi-container deployments, Alembic migrations, Prometheus/Grafana/Phoenix observability stacks, extensive test suites (630+ tests in single repos), CI seeding utilities, and accessibility audits built to the standard of enterprise software.
