# TECHDECISIONS.md

## TD-001 — FastAPI backend for MVP
- **Decision:** Use FastAPI for the first API surface.
- **Why:** Fast delivery, clean schema-driven contracts, good fit for Python ingestion/retrieval services.
- **Consequence:** Keep service boundaries explicit so later decomposition stays easy.

## TD-002 — PostgreSQL + pgvector as the primary store
- **Decision:** Use Postgres for transactional tenant data and vector-backed retrieval.
- **Why:** Reduces moving parts, matches King’s strengths, and keeps deployment simple for pilots.
- **Consequence:** Early schema discipline matters; vector indexing choices should stay upgradeable.

## TD-003 — Two-layer tenant boundary
- **Decision:** Model both organizations and workspaces.
- **Why:** SMEs need tenant isolation plus internal scoped collaboration areas.
- **Consequence:** Retrieval/chat queries must always carry workspace and organization scope.

## TD-004 — PDF-only ingestion for MVP1
- **Decision:** Restrict the first ingestion happy path to PDF.
- **Why:** Faster demo path, lower parser complexity, easier test matrix.
- **Consequence:** Other file types wait until the PDF pipeline is stable.

## TD-005 — Audit trail before broader ingestion work
- **Decision:** Add `audit_logs` and wire sensitive tenant-management writes before expanding API surface further.
- **Why:** Tenant admin actions are security-relevant and client-visible; auditability increases credibility.
- **Consequence:** Membership/org/workspace mutations should stay centralized and consistently logged.

## TD-006 — Add phase-3 entities before full ingestion implementation
- **Decision:** Introduce `ingestion_jobs`, `documents`, `document_chunks`, `chat_sessions`, and `chat_messages` as first-class models now.
- **Why:** The retrieval/chat pipeline needs stable persistence contracts before endpoint implementation.
- **Consequence:** Alembic migration and isolation tests are now the immediate next execution step.
