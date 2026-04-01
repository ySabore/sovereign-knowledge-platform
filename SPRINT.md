# SPRINT

## Current sprint
Backend Phase 2 completion slice: close the most important organization/workspace management gaps so the authenticated multi-tenant skeleton is demoable beyond login.

## Next
- [x] Create repo-local `SPRINT.md` so execution status lives with the codebase
- [x] Add authenticated `GET /organizations/{org_id}`
- [x] Add authenticated `PATCH /organizations/{org_id}` for org owners
- [x] Add authenticated `GET /workspaces/me`
- [x] Add authenticated `GET /workspaces/{workspace_id}`
- [x] Add authenticated `PATCH /workspaces/{workspace_id}` for workspace admins
- [x] Update README / decisions docs to reflect expanded Phase 2 API surface
- [ ] Add user invitation / membership assignment flows
- [ ] Add document ingestion domain models and endpoints
- [ ] Add automated API tests

## In progress
- No active in-progress items at commit time

## Done
- Phase 0/1 scaffold: config, Compose, models, Alembic, auth, seed flow
- Organization creation + self-listing
- Workspace creation within org + org-scoped workspace listing
- Phase 2 read/update endpoints for organizations and workspaces

## Risks
- No automated test harness yet; changes validated via import/route loading only
- Membership management is still manual/seed-driven, which limits end-to-end org collaboration demos
- No slug/status validation beyond basic API constraints

## Next up after this sprint slice
1. Membership/invitation endpoints
2. Ingestion job + document metadata models
3. Retrieval pipeline skeleton
