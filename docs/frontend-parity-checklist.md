# Frontend Production Readiness Checklist

Use this checklist before finalizing deployment on `frontend` after promoting the refactor.

## 1) Functional Parity

- [ ] Login/logout flow works for all seeded roles.
- [ ] Organizations page parity verified.
- [ ] Workspaces list/open behavior parity verified.
- [ ] Chats list + embedded chat parity verified.
- [ ] Team panel parity verified.
- [ ] Documents upload/index/remove parity verified.
- [ ] Connectors panel parity verified.
- [ ] Analytics panel parity verified.
- [ ] Billing, audit, and settings panel parity verified in `/home`.
- [ ] Error/empty/loading states visually match expected behavior.

## 2) Automated Validation

Hard gate command (run inside `frontend`):

```bash
npm run verify:readiness
```

- [ ] `frontend`: typecheck passes (`npm run typecheck`).
- [ ] `frontend`: production build passes (`npm run build`).
- [ ] `frontend`: logic tests pass (`npm run test:logic`).
- [ ] Existing parity smoke tests pass against active frontend URL (`http://localhost:5173` or current Vite fallback port).
- [ ] No new TypeScript errors in CI (`npm run typecheck` or CI equivalent).

## 3) UX and Visual Consistency

- [ ] Back-navigation controls are consistent across org/workspace flows.
- [ ] Form controls in refactored modules use shell styling conventions.
- [ ] Sidebar/topbar behavior matches existing app.
- [ ] Bright/dark mode parity confirmed.

## 4) Runtime/Integration

- [ ] API endpoint usage is unchanged (no unexpected 4xx/5xx deltas).
- [ ] No new noisy console errors in critical flows.
- [ ] WebSocket/chat session behavior unchanged.

## 5) Deployment Readiness

- [ ] Deployment config points to `frontend` artifact/path.
- [ ] Rollback plan documented (switch path/env back to `frontend-legacy-20260416` if needed).
- [ ] Release notes include parity status + known deltas (if any).
- [ ] Monitoring dashboards/alerts updated for new frontend path (if needed).
- [ ] Cutover runbook reviewed (`docs/frontend-cutover-runbook.md`).

## 6) Archive Gate (Old Frontend Tree)

Archive or remove `frontend-legacy-20260416` only after all sections above are green and these release checks are complete:

- [ ] Tag cutover commit.
- [ ] One full day of staging monitoring shows no regression spikes (auth failures, chat errors, page load failures).
- [ ] Rename/archive old folder (for example `frontend-legacy-YYYYMMDD`).
- [ ] Keep archive for one release cycle minimum.

