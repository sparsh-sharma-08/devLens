<div align="center">

# DevLens AI

<p align="center">
  <strong>Understand any codebase in 15 minutes.</strong>
</p>

<p align="center">
  An open-source repository comprehension engine that parses codebases into an Engineering Knowledge Graph, traces execution paths end-to-end, visualizes module architecture, and delivers AI answers strictly grounded in actual code structure with exact line citations.
</p>

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.12+](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Next.js: 14+](https://img.shields.io/badge/Next.js-14%2B-black?logo=next.js&logoColor=white)](https://nextjs.org/)
[![PostgreSQL: 15 + pgvector](https://img.shields.io/badge/PostgreSQL-15%20%2B%20pgvector-336791?logo=postgresql&logoColor=white)](https://github.com/pgvector/pgvector)
[![Tree--sitter](https://img.shields.io/badge/Parser-Tree--sitter-1e293b?logo=tree-sitter&logoColor=white)](https://tree-sitter.github.io/tree-sitter/)
[![Docker Compose](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)

[**Explore Documentation**](00-README-Index.md) &bull;
[**Quick Start**](#-getting-started) &bull;
[**Architecture**](#-architecture--workflows) &bull;
[**API Reference**](06-API-Specification.md) &bull;
[**Roadmap**](#-roadmap)

<br />

<img src="docs/screenshots/hero-banner.jpg" alt="DevLens AI — Understand any codebase in 15 minutes" width="100%" />

</div>

---

## 📑 Table of Contents

- [The Problem DevLens Solves](#-the-problem-devlens-solves)
- [Product Overview](#-product-overview)
- [Screenshots & Visual Preview](#-screenshots--visual-preview)
- [Key Features](#-key-features)
- [System Architecture & Workflows](#-system-architecture--workflows)
- [Technology Stack](#-technology-stack)
- [Getting Started](#-getting-started)
- [Usage Guide](#-usage-guide)
- [Repository Structure](#-repository-structure)
- [Configuration Reference](#-configuration-reference)
- [Roadmap](#-roadmap)
- [Contributing](#-contributing)
- [License & Acknowledgements](#-license--acknowledgements)

---

## 💡 The Problem DevLens Solves

Modern production codebases span tens of thousands to millions of lines of code across hundreds of files. When joining a new team or reviewing an unfamiliar repository, developers face significant roadblocks:

* **Lengthy Onboarding**: Engineers spend weeks reading disjointed files and chasing call stacks just to build a mental model.
* **The "Chunk and Embed" Trap**: Most AI assistants slice files into arbitrary 500-token chunks and feed them to an LLM. Without structural context, they hallucinate non-existent functions, misidentify call targets, and miss architectural dependencies.
* **Code Generation vs. Code Comprehension**: Existing tools are built to *write* code, not to *explain* systems. They have no persistent structural model of how interfaces, callers, and database queries interconnect.
* **Stale Documentation**: Architecture documents rot within weeks of release, leaving engineers without an accurate system blueprint.

**DevLens AI eliminates this guesswork.** Instead of treating code like prose, DevLens builds a persistent, queryable **Engineering Knowledge Graph** directly from Abstract Syntax Trees (ASTs). Every AI answer, feature trace, and architecture diagram is deterministically backed by real code entities and exact file/line citations.

---

## 🚀 Product Overview

DevLens AI is a self-hostable developer tool designed for **engineers, tech leads, and open-source contributors** who need to ramp up on complex repositories rapidly.

```
       Paste GitHub URL               7-Stage Asynchronous Pipeline                 Interactive Exploration
┌─────────────────────────────┐        ┌───────────────────────────────┐        ┌─────────────────────────────┐
│  https://github.com/org/repo │ ───►  │ • Tree-sitter AST Parsing     │  ───►  │ 🏥 Transparent Health Tab  │
└─────────────────────────────┘        │ • Call & Inheritance Graph    │        │ 🏛️ Interactive Architecture │
                                       │ • pgvector Embeddings         │        │ 🔍 Execution Feature Trace  │
                                       │ • Ruff + Bandit Security Scan │        │ 💬 Grounded AI Chat         │
                                       └───────────────────────────────┘        └─────────────────────────────┘
```

### Primary User Benefits

1. **Ramp Up in 15 Minutes**: Go from zero repository knowledge to answering architectural questions immediately.
2. **100% Grounded Citations**: Every AI response includes clickable citation chips (`file_path:line`) that prove where the logic lives.
3. **Deterministic Health Auditing**: Transparent mathematical scoring across Security, Complexity, Defect Density, and Dependencies — with no opaque AI scoring.
4. **Zero-Budget Self-Hostability**: Engineered to run on self-hosted open-source technologies (PostgreSQL, Redis, Celery, Tree-sitter, CPU embeddings) with zero required recurring API costs.

---

## 📸 Screenshots & Visual Preview

Explore the core user interface of DevLens AI:

<table width="100%">
  <tr>
    <td width="50%" valign="top">
      <h4 align="center">1. Repository Dashboard & Health Audit</h4>
      <a href="docs/screenshots/repo-health.png">
        <img src="docs/screenshots/hero-banner.jpg" alt="Health Audit Gauge and Issue Breakdown" width="100%" />
      </a>
      <p align="center"><em>Real-time health score across 4 pillars (Security, Quality, Complexity, Dependencies) with verified ceiling logic.</em></p>
    </td>
    <td width="50%" valign="top">
      <h4 align="center">2. Grounded Codebase Chat</h4>
      <a href="docs/screenshots/grounded-chat.png">
        <img src="docs/screenshots/hero-banner.jpg" alt="Grounded AI Chat with Exact Line Citations" width="100%" />
      </a>
      <p align="center"><em>Semantic search merged with graph neighborhood context; every claim cites exact file and line numbers.</em></p>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <h4 align="center">3. Feature Execution Tracing</h4>
      <a href="docs/screenshots/feature-trace.png">
        <img src="docs/screenshots/hero-banner.jpg" alt="Feature Tracing from Entry Point to Data Access" width="100%" />
      </a>
      <p align="center"><em>End-to-end call path traversal tagging entry points, handlers, business logic, and database access.</em></p>
    </td>
    <td width="50%" valign="top">
      <h4 align="center">4. Interactive Module Architecture</h4>
      <a href="docs/screenshots/architecture-graph.png">
        <img src="docs/screenshots/hero-banner.jpg" alt="Interactive Architecture Graph" width="100%" />
      </a>
      <p align="center"><em>Mermaid-rendered module dependency graphs extracted live from AST imports and inheritance edges.</em></p>
    </td>
  </tr>
</table>

> [!TIP]
> High-resolution gallery templates and step-by-step instructions for adding custom screenshots are documented in [`docs/screenshots/README.md`](docs/screenshots/README.md).

---

## ✨ Key Features

| Capability | How It Works Under the Hood | User Value |
|---|---|---|
| **Code-Aware AST Parsing** | Parses source files using **Tree-sitter** into typed AST entities (`Function`, `Class`, `Method`, `Module`, `Import`). | Eliminates regex inaccuracies and captures true programming language semantics. |
| **Engineering Knowledge Graph** | Resolves cross-file references into directed edges (`calls`, `imports`, `extends`, `depends_on`) stored in PostgreSQL. | Grounds code navigation in actual system architecture, not keyword coincidence. |
| **Grounded AI Q&A** | Hybrid retrieval engine combining **pgvector cosine similarity** with graph neighborhood expansion before prompting the LLM. | Zero hallucinated functions; responses cite exact file paths and line ranges. |
| **Feature Tracing** | Identifies query entry points via semantic search and performs BFS/shortest-path traversal across the call graph. | Visually reveals complex workflows (e.g. auth flows, request dispatch) from route to database. |
| **Architecture Visualization** | Aggregates AST relationships into modular components and renders interactive **Mermaid.js** diagrams. | Provides an up-to-date, interactive structural map of unfamiliar repositories. |
| **Multi-Tool Static Analysis** | Concurrently executes **Ruff** and **Bandit** inside sandboxed workers with cross-tool deduplication. | Flags genuine vulnerabilities and quality issues with zero manual configuration. |
| **Hardened Health Scoring** | Transparent formula scoring 4 pillars with strictly verified security ceilings (`verify=False`, dynamic shell injection). | Delivers defensible, repeatable metrics free of black-box LLM variability. |

---

## 🏛️ System Architecture & Workflows

DevLens AI is engineered as a **modular monolith with an asynchronous distributed pipeline**. Heavy computational operations (cloning, AST parsing, embedding, static analysis) are offloaded to Celery workers, keeping the FastAPI backend responsive.

### High-Level System Architecture

```mermaid
flowchart TD
    subgraph Client [Presentation Layer]
        UI[Next.js 14 App Router]
        Merm[Mermaid.js / React Flow]
    end

    subgraph Gateway [API Layer]
        Nginx[Nginx Reverse Proxy]
        API[FastAPI REST API :8000]
        Auth[JWT & OAuth Module]
    end

    subgraph Queue [Task Broker]
        Redis[(Redis 7 Broker & Cache)]
    end

    subgraph Workers [Distributed Processing Engine]
        Celery[Celery Worker Cluster]
        TS[Tree-sitter AST Engine]
        Static[Ruff & Bandit Analyzers]
        ST[Sentence-Transformers Embeddings]
    end

    subgraph Storage [Data Layer]
        PG[(PostgreSQL 15)]
        PGV[(pgvector Embeddings)]
        Graph[(Graph Nodes & Edges Tables)]
    end

    subgraph AI [Inference Layer]
        LLM[LLM Provider: Groq / Claude / OpenAI / Ollama]
    end

    UI -->|HTTPS / REST| Nginx
    Nginx --> API
    API --> Auth
    API -->|Enqueue Jobs| Redis
    Redis --> Celery
    Celery --> TS
    Celery --> Static
    Celery --> ST
    Celery -->|Persist Graph & Metrics| PG
    Celery -->|Store Vectors| PGV
    API -->|Query Relational & Graph| PG
    API -->|Hybrid Vector Search| PGV
    API -->|Grounded RAG Prompting| LLM
```

---

### The 7-Stage Asynchronous Indexing Pipeline

When a repository URL is submitted, Celery coordinates a multi-stage pipeline:

```mermaid
flowchart LR
    S1[Stage 1: Clone<br/><b>5%</b>] --> S2[Stage 2: Language<br/><b>15%</b>]
    S2 --> S3[Stage 3: AST Parse<br/><b>30%</b>]
    S3 --> S4[Stage 4: Build Graph<br/><b>50%</b>]
    S4 --> S5[Stage 5: Embeddings<br/><b>70%</b>]
    S5 --> S6[Stage 6: Static Scan<br/><b>85%</b>]
    S6 --> S7[Stage 7: Health Report<br/><b>100%</b>]
```

1. **Stage 1 &bull; Cloning (5%)**: Shallow clone (`--depth 1`) to an ephemeral sandboxed workspace with repository size guards.
2. **Stage 2 &bull; Language Detection (15%)**: Inventory scan calculating language distribution, filtering out virtual environments and vendor files, and computing accurate LOC.
3. **Stage 3 &bull; AST Parsing (30%)**: Tree-sitter walks the syntax tree, registering typed `GraphNode` records for classes, functions, and imports with line numbers.
4. **Stage 4 &bull; Graph Construction (50%)**: Resolves symbols across files to generate directed `GraphEdge` records (`calls`, `imports`, `extends`, `depends_on`).
5. **Stage 5 &bull; Semantic Embedding (70%)**: Generates 384-dimensional dense vectors using `sentence-transformers/all-MiniLM-L6-v2` and persists them into `pgvector`.
6. **Stage 6 &bull; Static Analysis (85%)**: Executes Ruff and Bandit concurrently with deduplication across overlapping security and lint rules.
7. **Stage 7 &bull; Health Report Generation (100%)**: Calculates the 4-pillar health score, applies hardened security ceilings, cleans up disk workspaces, and marks the job complete.

---

### Grounded Retrieval (Hybrid RAG) Flow

```mermaid
flowchart LR
    UserQuery[User Question] --> EmbedQuery[Embed Question Vector]
    EmbedQuery --> VectorMatch[pgvector Cosine Search]
    UserQuery --> EntityNER[AST Symbol Matching]
    EntityNER --> GraphWalk[Call Graph 1-Hop Expansion]
    VectorMatch --> ContextAssembler[Context Assembler]
    GraphWalk --> ContextAssembler
    ContextAssembler --> LLMCall[LLM Provider]
    LLMCall --> GroundedAnswer[Response with File & Line Citations]
```

---

## 🛠️ Technology Stack

| Layer | Technology | Version | Purpose |
|---|---|---|---|
| **Frontend** | [Next.js](https://nextjs.org/) | 14+ (App Router) | Reactive web UI, Server Components, and client dashboard |
| **Language** | [TypeScript](https://www.typescriptlang.org/) | 5+ | End-to-end type safety across dashboard views and API contracts |
| **Styling** | [Tailwind CSS](https://tailwindcss.com/) | 4.0 | Sleek, dark-mode glassmorphism design system |
| **Visualizations** | [Mermaid.js](https://mermaid.js.org/) & [XYFlow](https://reactflow.dev/) | 11+ / 12+ | Client-side dynamic rendering of architecture and call graphs |
| **Backend API** | [FastAPI](https://fastapi.tiangolo.com/) | 0.115+ | High-performance asynchronous REST API in Python 3.12 |
| **Task Queue** | [Celery](https://docs.celeryq.dev/) & [Redis](https://redis.io/) | 5.4+ / 7+ | Distributed background execution of multi-stage indexing jobs |
| **Database** | [PostgreSQL](https://www.postgresql.org/) + [pgvector](https://github.com/pgvector/pgvector) | 15+ | Relational data, graph relational tables, and vector similarity search |
| **AST Parser** | [Tree-sitter](https://tree-sitter.github.io/tree-sitter/) | 0.23+ | Multi-language syntax parsing and AST traversal |
| **Static Analysis** | [Ruff](https://astral.sh/ruff) & [Bandit](https://bandit.readthedocs.io/) | Latest | Concurrent linting and automated Python security auditing |
| **Embeddings** | [Sentence-Transformers](https://www.sbert.net/) | 3.0+ | Local CPU embedding generation (`all-MiniLM-L6-v2`) |
| **LLM Inference** | [Groq](https://groq.com/) / [Anthropic](https://anthropic.com/) / [OpenAI](https://openai.com/) / [Ollama](https://ollama.com/) | Pluggable | Swappable provider interface with zero vendor lock-in |
| **Containers** | [Docker](https://www.docker.com/) & Docker Compose | Latest | Standardized container orchestration and isolated runtime |

---

## 🏁 Getting Started

### Prerequisites

Ensure you have the following installed on your host system:
* [Docker](https://docs.docker.com/get-docker/) (v24.0+) & [Docker Compose](https://docs.docker.com/compose/) (v2.20+)
* [Node.js](https://nodejs.org/) (v18+ or v20 LTS) & `npm`
* *(Optional)* Python 3.12+ (only required if developing the backend outside Docker)

---

### Step 1: Clone and Configure Environment

```bash
git clone https://github.com/sparsh-sharma-08/devLens.git
cd DevLens

# Copy environment variables template
cp .env.example .env
```

Open `.env` and configure your preferred LLM provider. DevLens defaults to **Groq** for high-speed, zero-cost development inference:

```ini
LLM_PROVIDER=groq
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile
```

*(You can also set `LLM_PROVIDER=ollama` to run 100% locally with no API key).*

---

### Step 2: Start Backend Services with Docker

Launch PostgreSQL, Redis, FastAPI, Celery, and Nginx in detached mode:

```bash
docker compose up -d
```

Verify that all five services are healthy:

```bash
docker compose ps
```

Test backend connectivity:

```bash
curl http://localhost:8000/health
# Expected response: {"status":"ok","version":"1.0.0"}
```

---

### Step 3: Start the Next.js Frontend

In a separate terminal window:

```bash
cd frontend
npm install
npm run dev
```

Open your browser to **[http://localhost:3000](http://localhost:3000)**.

---

### Pre-Configured Test Credentials

For rapid local testing, a pre-seeded account is available:
* **Login URL**: [http://localhost:3000/auth](http://localhost:3000/auth)
* **Email**: `test@devlens.ai`
* **Password**: `SecurePassword123!`

---

## 📖 Usage Guide

### 1. Ingesting a Repository
1. Log in to the dashboard at `http://localhost:3000/dashboard`.
2. Click **"Import Repository"** or paste any public GitHub URL (e.g., `https://github.com/encode/httpx` or `https://github.com/pallets/click`).
3. Watch the live 7-stage progress bar update in real time from **5%** through **100%**.

### 2. Exploring the 4 Analysis Tabs

#### 🏥 Health Tab
* Inspect your repository's composite **Health Score** (0–100).
* Review the 4-pillar breakdown: **Security**, **Code Quality**, **Complexity**, and **Dependencies**.
* Check the **Ceiling Status**: DevLens enforces security ceilings (e.g. genuine dynamic shell injections cap health at 70; broken SSL algorithms cap at 85).
* Filter categorized findings with exact line numbers and rule identifiers.

#### 🏛️ Architecture Tab
* View an auto-generated, interactive Mermaid diagram representing packages, components, and module dependencies.
* Click into any module to inspect member files and inter-package coupling.

#### 🔍 Trace Tab
* Type an execution intent in plain English, such as:
  * `"HTTP request dispatch and connection pooling"`
  * `"Authentication token validation and user lookup"`
* DevLens discovers the entry point via semantic search, walks the call graph, and generates an ordered sequence of steps with lifecycle badges:
  * `[Entry Point]` &rarr; `[Handler]` &rarr; `[Business Logic]` &rarr; `[Data Access]`

#### 💬 Chat Tab
* Ask technical questions about the codebase:
  * *"Where are HTTP requests constructed and dispatched?"*
  * *"How does the retry backoff algorithm function?"*
* Responses are streamed with clickable citation chips (`file_path:line`) that link directly to the underlying code.

---

## 📁 Repository Structure

```
DevLens/
├── backend/                       # FastAPI application & worker engine
│   ├── app/
│   │   ├── api/                   # REST endpoints (auth, repos, jobs, chat)
│   │   ├── auth/                  # JWT authentication & password hashing
│   │   ├── workers/               # Celery application & 7-stage pipeline
│   │   │   └── pipeline.py        # Clone, Parse, Graph, Embed, Scan, Report
│   │   ├── config.py              # Pydantic environment configuration
│   │   ├── database.py            # SQLAlchemy async database session setup
│   │   ├── embeddings.py          # Sentence-Transformers vector generator
│   │   ├── models.py              # Database models (GraphNode, GraphEdge, etc.)
│   │   └── main.py                # FastAPI entry point & CORS configuration
│   ├── db/
│   │   └── init.sql               # PostgreSQL pgvector & pgcrypto initialization
│   ├── Dockerfile                 # Backend container definition
│   └── pyproject.toml             # Python dependencies & Ruff/Pytest configs
├── frontend/                      # Next.js 14 App Router application
│   ├── src/
│   │   ├── app/
│   │   │   ├── auth/              # Sign in & registration pages
│   │   │   ├── dashboard/         # Repository inventory & import modal
│   │   │   ├── repos/[id]/        # Repository workspace layout & tab switcher
│   │   │   │   └── tabs/          # HealthTab, ArchitectureTab, TraceTab, ChatTab
│   │   │   ├── globals.css        # Glassmorphism styling & design variables
│   │   │   └── page.tsx           # Product landing page & feature showcase
│   │   └── lib/
│   │       └── api.ts             # Typed API client for FastAPI backend
│   └── package.json               # Frontend dependencies & Next scripts
├── docs/                          # Developer documentation & assets
│   └── screenshots/               # Application preview images & gallery guide
├── nginx/
│   └── dev.conf                   # Nginx reverse proxy routing
├── docker-compose.yml             # Orchestration for Postgres, Redis, API, Worker, Nginx
├── startup.md                     # Step-by-step local testing & verification guide
├── CURRENT_STATUS_DEEP_DIVE.md    # Detailed engineering status & benchmarks
└── FINAL_STATUS.md                # V1 completion audit & benchmark baseline
```

---

## ⚙️ Configuration Reference

All settings can be configured in `.env` (derived from [`.env.example`](.env.example)):

### Core Infrastructure

| Variable | Default Value | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://devlens:devlens_secret@postgres:5432/devlens` | Async connection string for PostgreSQL |
| `REDIS_URL` | `redis://redis:6379/0` | Redis broker URL for Celery and caching |
| `CELERY_BROKER_URL` | `redis://redis:6379/0` | Task queue broker endpoint |
| `CELERY_RESULT_BACKEND` | `redis://redis:6379/1` | Celery task result storage endpoint |

### Authentication & Security

| Variable | Default Value | Description |
|---|---|---|
| `JWT_SECRET_KEY` | *(Set in .env)* | 256-bit secret used to sign session JWTs |
| `JWT_ALGORITHM` | `HS256` | JWT signing algorithm |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | Duration before access tokens expire |
| `GITHUB_CLIENT_ID` | — | GitHub OAuth App client identifier |
| `GITHUB_CLIENT_SECRET` | — | GitHub OAuth App client secret |

### LLM & Embeddings

| Variable | Default Value | Description |
|---|---|---|
| `LLM_PROVIDER` | `groq` | Active LLM backend (`groq`, `claude`, `openai`, `ollama`) |
| `GROQ_API_KEY` | — | API key from [Groq Console](https://console.groq.com) |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Groq model selection |
| `EMBEDDING_PROVIDER` | `local` | Embedding backend (`local`, `voyage`, `groq`) |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Sentence-Transformers model for local CPU embeddings |

### Ingestion Limits

| Variable | Default Value | Description |
|---|---|---|
| `MAX_REPO_SIZE_MB` | `500` | Maximum repository git packfile limit |
| `MAX_REPO_LOC` | `50000` | Maximum supported lines of code per repository for V1 |
| `CLONE_WORKSPACE_DIR`| `/tmp/devlens_repos` | Ephemeral disk workspace for git clones |

---

## 🗺️ Roadmap

The DevLens AI vision is structured into focused evolutionary phases:

```
  ┌─────────────────────────┐      ┌─────────────────────────┐      ┌─────────────────────────┐
  │         V1 (MVP)        │      │           V2            │      │          V3/V4          │
  │   Feature Complete ✅   │ ──►  │    Next Development     │ ──►  │      Future Vision      │
  │ • 7-stage Celery engine │      │ • Neo4j graph migration │      │ • PR review agent       │
  │ • Tree-sitter AST parse │      │ • JS/TS grammar support │      │ • CI/CD pipeline bot    │
  │ • pgvector search       │      │ • Stack trace debugger  │      │ • Gitlab & Bitbucket    │
  │ • Health report audit   │      │ • Auto doc generator    │      │ • Multi-repo analytics  │
  └─────────────────────────┘      └─────────────────────────┘      └─────────────────────────┘
```

* **V1 (Current &bull; Feature Complete)**:
  * Full 7-stage distributed indexing pipeline with Celery and Redis.
  * Python AST parsing via Tree-sitter; security static analysis via Ruff & Bandit.
  * Grounded AI Chat with exact file/line citations and vector similarity search.
  * Feature call-path tracing and interactive Mermaid architecture diagrams.
  * Validated against production Python codebases (**Django**: 456k LOC in 57s, **HTTPX**: 14k LOC).
* **V2 (Deepen the Intelligence)**:
  * Migration of knowledge graph to Neo4j Community Edition for complex recursive traversals.
  * Expanded grammar support for JavaScript/TypeScript and Go.
  * Automated bug root-cause investigation from pasted log stack traces.
  * Automated living documentation and API schema generation.
* **V3 & V4 (Team Integration & Predictive Engineering)**:
  * Pull request review bot with architectural drift detection.
  * GitHub App & CI/CD status checks.
  * Predictive regression risk analysis based on dependency centrality.

---

## 🤝 Contributing

Contributions are warmly welcomed! Please adhere to our contribution process:

1. **Fork the Repository**: Create your feature branch (`git checkout -b feature/amazing-capability`).
2. **Set Up Local Environment**: Follow the [Getting Started](#-getting-started) guide.
3. **Format & Lint Code**:
   * Backend: Run `ruff check backend/app` and `ruff format backend/app`.
   * Frontend: Run `cd frontend && npm run lint`.
4. **Commit Your Changes**: Write clean, descriptive conventional commits (`git commit -m 'feat: add support for Go AST parsing'`).
5. **Open a Pull Request**: Submit your pull request against the `main` branch with a clear description of your changes.

---

## 📄 License & Acknowledgements

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

### Acknowledgements & Open-Source Foundations

DevLens AI is made possible by the incredible open-source community:

* [Tree-sitter](https://tree-sitter.github.io/tree-sitter/) — Fast, robust incremental AST parsing.
* [pgvector](https://github.com/pgvector/pgvector) — Vector similarity search for PostgreSQL.
* [FastAPI](https://fastapi.tiangolo.com/) — Modern, asynchronous web framework for Python.
* [Next.js](https://nextjs.org/) — React framework by Vercel for scalable web applications.
* [Sentence-Transformers](https://www.sbert.net/) — State-of-the-art dense text embeddings.
* [Ruff](https://astral.sh/ruff) & [Bandit](https://bandit.readthedocs.io/) — Lightning-fast linting and static security analysis.
* [Celery](https://docs.celeryq.dev/) — Reliable distributed task processing.

---

<div align="center">
  <sub>Built with ❤️ for developers who value understanding over guessing.</sub>
</div>
