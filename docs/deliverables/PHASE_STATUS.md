# PHASE_STATUS.md — SKP Delivery Status

*Last updated: 2026-04-15 America/New_York*

Legend: **Done** | **Partial** | **Planned**

This file tracks delivery status against the current codebase reality, not older planning assumptions.

## Phase 0 — Core platform decisions

| Deliverable | Status | Notes |
|-------------|--------|--------|
| FastAPI + Postgres/pgvector + Redis + React/Vite | **Done** | Core stack is implemented and live in repo |
| Docker-first deployment model | **Done** | `docker-compose.gpu.yml` is the current canonical deployment artifact |
| Self-hosted / sovereign deployment posture | **Done** | Reflected in architecture, deployment, and product docs |

## Phase 1 — Backend foundation

| Deliverable | Status | Notes |
|-------------|--------|--------|
| JWT auth and protected routes | **Done** | Local auth is implemented |
| Optional Clerk auth path | **Done** | Clerk JWT support and related frontend pages exist |
| SQLAlchemy + Alembic data model | **Done** | Mature schema already extends beyond earliest MVP slices |
| Health, readiness, and AI-readiness endpoints | **Done** | Present in backend and deployment flows |

## Phase 2 — Organizations, workspaces, and access control

| Deliverable | Status | Notes |
|-------------|--------|--------|
| Org CRUD and membership | **Done** | `app/routers/organizations.py` |
| Workspace CRUD and membership | **Done** | Same router module |
| Org invites | **Done** | Invite issue/resend/revoke/accept flows implemented |
| Audit logging for sensitive mutations | **Done** | Audit log writes are wired for major org/workspace actions |
| RBAC tightening for membership visibility | **Done** | Prior regression fix and test evidence already recorded |

## Phase 3 — Knowledge ingestion and indexing

| Deliverable | Status | Notes |
|-------------|--------|--------|
| Upload persistence, extraction, chunking, embeddings, vector storage | **Done** | Core ingestion pipeline exists |
| Ingestion jobs and document status APIs | **Done** | Document and job status endpoints exist |
| Raw text / connector-style ingestion path | **Done** | `ingest_document()` supports reusable text-based ingestion |
| PDF-only MVP wording | **Partial / outdated as wording** | Product messaging still references PDF-first, but implementation has moved beyond that |
| Expanded multi-format ingestion behavior | **Partial to Done** | Codebase and tests indicate broader support; feature docs should continue being tightened |

## Phase 4 — Retrieval and grounded chat

| Deliverable | Status | Notes |
|-------------|--------|--------|
| Workspace-scoped retrieval | **Done** | Retrieval remains tenant/workspace scoped |
| Persisted chat sessions and messages | **Done** | Chat history is modeled and stored |
| Citation-bearing answers | **Done** | Assistant messages store structured citations |
| Exact no-evidence fallback | **Done** | Product invariant preserved |
| SSE chat streaming | **Done** | Streaming route and frontend integration exist |
| Retrieval strategy options | **Done** | Heuristic, hybrid, and rerank modes are implemented |
| Cohere rerank support | **Done** | Optional hosted rerank exists |
| Multi-provider answer generation | **Done** | Extractive, Ollama, OpenAI, and Anthropic paths exist |

## Phase 5 — Frontend product surface

| Deliverable | Status | Notes |
|-------------|--------|--------|
| Marketing/public landing flow | **Done** | Present in frontend routes |
| Login and protected shell | **Done** | Present and wired |
| Organization/workspace shell | **Done** | Large but functional admin/operator shell exists |
| Workspace chat UX | **Done** | `DashboardPage.tsx` and related chat components |
| Admin pages | **Done** | Documents, connectors, team, billing, audit, settings pages exist |
| Frontend architectural cleanliness | **Partial** | `HomePage.tsx` is a known refactor hotspot |

## Phase 6 — Operations and enterprise baseline

| Deliverable | Status | Notes |
|-------------|--------|--------|
| Structured logging | **Done** | JSON logging optional |
| Request correlation | **Done** | Request ID middleware |
| Security headers | **Done** | Middleware present |
| Rate limiting | **Done** | SlowAPI plus org-aware rate limits |
| CORS / trusted hosts support | **Done** | Config-driven |
| Docker image and compose deployment variants | **Done** | Multiple compose paths exist |
| GPU-first local deployment path | **Done** | Deployment runbook and compose artifact exist |

## Phase 7 — Integrations and platform extensions

| Deliverable | Status | Notes |
|-------------|--------|--------|
| Connector activation model | **Done** | Integration connector rows and activation flow exist |
| Connector sync orchestration | **Done** | Sync orchestrator exists |
| Billing surface | **Partial** | Backend and frontend surfaces exist; live integration proof is still a separate concern |
| Webhook surfaces | **Done** | Clerk and Stripe webhook routes exist |

## Phase 8 — Documentation and repo clarity

| Deliverable | Status | Notes |
|-------------|--------|--------|
| Current architecture docs | **Done** | Refreshed to match implementation |
| Codebase map | **Done** | Added |
| Ingestion/retrieval architecture doc | **Done** | Added |
| Frontend refactor plan | **Done** | Added |
| Docs consolidation and pointer cleanup | **In Progress** | Root duplicates reduced; more cleanup still possible |

## Current watch items

### 1. Documentation wording drift
Some older product/demo docs still describe a narrower system than the current codebase actually implements.

### 2. Frontend maintainability / cutover
**Legacy `frontend/`:** `HomePage.tsx` remains the biggest structural risk (monolithic shell).

**`frontend/`:** shell logic is modularized under `src/features/home-shell/`; remaining risk is **parity**, **operational burn-in**, and avoiding re-expansion of `HomePage.tsx`. Track readiness in `docs/frontend-parity-checklist.md` and `docs/frontend-cutover-runbook.md`.

### 3. Repo hygiene
Broad working-tree changes, generated assets, and demo corpora still need ongoing organization and selective cleanup.

## Bottom line

SKP is no longer in a “can it do ingestion/retrieval/chat?” phase.

The current repo already demonstrates:
- tenant administration
- ingestion and indexing
- grounded retrieval and chat
- connector scaffolding and sync
- operator/admin surfaces
- deployable Docker-first runtime

The main work now is:
- documentation truthfulness
- structural cleanup
- UX verification and refactor
- packaging and hardening discipline

