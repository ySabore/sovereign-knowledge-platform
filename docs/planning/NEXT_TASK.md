# NEXT_TASK.md — Single Most Important Task

*Last updated: 2026-04-21 America/New_York*

## The one task

Finish a trustworthy current-state project-status reconciliation across the SKP repo and all agent planning surfaces, then pivot immediately into frontend cutover/parity validation for demo-critical flows.

## Why this matters most now

The repo is no longer in the early foundation phase, but several planning surfaces still describe it that way.
That creates four immediate costs:
1. agents can waste cycles targeting already-finished foundation work
2. roadmap/sprint framing can understate what the product already does
3. frontend cutover/parity risk can be deprioritized incorrectly
4. packaging/demo decisions can be made against stale assumptions

## Acceptance criteria

- [ ] repo planning docs (`SPRINT.md`, `BLOCKERS.md`, `NEXT_TASK.md`) reflect the live working tree and current test evidence
- [ ] agent-side Forge planning docs no longer describe the project as pre-ingestion / pre-runtime / pre-API
- [ ] current frontend cutover/parity work is explicitly recognized as the next implementation proof lane
- [ ] the next engineering move is obvious without rereading the whole repo

## Concrete subtasks

1. reconcile repo planning docs against current working-tree evidence
2. update stale Forge workspace planning/status files to point at repo docs as the primary truth
3. summarize the current implementation breadth: connectors, chat/session/message flows, admin/org shell, migrations, and frontend shell work
4. identify the next proof lane as frontend cutover/parity validation rather than generic docs cleanup
5. keep delivery/status docs and roadmap phrasing aligned with that reality

## After this

Once status drift is corrected, the best next engineering move is:
1. validate the live frontend against demo-critical org/workspace/chat/admin flows
2. complete parity/cutover checks against the legacy frontend snapshot
3. then continue hardening connectors, billing/admin surfaces, and packaging discipline
