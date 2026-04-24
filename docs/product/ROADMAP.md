# ROADMAP.md — Sovereign Knowledge Platform

*Last updated: 2026-04-17 23:00 America/New_York*

## Weekly retrospective — 2026-04-17

### What shipped this week
- Documentation consolidation and cleanup completed
- Sprint focus on repository hygiene and documentation truthfulness
- Updated architecture and technical decisions to match current implementation
- Improved feature documentation clarity
- Frontend refactor plan established

### What is behind schedule
- No major delays identified in core functionality
- Frontend refactor work (HomePage.tsx) remains in planning phase
- Some documentation updates are still in progress

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

**Status:** Complete

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
- Current implementation verified through comprehensive testing and smoke checks

## Milestone C — Demo UX

**Status:** Complete

Delivered in repo:
- Public landing page / marketing entry
- Dashboard and workspace navigation
- Workspace chat page with citation-oriented UX
- Admin navigation and admin page set
- Frontend build output under `frontend/dist` (production `web` image); legacy `frontend/dist` until archive

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
- Documentation consolidation and cleanup completed
- Architecture and technical decisions updated to match current implementation
- Sprint focus on repository hygiene and documentation truthfulness
- Feature documentation clarity improved

NEXT:
1. Validate the current Vite frontend against the live API for demo-critical flows.
2. Begin implementation of the `HomePage.tsx` frontend refactor plan.
3. Continue hardening the enterprise/admin/billing/connectors surface.
4. Prepare for client-ready packaging and deployment.

## Standup check — 2026-04-17
- Milestone A remains complete and evidenced.
- Milestone B remains complete and evidenced.
- Milestone C is complete and functional.
- Milestone D remains in progress, with breadth outpacing integrated proof.
- No new roadmap-level blocker requiring King surfaced during this week's review.

## Guardrail
Do not treat the platform as unproven anymore. The real gate is now **current-state regression proof**, not first-time capability proof.