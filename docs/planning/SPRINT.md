# SPRINT.md — Week of April 6-12, 2026

## Current Sprint Goals
1. Verify E2E happy path after broad repo expansion (✓ smoke JSON verified 2026-04-09)
2. Complete Vite frontend `/organizations` page verification across seeded roles
3. Address missing `/admin/*` endpoints for live admin panel functionality
4. Clean up and commit the broad working tree

## Today's Focus (Friday, April 10, 2026) — 12:14 PM Update

### Past 24h Summary
- Fresh backend smoke proof generated: `data/smoke/E2E_CHAT_SMOKE_2026-04-09.json`
- **Admin endpoints VERIFIED LIVE**: `/admin/metrics/summary`, `/admin/documents/{org_id}`, `/admin/connectors/{org_id}`, `/admin/audit/{org_id}` all registered and responding
- Cross-agent visibility fixed in OpenClaw config
- Model confirmed: `ollama/qwen3-coder:30b`

### Blockers Identified (UPDATED)
1. ~~Missing admin endpoints~~ **RESOLVED** — endpoints exist and are live
2. **Frontend verification incomplete**: `/organizations` page not fully validated across seeded roles
3. **RBAC concern**: org membership reads appearing too permissive across roles (needs validation)

### 3 Coding Goals for Today (UPDATED)
1. **Verify `/admin/documents/{org_id}` endpoint** with live API call — confirm it returns expected data
2. **Verify `/admin/metrics/summary` endpoint** with live API call — confirm dashboard data shape
3. **Verify `/organizations` frontend page** across all seeded roles (owner, member, workspace admin)

## Task Registry

| ID | Task | Status | Owner | Notes |
|----|------|--------|-------|-------|
| T1 | Fresh E2E smoke proof | ✅ Done | Forge | 2026-04-09.json verified |
| T2 | `/organizations` page verification | 🔄 In Progress | — | Shift to priority |
| T3 | ~~Missing `/admin/documents` endpoint~~ | ✅ **EXISTS** | — | Code inspection + live OpenAPI confirms |
| T4 | ~~Missing `/admin/metrics` endpoint~~ | ✅ **EXISTS** | — | Code inspection + live OpenAPI confirms |
| T5 | Live API verification of admin endpoints | 🔄 In Progress | — | Test with real auth tokens |
| T6 | RBAC membership audit | ⏳ Blocked | — | After T5 |
| T7 | Working tree cleanup + commit | ⏳ Blocked | — | After verification |

## Live API Status (as of 12:14 PM)
- ✅ Backend running on localhost:8000
- ✅ `/health` returns ok
- ✅ OpenAPI shows `/admin/*` routes registered:
  - `GET /admin/metrics/summary`
  - `GET /admin/connectors/{organization_id}`
  - `GET /admin/documents/{organization_id}`
  - `GET /admin/audit/{organization_id}`

## Next Actions
1. Test `/admin/documents/{org_id}` with seeded owner token
2. Test `/admin/metrics/summary` with seeded owner token
3. Proceed to frontend `/organizations` page verification

## 4:00 PM — Afternoon Status Update

### Progress Since Midday
**No new progress recorded.** The live API verification tasks identified at 12:14 PM remain pending:
- `/admin/documents/{org_id}` endpoint — NOT yet tested with live JWT tokens
- `/admin/metrics/summary` endpoint — NOT yet tested with live JWT tokens
- Frontend `/organizations` page — NOT yet verified across seeded roles

### Blockers
**No new blockers**, but verification work is stalled. The backend is confirmed running (confirmed at 12:14 PM), but no actual API calls with authentication have been executed since then.

### Afternoon Plan Adjustment
Given it's now 4:00 PM and no verification work has occurred:
1. **Immediate priority:** Execute live API verification (15 min task)
2. **If time permits:** Quick frontend smoke check
3. **Acceptance:** May need to carry verification tasks to Monday if not completed today

### Risk Assessment
- **Low risk** — Endpoints exist and are confirmed live
- **Medium risk** — Frontend integration gap remains unvalidated
- **Recommendation:** Complete at least one live API call before end of day to confirm auth flow works

Updated: 2026-04-10 4:00 PM
