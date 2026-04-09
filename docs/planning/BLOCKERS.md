# BLOCKERS.md — Sovereign Knowledge Platform

*Last updated: 2026-04-09 16:00 America/New_York*

## Active Blockers

### 1. Fresh current-state smoke proof is missing after major repo expansion

**STATUS: RESOLVED 2026-04-09**

- **Status:** Resolved — fresh smoke proof completed
- **What is now proven:**
  - `scripts/e2e_chat_smoke.py` executed successfully on current codebase (run_id: d7aae836)
  - Fresh dated artifact saved: `data/smoke/E2E_CHAT_SMOKE_2026-04-09.json`
  - Verified paths: `/health`, OpenAPI documents/chat endpoints, Ollama preflight, org/workspace creation, PDF upload/indexing, retrieval search, grounded cited answer
  - Verified behaviors:
    - Hit question answer: "Project Atlas retention period is 45 days" with citation
    - No-hit fallback: "I don't know based on the documents in this workspace."
    - Workspace isolation: isolated workspace correctly returns no-hit fallback
    - Persistence: 4 messages in evidence workspace, 2 in isolated workspace
    - Document/chunk counts: 1 document, 1 chunk in evidence workspace; 0 chunks in isolated
- **Impact:** The core SKP backend capability is now re-proven on the widened codebase. Demo regression risk for backend chat/ingestion path is closed.
- **What is still not proven:**
  1. Browser-backed Vite frontend verification against live API (next priority)
  2. External integrations (Stripe billing, Nango connectors, Clerk webhooks)
  3. Full admin UI paths

## Resolved Blockers (2026-04-09)

### 1. RBAC exposure — org membership reads too broad

- **Status:** Resolved — commit `615897a`
- **Fix:** Tightened `list_organization_members` to require org_owner; tightened `list_workspace_members` to require workspace_admin.
- **Evidence:** `tests/test_rbac_membership_visibility.py` passes; non-owner roles now receive 403 on member-list endpoints.

## Active Blockers (2026-04-09 evening)

### 1. Frontend/backend contract consistency

- **Status:** Watch item — not a demo blocker
- **Context:** `/admin/*` endpoints exist in code but UI may expect them on live API; backend routes are present, may need UI guards for graceful degradation if not exposed.
- **Next step:** Verify frontend handles missing admin endpoints gracefully; add UI guards if needed.

## Next active blockers / watch items

### A. Frontend integration confidence gap (awaiting backend alignment)

- **Status:** Waiting on blocker #1
- **Impact:** Browser-backed verification cannot be trustworthy until the frontend/backend contract is aligned.
- **Next step:** Revisit after admin endpoint decision and implementation.

### B. External integration proof gap

- **Status:** Watch item
- **Impact:** Billing, connectors, and webhook plumbing exist but have no live integration evidence.
- **Next step:** Prioritize only after frontend happy path is verified.

## Resolved Blockers

### A. Local runtime verification

- **Status:** Resolved on 2026-04-03
- **Evidence:**
  - Alembic upgrade/connectivity succeeded.
  - Seed completed and created `owner@example.com`.
  - `/health` returned OK.
  - `/auth/login` returned a bearer token.
  - `/auth/me` confirmed the seeded platform owner.

### B. First end-to-end ingestion / retrieval / chat proof

- **Status:** Resolved on 2026-04-03
- **Evidence:**
  - `docs/planning/E2E_CHAT_SMOKE_2026-04-03.md` records successful upload, indexing, retrieval, grounded cited answer, exact no-hit fallback, persistence checks, and workspace isolation.

## Watch Items

### Embedding service / Ollama readiness

- **Status:** Watch item
- **Impact:** Still the most likely operational failure point for any new smoke or demo run.
- **Observed evidence:**
  - Today’s test signal included successful `/health/ai` behavior.
  - The live smoke lane still depends on the configured embedding model actually being available to the runtime environment used for the smoke.
- **Next recovery step:**
  - Check `/health/ai` immediately before the fresh smoke run and pull the required model if missing.

### Frontend integration confidence gap

- **Status:** Watch item
- **Impact:** The frontend is materially more complete now, but there is not yet a fresh browser-backed verification artifact for the current repo state.
- **Observed evidence:**
  - Vite frontend source and built assets exist under `frontend/` and `frontend/dist`.
  - Prior Next.js SIGKILL concern is stale relative to the current Vite-based repo shape.
- **Next recovery step:**
  - Run the frontend against the live API and verify the core upload/chat path after the fresh smoke artifact is captured.

### Repo hygiene / generated artifacts

- **Status:** Watch item
- **Impact:** Built assets, caches, and broad uncommitted changes increase review and packaging risk.
- **Observed evidence:**
  - The repo contains generated artifacts such as `frontend/dist`, `node_modules`, caches, and many uncommitted tracked/untracked files.
  - There were no new commits since the morning window, which means this breadth is still accumulated local WIP.
- **Next recovery step:**
  - Separate generated/runtime artifacts from source-of-truth changes and tighten commit boundaries before packaging.

## Decisions Made (2026-04-09)

### RBAC tightening
- **Decision:** Restrict org member lists to org_owner/platform_owner; restrict workspace member lists to workspace_admin/org_owner.
- **Implemented:** Commit `615897a`

### Deployment model
- **Decision:** Docker-first on RTX 5090; `docker-compose.gpu.yml` is canonical.
- **Implemented:** Commit `7fdf62e` and docs updates

## Operational watch item

### Forge execution reliability after LLM change

- **Status:** Watch item
- **Impact:** Forge did not complete the requested browser-backed `/organizations` verification task cleanly after the per-agent model change.
- **Observed evidence:**
  - Forge is currently running on `ollama/qwen3-coder:30b`
  - Cross-agent visibility/status is now fixed, so future checks can confirm live Forge model/session state directly
  - The delegated task timed out without returning a trustworthy browser-backed verification result
- **Next step:** Investigate whether the failure is due to the local model, context handling, task shape, missing browser-tool path in Forge's lane, or a broader reliability issue before depending on Forge for critical verification tasks.

## Standup review note
- Tonight's blocker review confirms the main active blocker is still missing current-state verification evidence, not a product-direction decision.
- No Telegram ping to King was needed because there is no unresolved decision requiring a forced tradeoff tonight.
