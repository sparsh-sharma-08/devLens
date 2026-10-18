# DevLens AI — Startup & Manual Testing Guide

> Complete, step-by-step instructions to get DevLens running locally and test all features end-to-end.

---

## ⚡ Quick Start (Start Everything in 2 Commands)

The backend and background workers run in Docker; the frontend Next.js development server runs on your host machine.

### Step 1: Start Backend Services (Docker)

From the project root:

```bash
docker compose up -d
```

This launches all background services in detached mode:
* `devlens_postgres` (port `5432`): PostgreSQL 15 with `pgvector`
* `devlens_redis` (port `6379`): Redis 7 task broker & results backend
* `devlens_api` (port `8000`): FastAPI application with automatic table creation & hot reload
* `devlens_worker`: Distributed Celery worker executing Stages 1–7 of the analysis pipeline
* `devlens_nginx` (port `80`): Reverse proxy

*Verify backend health:*
```bash
curl http://localhost:8000/health
# Response: {"status":"ok","version":"1.0.0"}
```

### Step 2: Start Frontend Application

In a new terminal window:

```bash
cd frontend
npm install
npm run dev
```

The Next.js UI is now accessible at **[http://localhost:3000](http://localhost:3000)**.

---

## 🧪 Manual Testing Walkthrough

Follow these steps to manually verify the full end-to-end user journey:

### 1. Authentication
1. Open **[http://localhost:3000/auth](http://localhost:3000/auth)** in your browser.
2. Either create a new account or log in with the pre-registered testing user:
   * **Email:** `test@devlens.ai`
   * **Password:** `SecurePassword123!`
3. You will be redirected to the main dashboard at **[http://localhost:3000/dashboard](http://localhost:3000/dashboard)**.

### 2. View or Import a Repository
* **Pre-Indexed Repository:** Click on the `encode/httpx` repository card already in your dashboard.
* **Import a New Repository:**
  1. Click **"Import Repository"** or paste a public GitHub URL in the input bar (e.g. `https://github.com/pallets/click` or `https://github.com/encode/httpx`).
  2. Watch the live progress bar transition through the 7 Celery pipeline stages:
     * *Stage 1:* Cloning (5%)
     * *Stage 2:* Detecting language & inventory (15%)
     * *Stage 3:* AST parsing (30%)
     * *Stage 4:* Building graph edges (50%)
     * *Stage 5:* Generating vector embeddings (70%)
     * *Stage 6:* Multi-tool static analysis (85%)
     * *Stage 7:* Health report generation & workspace cleanup (100%)

### 3. Explore the 4 Analysis Tabs
Once indexing completes, click into the repository to test each tab:

* **🏥 Health Tab:**
  * Displays the overall health score (e.g., **94 / 100** for HTTPX).
  * Shows radar breakdown: Security (**97**), Code Quality (**94**), Complexity (**99**), and Dependencies (**77**).
  * Verifies **Ceiling: NONE** (no false positive caps).
  * Lists real categorized issues sorted by severity with line numbers.
* **🏛️ Architecture Tab:**
  * Renders an interactive Mermaid diagram representing module-level components and dependencies derived from real AST `imports`, `calls`, and `extends` edges.
* **🔍 Trace Tab:**
  * Enter an execution intent such as `"HTTP request dispatch"` and click **Trace**.
  * Confirms semantic entry-point discovery via vector embeddings (`httpx/_api.py:request`) and multi-hop call traversal through `httpx/_client.py:Client` and `BaseClient` with lifecycle role tags.
* **💬 Chat Tab:**
  * Ask technical questions about the codebase (e.g. *"How does HTTPX send an asynchronous request?"*).
  * The system performs vector similarity search over code chunks and streams a detailed explanation with clickable citation chips (`file_path#Lline`).

---

## 🛠️ Environment Configuration

### Root `.env` (Backend & Docker)
Copy `.env.example` to `.env` if not already present:
```bash
cp .env.example .env
```
Key configuration values:
```ini
ENVIRONMENT=development
DATABASE_URL=postgresql+asyncpg://devlens:devlens_secret@postgres:5432/devlens
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/1

# LLM Provider
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_...
GROQ_MODEL=qwen/qwen3.8-27b
```

### Frontend `.env.local`
Located at `frontend/.env.local`:
```ini
NEXT_PUBLIC_API_URL=http://localhost:8000/v1
```

---

## 📜 Useful Management Commands

### Docker Controls
```bash
# Check status of all containers
docker compose ps

# View live Celery worker pipeline logs
docker compose logs -f worker

# View live FastAPI logs
docker compose logs -f api

# Restart backend services
docker compose restart api worker

# Shut down all services
docker compose down
```

### Database Inspection
```bash
# 1. Direct one-liner from terminal to check latest indexing jobs:
docker exec devlens_postgres psql -U devlens -d devlens -c "SELECT id, stage, progress_pct, error_message FROM indexing_jobs ORDER BY started_at DESC LIMIT 5;"

# 2. Direct one-liner to view all repositories and their status:
docker exec devlens_postgres psql -U devlens -d devlens -c "SELECT name, status, last_indexed_at FROM repositories ORDER BY created_at DESC;"

# 3. Or enter interactive psql shell:
docker exec -it devlens_postgres psql -U devlens -d devlens
# (Once inside psql, you can run \dt, SQL queries, and type \q to exit)
```

---

## 🌐 Quick Reference URLs

| Service | URL |
|---|---|
| **Frontend Web App** | [http://localhost:3000](http://localhost:3000) |
| **User Authentication** | [http://localhost:3000/auth](http://localhost:3000/auth) |
| **Repository Dashboard** | [http://localhost:3000/dashboard](http://localhost:3000/dashboard) |
| **Backend API Docs (Swagger)** | [http://localhost:8000/docs](http://localhost:8000/docs) |
| **Backend Health Check** | [http://localhost:8000/health](http://localhost:8000/health) |
| **PostgreSQL Port** | `localhost:5432` |
| **Redis Port** | `localhost:6379` |
