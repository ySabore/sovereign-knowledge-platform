# ROADMAP.md — Sovereign Knowledge Platform

*Last updated: 2026-04-09 18:57 America/New_York*

## Daily standup — 2026-04-08

### What changed materially since the previous roadmap update
- The architect-side status docs had drifted behind the real repo state.
- Repo evidence already contains both:
  - Phase 1 runtime proof in `docs/planning/RUNTIME_VERIFICATION_2026-04-03.md`
  - End-to-end ingestion, retrieval, grounded chat, exact fallback, and workspace isolation proof in `docs/planning/E2E_CHAT_SMOKE_2026-04-03.md`
- In the last 3 days, the product surface expanded significantly:
  - Vite/React frontend with landing page, dashboard, workspace chat, admin pages, Clerk pages, and built assets
  - backend support for admin metrics, billing, connectors, document permissions, Clerk JWT linking, SSE chat, runtime config, structured logging, rate limits, and health/readiness/AI-readiness
  - deployment packaging via `Dockerfile`, `docker-compose.prod.yml`, `docker-compose.gpu.yml`, nginx example config, and setup/smoke scripts
- Validation signal improved today: `python -m unittest discover -s tests -v` passed **24/24 tests**.

### Current true status
- **Milestone A — Foundation & Runtime Verification:** Complete and evidenced.
- **Milestone B — Demoable Ingestion + Retrieval Happy Path:** Complete with fresh Docker smoke proof.
- **Milestone C — Demo UX:** Substantially advanced; Docker is canonical deployment; frontend verification next.
- **Milestone D — Client-Ready Hardening:** In progress; RBAC tightened; admin surfaces need UI guards validation.

## Milestone A — Foundation & Runtime Verification

**Status:** Complete

Delivered:
- Backend runtime verified locally.
- Database migration path verified.
- Seed path verified.
- Auth flow verified with platform owner login and `/auth/me` proof.
- Health endpoint verified.

Evidence captured:
- `docs/planning/RUNTIME_VERIFICATION_2026-04-03.md`

## Milestone B — Demoable Ingestion + Retrieval Happy Path

**Status:** Functionally proven, needs fresh regression proof on current code

Delivered historically:
- Upload a document.
- Parse and chunk content.
- Generate embeddings via Ollama `nomic-embed-text`.
- Persist vectors in PostgreSQL + pgvector.
- Retrieve grounded context for chat queries.
- Persist chat sessions/messages with citations.
- Enforce exact no-evidence fallback.
- Prove workspace isolation in smoke flow.

Evidence captured:
- `docs/planning/E2E_CHAT_SMOKE_2026-04-03.md`

Immediate focus:
- Re-run the smoke lane on the current repo state and capture a new dated artifact.

## Milestone C — Demo UX

**Status:** In progress, materially ahead of prior roadmap

Delivered in repo:
- Public landing page / marketing entry
- Dashboard and workspace navigation
- Workspace chat page with citation-oriented UX
- Admin navigation and admin page set
- Frontend build output under `frontend/dist`

Still needed:
- Fresh browser-backed validation of the current upload + chat happy path
- Confirmation that the current UI matches the widened backend contract cleanly

## Milestone D — Client-Ready Hardening

**Status:** In progress

Delivered in repo:
- Structured logging and request correlation
- Security headers, CORS, trusted hosts
- Rate limiting
- Redis readiness and AI-readiness checks
- Docker image and Compose deployment variants
- GPU-first local deployment path
- Billing, connector, permissions, webhook, and admin-metrics surfaces

Still needed:
- Fresh integrated runtime proof on current code
- Validation of external integration paths where enabled
- Cleanup of repo hygiene and commit boundaries before packaging/demo handoff

## Immediate priorities
DONE:
- Fresh dated end-to-end smoke artifact on Docker stack — verified 2026-04-09
- RBAC tightening for member-list visibility — commit `615897a`
- Docker-first deployment established — commit `7fdf62e`

NEXT:
1. Validate the current Vite frontend against the live API for demo-critical flows.
2. Reduce regression risk by reconciling generated/uncommitted artifacts and clarifying commit boundaries.
3. Then continue hardening the enterprise/admin/billing/connectors surface.

## Standup check — 2026-04-08 22:57
- Milestone A remains complete and evidenced.
- Milestone B remains historically proven, but still needs fresh current-state regression proof.
- Milestone C is still advancing well, but remains blocked on fresh browser-backed verification rather than missing implementation.
- Milestone D remains in progress, with breadth outpacing integrated proof.
- No new roadmap-level blocker requiring King surfaced during tonight's review.

## Guardrail
Do not treat the platform as unproven anymore. The real gate is now **current-state regression proof**, not first-time capability proof.
