# Sovereign Knowledge Platform (SKP)

Private, multi-tenant RAG for SMEs. **Phase deliverables checklist:** `docs/deliverables/PHASE_STATUS.md`. Planning truth in OpenClaw `workspace-architect/` (`PRODUCT_REQUIREMENTS.md`, `MVP_IMPLEMENTATION_PLAN.md`, `DELIVERY_SPEC.md`).

## Phase 0 — locked decisions

| Area | Choice |
|------|--------|
| API | FastAPI (Python 3.11+) |
| DB | PostgreSQL 16 + pgvector extension |
| Cache / hot session | Redis (readiness checks + future hot state) |
| ORM / migrations | SQLAlchemy 2.x + Alembic |
| Auth | JWT (HS256), bcrypt password hashes |
| Frontend | React + Vite (`frontend/`) |
| Inference | Ollama for embeddings / optional LLM generation |
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
- [x] Chat/session/message API slice implemented on top of retrieval substrate with persisted history and citation payloads

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
set SEED_DEMO_USERS=true
python scripts/seed_demo_users.py
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

If an existing virtualenv was created before the bcrypt/passlib compatibility fix, refresh it first:

```powershell
pip uninstall -y bcrypt
pip install -r requirements.txt
```

- API docs (Swagger): http://127.0.0.1:8000/docs  
- Health: http://127.0.0.1:8000/health  
- Readiness (DB + Redis): http://127.0.0.1:8000/health/ready  
- AI readiness (Ollama + model): http://127.0.0.1:8000/health/ai  

### Web UI (React)

```powershell
cd frontend
npm install
npm run dev
```

Open http://127.0.0.1:5173 — sign in with the seeded platform owner, create an organization (platform owner), add a workspace, then open the workspace to upload a PDF and chat. The dev server proxies `/api` to the API (see `frontend/vite.config.ts`).

### Full stack in Docker (API + Postgres + Redis)

Requires **Ollama** on the host (or reachable URL) for embeddings; Compose maps `host.docker.internal:11434` on Docker Desktop.

```powershell
copy .env.example .env
# Set JWT_SECRET, SEED_PLATFORM_OWNER_PASSWORD, and optionally EMBEDDING_OLLAMA_BASE_URL
docker compose -f docker-compose.prod.yml --env-file .env up --build -d
docker compose -f docker-compose.prod.yml exec api runuser -u skp -- python /app/scripts/seed.py
```

This stack now includes `connector-sync-worker`, which drains queued connector sync jobs out-of-band from API request workers.

See `deploy/nginx.example.conf` for TLS + static `frontend/dist` + `/api` upstream.

### GPU-first local stack (RTX 5090 + Ollama in Docker)

**Runbook:** [`docs/deploy/GPU_RTX5090.md`](docs/deploy/GPU_RTX5090.md)

This path runs **Ollama as a GPU container** and points SKP API to it.

Prerequisites:
- Windows + Docker Desktop (WSL2 backend)
- NVIDIA driver with container GPU support enabled in Docker Desktop

```powershell
copy .env.example .env
# set JWT_SECRET and SEED_PLATFORM_OWNER_PASSWORD
powershell -ExecutionPolicy Bypass -File .\scripts\setup_gpu_stack.ps1
```

The script waits until `http://127.0.0.1:8000/health` responds before seeding (first boot can take a few minutes while migrations run).

Manual alternative:

```powershell
docker compose -f docker-compose.gpu.yml --env-file .env up -d --build
docker compose -f docker-compose.gpu.yml exec ollama ollama pull nomic-embed-text
docker compose -f docker-compose.gpu.yml exec ollama ollama pull llama3.2
docker compose -f docker-compose.gpu.yml exec api runuser -u skp -- python /app/scripts/seed.py
```

If `health/ai` reports model missing, pull the model shown in the response and rerun.

**Smoke check:** `POST /auth/login` with `SEED_PLATFORM_OWNER_EMAIL` / `SEED_PLATFORM_OWNER_PASSWORD` from `.env`, then `GET /auth/me` with `Authorization: Bearer <token>`. Platform owner can `POST /organizations` to create an org (creator becomes `org_owner` on that org), `POST /workspaces/org/{org_id}` to create a workspace, then use `PUT /organizations/{org_id}/members` and `PUT /workspaces/{workspace_id}/members` to assign existing users by email. `DELETE /organizations/{org_id}/members/{user_id}` and `DELETE /workspaces/{workspace_id}/members/{user_id}` now support removal while protecting the last org owner / workspace admin from accidental eviction. Workspace members can now `POST /documents/workspaces/{workspace_id}/upload` with a multipart `file` field (PDF-only) to store, chunk, and embed a document, `POST /documents/workspaces/{workspace_id}/search` with `{ "query": "..." }` to run workspace-scoped semantic retrieval, `GET /documents/{document_id}` and `GET /documents/ingestion-jobs/{job_id}` to read document and ingestion-job status (workspace members only), `POST /chat/workspaces/{workspace_id}/sessions` to open a conversation, `GET /chat/workspaces/{workspace_id}/sessions` to list their sessions, `GET /chat/sessions/{session_id}` to fetch history, and `POST /chat/sessions/{session_id}/messages` to persist a grounded answer turn with citation payloads. Chat falls back exactly to `I don't know based on the documents in this workspace.` when retrieval evidence is insufficient, and Ollama-generated answers are now runtime-guarded to require valid inline citation markers or they deterministically degrade to extractive grounded output.

## Current repo milestone

Phase 1 runtime verification is now proven on hardware:
- Alembic connected successfully.
- Seed succeeded with `Seeded platform owner: owner@example.com`.
- `GET /health` returned `{"status":"ok"}`.
- `POST /auth/login` returned a bearer token.
- `GET /auth/me` returned the platform owner with `is_platform_owner=true`.

The repo now has a verified backend/auth foundation plus the persistence-layer substrate for ingestion/chat and auditability. The ingestion/indexing groundwork is now in place: `POST /documents/workspaces/{workspace_id}/upload` accepts a PDF, stores it locally, extracts text, chunks it deterministically, creates `ingestion_jobs` + `documents` records, calls Ollama embeddings, and persists pgvector-backed `document_chunks`. `POST /documents/workspaces/{workspace_id}/search` now embeds the query and returns tenant-safe top-k retrieval hits plus a grounded summary stub for the next answer-generation step. The first chat execution slice is also in place: chat sessions and messages persist in the DB, retrieval stays workspace-scoped, assistant turns store structured citations, and the MVP-required exact fallback string is enforced when evidence is too weak.

## Environment

**Full reference:** [`docs/configuration.md`](docs/configuration.md) (every tunable env var). Copy `.env.example` to `.env`. Minimum: `DATABASE_URL`, `JWT_SECRET`, `JWT_ISSUER`, seed credentials for dev.

**Runtime (non-secret) config for UIs:** `GET /config/public` — embedding model, limits, feature flags (disable with `EXPOSE_PUBLIC_CONFIG=false`).

**Operations / enterprise baseline (optional):**

- `ENVIRONMENT` — `development` | `staging` | `production` (affects log verbosity defaults).
- `CORS_ORIGINS` — comma-separated browser origins for the SPA; avoid `*` when using credentials.
- `LOG_JSON` — `true` for JSON lines (aggregation / SIEM).
- `RATE_LIMIT_ENABLED` / `RATE_LIMIT_PER_MINUTE` — SlowAPI global rate limit per client IP (health endpoints exempt).
- `TRUSTED_HOSTS` — if set, enables `TrustedHostMiddleware` (comma-separated hostnames).

Ingestion/retrieval-specific knobs:
- `DOCUMENT_STORAGE_ROOT` → local file storage root for uploaded PDFs
- `INGESTION_CHUNK_SIZE` → characters per chunk (default `1200`)
- `INGESTION_CHUNK_OVERLAP` → overlap between chunks (default `200`)
- `EMBEDDING_PROVIDER` → currently `ollama`
- `EMBEDDING_MODEL` → default `nomic-embed-text`
- `EMBEDDING_DIMENSIONS` → pgvector size, default `768` (schema-level setting; after changing it, run the latest Alembic migration and re-index embeddings)
- `EMBEDDING_OLLAMA_BASE_URL` → Ollama endpoint, default `http://127.0.0.1:11434`
- `RETRIEVAL_TOP_K` → default semantic retrieval hit count
- `CHAT_MIN_CITATION_SCORE` → minimum top-hit similarity score before chat answers anything other than the exact fallback
- `ANSWER_GENERATION_PROVIDER` → `extractive` by default, or `ollama` for model-generated answers grounded in retrieved citations
- `ANSWER_GENERATION_MODEL` / `ANSWER_GENERATION_OLLAMA_BASE_URL` → Ollama generation settings when provider is `ollama`

## Minimal validation

```powershell
cd C:\Users\Yeshi\ProjectRepo\sovereign-knowledge-platform
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

This includes chat fallback/citation guards and health API tests.

### Optional demo workspace seed

After `scripts/seed.py`, run `SEED_DEMO_WORKSPACE=true python scripts/seed_demo_workspace.py` to ensure the `sterling-vale-llp` org (Sterling & Vale LLP) has a pilot workspace for the platform owner, or create that org if missing (see script for env overrides). To drop other orgs from the database, use `PRUNE_ORGANIZATIONS=true python scripts/prune_organizations_keep_slug.py`.

After `SEED_LAW_FIRM=true python scripts/seed_law_firm.py` (Sterling & Vale LLP sample org), run `SEED_LAW_FIRM_RAG=true python scripts/seed_law_firm_rag.py` to generate demo PDFs in each practice workspace **including General** (`Firm_Operations_and_Billing_Policy.pdf` and others), chunk and embed them (Ollama must serve `EMBEDDING_MODEL`), and insert sample questions plus chat snippets. **Indexed documents** for a workspace appear under **Documents** in the org shell after you select that workspace; **Chats** and **Team** stay disabled until at least one PDF is indexed anywhere in that organization.

## Pre-demo integration smoke lane

### Recommended Windows operator wrapper

For local demo prep on this Windows workstation, use the thin wrapper first:

```powershell
cd C:\Users\Yeshi\ProjectRepo\sovereign-knowledge-platform
powershell -ExecutionPolicy Bypass -File .\scripts\demo_chat_smoke.ps1
```

What the wrapper does:
- verifies `.env`, `.venv`, Python, and Docker availability
- ensures `postgres` and `redis` are up via `docker compose up -d`
- runs `alembic upgrade head`
- runs `scripts/seed.py` so the expected owner exists
- reuses a healthy API already on `127.0.0.1:8000`, or starts `uvicorn app.main:app` if nothing is listening
- verifies `/openapi.json` still exposes the required `/documents/*` and `/chat/*` routes to catch stale processes early
- runs the live end-to-end chat smoke and writes a JSON artifact under `data/smoke/`

Useful wrapper flags:
- `-BaseUrl http://127.0.0.1:8000`
- `-HealthWaitSeconds 60`
- `-OutputJson .\data\smoke\demo-run.json`
- `-ApiLogPath .\data\smoke\demo-api.log`
- `-SkipOpenApiCheck` only if you intentionally want to bypass the stale-process guard
- `-SkipMigrate` or `-SkipSeed` if you already know the environment is ready
- `-NoStartApi` to require an already-running API

### Direct smoke script

Once the API is running on `127.0.0.1:8000` and the seeded owner exists, you can also run the live chat smoke lane directly:

```powershell
cd C:\Users\Yeshi\ProjectRepo\sovereign-knowledge-platform
.\.venv\Scripts\python.exe scripts\e2e_chat_smoke.py --output-json .\data\smoke\latest-chat-smoke.json
```

What this lane now does:
- waits for `/health` before starting
- verifies `/openapi.json` contains the required `/documents/*` and `/chat/*` routes so a stale API process is caught early
- logs in as the seeded owner
- creates an isolated org + two workspaces for the run
- uploads a tiny generated PDF, indexes it, runs retrieval, and exercises grounded chat
- verifies the exact no-evidence fallback string and workspace isolation behavior
- checks persisted chat/document/chunk state directly in Postgres via SQLAlchemy
- prints a JSON summary and optionally writes it to disk for demo evidence

Useful knobs:
- `--base-url http://127.0.0.1:8000`
- `--owner-email ... --owner-password ...`
- `--health-wait-seconds 45`
- `--skip-openapi-check` only if you intentionally do not want the stale-process guard
- env-var equivalents: `SKP_BASE_URL`, `SKP_OWNER_EMAIL`, `SKP_OWNER_PASSWORD`, `SKP_SMOKE_OUTPUT_JSON`

If the script fails with missing `/documents/*` or `/chat/*` routes, the most likely cause is that an older Uvicorn process is still bound to port `8000`.

## License

Proprietary — King / Sovereign Knowledge Platform.
