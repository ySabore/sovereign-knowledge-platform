# End-to-end chat smoke proof — 2026-04-03

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

Resolution in this session:
1. identified the listener on `127.0.0.1:8000`
2. stopped the stale process
3. restarted Uvicorn from the current repo code
4. verified current OpenAPI now includes `/documents/*` and `/chat/*`

This is now a known operational footgun for future live-proof work.

## Repeatable smoke script added
- `scripts/e2e_chat_smoke.py`

The script now acts as a more reproducible pre-demo validation lane:
1. waits for `/health` to return `{"status":"ok"}` before starting
2. verifies `/openapi.json` includes the required `/documents/*` and `/chat/*` routes to catch stale/wrong API processes on port `8000`
3. logs in as the seeded platform owner
4. creates a unique org and two workspaces
5. generates a tiny one-page PDF in-memory with the evidence sentence:
   - `Project Atlas retention period is 45 days.`
6. uploads the PDF to workspace A and indexes it
7. runs retrieval search in workspace A
8. opens a chat session in workspace A
9. posts a hit question: `What is the Project Atlas retention period?`
10. posts a no-hit question: `What is the office snack policy?`
11. opens a chat session in workspace B and asks the same hit question to prove workspace isolation
12. verifies persisted session/message/document/chunk state directly via SQLAlchemy
13. prints a JSON result payload and can optionally write it to disk with `--output-json`

### Recommended command
```powershell
cd C:\Users\Yeshi\ProjectRepo\sovereign-knowledge-platform
.\.venv\Scripts\python.exe scripts\e2e_chat_smoke.py --output-json .\data\smoke\latest-chat-smoke.json
```

### Configuration knobs
- CLI args: `--base-url`, `--owner-email`, `--owner-password`, `--health-wait-seconds`, `--timeout-seconds`, `--output-json`
- env equivalents: `SKP_BASE_URL`, `SKP_OWNER_EMAIL`, `SKP_OWNER_PASSWORD`, `SKP_SMOKE_OUTPUT_JSON`
- `--skip-openapi-check` is available, but default behavior should be kept for pre-demo runs because it protects against the already-observed stale-process failure mode.

## Live result summary
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

## Conclusion
The current backend now has live proof for the end-to-end ingestion -> retrieval -> chat -> persisted citation path, including no-hit fallback and basic workspace isolation.

## Next highest-value follow-up
Turn this smoke script into an automated integration test lane that starts from a clean app process / dedicated test database so it can run reliably in CI or local pre-demo validation.
