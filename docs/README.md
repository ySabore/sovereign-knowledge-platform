# Docs Index — Sovereign Knowledge Platform

This folder is organized by purpose.

## Start here

### Product and delivery
- `product/PRODUCT_REQUIREMENTS.md` — product requirements
- `product/MVP_IMPLEMENTATION_PLAN.md` — implementation plan
- `product/DELIVERY_SPEC.md` — delivery constraints and expectations
- `product/PILOT_V1_DEFINITION.md` — pilot scope and sales-friendly v1 framing
- `product/ROADMAP.md` — product/milestone roadmap

### Current execution state
- `planning/SPRINT.md` — current sprint and active execution focus
- `planning/NEXT_TASK.md` — single highest-priority next task
- `planning/BLOCKERS.md` — active blockers and watch items
- `deliverables/PHASE_STATUS.md` — shipped vs partial vs planned status

### Architecture and engineering understanding
- `architecture/ARCHITECTURE.md` — top-level system architecture
- `architecture/CODEBASE_MAP.md` — codebase map and module guide
- `architecture/INGESTION_AND_RETRIEVAL.md` — ingestion and retrieval pipeline
- `architecture/ROLES_AND_USERS.md` — roles, users, and access model
- `architecture/TECHDECISIONS.md` — technical decisions
- `architecture/FRONTEND_ARCHITECTURE.md` — SPA architecture map (`frontend` as cutover target; legacy `frontend` noted where still present)
- `architecture/FRONTEND_REFACTOR_PLAN_HOMEPAGE.md` — targeted homepage/shell modularization plan (implementation lives under `frontend/src/features/home-shell/`)

### Operations
- `configuration.md` — environment and runtime config reference
- `deploy/GPU_RTX5090.md` — GPU-first deployment runbook
- `frontend-parity-checklist.md` — pre-cutover parity and readiness gates
- `frontend-cutover-runbook.md` — deploy, monitoring, rollback for promoting `frontend`

### Evidence and status artifacts
- `deliverables/README.md`
- `deliverables/PRODUCT_EVALUATION_2026-04-09.md`
- dated planning/runtime verification artifacts under `planning/`

### Supporting material
- `sales/` — demo, pilot, and outreach material
- `demo/` — demo corpora and sample workspace content
- `sources/` — source/reference material imported into the repo

## Canonical file rules

To reduce documentation drift:

- root-level `SPRINT.md`, `NEXT_TASK.md`, and `ROADMAP.md` are compatibility pointers only
- canonical current sprint docs live under `planning/`
- canonical product roadmap lives under `product/`
- architecture docs live under `architecture/`
- phase/delivery status lives under `deliverables/`

## Cleanup note

If a doc duplicates another doc at a more specific location, prefer the more specific location as source of truth and convert the duplicate into a pointer or remove it.

