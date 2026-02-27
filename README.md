# Lender-Matching-Platform

**LenderMatch** — AI-powered equipment-finance platform: submit loan applications, get matched to lenders by their credit policies, and ingest new lenders from PDF guidelines.

---

## Overview

- **Frontend** (Next.js, TypeScript): Home, multi-step application form, applications list/detail with match results, lender list/detail with rule editing, and PDF upload + ingestion review. See [frontend/README.md](frontend/README.md).
- **Backend** (FastAPI, PostgreSQL): REST API for applications (create, list, get, re-run matching), lenders (CRUD + rules/programs), and PDF ingestion (upload → async extract + GPT-4o parse → approve/reject). See [backend/README.md](backend/README.md).

---

## Repository structure

| Path | Description |
|------|-------------|
| `frontend/` | Next.js 16 app (React 19, Tailwind, shadcn/ui). Port **3000** by default. |
| `backend/` | FastAPI app, SQLAlchemy, Alembic, Hatchet worker. API on port **8001** (to match frontend default). |
| `docker-compose.yml` | PostgreSQL 16. Exposes DB on host port **5433**. |
| `.env` | Copy from `.env.example`; used by backend and (optionally) frontend. |

---

## Prerequisites

- **Node 18+** (frontend)
- **Python 3.11+** (backend)
- **Docker** (for PostgreSQL, optional if you have a local Postgres)
- **OpenAI API key** (for PDF policy parsing)
- **Hatchet** account/token (for async PDF ingestion workflow)

---

## Environment

Copy the example env and fill in values:

```bash
cp .env.example .env
```

| Variable | Used by | Description |
|----------|---------|-------------|
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | docker-compose | DB credentials for the Postgres container. |
| `DATABASE_URL` | backend | Full PostgreSQL URL (e.g. `postgresql://user:pass@localhost:5432/lender_db`). For Docker, use host `localhost` and port **5433** if mapped. |
| `OPENAI_API_KEY` | backend | Required for LLM parsing of lender PDFs. |
| `HATCHET_CLIENT_TOKEN` | backend | For triggering and running the PDF ingestion workflow. |
| `NEXT_PUBLIC_API_URL` | frontend | Backend base URL (default in code: `http://localhost:8001`). Set in `frontend/.env.local` if needed. |

---

## Backend setup

1. **Install dependencies**

   ```bash
   cd backend
   python -m venv .venv
   source .venv/bin/activate   # or `.venv\Scripts\activate` on Windows
   pip install -r requirements.txt
   ```

2. **Database**

   Start Postgres (e.g. with Docker):

   ```bash
   docker compose up -d
   ```

   Then run migrations and optionally seed lenders:

   ```bash
   cd backend
   alembic upgrade head
   python seed.py
   ```

   If using Docker, ensure `DATABASE_URL` uses host `localhost` and port **5433** (as in `.env.example` when using the compose port mapping).

3. **Run the API**

   ```bash
   uvicorn app.main:app --reload --port 8001
   ```

   The frontend expects the API at `http://localhost:8001` by default. CORS is configured in `app/main.py` (allow origin `http://localhost:3001`); if you run the frontend on port 3000, either run the frontend on 3001 (`npm run dev -- -p 3001`) or add `http://localhost:3000` to `allow_origins` in `backend/app/main.py`.

4. **Run the Hatchet worker** (for PDF ingestion)

   In a separate terminal:

   ```bash
   cd backend
   python -m app.worker
   ```

---

## Frontend setup

1. **Install and run**

   ```bash
   cd frontend
   npm install
   npm run dev
   ```

   Open [http://localhost:3000](http://localhost:3000). The app will call the backend at `http://localhost:8001` unless you set `NEXT_PUBLIC_API_URL` in `frontend/.env.local`.

2. **Build for production**

   ```bash
   npm run build
   npm run start
   ```

---

## Ports summary

| Service | Default port | Note |
|---------|--------------|------|
| Frontend | 3000 | Next.js dev server |
| Backend API | 8001 | Use this so frontend default base URL works |
| PostgreSQL (Docker) | 5433 (host) | Compose maps 5433 → 5432 in container |

---

## Quick start (full stack)

```bash
# 1. Env
cp .env.example .env
# Edit .env: DATABASE_URL (port 5433 if using Docker), OPENAI_API_KEY, HATCHET_CLIENT_TOKEN

# 2. DB
docker compose up -d
cd backend && alembic upgrade head && python seed.py

# 3. Backend (terminal 1)
cd backend && uvicorn app.main:app --reload --port 8001

# 4. Hatchet worker (terminal 2)
cd backend && python -m app.worker

# 5. Frontend (terminal 3)
cd frontend && npm install && npm run dev
```

Then open http://localhost:3000. Use “New Application” to submit an application and see match results (after implementing or visiting the applications detail page).

---

## Docs

- [Frontend](frontend/README.md) — Tech stack, project structure, API client, pages (apply, applications, lenders, ingest), setup and env.
- [Backend](backend/README.md) — API endpoints, data model, rule types, PDF ingestion flow, tests, seed data.
