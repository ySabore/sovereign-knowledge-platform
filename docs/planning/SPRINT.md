# SPRINT.md — Sovereign Knowledge Platform

_Last updated: 2026-04-09 16:00 America/New_York_

## Sprint Goal
Stabilize and package the already-proven SKP demo path on the current repo state: auth, org/workspace setup, PDF ingestion, retrieval-grounded chat, and demo-ready UI/ops surfaces.

## Reconciled current state

### What is materially true now
- The backend foundation is no longer hypothetical. `docs/planning/RUNTIME_VERIFICATION_2026-04-03.md` records successful migration connectivity, seed, `/health`, `/auth/login`, and `/auth/me` proof.
- The core ingestion → retrieval → chat lane is also already proven historically. `docs/planning/E2E_CHAT_SMOKE_2026-04-03.md` records a successful live smoke run including upload, indexing, retrieval hit, grounded cited answer, exact no-evidence fallback, persistence checks, and workspace isolation.
- Since then, the repo expanded substantially:
  - production-shaped runtime config, logging, request ID middleware, security headers, rate limiting, health/readiness/AI readiness
  - richer domain schema and migrations through billing, RBAC/document permissions, ingestion metadata, connectors, and query logs
  - additional API surfaces for billing, connectors, admin metrics, public config, Clerk JWT support, Stripe/Clerk webhooks, and SSE chat aliasing
  - React + Vite frontend with landing page, dashboard, workspace chat, admin views, Clerk pages, and built static assets under `frontend/dist`
  - Docker packaging for prod and GPU-first local deployment plus smoke/setup scripts
- Validation run today: `python -m unittest discover -s tests -v` passed with **24/24 tests green**.

## What changed today
- Backend surface expanded beyond the earlier MVP lane: billing routes, connector activation/sync endpoints, SSE chat aliasing, Clerk JWT support, request limiting, structured logging, middleware, and additional migrations for RBAC, billing, ingestion metadata, and query logs are now in the tree.
- Frontend moved into a more complete React + Vite app shape with Clerk-aware bootstrapping, stronger landing/dashboard flows, admin navigation, analytics views, billing/team/connectors pages, and shared chat/layout components.
- Packaging and deployment assets were added or widened: `Dockerfile`, `docker-compose.prod.yml`, `docker-compose.gpu.yml`, deploy docs/assets, smoke scripts, seeding helpers, and runtime configuration docs.
- No new commits were recorded since `2026-04-08 06:00`; tonight's state is still a broad local working tree rather than reviewable committed slices.
- A fresh verification pass tonight reconfirmed `python -m unittest discover -s tests -v` at **24/24 green**.

## What is not yet freshly re-proven on today's code
- External integration paths (Stripe, Nango/connectors, Clerk webhook handling) are present but not proven live in repo evidence.
- Full trustworthy browser-path verification of the Vite UI against the current backend is still not captured.
- The exact `/organizations` behavior across seeded non-owner roles is not yet recorded as a completed artifact.

## Active risks
- **Regression risk after large surface expansion:** mitigated by fresh Docker smoke proof on 2026-04-09 — upload, indexing, retrieval, grounded cited answer, exact no-hit fallback, and workspace isolation verified.
- **Uncommitted breadth risk:** many tracked and untracked files are in flight at once, which raises review, rollback, and packaging risk.
- **Frontend integration confidence gap:** the Vite UI is live, but a trustworthy browser-backed `/organizations` pass is still incomplete.
- **Frontend/backend contract drift risk:** the running API has `/admin/*` endpoints in code but may need UI guards for graceful degradation.
- **External integration proof gap:** Stripe, Clerk, and connector plumbing exist in code, but live integration evidence is still missing.

## Task status
- [x] Re-scan repo and reconcile actual implementation state against stale architect docs.
- [x] Confirm current automated validation signal, `python -m unittest discover -s tests -v` passed 24/24 tests on 2026-04-08.
- [x] Reconfirm tonight that the same test suite still passes 24/24 on the current working tree.
- [x] Refresh planning docs to match the current implementation direction and risk posture.
- [x] Expand backend surface for billing, connectors, runtime/config middleware, and chat/API integration paths.
- [x] Expand frontend surface for React + Vite app shell, admin flows, analytics/dashboard pages, and Clerk-aware bootstrapping.
- [x] Add production/GPU packaging assets, deployment docs, seed/smoke helpers, and related repo scaffolding.
- [x] Run daily standup review against current sprint, roadmap, and blockers docs.
- [x] Re-run the live smoke lane on the current repo state and save a fresh dated artifact.
- [x] Tighten RBAC for org/workspace membership visibility (commit `615897a`).
- [x] Make Docker the canonical deployment and validation path (commit `7fdf62e`).
- [ ] Complete a trustworthy browser-backed verification of `/organizations` across seeded org/workspace admin/member roles.
- [ ] Verify frontend gracefully handles any admin endpoint contract gaps.
- [ ] Clean up repo hygiene around generated artifacts and commit boundaries.
- [ ] Re-prove or trim external integration paths before relying on them in a client demo.

## Recommended next sequence
1. ~~Re-run the live smoke lane on the current repo state and save a fresh dated artifact.~~ — Completed 2026-04-09.
2. ~~Complete the `/organizations`-first frontend verification across seeded non-owner roles and log exact failures.~~ — Deferred; focus on backend contract alignment first.
3. Resolve the current frontend/backend contract drift around missing `/admin/*` endpoints or guard those surfaces properly.
4. Decide and tighten intended RBAC behavior for org membership visibility.
5. Split the broad local working tree into reviewable commit slices and clean up generated artifacts, including `dist` output.
6. Investigate Forge reliability after the model change before depending on it for future critical verification work.

## Afternoon plan (2026-04-09)
1. **Backend contract alignment** — Add missing `/admin/documents/{org_id}` and `/admin/metrics/summary` endpoints OR add proper UI guards/fallbacks where those routes are expected.
2. **RBAC tightening** — Review and fix org membership visibility to restrict reads to appropriate roles only.
3. **Repo hygiene** — Commit the working tree changes in reviewable slices; separate generated artifacts from source changes.
4. **Frontend verification prep** — Once backend contract is aligned, run browser-backed verification of the `/organizations` flow.
5. **External integration triage** — Document which external paths (Stripe, Clerk webhooks, Nango) are demo-critical vs future work.

## Current proven state
- Unit tests: 24/24 passing (includes new RBAC regression test).
- Integration smoke test: `scripts/e2e_chat_smoke.py` executed successfully via Docker on 2026-04-09.
- Smoke wrapper: `scripts/demo_chat_smoke.ps1` now Docker-first.
- Smoke artifacts: `data/smoke/E2E_CHAT_SMOKE_docker_verified.json`
- Docker stack: `docker-compose.gpu.yml` is canonical for 5090 deployment.
- Verified: login, org/workspace creation, PDF upload/indexing, grounded cited answer, exact no-hit fallback ("I don't know based on the documents in this workspace."), workspace isolation, RBAC member-list restrictions.

## Standup note
- Tonight's standup did not uncover a new decision blocker for King.
- The highest-value unresolved work remains verification and repo hygiene, not architecture churn.
- ROADMAP location confirmed at `docs/product/ROADMAP.md`; sprint assumptions should keep using that path unless planning docs are reorganized.
