# Engineering decisions (Phase 0–2)

Mirrors `README.md` phase summary. Promote decisions into ADR-style records as the implementation surface grows.

- **2026-04-07:** Initial scaffold; sync SQLAlchemy + Alembic; JWT in `Authorization: Bearer`.
- **2026-04-07:** Keep organization/workspace authorization checks close to router handlers for the MVP so role gates stay explicit and easy to audit before introducing a service layer.
- **2026-04-07:** Phase 2 scope for this sprint slice is read/update coverage for organizations and workspaces; invitations, membership management, and ingestion remain the next domain slice.
