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

## Phase 1–2 status (backend foundation)

- [x] Repo scaffold, config, Docker Compose (Postgres + Redis)
- [x] SQLAlchemy models: users, organizations, memberships, workspaces, workspace_members
- [x] Alembic migration
- [x] `POST /auth/login`, `GET /auth/me`, JWT dependency
- [x] `POST /organizations`, `GET /organizations/me`, `GET /organizations/{org_id}`, `PATCH /organizations/{org_id}`
- [x] `POST /workspaces/org/{org_id}`, `GET /workspaces/org/{org_id}`, `GET /workspaces/me`, `GET /workspaces/{workspace_id}`, `PATCH /workspaces/{workspace_id}`
- [x] Membership management for existing users: `GET/PUT/DELETE /organizations/{org_id}/members`, `GET/PUT/DELETE /workspaces/{workspace_id}/members`
- [x] Seed script for platform owner (dev)
- [x] Phase-3 core ORM entities added: `ingestion_jobs`, `documents`, `document_chunks`, `chat_sessions`, `chat_messages`, `audit_logs`
- [x] Audit log writes added for sensitive org/workspace/member mutations

**Exit criteria:** login works; protected routes enforced; org/workspace entities persist; owners/admins can inspect and update their org/workspace metadata; org owners and workspace admins can assign existing users to the right tenant/workspace scope.

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

If an existing virtualenv was created before the bcrypt/passlib compatibility fix, refresh it first:

```powershell
pip uninstall -y bcrypt
pip install -r requirements.txt
```

- API docs (Swagger): http://127.0.0.1:8000/docs  
- Health: http://127.0.0.1:8000/health  

**Smoke check:** `POST /auth/login` with `SEED_PLATFORM_OWNER_EMAIL` / `SEED_PLATFORM_OWNER_PASSWORD` from `.env`, then `GET /auth/me` with `Authorization: Bearer <token>`. Platform owner can `POST /organizations` to create an org (creator becomes `org_owner` on that org), `POST /workspaces/org/{org_id}` to create a workspace, then use `PUT /organizations/{org_id}/members` and `PUT /workspaces/{workspace_id}/members` to assign existing users by email. `DELETE /organizations/{org_id}/members/{user_id}` and `DELETE /workspaces/{workspace_id}/members/{user_id}` now support removal while protecting the last org owner / workspace admin from accidental eviction.

## Current repo milestone

The repo now has the persistence-layer substrate for ingestion/chat and auditability, but it still needs the next Alembic migration applied before those new tables exist in the database. After migration, the next pilot step is a PDF upload endpoint that creates `documents` + `ingestion_jobs` records behind a clean storage/parser interface.

## Environment

See `.env.example`. Minimum: `DATABASE_URL`, `JWT_SECRET`, `JWT_ISSUER`, seed credentials for dev.

## License

Proprietary — King / Sovereign Knowledge Platform.
