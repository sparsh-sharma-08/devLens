# DevLens AI — Current Status, Architecture Decisions & Deep-Down System Scan

> **Generated on:** September 7, 2026  
> **Project Goal:** *"Understand any codebase in 15 minutes."*  
> **Repository:** `DevLens` (Full-stack AI-powered Engineering Intelligence Platform)

---

## 1. Executive Summary: Plumbing vs Core Intelligence Reality

DevLens AI is designed to help engineers understand complex codebases through **Abstract Syntax Tree (AST) parsing**, an **in-memory/relational Knowledge Graph**, **vector embeddings with pgvector**, and **grounded LLM inference (RAG with citations)**.

### The Real Picture: Platform Shell vs Intelligence Engine

To be completely clear-eyed about the current state of the codebase:
- **Platform Infrastructure, Auth, Database Schema & UI Shell: ~95% COMPLETE**
  The plumbing is genuinely solid: PostgreSQL with pgvector, 11 relational models with cascade relationships, multi-provider JWT authentication (GitHub, Google, Email/Password), Celery task chaining, Redis job queues, and a polished Next.js 16 dark-mode UI with live polling and interactive tabs.
- **Core Intelligence Engine (AST, Graph, Embeddings, Static Analysis): ~15% COMPLETE (STUBS)**
  The four analytical features visible in the UI (Chat RAG, Architecture Graph, Feature Trace, Health Report) are currently operating on **keyword-matching heuristics and folder groupings** because the four foundational worker tasks (Sprints 3–6) are currently pass-through stubs.

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                PLATFORM LAYER VS ENGINE REALITY                                  │
├──────────────────────────┬─────────────┬───────────┬─────────────────────────────────────────────┤
│ Component / Feature      │ UI / API    │ Worker /  │ Reality Underneath                          │
│                          │ Shell Status│ Engine    │                                             │
├──────────────────────────┼─────────────┼───────────┼─────────────────────────────────────────────┤
│ 1. Foundations & Auth    │ 100% DONE   │ 100% DONE │ Real JWTs, bcrypt, GitHub & Google OAuth.   │
│ 2. Repo Clone & Ingest   │ 100% DONE   │ 100% DONE │ Real Git shallow clone, 50k LOC limit.      │
│ 3. Tree-sitter Parser    │ 100% Wire   │ 0% STUB   │ Grammars installed; worker does no parsing. │
│ 4. Knowledge Graph       │ 100% Schema │ 0% STUB   │ Schema exists; build_graph_task is a stub.  │
│ 5. pgvector Embeddings   │ 100% Schema │ 0% STUB   │ pgvector ready; embed_task is a stub.       │
│ 6. Static Analysis       │ 100% Schema │ 0% STUB   │ Gauges rendered; Ruff/Bandit not executing. │
│ 7. Grounded AI Chat      │ 95% UI/API  │ Keyword   │ RAG searches raw keywords, not AST vectors. │
│ 8. Architecture Graph    │ 90% UI/API  │ Heuristic │ Groups by top folder, not graph edges.      │
│ 9. Feature Tracing       │ 90% UI/API  │ Heuristic │ Keyword scoring; no call-graph traversal.   │
│ 10. Health Score Report  │ 90% UI/API  │ Mock/Empty│ UI ready; static analysis results empty.    │
└──────────────────────────┴─────────────┴───────────┴─────────────────────────────────────────────┘
```

---

## 2. System Architecture & Tech Stack Decisions

```
                           ┌──────────────────────────────────────────────────────────┐
                           │                     Next.js Frontend                     │
                           │   (App Router, React 19, TypeScript, Lucide, Mermaid)    │
                           └────────────────────────────┬─────────────────────────────┘
                                                        │ HTTP REST (JWT Bearer)
                                                        ▼
                           ┌──────────────────────────────────────────────────────────┐
                           │                    Nginx Reverse Proxy                   │
                           │                     (Port 80 -> 8000)                    │
                           └────────────────────────────┬─────────────────────────────┘
                                                        │
                                                        ▼
                           ┌──────────────────────────────────────────────────────────┐
                           │                   FastAPI Backend API                    │
                           │           (Async SQLAlchemy, Pydantic, Jose)             │
                           └──────────────┬─────────────────────────────┬─────────────┘
                                          │                             │
                     Async Database Calls │                             │ Enqueue Tasks
                                          ▼                             ▼
┌──────────────────────────────────────────────────────────┐  ┌─────────────────────────────────┐
│              PostgreSQL 15 + pgvector                     │  │             Redis 7             │
│  - 11 relational tables                                  │  │   - Celery Broker (db 0)        │
│  - HNSW vector index (384 dims)                          │  │   - Result Backend (db 1)       │
│  - pgcrypto & UUID primary keys                          │  └────────────────┬────────────────┘
└──────────────────────────────────────────────────────────┘                   │
                                                                               ▼
                                                              ┌─────────────────────────────────┐
                                                              │          Celery Worker          │
                                                              │  - Git shallow clone   [REAL]   │
                                                              │  - Language detection  [REAL]   │
                                                              │  - Tree-sitter parser  [STUB]   │
                                                              │  - Graph builder       [STUB]   │
                                                              │  - Sentence embeddings [STUB]   │
                                                              │  - Ruff/Bandit/ESLint  [STUB]   │
                                                              │  - Health score gen    [STUB]   │
                                                              └─────────────────────────────────┘
```

### Key Architectural Decisions Made

1. **Monolithic Relational + Vector Storage (PostgreSQL 15 + pgvector)**:
   - **Decision:** Use PostgreSQL for relational entities (`users`, `repositories`, `graph_nodes`, `graph_edges`) and vector embeddings (`embeddings` with 384 dimensions) instead of managing a separate vector database.
   - **Rationale:** Zero hosting cost, eliminates dual-write synchronization bugs, and supports atomic cascade deletes.

2. **Asynchronous Background Processing (Celery + Redis)**:
   - **Decision:** All repository processing stages run asynchronously through Celery task chains (`run_pipeline`).
   - **Rationale:** Repository analysis is long-running. The API immediately responds with `202 Accepted` and a `job_id`, which the frontend polls via `/v1/jobs/{job_id}`.

3. **Multi-Provider Authentication**:
   - **Decision:** Support GitHub OAuth, Google OAuth, and Email/Password with bcrypt under a unified JWT session.

4. **Grounded LLM Chat with Citation Extraction**:
   - **Decision:** Enforce that LLM responses return exact file paths and line ranges from `graph_nodes`.

---

## 3. Database Schema Breakdown (11 Relational Tables)

All models are defined in [backend/app/models.py](file:///Users/sparsh/Documents/Coding/DevLens/backend/app/models.py):

```
+----------------------------------------------------------------------------------------------------+
|                                         DATABASE SCHEMA                                            |
+----------------------------------------------------------------------------------------------------+

  ┌───────────────┐        1:N        ┌───────────────────────┐        1:N        ┌────────────────┐
  │     users     ├──────────────────►│     repositories      ├──────────────────►│ indexing_jobs  │
  └───────┬───────┘                   └───────────┬───────────┘                   └────────────────┘
          │                                       │
          │ 1:N                                   ├──────────────────────────────►┌────────────────┐
          │                                       │ 1:N                           │     files      │
          ▼                                       │                               └───────┬────────┘
  ┌───────────────────────┐                       ├──────────────────────────────┐        │ 1:N
  │  chat_conversations   │                       │ 1:N                          │        ▼
  └───────┬───────────────┘                       ▼                              ▼ ┌───────────────┐
          │                           ┌───────────────────────┐                 ──►│  graph_nodes  │
          │ 1:N                       │ static_analysis_res.  │                    └───┬───────┬───┘
          ▼                           └───────────────────────┘                        │1:N    │1:N
  ┌───────────────────────┐                       │                                    ▼       ▼
  │     chat_messages     │                       │ 1:N                        ┌────────┐ ┌────────┐
  └───────────────────────┘                       ▼                            │ edges  │ │ embed. │
                                      ┌───────────────────────┐                │ (src/  │ │ (384d  │
                                      │    health_reports     │                │  tgt)  │ │ vector)│
                                      └───────────────────────┘                └────────┘ └────────┘
```

1. **`users`**: UUID PK, GitHub ID, Google ID, email, username, bcrypt `password_hash`, timestamps.
2. **`repositories`**: UUID PK, `owner_user_id` (FK), names, source URL, language stats (JSONB), `status`, `health_score`.
3. **`indexing_jobs`**: Job stages (`pending` → `cloning` → `detecting_language` → `parsing` → `building_graph` → `embedding` → `static_analysis` → `report_generation` → `done`/`failed`), progress percentage (0–100).
4. **`files`**: Relative path, language, lines of code (`loc`), git blob `sha`.
5. **`graph_nodes`**: Code entities (`file`, `class`, `function`, `method`, `module`, `route`), qualified names, line ranges, signatures, docstrings.
6. **`graph_edges`**: Directed relationships (`calls`, `imports`, `extends`, `implements`, `defines`, `depends_on`), confidence score (0.0–1.0).
7. **`embeddings`**: pgvector `Vector(384)` matching `sentence-transformers/all-MiniLM-L6-v2`.
8. **`static_analysis_results`**: Normalized findings from Ruff, Bandit, and ESLint (severity, rule ID, message, line).
9. **`health_reports`**: Category scores (Complexity, Security, Duplication, Dependencies) and overall score.
10. **`chat_conversations`**: Conversation threads per repo and user.
11. **`chat_messages`**: Chat messages with structured citation JSON linking to code nodes.

---

## 4. Component-by-Component Scan

### 4.1 Backend API Layer ([backend/app/api/](file:///Users/sparsh/Documents/Coding/DevLens/backend/app/api/))
- **`repos.py`** (481 lines): Handles repository import, listing, details, cascade deletion, reindexing, health retrieval, architecture summaries, and search. *(Verified: Duplicate block previously at lines 482–698 has been cleaned up)*.
- **`chat.py`** (321 lines): Manages conversation sessions, prompt construction with code context, Groq LLM invocation (`llama-3.1-70b-versatile`), and citation packaging.
- **`auth.py`** (417 lines): Triple auth provider (GitHub OAuth, Google OAuth, Email/Password), JWT access & refresh token lifecycle.
- **`jobs.py`** (43 lines): Stage progress polling endpoint.

### 4.2 Background Worker Pipeline ([backend/app/workers/](file:///Users/sparsh/Documents/Coding/DevLens/backend/app/workers/))
- **`pipeline.py`** (337 lines):
  - `clone_task`: **REAL** — Executes Git shallow clone, counts LOC, validates against 50k LOC limit.
  - `detect_language_task`: **REAL** — Analyzes file extension distribution and persists primary language.
  - `parse_task`: **STUB** — Does not extract AST nodes.
  - `build_graph_task`: **STUB** — Does not compute or insert graph edges.
  - `embed_task`: **STUB** — Does not generate sentence-transformers embeddings.
  - `static_analysis_task`: **STUB** — Does not run Ruff/Bandit/ESLint.
  - `report_generation_task`: **STUB** — Does not compute health score.

### 4.3 Frontend Next.js Application ([frontend/src/](file:///Users/sparsh/Documents/Coding/DevLens/frontend/src/))
- **`src/lib/api.ts`**: Centralized HTTP client with automatic Bearer token injection and seamless 401 token refresh.
- **`src/app/page.tsx` & `src/app/auth/page.tsx`**: Landing page and multi-tab authentication UI.
- **`src/app/dashboard/page.tsx`**: Repository overview, live indexing job polling, import modal, delete/reindex actions.
- **`src/app/repos/[id]/page.tsx` & Tabs**:
  - `ChatTab.tsx`: Markdown chat, citation badges, starter suggestion prompts.
  - `ArchitectureTab.tsx`: Dynamic Mermaid.js component graph.
  - `TraceTab.tsx`: Execution path cards with role badges and confidence meters.
  - `HealthTab.tsx`: SVG circular score gauges and categorized issue list.

---

## 5. Prioritized Execution Plan (The Core Engine Roadmap)

To transform the project from a well-crafted UI shell into a genuine code understanding platform, development must follow this strict dependency order:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                CORE ENGINE BUILD ORDER                                 │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ Step 1: Python Tree-sitter Parser (Sprint 3) ──► Unblocks AST nodes in `graph_nodes`   │
│                                │                                                       │
│                                ▼                                                       │
│ Step 2: Graph Edge Resolution (Sprint 4)    ──► Turns Architecture & Trace tabs real   │
│                                │                                                       │
│                                ▼                                                       │
│ Step 3: pgvector Embeddings (Sprint 5)      ──► Makes Chat citations grounded & true   │
│                                │                                                       │
│                                ▼                                                       │
│ Step 4: Static Analysis Runners (Sprint 6)  ──► Powers Health gauges with real metrics │
│                                │                                                       │
│                                ▼                                                       │
│ Step 5: Hardening & Deployment (Sprint 11–12)                                          │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### 1. Step 1: Tree-sitter AST Parser (Sprint 3) — **HIGHEST PRIORITY**
- **Action**: Implement `parse_task` in `pipeline.py` using `tree-sitter-python`.
- **Target**: Walk all `.py` files, extract `FunctionDef`, `ClassDef`, `AsyncFunctionDef`, docstrings, signatures, and `Import` / `ImportFrom` statements, and populate the `files` and `graph_nodes` tables.
- **Why First**: Every subsequent intelligence layer depends on real AST nodes existing in the database.

### 2. Step 2: Knowledge Graph Edge Resolution (Sprint 4)
- **Action**: Implement `build_graph_task` to resolve imports and intra-file/inter-file function calls.
- **Target**: Insert directed relationships (`imports`, `calls`, `defines`, `extends`) into `graph_edges`.
- **Impact**: Upgrades `/architecture` from directory groupings to real dependency graphs, and `/trace` to real call-graph path traversals.

### 3. Step 3: pgvector Embeddings & Semantic Search (Sprint 5)
- **Action**: Implement `embed_task` using `sentence-transformers/all-MiniLM-L6-v2`.
- **Target**: Compute 384-dimensional vectors for every AST node's signature + docstring, insert into `embeddings`, and upgrade `/search` to use pgvector cosine distance `<=>`.
- **Impact**: Provides trustworthy, semantic retrieval for AI Chat context assembly.

### 4. Step 4: Static Analysis Subprocess Engine (Sprint 6)
- **Action**: Implement `static_analysis_task` to run Ruff and Bandit in isolated workspaces.
- **Target**: Parse JSON outputs, populate `static_analysis_results`, and compute real Health Scores via the HLD formula.

### 5. Step 5: Hardening & Production Deployment (Sprint 11–12)
- **Action**: Run end-to-end tests against real reference repositories and finalize production container orchestration.

---

## 6. How to Run Locally

```bash
# 1. Environment configuration
cp .env.example .env

# 2. Start PostgreSQL, Redis, FastAPI, Celery Worker, Nginx
docker compose up --build -d

# 3. Start Next.js frontend
cd frontend
npm install
npm run dev
```

---

## 7. Verification & Service Map

| Service | Port / URL | Status | Description |
|---|---|---|---|
| **Frontend Web App** | `http://localhost:3000` | Active | Next.js 16 App Router UI |
| **Backend REST API** | `http://localhost:8000` | Active | FastAPI server |
| **Swagger Interactive Docs** | `http://localhost:8000/docs` | Active | Full OpenAPI endpoint testing |
| **Health Check** | `http://localhost:8000/health` | Active | API liveness probe |
| **Nginx Gateway** | `http://localhost:80` | Active | Reverse proxy |
| **PostgreSQL + pgvector** | `localhost:5432` | Active | Relational DB + vector search |
| **Redis** | `localhost:6379` | Active | Celery queue broker & cache |
