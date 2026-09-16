# Software Requirements Specification (SRS)
## DevLens AI — MVP (V1)

**Document Version:** 1.0
**Standard Followed:** Loosely based on IEEE 830-1998 structure
**Scope of This SRS:** V1 (MVP) only. Later versions (V2–V4) are described at a lower fidelity in `07-Roadmap-and-Sprint-Plan.md` and will each get their own SRS addendum when scheduled.

---

## 1. Introduction

### 1.1 Purpose
This document specifies the functional and non-functional requirements for **DevLens AI V1**, an engineering intelligence platform that ingests a source code repository and provides structured, AI-assisted understanding of it via natural-language Q&A, feature tracing, architecture visualization, and a health report.

### 1.2 Intended Audience
- Solo developer/founder (author and sole engineer)
- Future contributors or collaborators
- Technical reviewers/interviewers assessing the project
- Early adopter users (developers, students)

### 1.3 Scope
DevLens AI V1 allows a user to:
1. Register/log in via GitHub OAuth.
2. Import a public GitHub repository by URL.
3. Trigger processing: clone → parse → build graph → embed → analyze.
4. View a dashboard with repository summary and health score.
5. Chat with an AI assistant grounded in that repository's knowledge graph and embeddings.
6. Request a feature trace (e.g., "trace the login flow") and see an ordered path of files/functions.
7. View an auto-generated architecture diagram.
8. View a health report covering complexity, security findings, duplication, and dependency staleness.

**Out of scope for V1** (deferred to later versions, see Section 8 and the roadmap document): GitLab import, ZIP upload, team/multi-user permissions, PR review, bug investigation from logs, documentation generation, CI/CD integration, repository comparison, predictive analytics.

### 1.4 Definitions

| Term | Definition |
|---|---|
| Knowledge Graph | The set of nodes (code entities: functions, classes, files, modules) and edges (relationships: calls, imports, extends, depends-on) derived from static parsing of a repository |
| Node | A single code entity in the graph |
| Edge | A directed relationship between two nodes |
| Embedding | A vector representation of a code or documentation chunk used for semantic similarity search |
| Feature Trace | An ordered sequence of nodes representing the call/data path implementing a described feature |
| Health Score | A composite 0–100 score derived from complexity, security, duplication, and dependency metrics |
| RAG | Retrieval-Augmented Generation — retrieving relevant context (graph facts + embeddings) before generating an LLM answer |

---

## 2. Overall Description

### 2.1 Product Perspective
DevLens AI V1 is a new, standalone web application. It is not an IDE plugin and does not modify source code. It reads repositories (read-only) and produces derived artifacts (graph, embeddings, reports) stored in its own database.

### 2.2 Product Functions (Summary)
1. User authentication (GitHub OAuth)
2. Repository import and indexing pipeline
3. Code parsing via Tree-sitter (multi-language: Python, JavaScript/TypeScript to start)
4. Knowledge graph construction and storage
5. Embedding generation and semantic search
6. AI chat interface grounded in graph + embeddings
7. Feature tracing
8. Architecture diagram rendering
9. Static analysis execution and health report generation

### 2.3 User Classes and Characteristics

| User Class | Description | Technical Level |
|---|---|---|
| Registered Developer User | Primary user; imports and explores repositories | Intermediate–advanced developer |
| Anonymous Visitor | Can view marketing/landing page only | N/A |

*(Team/enterprise roles are explicitly deferred — V1 is single-user-per-repository ownership.)*

### 2.4 Operating Environment
- Frontend: modern evergreen browsers (Chrome, Firefox, Edge, Safari — last 2 major versions)
- Backend: Linux containers (Docker), deployed per `02-Tech-Stack.md`
- No mobile app; responsive web only (desktop-first, since code exploration is desktop-centric)

### 2.5 Design and Implementation Constraints
- Must run within free-tier infrastructure limits (see Tech Stack doc) for the MVP phase.
- Must support at minimum: Python and JavaScript/TypeScript repositories at launch (broadest open-source coverage for lowest initial parser investment).
- Repository size ceiling for V1: **50,000 lines of code** (larger repos may be attempted but are not guaranteed to complete within the 15-minute target).
- LLM provider must be abstracted behind an internal interface (no hard dependency on a single vendor).

### 2.6 Assumptions and Dependencies
- Assumes target repositories are **public** GitHub repositories in V1 (private repo support requires additional OAuth scopes and is deferred to V1.1/V2).
- Assumes availability of free-tier LLM inference (Groq or equivalent) for AI features; a paid fallback provider can be configured but is optional.
- Assumes users have a GitHub account for authentication.

---

## 3. Functional Requirements

Each requirement has a unique ID for traceability. Priority: **M**ust have, **S**hould have, **C**ould have (MoSCoW).

### 3.1 Authentication

| ID | Requirement | Priority |
|---|---|---|
| FR-1.1 | The system shall allow a user to sign up/log in using GitHub OAuth. | M |
| FR-1.2 | The system shall create a user record on first login, storing GitHub username, avatar, and email (if permitted). | M |
| FR-1.3 | The system shall issue a session token (JWT) valid for a configurable expiry (default 7 days). | M |
| FR-1.4 | The system shall allow a user to log out, invalidating the session. | M |
| FR-1.5 | The system shall support Google OAuth as a secondary login method. | S |

### 3.2 Repository Import & Processing

| ID | Requirement | Priority |
|---|---|---|
| FR-2.1 | The system shall allow a logged-in user to submit a public GitHub repository URL for import. | M |
| FR-2.2 | The system shall validate the URL format and reachability before starting processing. | M |
| FR-2.3 | The system shall clone the repository into a sandboxed, size-limited workspace. | M |
| FR-2.4 | The system shall reject repositories exceeding a configurable size limit (default: 500MB or 50,000 LOC) with a clear error message. | M |
| FR-2.5 | The system shall detect the primary language(s) of the repository by file extension and content heuristics. | M |
| FR-2.6 | The system shall show real-time (or near-real-time, polling-based) indexing progress to the user (e.g., "Cloning" → "Parsing" → "Building graph" → "Generating embeddings" → "Running analysis" → "Done"). | M |
| FR-2.7 | The system shall store repository metadata: name, owner, default branch, size, primary language, last indexed timestamp. | M |
| FR-2.8 | The system shall allow a user to re-index (refresh) a previously imported repository. | S |
| FR-2.9 | The system shall allow a user to delete an imported repository and all derived data. | M |

### 3.3 Code Parsing

| ID | Requirement | Priority |
|---|---|---|
| FR-3.1 | The system shall parse supported source files using Tree-sitter to extract: functions, classes, methods, imports, and top-level variables. | M |
| FR-3.2 | The system shall support Python and JavaScript/TypeScript in V1. | M |
| FR-3.3 | The system shall record, for each extracted entity, its file path, line range, and containing scope (e.g., class → method). | M |
| FR-3.4 | The system shall skip binary files, vendored/third-party directories (e.g., `node_modules`, `venv`, `vendor`), and files exceeding a configurable size threshold. | M |
| FR-3.5 | The system shall gracefully skip files that fail to parse (syntax errors, unsupported dialects) and log the failure without halting the overall pipeline. | M |

### 3.4 Knowledge Graph

| ID | Requirement | Priority |
|---|---|---|
| FR-4.1 | The system shall create a graph node for every extracted function, class, and file. | M |
| FR-4.2 | The system shall create edges for: `imports`, `calls`, `extends`, `implements`, and `defines` (file → function/class) relationships, wherever staticaly resolvable. | M |
| FR-4.3 | The system shall persist the graph in a queryable store supporting multi-hop traversal (see Tech Stack doc, Section 3.1). | M |
| FR-4.4 | The system shall expose an internal query API to retrieve: a node's direct neighbors, the shortest path between two nodes, and all nodes within N hops of a given node. | M |

### 3.5 Semantic Search / Embeddings

| ID | Requirement | Priority |
|---|---|---|
| FR-5.1 | The system shall generate vector embeddings for each function/class (using its signature + docstring/leading comment + body summary) and for README/Markdown documentation chunks. | M |
| FR-5.2 | The system shall store embeddings alongside a reference to the originating graph node or document chunk. | M |
| FR-5.3 | The system shall support top-K nearest-neighbor semantic search over stored embeddings given a natural-language query. | M |

### 3.6 AI Chat / Q&A

| ID | Requirement | Priority |
|---|---|---|
| FR-6.1 | The system shall provide a chat interface scoped to a single imported repository. | M |
| FR-6.2 | For each user question, the system shall retrieve relevant context using both semantic search (embeddings) and graph traversal (structured facts) before generating an answer. | M |
| FR-6.3 | The system shall include, in every AI answer, references to the specific files/functions the answer is grounded in (clickable citations). | M |
| FR-6.4 | The system shall persist chat history per repository per user. | S |
| FR-6.5 | The system shall clearly indicate when a question cannot be answered with sufficient confidence, rather than fabricating an answer. | M |

### 3.7 Feature Tracing

| ID | Requirement | Priority |
|---|---|---|
| FR-7.1 | The system shall allow a user to submit a natural-language description of a feature (e.g., "login flow") to trace. | M |
| FR-7.2 | The system shall use semantic search to identify likely entry-point nodes, then use graph traversal to construct an ordered path of related nodes (e.g., controller → service → repository → database). | M |
| FR-7.3 | The system shall display the trace as an ordered, clickable list and as a visual path diagram. | M |
| FR-7.4 | The system shall indicate confidence/completeness of the trace (e.g., "5 of an estimated 6 steps found"). | S |

### 3.8 Architecture Visualization

| ID | Requirement | Priority |
|---|---|---|
| FR-8.1 | The system shall generate a component/module-level diagram derived from the knowledge graph (not a static template). | M |
| FR-8.2 | The system shall render the diagram client-side (e.g., via Mermaid.js or an equivalent graph-rendering library). | M |
| FR-8.3 | The system shall allow the user to click a node in the diagram to view its details (file, functions, relationships). | S |
| FR-8.4 | The system shall allow zoom/pan interaction on large diagrams. | S |

### 3.9 Repository Health Report

| ID | Requirement | Priority |
|---|---|---|
| FR-9.1 | The system shall run static analysis tools appropriate to the detected language(s) (Ruff + Bandit for Python; ESLint for JS/TS). | M |
| FR-9.2 | The system shall compute and display: cyclomatic complexity distribution, duplicate code percentage, count/severity of security findings, and count of outdated dependencies. | M |
| FR-9.3 | The system shall compute a composite Health Score (0–100) from the above metrics using a documented, transparent formula (see `04-System-Architecture-HLD.md`, Section 6). | M |
| FR-9.4 | The system shall list the top N issues by severity/impact with file/line references. | M |

### 3.10 Dashboard

| ID | Requirement | Priority |
|---|---|---|
| FR-10.1 | The system shall display, per repository, a summary card showing: name, language(s), size, health score, last indexed time. | M |
| FR-10.2 | The system shall list all repositories imported by the current user. | M |

---

## 4. Non-Functional Requirements

| ID | Category | Requirement |
|---|---|---|
| NFR-1 | Performance | A repository up to 50,000 LOC shall complete full indexing (clone → parse → graph → embeddings → analysis) within 15 minutes on the reference deployment (Oracle Always Free VM, 4 OCPU/24GB RAM). |
| NFR-2 | Performance | AI chat responses shall return a first token/response within 8 seconds under normal load (excluding cold-start of the LLM provider). |
| NFR-3 | Scalability | The processing pipeline shall run as queued background jobs (Celery/Arq) so that concurrent repository imports do not block the API. |
| NFR-4 | Reliability | If any single pipeline stage fails (e.g., one file fails to parse), the overall job shall continue and report partial results rather than failing entirely. |
| NFR-5 | Security | Cloned repository code shall be processed in an isolated workspace/container with no network egress during parsing, to prevent malicious code execution risk. |
| NFR-6 | Security | All secrets (OAuth tokens, API keys) shall be stored in environment variables / secret managers, never committed to source control or exposed to the frontend. |
| NFR-7 | Security | User sessions shall use signed, expiring JWTs; passwords are never stored directly (OAuth-only in V1). |
| NFR-8 | Usability | A first-time user shall be able to import a repository and reach the dashboard without reading documentation (self-evident UI). |
| NFR-9 | Maintainability | The LLM provider integration shall be abstracted behind a single interface to allow swapping providers (Groq ↔ Claude ↔ OpenAI) without touching business logic. |
| NFR-10 | Observability | All pipeline stage transitions, failures, and durations shall be logged and queryable for debugging. |
| NFR-11 | Portability | The entire stack shall run via Docker Compose on a single VM for local development and small-scale production. |
| NFR-12 | Cost | The MVP shall operate within free-tier limits of all chosen providers under expected early-stage load (see `02-Tech-Stack.md`, Section 5). |
| NFR-13 | Data Privacy | A user shall be able to fully delete a repository and all derived data (graph, embeddings, reports, chat history) on request. |

---

## 5. External Interface Requirements

### 5.1 User Interfaces
- Landing page (public)
- Auth pages (GitHub/Google OAuth redirect flows)
- Repository import form
- Dashboard (repository list + summary cards)
- Repository detail view with tabs: **Chat**, **Architecture**, **Trace**, **Health Report**

### 5.2 Software Interfaces
- GitHub REST/GraphQL API (repository metadata, cloning via Git protocol)
- LLM provider API (Groq/Claude/OpenAI — abstracted)
- Embedding model (local inference or hosted API — abstracted)

### 5.3 Communication Interfaces
- HTTPS for all client-server communication
- WebSocket or polling for indexing progress updates (polling acceptable for V1 to reduce complexity)

---

## 6. Data Requirements (Summary — Full Schema in `05-Database-Design.md`)

Core entities: `users`, `repositories`, `files`, `graph_nodes`, `graph_edges`, `embeddings`, `static_analysis_results`, `health_reports`, `chat_conversations`, `chat_messages`.

---

## 7. Acceptance Criteria (Definition of Done for V1)

The MVP is considered complete and demo-ready when all **Must (M)** priority requirements in Section 3 and all NFRs in Section 4 are met, verified against the MVP Success Criteria in `01-Project-Charter-and-Vision.md`, Section 6, using at least three real public repositories of varying size (small ~2k LOC, medium ~15k LOC, large ~45k LOC) as test cases.

---

## 8. Deferred Requirements (V2+)

Explicitly out of scope for this SRS, tracked for future SRS addenda:
- GitLab import, ZIP upload
- Private repository support
- Team/multi-user collaboration and permissions
- Bug investigation from logs/stack traces
- Documentation auto-generation
- Pull request review agent
- CI/CD (GitHub App) integration
- Repository comparison
- Predictive analytics / regression prediction
