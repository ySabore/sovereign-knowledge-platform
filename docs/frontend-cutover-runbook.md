# Frontend Cutover Runbook

Use this runbook to promote `frontend` to production and keep rollback low risk.

## 1) Pre-cutover checks

From `frontend`:

```bash
npm run verify:readiness
```

From repo root:

```bash
docker compose -f docker-compose.prod.yml config --services
docker compose -f docker-compose.gpu.yml config --services
docker compose -f docker-compose.prod.yml build web
```

Expected:
- `verify:readiness` passes.
- `web` service builds successfully from `frontend/Dockerfile`.
- Compose files parse without errors.

## 2) Production deploy

```bash
docker compose -f docker-compose.prod.yml --env-file .env up -d --build
```

Post-deploy quick checks:
- Open `http://localhost:${WEB_PORT:-8080}`.
- Login with seeded owner/admin/member accounts.
- Verify orgs/workspaces/chats/team/documents/connectors/analytics/billing navigation.
- Check browser console for new errors.

## 3) Monitoring window

Keep a burn-in window before archiving legacy frontend:
- Duration: at least one business day.
- Track: auth failures, chat failures, API 4xx/5xx spikes, page-load errors.
- Confirm no regression trend compared with pre-cutover baseline.

## 4) Rollback

If critical regressions appear:
1. Revert web dockerfile reference from `frontend/Dockerfile` to `frontend-legacy-20260416/Dockerfile` in compose.
2. Rebuild and restart web:

```bash
docker compose -f docker-compose.prod.yml --env-file .env up -d --build web
```

3. Re-run smoke checks.
4. Capture regression notes and blockers before retrying cutover.

## 5) Archive gate

Archive old `frontend-legacy-20260416` only after:
- Burn-in window is green.
- Rollback procedure has been validated in staging.
- Release notes include final parity status and known deltas.

