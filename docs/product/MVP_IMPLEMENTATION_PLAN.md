# MVP_IMPLEMENTATION_PLAN.md — Sovereign Knowledge Platform

Absorbed from `Downloads\SME-RAG\MVP_IMPLEMENTATION_PLAN.md`, aligned to product name **Sovereign Knowledge Platform**.

## Objective

Deliver a working MVP for a local, **multi-tenant** RAG platform with:

- multi-organization support  
- workspace isolation  
- **PDF-first** ingestion for MVP1 positioning  
- grounded chat with citations  
- **exact** fallback when evidence is insufficient  
- Docker Compose deployment  

## Guiding principles

- Correctness over breadth.  
- Tenant safety over features.  
- End-to-end flows over premature abstractions.  
- Keep MVP infrastructure as simple as the spec allows.

## Delivery phases

### Phase 0: Finalize core decisions

Lock before heavy coding:

- PostgreSQL + pgvector for vectors.  
- React + Vite for frontend.  
- FastAPI for backend.  
- Ollama for embeddings (and generation or compatible local serving).  
- Docker Compose (not Kubernetes for MVP).  
- PDF-first ingestion for MVP1 packaging, even if implementation broadens internally.

### Phase 1: Backend foundation

Scaffold, config, models, migrations, JWT auth, roles, org/workspace membership enforcement.

**Exit:** login works; protected routes enforced; org/workspace entities persist.

### Phase 2: Organization and workspace APIs

Orgs, workspaces, membership endpoints with authz and audit logging for sensitive actions.

**Exit:** platform owner creates orgs; org owner creates workspaces; users attach to workspaces.

### Phase 3: Ingestion pipeline

Upload/storage, job/status lifecycle, parse and normalize source content, chunk, embed, pgvector writes with org/workspace metadata.

**Exit:** the primary pilot ingestion path reaches indexed state; failures are observable; vectors remain correctly scoped.

### Phase 4: Chat and retrieval

Query embed, top-k retrieval **filtered by org_id + workspace_id**, prompt build, LLM generation, citations, fallback behavior, session/message persistence.

**Exit:** grounded answers; cross-workspace/cross-org retrieval blocked; fallback exact per `PRODUCT_REQUIREMENTS.md`.

### Phase 5: Frontend MVP

Login, dashboard, workspace selection, upload UI, chat UI, citations, loading/error states.

**Exit:** end-to-end user journey on happy path.

### Phase 6: Reliability and ops basics

Redis (sessions/cache), structured logging, health, rate limiting, Dockerfiles, Compose, Nginx as specified.

**Exit:** one command brings stack up; health reachable.

### Phase 7: Seed data and demo readiness

Seed orgs/workspaces/users/PDFs; demo script; empty workspace for fallback demo.

**Exit:** repeatable demo with both success and fallback cases.

### Phase 8: Test coverage

Auth, authz, tenant isolation, workspace isolation, ingest smoke, fallback, citation presence, unauthorized access.

**Exit:** critical paths automated.

## Suggested API set (MVP)

- `POST /auth/login`  
- `POST /organizations`  
- `GET /organizations/me`  
- `POST /workspaces`  
- `GET /workspaces`  
- `POST /workspaces/{id}/members`  
- `POST /workspaces/{id}/documents/upload`  
- `GET /documents/{id}/status`  
- `POST /workspaces/{id}/chat`  
- `GET /workspaces/{id}/chat/sessions`  
- `GET /health`  

## Demo script (high level)

1. Login as platform owner; show orgs.  
2. Login as org owner; select/create workspace.  
3. Upload PDF; wait for indexed.  
4. Ask grounded question; show citations.  
5. Switch org; show isolation.  
6. Ask in empty workspace; show **exact** fallback.

## Risks to watch

- Cross-tenant data leak (highest).  
- Unscoped retrieval.  
- Hallucinations when retrieval is weak.  
- Fragile PDF parsing.

## Post-MVP

Connectors, reranking, analytics, billing, Qdrant if needed, SSO.
