# NEXT_TASK.md — Sovereign Knowledge Platform

_Last updated: 2026-04-09 18:57 America/New_York_

## Current next task
Verify the frontend handles the backend contract correctly and complete browser-backed validation of the `/organizations` flow.

## Background
- Docker is now the canonical deployment path.
- RBAC member-list restrictions are in place.
- Demo smoke passes end-to-end on Docker stack.
- Frontend may expect `/admin/*` endpoints; need to confirm graceful degradation or add guards.

## Definition of done
- Log in successfully with seeded accounts (org-admin, ws-admin, org-member, ws-member)
- For each role, verify under `/organizations`:
  - organization list visibility
  - workspace list visibility
  - workspace chat opens correctly
  - member-management surfaces respect RBAC (non-admins should not see full member lists)
  - any admin panels degrade gracefully if backend endpoints unavailable
- Capture exact failures with route, role, UI surface
- End with ranked fix order

## Why this comes first
Fresh backend smoke proof is complete on Docker. Remaining demo risk is frontend contract alignment and graceful handling of backend endpoint availability.

## Immediate execution notes
1. Treat `data/smoke/E2E_CHAT_SMOKE_2026-04-09.json` as backend proof already complete.
2. Prioritize `/organizations` over `/admin` routes.
3. Use the seeded role accounts, not only `owner@example.com`, so RBAC and non-owner behavior are exercised.
4. Assume the running backend shape is authoritative for debugging the current live stack.
5. If a page depends on `/admin/documents/{org_id}` or `/admin/metrics/summary`, log the mismatch explicitly instead of hand-waving it.
6. After the frontend pass, open a separate investigation into Forge reliability after the model change.
