# HISTORICAL E2E CHAT SMOKE PROOF — 2026-04-03

## Status of this document

This is a **historical evidence artifact**, not the current sprint plan.

Its value is that it captured an earlier successful end-to-end proof of:
- ingestion
- retrieval
- grounded chat
- exact fallback
- workspace isolation

For current execution status, use:
- `SPRINT.md`
- `NEXT_TASK.md`
- `BLOCKERS.md`
- `../deliverables/PHASE_STATUS.md`

---

## Objective
Prove the live API path for:
- seeded user login
- organization creation
- workspace creation
- PDF upload + indexing
- retrieval-backed chat answer with persisted citations
- no-hit fallback behavior
- workspace isolation

## Environment facts used
- API base URL: `http://127.0.0.1:8000`
- embedding service: Ollama on `http://127.0.0.1:11434`
- embedding model available: `nomic-embed-text`
- Postgres container healthy on port `5433`
- Redis container running on port `6380`
- Alembic migration `002` applied successfully
- seeded platform owner already present: `owner@example.com`

## Important runtime finding
A stale older API process was already bound to port `8000` and exposed only auth/org/workspace routes. That process caused a real `404` on `/documents/workspaces/{workspace_id}/upload` during the first smoke attempt.

### Historical resolution
1. identified the listener on `127.0.0.1:8000`
2. stopped the stale process
3. restarted Uvicorn from the current repo code
4. verified current OpenAPI now includes `/documents/*` and `/chat/*`

This remained a useful operational lesson for later smoke and demo validation work.

## Repeatable smoke script added
- `scripts/e2e_chat_smoke.py`

The script acted as a reproducible pre-demo validation lane:
1. wait for `/health`
2. verify `/openapi.json` includes required `/documents/*` and `/chat/*` routes
3. login as seeded platform owner
4. create a unique org and two workspaces
5. generate a tiny one-page PDF in-memory with evidence text
6. upload and index the PDF in workspace A
7. run retrieval search in workspace A
8. open a chat session in workspace A
9. ask a hit question
10. ask a no-hit question
11. ask the same hit question in workspace B to prove isolation
12. verify persisted session/message/document/chunk state directly via SQLAlchemy
13. emit a JSON result payload

## Historical live result summary
Smoke run completed successfully.

### Evidence workspace
- upload status: `indexed`
- page count: `1`
- chunk count: `1`
- retrieval hit count: `1`
- top hit score: `0.6904014143229731`

### Chat behavior
- hit answer returned grounded extractive response with citation content referencing `45 days`
- hit citation count: `1`
- no-hit answer returned exact fallback:
  - `I don't know based on the documents in this workspace.`
- isolated workspace asking the hit question also returned the same fallback

### Persistence checks
For the evidence session:
- persisted message roles: `user, assistant, user, assistant`
- DB message count: `4`

For the isolation session:
- DB message count: `2`

Workspace/document isolation:
- evidence workspace document count: `1`
- evidence workspace chunk count: `1`
- isolation workspace chunk count: `0`

## Historical conclusion
This artifact proved that the backend had already achieved the end-to-end ingestion -> retrieval -> chat -> persisted citation path, including no-hit fallback and workspace isolation, at that point in time.

## Historical next step
The next suggested step at the time was to turn the smoke lane into a more automated, reliable integration-test or pre-demo validation path.
