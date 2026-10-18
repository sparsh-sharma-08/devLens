# DevLens AI — Final Status & Handover Record

**Date:** September 30, 2026  
**Status:** Feature Complete for V1 Core Scope / Paused for Next Phase

---

## 1. What Is Fully Built and Validated

The core 7-stage engine, analytical pipeline, scoring algorithms, and full-stack interfaces are built and verified across multiple production Python codebases:

* **Engine & Pipeline Architecture (`backend/app/workers/pipeline.py`):**
  * **Scope & Language:** V1 is engineered and validated exclusively for **Python** codebases. Python AST parsing is powered by Tree-sitter Python, and static analysis is driven by Ruff and Bandit. (JS/TS grammars and ESLint dependencies in pyproject/Docker are deferred stubs for V2).
  * **Accurate 7-Stage Celery Pipeline:**
    * **Stage 1 — `cloning` (5%):** Git clone to ephemeral container workspace, branch resolution, and size accounting.
    * **Stage 2 — `detecting_language` (15%):** Repository inventory, language breakdown, file filtering (ignoring `.git`, virtualenvs, vendor dirs), and accurate LOC counting.
    * **Stage 3 — `parsing` (30%):** Tree-sitter AST parsing extracting functions, methods, classes, module definitions, and imports into typed `GraphNode` records.
    * **Stage 4 — `building_graph` (50%):** Relationship resolution creating `GraphEdge` records (`imports`, `calls`, `extends`, `depends_on`) and registering external package nodes.
    * **Stage 5 — `embedding` (70%):** Semantic chunking and vector embedding generation (`sentence-transformers/all-MiniLM-L6-v2`) stored into PostgreSQL via `pgvector`.
    * **Stage 6 — `static_analysis` (85%):** Multi-linter analysis running Ruff and Bandit concurrently with deduplication across overlapping rules (e.g. S-rules vs B-rules).
    * **Stage 7 — `report_generation` (95% -> 100%):** Mathematical health scoring across 4 pillars, score ceiling enforcement, persistence to `health_reports`, atomic job completion, and disk workspace cleanup.

* **Score Ceiling Hardening & Precision Audit:**
  * **Exclusions Applied:** Removed purely syntactic pattern matchers prone to false positives:
    * `B703` (flags `mark_safe` on exception/template strings safe-by-construction).
    * `B608` / `S608` (flags SQL keyword heuristics in exception prose and non-executing strings).
    * `B601`, `B604`, `B605` (shell execution helpers that cannot trace argument sanitization/`shlex.quote`).
    * `B504` (rated LOW severity omission by Bandit).
  * **Dynamic Injection Hardening:** Hardened `B602` / `S602` (`shell=True`) to require verified `critical` or `high` severity dynamic arguments; safe static string literals (rated `LOW` by Bandit) do not cap scores.
  * **Retained Strict Ceilings:** Genuine structural vulnerabilities are strictly enforced: `B602`/`S602` (dynamic shell injection, cap 70), `B501` (`verify=False`, cap 85), `B502` (broken SSL constants, cap 85), `B503` (broken SSL defaults, cap 85), `B506`/`S506` (unsafe `yaml.load`, cap 85), and `B612` (logging listen socket without verify, cap 85).
  * **Benchmark Repositories:**
    * **Django (456,522 LOC, 2,932 files):** Wall time 57.1s, Raw Security 96.8, Overall Health **93 / 100**, Ceiling: **CLEARED**.
    * **Scrapy (78,227 LOC, 505 files):** Wall time 9.5s, Raw Security 96.5, Overall Health **85 / 100**, capped at 85 by genuine `B503` (`SSLv23_METHOD`) finding.
    * **HTTPX (14,376 LOC, 60 files):** Reconciled Overall Health **94 / 100**, Ceiling: **CLEARED**.

* **Real Engine Data in API Endpoints (`backend/app/api/repos.py`):**
  * **`/architecture`:** Migrated from stub-era directory splitting to query real `GraphEdge` records (`imports`, `calls`, `extends`). Clusters modular packages to keep Mermaid diagrams legible while preserving the `{ components, relationships }` frontend contract.
  * **`/trace`:** Migrated from keyword heuristics to pgvector cosine similarity for entry-point discovery followed by real multi-hop call-graph traversal over `graph_edges` with inferred lifecycle roles (`entry_point`, `handler`, `business_logic`, `data_access`, `utility`).
  * **`/health`:** Returns the 4-pillar scores, ceiling status, and top issues. (Clarification: `duplication_score` and `code_quality_score` are identical aliases pointing to the same underlying defect-density score stored in the legacy database column `duplication_score`).

---

## 2. End-to-End System Integration & Reconciled Baseline

* **Full Live Chain Tested:** User registration (`POST /v1/auth/signup`) -> Repo submission (`POST /v1/repositories`) -> Celery worker pipeline processing -> Real-time status polling (`GET /v1/jobs/{id}`) -> Dashboard verification across Health, Architecture, Trace, and Chat.
* **HTTPX Reconciled Baseline:**
  * **Security Score:** **97** (Raw score: 96.91 across 65 retained findings: 56 low, 8 medium, 1 high, 0 critical).
  * **Complexity Score:** **99** (107 classes, 5 large; 1,134 functions, 21 long).
  * **Code Quality / Defect Density:** **94** (Raw score: 94.02; exposed under both `code_quality_score` and legacy column alias `duplication_score`).
  * **Dependency Score:** **77** (Reconciled from 72: accurately accounts for 994 inserted edges, 66 external nodes, and 3,446 unresolved dynamic calls).
  * **Overall Composite Health:** **94 / 100** (`0.35 * 96.91 + 0.30 * 94.02 + 0.20 * 99 + 0.15 * 77.3 = 93.53 -> 94`).
  * **Ceiling Status:** **`{"triggered": false, "level": null}`** (Clean, ceiling cleared).
* **Explanation of Score Shift vs. Early Standalone Scripts:**
  * The earlier standalone script (`validate_scale_stress.py`) reported a dependency score of ~96.5 and overall 96 because it applied a hardcoded `0.1` dampening factor to import null rates and mocked external node counts (`min(file_count * 1.5, 60)`).
  * In the real engine, external nodes are queried live from PostgreSQL (`66` nodes), and uncalibrated AST ambiguity across dynamic Python calls (`3,446 / 4,440`) yields a real dependency score of 77. The external node fix itself only adjusted the score by 0.3 points (66 nodes vs 60 nodes).

---

## 3. Bugs Discovered & Resolved During Live E2E Run

1. **External Node Foreign Key Violation (`pipeline.py`):**
   * *Symptom:* `build_graph_task` crashed with `ForeignKeyViolationError` on constraint `graph_edges_target_node_id_fkey`.
   * *Root Cause:* `get_or_create_external_node()` generated synthetic external nodes and appended them to an in-memory list, but never attached them to the active SQLAlchemy session (`db.add()`) when discovered mid-traversal. When `pending_edges` flushed, target foreign keys did not exist in `graph_nodes`.
   * *Fix:* Added `db.add(ext_node)` immediately inside `get_or_create_external_node()` and cleared initial module nodes after the first flush, ensuring external nodes are committed before dependent edges.
2. **`JobStatusOut` Attribute Mapping (`jobs.py`):**
   * *Symptom:* Polling `GET /v1/jobs/{id}` failed with HTTP 500 (`ValidationError: job_id field required`).
   * *Root Cause:* `IndexingJob` ORM primary key is `id`, but Pydantic schema expects `job_id`. Calling `JobStatusOut.model_validate(job)` failed attribute lookup.
   * *Fix:* Explicitly instantiated `JobStatusOut` mapping `job_id=job.id`.
3. **`edges_inserted` Key Omission in `build_graph_task` (`pipeline.py`):**
   * *Symptom:* `dependency_score` defaulted to maximum 25-point ambiguity penalty, reporting `edges_inserted: 0`.
   * *Root Cause:* `build_graph_task` returned `edges_resolved` and `edges_external`, while Stage 7 looked up `edges_inserted`.
   * *Fix:* Returned `edges_inserted = edges_resolved + edges_external` in `build_graph_task` and added a fallback in `_generate_health_report`.

---

## 4. Known Gaps & Unvalidated Risks

1. **Celery Worker Concurrency & Memory Footprint:**
   * In-process PyTorch and sentence-transformers run inside Celery workers. Multiple parallel multi-hundred-thousand LOC indexing jobs will require worker memory recycling (`--max-tasks-per-child=10`) or moving embeddings to an isolated sidecar service.
2. **Docker Build Dependency Size (CPU vs CUDA):**
   * The default Linux pip wheel for `torch>=2.3.0` downloads gigabytes of NVIDIA/CUDA runtime wheels during container build. Standardizing on `--extra-index-url https://download.pytorch.org/whl/cpu` in `backend/Dockerfile` will shrink the image build from ~3GB down to ~200MB.
3. **LOC Pre-Flight Cap:**
   * Repositories up to ~500k LOC (Django) process within ~57 seconds. Repositories over 1M LOC risk AST memory limits or query timeouts. An early size guard should be added before multi-tenant public launch.
4. **Graph Pruning for Large Codebases:**
   * `/architecture` currently caps inter-component queries at `limit(2000)`. Highly dense codebases would benefit from degree-centrality or PageRank pruning.

---

## 5. Logical Next Steps (When Resuming)

1. **Optimize Dockerfile:** Update `backend/Dockerfile` to install CPU-only PyTorch wheels to allow instant CI/CD builds.
2. **Deploy to Staging Environment:** Spin up managed PostgreSQL (`pgvector`) and Redis instances, and deploy API and Celery workers on ECS / Kubernetes.
3. **Playwright E2E Test Suite:** Implement headless browser tests automating user signup, repo import, and four-tab UI assertions.
