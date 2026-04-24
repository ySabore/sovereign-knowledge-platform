# SPRINT.md — Current Execution Sprint

*Last updated: 2026-04-21 America/New_York*

## Sprint window
- **Sprint start:** 2026-04-15
- **Sprint focus window:** current-state hardening, frontend cutover/parity work, and documentation/status alignment with the live codebase

## Sprint goal
Keep the repo’s execution docs truthful while the codebase advances through connector, chat, org-shell, and frontend-shell work so the team is steering against current implementation reality instead of stale documentation.

## What is already complete in this sprint

### Documentation and architecture refresh
- Updated architecture and delivery docs to reflect the live codebase rather than the earliest MVP framing
- Clarified the distinction between planning docs, architecture docs, product docs, and deliverable/status docs
- Established a much cleaner repo narrative around what SKP already does versus what is still being hardened

### Proven implementation baseline
- `python -m unittest discover -s tests -v` currently passes **53/53 tests**
- RBAC coverage remains green, including org-member/workspace-member visibility rules and role enforcement
- Chat grounding behavior remains covered, including exact fallback, citation handling, and answer-generation guards

## Active sprint objectives

### 1. Keep repo truth synced to current feature work
- update planning/status docs as backend/frontend work lands
- prevent drift between repo docs and the working tree
- keep current blockers/watch items anchored to real evidence

### 2. Advance frontend cutover and org-shell usability
- continue reducing monolithic `HomePage.tsx` risk through modular shell extraction
- validate parity between the active frontend and the legacy snapshot
- tighten admin/org/workspace surfaces around connectors, team, chat, and settings

### 3. Continue enterprise/admin/connectors hardening
- preserve RBAC correctness while connector and org-surface breadth expands
- keep audit, metrics, rate-limit, and sync orchestration behavior aligned with the intended product surface
- maintain deployment/config clarity as env/config behavior evolves

### 4. Prepare the codebase for cleaner packaging and demo confidence
- reduce status ambiguity before packaging/demo handoff work
- keep roadmap phrasing aligned with what is already implemented versus what still needs integrated proof

## In progress now
- backend changes across config, models, org/chat/connectors routers, sync orchestration, rate limits, metrics, and SSE chat services
- frontend changes across home shell, connectors, team, org settings, chat sources, dashboard, invite, and styling surfaces
- new DB migrations for chat session/message metadata (`017`, `018`)
- continued frontend cutover staging with `frontend-legacy-20260416/` present in the repo

## Current evidence from the working tree
- Active modified backend files include:
  - `app/config.py`
  - `app/models.py`
  - `app/routers/chat.py`
  - `app/routers/connectors.py`
  - `app/routers/organizations.py`
  - `app/services/chat_sse.py`
  - `app/services/metrics.py`
  - `app/services/nango_client.py`
  - `app/services/rate_limits.py`
  - `app/services/sync_orchestrator.py`
- Active modified frontend files include:
  - `frontend/src/pages/HomePage.tsx`
  - `frontend/src/pages/app/DashboardPage.tsx`
  - `frontend/src/components/TeamManagementPanel.tsx`
  - `frontend/src/components/WorkspaceConnectorsPanel.tsx`
  - `frontend/src/components/chat/ChatSourcesPanel.tsx`
  - `frontend/src/features/home-shell/*`
  - `frontend/src/features/organization-settings/OrganizationSettingsPanel.tsx`
- New migrations present:
  - `alembic/versions/017_chat_session_pinned.py`
  - `alembic/versions/018_chat_message_generation_meta.py`

## Risks
- Repo docs can drift quickly because implementation is moving on both backend and frontend at once
- AI-readiness and Redis-backed behaviors still show local-environment fragility in tests when external services are not reachable by hostname, even though the suite remains green overall
- `HomePage.tsx` remains a hotspot until cutover/parity work is fully stabilized
- `frontend-legacy-20260416/` is useful for safety but increases repo noise until archive/cutover is complete

## Definition of done for this sprint slice
- planning docs describe the live repo rather than the earlier bootstrap phase
- current blockers/watch items reflect real evidence from tests and the working tree
- roadmap phrasing matches current product breadth
- Forge/Apex planning context no longer points at already-finished foundation work
- the team can identify the actual next engineering move without re-auditing the whole repo first
