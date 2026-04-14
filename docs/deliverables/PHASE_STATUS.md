# PHASE_STATUS — SKP MVP vs implementation

_Last updated: 2026-04-09_

Legend: **Done** | **Partial** | **Planned**

## Phase 0 — Core decisions

| Deliverable | Status | Notes |
|-------------|--------|--------|
| Stack: FastAPI, Postgres+pgvector, Redis, Ollama, React+Vite | **Done** | `README.md`, `DELIVERY_SPEC.md` |
| PDF-only MVP1 | **Done** | `app/routers/documents.py` |
| Compose-first deploy | **Done** | `docker-compose.yml`, `docker-compose.prod.yml`, `Dockerfile` |

## Phase 1 — Backend foundation

| Deliverable | Status | Notes |
|-------------|--------|--------|
| JWT auth, users, migrations | **Done** | Alembic, `app/routers/auth.py` |
| Protected routes | **Done** | `app/deps.py` |

## Phase 2 — Organizations & workspaces

| Deliverable | Status | Notes |
|-------------|--------|--------|
| Org CRUD, membership | **Done** | `app/routers/organizations.py` |
| Workspace CRUD, membership | **Done** | Same module |
| Audit logs (sensitive mutations) | **Done** | `AuditLog` writes |

## Phase 3 — PDF ingestion

| Deliverable | Status | Notes |
|-------------|--------|--------|
| Upload, chunk, embed, pgvector | **Done** | `app/services/ingestion.py`, embeddings |
| Job/document status API | **Done** | `GET /documents/{document_id}`, `GET /documents/ingestion-jobs/{job_id}` |

## Phase 4 — Chat & retrieval

| Deliverable | Status | Notes |
|-------------|--------|--------|
| Workspace-scoped retrieval | **Done** | `app/services/retrieval.py` |
| Chat sessions + citations + exact fallback | **Done** | `app/services/chat.py` |

## Phase 5 — Frontend MVP

| Deliverable | Status | Notes |
|-------------|--------|--------|
| Login, org/workspace selection | **Done** | `frontend/` — Vite + React + TS |
| PDF upload, chat, citations UI | **Done** | `WorkspaceChatPage.tsx` |
| Browser-backed `/organizations` verification on current live stack | **Partial** | Frontend/backend are live and seeded role/API behavior is verified, but a trustworthy completed browser pass is still outstanding. |

## Phase 6 — Reliability & ops (enterprise baseline)

| Deliverable | Status | Notes |
|-------------|--------|--------|
| Structured logging (JSON optional) | **Done** | `LOG_JSON`, `app/logging_config.py` |
| Request correlation | **Done** | `X-Request-ID` middleware |
| Security headers | **Done** | `SecurityHeadersMiddleware` |
| Rate limiting | **Done** | SlowAPI; `RATE_LIMIT_*`; health exempt |
| Redis readiness | **Done** | `GET /health/ready` |
| Docker image (non-root runtime) | **Done** | `Dockerfile`, `scripts/docker-entrypoint.sh` |
| Compose stack | **Done** | `docker-compose.prod.yml` |
| CORS / trusted hosts | **Done** | `CORS_ORIGINS`, `TRUSTED_HOSTS` |
| Edge proxy example | **Done** | `deploy/nginx.example.conf` |

## Phase 7 — Seed & demo

| Deliverable | Status | Notes |
|-------------|--------|--------|
| Platform owner seed | **Done** | `scripts/seed.py` |
| Optional demo org/workspace | **Done** | `scripts/seed_demo_workspace.py` (`SEED_DEMO_WORKSPACE=true`) |

## Phase 8 — Tests

| Deliverable | Status | Notes |
|-------------|--------|--------|
| Chat unit tests | **Done** | `tests/test_chat_service.py` |
| Health tests | **Done** | `tests/test_health.py` |
| Tenant isolation integration tests | **Partial** | Extend with DB fixtures as needed |

## Current live-stack notes

- Fresh backend smoke proof exists at `data/smoke/E2E_CHAT_SMOKE_2026-04-09.json`.
- The running API currently exposes org/workspace/member routes used by `/organizations`.
- The running API does **not** currently expose `/admin/documents/{org_id}` or `/admin/metrics/summary`, so any frontend surfaces expecting those routes need either backend alignment or UI guards/fallbacks.
- Current live API behavior appears to allow org membership reads more broadly than intended across seeded roles and should be reviewed as an RBAC issue.

## Enterprise follow-ups (your decisions)

- IdP / SSO, per-tenant secrets, HSM-backed JWT signing  
- HA Postgres / Redis, horizontal API replicas + shared rate-limit store  
- Full OpenTelemetry traces, WAF, SOC2 control mapping  
- Air-gapped bundles and signed release artifacts  
