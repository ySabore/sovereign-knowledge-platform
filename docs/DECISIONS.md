# DECISIONS.md — Engineering and Documentation Decisions

*Last updated: 2026-04-15 America/New_York*

This file records durable decisions that still matter. It is not a full ADR system yet, but it should hold decisions worth preserving.

## Product and platform decisions

- **Docker-first deployment is canonical.** `docker-compose.gpu.yml` is the main deployable path for current demo and validation work.
- **PostgreSQL + pgvector remains the primary persistence and vector retrieval substrate.**
- **Organizations + workspaces remain the core tenant boundary model.**
- **The exact no-evidence fallback remains a product invariant:**
  `I don't know based on the documents in this workspace.`
- **Retrieval is strategy-based, not single-path.** Current strategies include heuristic, hybrid, and rerank.
- **Answer generation is provider-configurable.** Current supported providers include extractive, Ollama, OpenAI, and Anthropic.

## Access and safety decisions

- **Tenant and workspace authorization checks stay explicit.** The backend continues to enforce org/workspace access at the route and service level.
- **Document permissions remain available as a stricter RBAC layer.** Full document ACL behavior should remain supported even when simple RBAC mode is used operationally.

## Documentation structure decisions

- **Root-level `docs/SPRINT.md`, `docs/NEXT_TASK.md`, and `docs/ROADMAP.md` are compatibility pointers only.**
- **Canonical sprint and execution status lives under `docs/planning/`.**
- **Canonical product roadmap lives under `docs/product/ROADMAP.md`.**
- **Canonical architecture understanding lives under `docs/architecture/`.**
- **Canonical shipped-vs-partial status lives under `docs/deliverables/PHASE_STATUS.md`.**
- **When a root doc duplicates a more specific doc, the more specific location wins.**

## Documentation truth corrections recorded

- Older docs described several capabilities as planned even though the codebase already implemented them.
- Architecture docs were refreshed to reflect current implementation reality.
- A codebase map and ingestion/retrieval architecture doc were added to make current behavior easier to understand.

## Next likely evolution

If decision volume keeps growing, promote this file into lightweight ADRs under a dedicated `docs/decisions/` folder.
