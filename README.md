# Sovereign Knowledge Platform (SKP)

Private, multi-tenant RAG for SMEs. Planning truth lives in OpenClaw `workspace-architect/` (`PRODUCT_REQUIREMENTS.md`, `MVP_IMPLEMENTATION_PLAN.md`, `DELIVERY_SPEC.md`).

## Phase 0 — locked decisions

| Area | Choice |
|------|--------|
| API | FastAPI (Python 3.11+) |
| DB | PostgreSQL 16 + pgvector extension |
| Cache / hot session | Redis (wired in Compose; app integration in later phases) |
| ORM / migrations | SQLAlchemy 2.x + Alembic |
| Auth | JWT (HS256), bcrypt password hashes |
| Frontend (later) | React + Vite |
| Inference (later) | Ollama for embeddings / LLM |
| Packaging | Docker Compose |
| MVP1 ingestion | PDF-only first |

## Phase 1 status (backend foundation)

- [x] Repo scaffold, config, Docker Compose (Postgres + Redis)
- [x] SQLAlchemy models: users, organizations, memberships, workspaces, workspace_members
- [x] Alembic migration
- [x] `POST /auth/login`, `GET /auth/me`, JWT dependency
- [x] `POST /organizations` (platform owner), `GET /organizations/me`
- [x] Seed script for platform owner (dev)

**Exit criteria:** login works; protected routes enforced; org/workspace entities persist. *(API completion for org/workspace CRUD continues in Phase 2.)*

## Quick start (local API)

Requires **Docker Desktop** (or compatible engine) for Postgres/Redis, and **Python 3.11+** on `PATH`.

```powershell
cd C:\Users\Yeshi\ProjectRepo\sovereign-knowledge-platform
copy .env.example .env
docker compose up -d postgres redis
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
alembic upgrade head
python scripts/seed.py
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- API docs (Swagger): http://127.0.0.1:8000/docs  
- Health: http://127.0.0.1:8000/health  

**Smoke check:** `POST /auth/login` with `SEED_PLATFORM_OWNER_EMAIL` / `SEED_PLATFORM_OWNER_PASSWORD` from `.env`, then `GET /auth/me` with `Authorization: Bearer <token>`. Platform owner can `POST /organizations` to create an org (creator becomes `org_owner` on that org).

## Environment

See `.env.example`. Minimum: `DATABASE_URL`, `JWT_SECRET`, `JWT_ISSUER`, seed credentials for dev.

## License

Proprietary — King / Sovereign Knowledge Platform.
