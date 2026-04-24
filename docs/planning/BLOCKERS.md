# BLOCKERS.md — Sovereign Knowledge Platform

*Last updated: 2026-04-21 11:55 PM America/New_York*

## Active Blockers

### None — no hard blocker currently stops implementation progress

The repo is actively moving on backend + frontend work, and the test suite is green. The current risks are coordination, proof, and environment fidelity rather than “cannot proceed” blockers.

---

## Current Watch Items (Not Hard Blockers)

### 1. Frontend cutover and parity confidence
- **Status:** Active
- **Impact:** The codebase has both an active frontend and `frontend-legacy-20260416/`, which implies cutover/parity work is still in flight
- **Why it matters:** Without disciplined parity checks, UI regressions or accidental capability gaps can hide behind the refactor
- **Next step:** Keep frontend parity/cutover docs current and verify demo-critical org/workspace/chat/admin flows against the live frontend

### 2. Repo truth drift versus live implementation
- **Status:** Active
- **Impact:** Older planning/workspace docs still describe the bootstrap/foundation stage even though the repo is far beyond that phase
- **Why it matters:** This creates wasted effort and mis-prioritization across Apex/Forge lanes
- **Next step:** Continue updating repo planning docs and agent-side status docs together whenever the working tree meaningfully shifts

### 3. External-service environment fidelity
- **Status:** Monitoring
- **Evidence:** Test logs still show hostname-resolution failures for AI readiness (`getaddrinfo failed`) and Redis-backed rate-limit warnings when external service names are unreachable in the current local test environment
- **Impact:** The suite still passes, but local runtime signals can look noisy or misleading when infrastructure assumptions differ between test and live environments
- **Next step:** Keep environment/config docs explicit and avoid treating these warnings as product blockers unless they reproduce in the intended runtime stack

### 4. Repo hygiene / commit boundary discipline
- **Status:** Active
- **Impact:** The working tree currently spans backend, frontend, docs, env examples, migrations, and legacy-frontend staging
- **Why it matters:** Broad mixed changes make review, rollback, and release packaging harder
- **Next step:** Organize current work into clearer commit boundaries after docs/status alignment is finished

### 5. External integration proof gap
- **Status:** Deferred but real
- **Impact:** Connectors, billing, webhooks, and sync surfaces exist, but not every path has current integrated proof in the target runtime
- **Next step:** Prioritize live proof selectively for demo/client-critical integrations instead of trying to verify every extension path at once

---

## Recently Confirmed

### 1. Current automated regression baseline remains healthy (2026-04-21)
**STATUS: CONFIRMED**
- `python -m unittest discover -s tests -v` passed **53/53 tests**
- RBAC visibility and role-enforcement suites are green
- Chat fallback, citation, rerank, and answer-generation guard tests are green

### 2. Admin/backend breadth is real, not aspirational
**STATUS: CONFIRMED**
- Current architecture and route docs match a broad live implementation surface including chat streaming, connectors, billing, audit, metrics, and org/workspace administration
- The repo should no longer be framed as an “ingestion pipeline foundation” project

---

## Decisions Made

### 2026-04-21
- Treat repo docs under `docs/` as the primary status truth for SKP, not stale agent-local bootstrap docs
- Treat current work as hardening/cutover/packaging coordination, not foundational backend bring-up
- Keep “no hard blocker” status unless a real runtime or product decision genuinely stops forward progress

---

## Standup Review Note

No immediate interrupt to Yeshi is required from blockers alone.
The important action is maintaining accurate status and choosing the next highest-value proof/hardening move, not escalating routine churn.
