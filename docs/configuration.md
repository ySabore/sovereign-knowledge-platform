# Configuration reference — Sovereign Knowledge Platform

All server options are loaded from **environment variables** (and optionally `.env` in the process working directory). Names are **case-insensitive** for env vars; Pydantic maps `DATABASE_URL` → `database_url`, etc.

**Source of truth in code:** `app/config.py` (`Settings` class).

**Safe runtime view (no secrets):** `GET /config/public` (disable with `EXPOSE_PUBLIC_CONFIG=false`).

**Stripe billing (Checkout, Customer Portal, webhooks):** step-by-step guide in [configuration/STRIPE.md](configuration/STRIPE.md). For Docker, keep Stripe values in runtime `.env` (not `.env.example`) because compose passes env vars from `.env` into `api`.

---

## Runtime & API metadata

| Variable | Default | Description |
|----------|---------|-------------|
| `ENVIRONMENT` | `development` | `development` \| `staging` \| `production` (logging behavior). |
| `API_TITLE` | `Sovereign Knowledge Platform API` | OpenAPI title. |
| `API_VERSION` | `0.2.0` | OpenAPI version string. |
| `EXPOSE_PUBLIC_CONFIG` | `true` | If `true`, `GET /config/public` returns non-secret tunables. |

---

## Database

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+psycopg://skp:skp@127.0.0.1:5433/skp` | SQLAlchemy URL. |
| `DB_POOL_SIZE` | `10` | SQLAlchemy pool size. |
| `DB_MAX_OVERFLOW` | `20` | Extra connections beyond pool size. |
| `DB_POOL_TIMEOUT_SECONDS` | `30` | Wait for a free connection from the pool. |
| `DATABASE_ECHO` | `false` | Log SQL (dev/troubleshooting only). |

---

## Redis

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_URL` | `redis://127.0.0.1:6380/0` | Used for readiness checks; future cache/session use. |
| `REDIS_SOCKET_TIMEOUT_SECONDS` | `2.0` | Socket timeout for health checks. |

---

## Auth / JWT

| Variable | Default | Description |
|----------|---------|-------------|
| `JWT_SECRET` | *(dev placeholder)* | **Required in production** — HS256 signing key. |
| `JWT_ISSUER` | `sovereign-knowledge-platform` | Token `iss` claim. |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | Access token lifetime. |

### Optional Clerk (RS256 session tokens)

| Variable | Default | Description |
|----------|---------|-------------|
| `CLERK_ENABLED` | `false` | If `true`, `Authorization: Bearer` may carry a Clerk session JWT (verified via JWKS). Email/password JWT (`HS256`) still works when disabled. |
| `CLERK_ISSUER` | *(empty)* | Clerk **Frontend API** URL, e.g. `https://your-instance.clerk.accounts.dev` (used as JWT `iss` and JWKS URL `{issuer}/.well-known/jwks.json`). |
| `CLERK_AUDIENCE` | *(empty)* | If set, JWT `aud` is verified; omit for default session tokens. |

Apply migration `003` so `users.clerk_user_id` exists. Clerk’s default session JWT does **not** include a usable email string—only `sub` (user id). Without an email claim, the API cannot link or create a user and `/auth/me` returns **401**.

In Clerk Dashboard → **Sessions** → **Customize session token**, add JSON such as:

```json
{
  "email": "{{user.primary_email_address.email_address}}"
}
```

(or `"primaryEmail": "{{user.primary_email_address.email_address}}"`). Save, then sign out and back in so a new JWT is minted.

**Docker / self-hosted:** set `CLERK_ENABLED=true` and `CLERK_ISSUER` to your Clerk **Frontend API** URL (Dashboard → **API keys** → *Frontend API URL / issuer*), then restart the API. If `CLERK_ENABLED` is `false`, Clerk JWTs are rejected.

---

## CORS & trusted hosts

| Variable | Default | Description |
|----------|---------|-------------|
| `CORS_ORIGINS` | `*` | Comma-separated origins, or `*`. With `*`, credentials are disabled in CORS middleware. |
| `CORS_ALLOW_METHODS` | `*` | Comma-separated methods or `*`. |
| `CORS_ALLOW_HEADERS` | `*` | Comma-separated header names or `*`. |
| `TRUSTED_HOSTS` | *(empty)* | Comma-separated `Host` values; empty disables `TrustedHostMiddleware`. |

---

## Logging

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | `INFO` | Root log level. |
| `LOG_JSON` | `false` | JSON log lines for aggregators. |

---

## Rate limiting

| Variable | Default | Description |
|----------|---------|-------------|
| `RATE_LIMIT_ENABLED` | `true` | Global SlowAPI switch. |
| `RATE_LIMIT_PER_MINUTE` | `120` | Default per-IP limit (health and `/config/public` exempt). |

---

## Documents & ingestion

| Variable | Default | Description |
|----------|---------|-------------|
| `DOCUMENT_STORAGE_ROOT` | `./data/documents` | PDF storage root. |
| `MAX_UPLOAD_SIZE_MB` | `50` | Maximum PDF upload size. |
| `INGESTION_CHUNK_SIZE` | `1200` | Characters per chunk. |
| `INGESTION_CHUNK_OVERLAP` | `200` | Overlap between chunks. |

---

## Embeddings & Ollama HTTP

| Variable | Default | Description |
|----------|---------|-------------|
| `EMBEDDING_PROVIDER` | `ollama` | Currently only `ollama` is supported. |
| `EMBEDDING_MODEL` | `nomic-embed-text` | Ollama embedding model name. |
| `EMBEDDING_DIMENSIONS` | `768` | Vector dimension (must match DB / migration). |
| `EMBEDDING_OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Ollama base URL for embeddings. |
| `OLLAMA_HTTP_TIMEOUT_SECONDS` | `60` | Timeout for Ollama HTTP calls (embed + generate). |

---

## Retrieval & chat

| Variable | Default | Description |
|----------|---------|-------------|
| `RETRIEVAL_TOP_K` | `5` | Default top-k chunks. |
| `CHAT_MIN_CITATION_SCORE` | `0.55` | Minimum similarity for non-fallback answers. |
| `CHAT_CITATION_QUOTE_MAX_CHARS` | `400` | Truncation length for citation quotes. |
| `ANSWER_GENERATION_PROVIDER` | `extractive` | `extractive` \| `ollama`. |
| `ANSWER_GENERATION_MODEL` | `llama3.2` | Ollama model when provider is `ollama`. |
| `ANSWER_GENERATION_OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Ollama URL for generation. |

---

## Seed scripts (not part of API settings)

| Variable | Description |
|----------|-------------|
| `SEED_PLATFORM_OWNER_EMAIL` | Owner email for `scripts/seed.py`. |
| `SEED_PLATFORM_OWNER_PASSWORD` | Owner password for seed. |

**Clerk users** are created with `is_platform_owner=false`. To make your Clerk account the platform owner after it exists in `users`, run `PROMOTE_PLATFORM_OWNER_EMAIL=you@example.com python scripts/promote_platform_owner.py` (same `DATABASE_URL` as the API), or from Docker: `docker compose exec -e PROMOTE_PLATFORM_OWNER_EMAIL=you@example.com api python scripts/promote_platform_owner.py`. Alternatively, sign in with Clerk using the **same email** as `SEED_PLATFORM_OWNER_EMAIL` *before* that row exists, or `UPDATE users SET is_platform_owner = true WHERE email = '…'` in Postgres.
| `SEED_DEMO_WORKSPACE` | Set `true` for optional `scripts/seed_demo_workspace.py`. |

---

## Frontend (Vite)

**Primary app:** `frontend/` (package `skp-web`). See `frontend/README.md`.

**Legacy archived app:** `frontend-legacy-20260416/` (kept as backup during transition).

Typical local dev: leave `VITE_API_BASE` unset so the browser calls `/api` and Vite proxies to the API (see `frontend/vite.config.ts`).

**Ports:** `frontend` defaults to dev port **5173**. Ensure `CORS_ORIGINS` on the API includes every origin you use (see root `.env.example`; Docker Compose defaults include both local Vite ports and `http://localhost:8080` for the `web` container).

**Production static UI:** `docker-compose.prod.yml` and `docker-compose.gpu.yml` build the `web` service from **`frontend/Dockerfile`** (nginx serves `dist/` and proxies `/api` to the API). Cutover checklist: `docs/frontend-parity-checklist.md`.

---

## GPU deployment notes (RTX 5090)

- Use `docker-compose.gpu.yml` to run `api + postgres + redis + ollama` together.
- Treat this compose path as the canonical deployable artifact for the 5090 machine.
- `OLLAMA_KEEP_ALIVE` is consumed by the Ollama container (not by FastAPI app code).
- Startup helper: `scripts/setup_gpu_stack.ps1`.
- Demo validation helper: `scripts/demo_chat_smoke.ps1`.
- Full runbook (troubleshooting, model pulls): [docs/deploy/GPU_RTX5090.md](deploy/GPU_RTX5090.md).
- Verify readiness via:
  - `/health/ready` (DB + Redis)
  - `/health/ai` (Ollama reachable + embedding model installed)

