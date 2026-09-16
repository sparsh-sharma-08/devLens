# DevLens AI — Startup Guide

> Complete instructions to get DevLens running locally on your machine.

---

## Prerequisites

Make sure the following are installed before proceeding:

| Tool | Version | Check command |
|---|---|---|
| **Docker** & **Docker Compose** | Docker ≥ 24, Compose V2 | `docker --version` / `docker compose version` |
| **Node.js** | ≥ 18 (LTS recommended) | `node --version` |
| **npm** | ≥ 9 | `npm --version` |
| **Python** | ≥ 3.12 | `python3 --version` |
| **Git** | ≥ 2.x | `git --version` |

---

## 1. Clone the Repository

```bash
git clone <your-repo-url> DevLens
cd DevLens
```

---

## 2. Environment Setup

### 2.1 — Root `.env` (Backend + Docker services)

Copy the example env file and fill in your secrets:

```bash
cp .env.example .env
```

Open `.env` and configure at minimum:

| Variable | What to do |
|---|---|
| `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` | Register an OAuth App at [GitHub Developer Settings](https://github.com/settings/developers). Set the callback URL to `http://localhost:8000/auth/github/callback` |
| `JWT_SECRET_KEY` | Replace with a long random string (e.g. `openssl rand -hex 32`) |
| `GROQ_API_KEY` | Get a free key from [console.groq.com](https://console.groq.com) |

Everything else has sensible defaults for local development.

### 2.2 — Frontend `.env.local`

The frontend env file is already set up at `frontend/.env.local`:

```
NEXT_PUBLIC_API_URL=http://localhost:8000/v1
```

No changes needed for local development.

---

## 3. Start with Docker (Recommended)

This is the easiest way — one command spins up **all** services.

### 3.1 — Build and start all services

```bash
docker compose up --build
```

Add `-d` to run in detached (background) mode:

```bash
docker compose up --build -d
```

### 3.2 — What gets started

| Service | Container | Port | Description |
|---|---|---|---|
| PostgreSQL 15 + pgvector | `devlens_postgres` | `5432` | Database with vector extension |
| Redis 7 | `devlens_redis` | `6379` | Celery broker + result backend |
| FastAPI Backend | `devlens_api` | `8000` | REST API with hot-reload |
| Celery Worker | `devlens_worker` | — | Background pipeline tasks |
| Nginx | `devlens_nginx` | `80` | Reverse proxy for API |

### 3.3 — Start the frontend (separately)

The frontend (Next.js) runs outside Docker:

```bash
cd frontend
npm install
npm run dev
```

### 3.4 — Verify everything is running

| Check | URL / Command |
|---|---|
| API Health | [http://localhost:8000/health](http://localhost:8000/health) |
| API Docs (Swagger) | [http://localhost:8000/docs](http://localhost:8000/docs) |
| Frontend | [http://localhost:3000](http://localhost:3000) |
| Nginx proxy | [http://localhost/health](http://localhost/health) |
| Docker containers | `docker compose ps` |

---

## 4. Start Without Docker (Manual Setup)

If you prefer to run services natively:

### 4.1 — Start PostgreSQL & Redis

You'll need PostgreSQL 15 (with pgvector) and Redis 7 running locally. For macOS:

```bash
# Install via Homebrew
brew install postgresql@15 redis

# Start services
brew services start postgresql@15
brew services start redis
```

Make sure to install the `pgvector` extension:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

Run the init script to set up the database:

```bash
psql -U devlens -d devlens -f backend/db/init.sql
```

### 4.2 — Backend

```bash
cd backend

# Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install --upgrade pip setuptools wheel
pip install -e ".[dev]"

# Run database migrations
alembic upgrade head

# Start the API server (with hot-reload)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4.3 — Celery Worker

In a separate terminal (with the venv activated):

```bash
cd backend
source .venv/bin/activate

celery -A app.workers.celery_app worker --loglevel=info --concurrency=2
```

### 4.4 — Frontend

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

---

## 5. Database Migrations (Alembic)

Migrations are managed with Alembic from the `backend/` directory.

```bash
cd backend

# Apply all pending migrations
alembic upgrade head

# Create a new migration after model changes
alembic revision --autogenerate -m "describe your change"

# Rollback the last migration
alembic downgrade -1

# View current migration status
alembic current
```

> **Note:** When using Docker, run Alembic inside the API container:
> ```bash
> docker compose exec api alembic upgrade head
> ```

---

## 6. Common Commands

### Docker

```bash
# Start all services
docker compose up --build -d

# Stop all services
docker compose down

# Stop and remove volumes (⚠️ deletes database data)
docker compose down -v

# View logs for a specific service
docker compose logs -f api
docker compose logs -f worker
docker compose logs -f postgres

# Restart a single service
docker compose restart api

# Open a shell inside the API container
docker compose exec api bash
```

### Frontend

```bash
cd frontend

npm run dev        # Development server (port 3000)
npm run build      # Production build
npm run start      # Start production server
npm run lint       # Run ESLint
```

### Backend

```bash
cd backend
source .venv/bin/activate

# Run tests
pytest

# Run linter
ruff check .

# Run security analysis
bandit -r app/
```

---

## 7. Service URLs (Quick Reference)

| Service | URL |
|---|---|
| Frontend (Next.js) | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API Docs (Swagger) | http://localhost:8000/docs |
| Health Check | http://localhost:8000/health |
| Nginx Proxy | http://localhost:80 |
| PostgreSQL | localhost:5432 |
| Redis | localhost:6379 |

---

## 8. Troubleshooting

### Port already in use

```bash
# Find what's using a port (e.g. 8000)
lsof -i :8000

# Kill the process
kill -9 <PID>
```

### Docker containers won't start

```bash
# Check container logs
docker compose logs

# Rebuild from scratch
docker compose down -v
docker compose up --build
```

### Database connection refused

- Make sure PostgreSQL is running and healthy: `docker compose ps`
- Verify `DATABASE_URL` in your `.env` matches the running Postgres instance
- If running without Docker, ensure the local Postgres user and database exist:
  ```bash
  createuser devlens
  createdb -O devlens devlens
  ```

### Frontend can't reach the API

- Ensure the backend is running on port `8000`
- Check that `NEXT_PUBLIC_API_URL=http://localhost:8000/v1` is set in `frontend/.env.local`
- The Next.js config proxies `/api/*` requests to the backend automatically

### Celery worker not processing tasks

- Check Redis is running: `redis-cli ping` (should return `PONG`)
- Check worker logs: `docker compose logs -f worker`
- Ensure `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND` are correctly set in `.env`
