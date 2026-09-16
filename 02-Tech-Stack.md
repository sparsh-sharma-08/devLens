# DevLens AI — Technology Stack (Zero-Budget Edition)

**Document Type:** Technical Stack Specification
**Version:** 1.0
**Constraint:** Every item below has a free tier sufficient for MVP + early users. Paid upgrade paths are noted only for future scaling, never required to launch.

---

## 1. Guiding Principles

1. **Prefer self-hosted open source over "free tier of a paid SaaS"** wherever the self-hosted option is not materially harder to run — free tiers can change terms; open source you run yourself cannot be taken away.
2. **One deployment target, not five** — avoid stitching together six different free tiers with six different cold-start/sleep behaviors. Pick a small number of platforms that play well together.
3. **Every paid-sounding capability has a real open-source equivalent** — vector DB, graph DB, LLM inference, static analysis, observability. None of these require a credit card for the MVP.

---

## 2. Stack Summary Table

| Layer | Choice | Why | Free Tier Limit to Know |
|---|---|---|---|
| Frontend | **Next.js 14 (App Router) + TypeScript + Tailwind CSS** | Original plan already used Next.js; huge free ecosystem | N/A (self-hosted or Vercel free) |
| Frontend hosting | **Vercel (Hobby plan)** or **Cloudflare Pages** | Zero-cost, generous, great DX | Vercel Hobby: 100GB bandwidth/mo |
| API Gateway | **Built into FastAPI + Nginx (self-hosted)** or Cloudflare in front | No need for a paid API gateway product at MVP scale | — |
| Backend | **FastAPI (Python 3.12)** | Async, great for I/O-bound repo processing, matches parsing ecosystem (Python bindings for Tree-sitter are excellent) | — |
| Background jobs / queue | **Celery + Redis** (or **Arq**, lighter-weight async alternative) | Repo cloning/parsing is long-running; needs a queue, not request/response | Self-hosted, free |
| Auth | **Supabase Auth** (free tier) or **Auth.js (NextAuth)** self-hosted | GitHub + Google OAuth out of the box | Supabase free: 50k MAU |
| Primary database | **PostgreSQL** (via **Supabase** free tier, or self-hosted via Docker/Fly.io) | Relational metadata: users, repos, files, reports | Supabase free: 500MB DB, pauses after 1 week inactivity |
| Graph storage | **Neo4j Community Edition (self-hosted)** or **Memgraph Community**, or model the graph *inside Postgres* using an edge table + recursive CTEs | Real graph queries (traversal, shortest path) for the Knowledge Graph | Neo4j Community: free forever, self-hosted |
| Vector store | **pgvector extension on the same Postgres** (simplest) or **Qdrant (self-hosted, free)** | Embedding storage/search for semantic search | pgvector: free, no extra service to run |
| Embeddings model | **Sentence-Transformers (`all-MiniLM-L6-v2` or `bge-small-en`)** run locally on CPU, or free-tier hosted embeddings from **Voyage AI** (has a free quota) | Zero-cost embeddings, no per-call billing | Local = fully free, no limit |
| LLM (reasoning/answers) | **Claude API** via a free/low-cost dev credit, OR self-hosted open models: **Llama 3.1 8B / Qwen2.5-Coder** via **Ollama** or **Groq's free API tier** (very fast, generous free limits) for early development | Groq free tier is realistically the best zero-cost option for a working demo | Groq free tier: rate-limited but usable for MVP demos |
| Code parsing | **Tree-sitter** (via `py-tree-sitter` + official grammars for Python/JS/TS/Java/Go) | Real AST-level parsing across languages, MIT-licensed | Free, no limits |
| Static analysis (Python) | **Ruff** (lint + many Bandit-style checks) + **Bandit** (security) | Both free, fast, actively maintained | Free |
| Static analysis (JS/TS) | **ESLint** | Free | Free |
| Static analysis (Java) | **PMD**, **SpotBugs** | Free | Free |
| Repo cloning | **GitPython** or plain `git` CLI via subprocess | Free | Free |
| Diagram generation | **Mermaid.js** (rendered client-side) for architecture/flow diagrams | No server-side rendering cost, renders directly in the browser | Free |
| File storage (cloned repos, cache) | Local disk on the compute host, or **Cloudflare R2** free tier (10GB) if you need object storage | Avoid S3 costs entirely at MVP scale | R2 free: 10GB storage, no egress fee |
| Backend hosting | **Fly.io free allowance** or **Railway free trial credits** or a single **Oracle Cloud Always Free** VM (4 ARM cores, 24GB RAM — the best-kept secret for zero-cost compute) | Repo parsing needs real CPU/RAM; Oracle's Always Free ARM tier is unusually generous | Oracle Always Free: genuinely free forever (subject to account approval) |
| Containerization | **Docker + Docker Compose** | Standard, free, portable across all the above hosts | Free |
| CI/CD | **GitHub Actions** (free minutes for public/private repos) | Already where your code lives | 2,000 free minutes/mo (private repos) |
| Observability / logs | **Grafana + Loki + Prometheus (self-hosted via Docker Compose)**, or **Better Stack free tier** if you'd rather not self-host | Track job queue health, API latency, errors | Better Stack free: 1GB logs/mo |
| Error tracking | **Sentry free tier** (Developer plan) | Crash/error visibility without self-hosting | 5k errors/mo free |
| Repository providers | **GitHub REST/GraphQL API**, **GitLab API** (both free for public read access; OAuth app is free to register) | Core import feature | Free, rate-limited per standard API limits |

---

## 3. Architecture Choices Explained

### 3.1 Why Postgres for both relational *and* vector *and* (optionally) graph
Running **one** database instead of three separate services (Postgres + Neo4j + Qdrant) is the single biggest cost/complexity reduction available. `pgvector` gives you production-quality approximate nearest-neighbor search. For the graph, a simple `nodes` + `edges` table with recursive CTEs handles MVP-scale traversal (a few hundred thousand edges) perfectly well.

**Recommendation for V1:** Postgres + pgvector only, graph modeled as tables.
**Recommendation for V2+ (once graph queries get complex — multi-hop traversals, centrality, shortest-path):** Migrate the graph layer to **Neo4j Community Edition** self-hosted in the same Docker Compose stack. This is a clean, isolated migration because the graph is already a bounded subsystem.

### 3.2 Why Tree-sitter over language-native compilers
Building real parsers per language (a Python AST module for Python, a Java compiler frontend for Java, etc.) is a multi-year engineering effort. **Tree-sitter** gives you a single, consistent incremental-parsing API across 40+ languages with community-maintained grammars, and is what tools like GitHub's code navigation and many modern IDEs use under the hood. This is the correct trade-off for a solo developer who still wants *real* structural parsing, not regex.

### 3.3 Why Groq (or Ollama) instead of only paid LLM APIs for development
You will make thousands of LLM calls during development and testing (agent prompts, embeddings, iteration). Relying solely on a metered paid API burns budget fast. **Groq's free tier** (open models like Llama 3.1/3.3, Mixtral) gives very fast, genuinely free inference for development and even light production use. For production quality answers once you have paying users or want the best reasoning, you can add Claude/OpenAI as a **swappable provider** behind one interface — the architecture should never hard-code a single LLM vendor.

### 3.4 Why Oracle Cloud Always Free for backend compute
Repository cloning + Tree-sitter parsing + static analysis are CPU/RAM-hungry, especially on large repos. Most "free tier" PaaS options (Render, Railway, Vercel serverless functions) either sleep after inactivity, have short execution-time limits, or lack the RAM for this workload. Oracle's **Always Free** tier (up to 4 OCPU / 24GB RAM on Ampere ARM) is unusually generous and is the most realistic option for actually running the processing engine without hitting walls. Fly.io's free allowance is a reasonable fallback for the API layer itself.

---

## 4. Component-to-Stack Mapping

| Original Architecture Component | Concrete Free Implementation |
|---|---|
| Frontend (Next.js) | Next.js 14 + Tailwind, hosted on Vercel Hobby |
| API Gateway | Nginx reverse proxy (self-hosted) or Cloudflare in front of Fly.io app |
| Authentication Service | Supabase Auth (GitHub + Google OAuth) |
| FastAPI Backend | FastAPI on Oracle Always Free VM (Dockerized) |
| Repository Processing Engine | Celery workers (same VM), GitPython for cloning |
| Static Analysis Engine | Ruff, Bandit, ESLint, PMD/SpotBugs run as subprocesses inside worker containers |
| Code Parsing Engine | Tree-sitter + language grammars |
| Engineering Knowledge Graph | Postgres tables (`nodes`, `edges`) in V1 → Neo4j Community in V2 |
| Semantic Search Engine | pgvector + Sentence-Transformers (local CPU embeddings) |
| AI Orchestrator / Agents | LangGraph or a hand-rolled agent loop calling Groq/Claude API, one Python service |
| Repository Database | Supabase Postgres (free tier) |
| User Dashboard | Next.js pages + Recharts/Chart.js for health scores |

---

## 5. Estimated Monthly Cost at MVP Scale

| Item | Cost |
|---|---|
| Vercel Hobby (frontend) | $0 |
| Oracle Always Free VM (backend + workers) | $0 |
| Supabase free tier (Postgres + Auth) | $0 |
| Groq free tier (LLM inference, dev/early prod) | $0 |
| Sentry Developer plan | $0 |
| GitHub Actions (CI/CD) | $0 (within free minutes) |
| Domain name | ~$10–12/year (the one unavoidable cost if you want a custom domain; a `vercel.app`/`fly.dev` subdomain is $0) |

**Total to launch and demo: effectively $0/month.**

---

## 6. Migration Path When You Do Have Budget

This stack is deliberately chosen so nothing needs to be re-architected later — only swapped:

- Supabase free → Supabase Pro (or self-hosted Postgres on a paid VM) when you outgrow 500MB/pause limits.
- Groq/Ollama → Claude API or OpenAI for higher-quality production answers.
- Postgres-graph-as-tables → Neo4j Community (already free) → Neo4j AuraDB (paid, managed) only if you need managed hosting.
- Oracle Always Free VM → paid Fly.io/Render/AWS instance when concurrent repo-processing load exceeds one VM.

No component requires a rewrite to scale — only a configuration/provider swap, because the system is built against interfaces (LLM provider interface, graph-store interface), not vendor SDKs directly.
