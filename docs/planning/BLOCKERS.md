# BLOCKERS.md — Sovereign Knowledge Platform

*Last updated: 2026-04-10 4:00 PM America/New_York*

## Active Blockers

### None — All previously identified blockers are RESOLVED or in verification

---

## Recently Resolved (2026-04-10 12:14 PM)

### 1. Missing `/admin/*` endpoints

**STATUS: RESOLVED**

- **Previous assumption:** `/admin/documents/{org_id}` and `/admin/metrics/summary` were missing from the running backend
- **Reality:** Both endpoints exist in code (`app/routers/admin_metrics.py`) and are registered in the live API
- **Evidence:**
  - OpenAPI spec at `http://localhost:8000/openapi.json` shows all `/admin/*` routes
  - Live API at `http://localhost:8000/health` returns `ok`
  - Routes confirmed:
    - `GET /admin/metrics/summary`
    - `GET /admin/documents/{organization_id}`
    - `GET /admin/connectors/{organization_id}`
    - `GET /admin/audit/{organization_id}`
- **Root cause of confusion:** Prior live API checks may have targeted wrong port, wrong host, or stale backend instance

---

## Previously Resolved

### Fresh current-state smoke proof (RESOLVED 2026-04-09)
- `data/smoke/E2E_CHAT_SMOKE_2026-04-09.json` generated and verified
- Core backend capability re-proven on widened codebase

### RBAC exposure — org membership reads too broad (RESOLVED 2026-04-09)
- Commit `615897a` tightened member list permissions
- `tests/test_rbac_membership_visibility.py` passes

---

## Watch Items (Not Blockers)

### 1. Frontend integration confidence gap
- **Status:** Active work item — **STALLED since 12:14 PM**
- **Impact:** Need browser-backed verification of `/organizations` page across seeded roles
- **Next step:** Test with live API + Vite frontend
- **Note:** No progress recorded since midday update; verification work pending

### 2. RBAC membership reads — needs validation
- **Status:** Verification pending — **STALLED since 12:14 PM**
- **Impact:** Ensure non-owner roles cannot access admin endpoints
- **Next step:** Test `/admin/*` with member-level tokens
- **Note:** Live API verification not yet executed despite backend being confirmed running

### 3. External integration proof gap
- **Status:** Deferred
- **Impact:** Billing, connectors, webhooks exist but lack live integration evidence
- **Next step:** Prioritize only after frontend happy path verified

### 4. Repo hygiene / generated artifacts
- **Status:** Cleanup pending
- **Impact:** Broad uncommitted changes need review
- **Next step:** After verification complete

### 5. Forge execution reliability after LLM change
- **Status:** Monitoring
- **Impact:** Prior browser-backed verification did not complete cleanly
- **Next step:** Continue monitoring; cross-agent visibility now fixed

---

## Decisions Made

### 2026-04-09
- RBAC tightening: Restrict org member lists to org_owner/platform_owner
- Deployment model: Docker-first on RTX 5090; `docker-compose.gpu.yml` canonical

### 2026-04-10
- Admin endpoints confirmed live — no implementation needed
- Shift focus from "build missing endpoints" to "verify existing endpoints"

---

## Standup Review Note

No Telegram ping to King required. All previously identified blockers are resolved. Current work is verification, not unblocking.
