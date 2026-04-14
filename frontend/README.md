# Sovereign Knowledge Platform — Web UI

Vite + React + TypeScript. In development, the Vite dev server proxies `/api` to the FastAPI backend (default `http://127.0.0.1:8000`).

## Scripts

```bash
npm install
npm run dev      # http://localhost:5173
npm run build    # output: frontend/dist
```

## Environment

| Variable | Purpose |
|----------|---------|
| `VITE_API_BASE` | API base URL. Default empty → use same origin `/api` (with dev proxy). For production static hosting against a separate API origin, set e.g. `https://api.example.com`. |
| `VITE_PROXY_TARGET` | (dev only) Override proxy target in `vite.config.ts`. |
| `VITE_CLERK_PUBLISHABLE_KEY` | Optional. When set, loads `@clerk/clerk-react` and adds `/sign-in` and `/sign-up` routes; session tokens are sent to the API as `Bearer`. Requires backend `CLERK_ENABLED=true`, `CLERK_ISSUER`, and migration `003`. |

Ensure backend `CORS_ORIGINS` includes your UI origin when not using the Vite proxy.

## App routes (Vite + React Router)

| Path | Purpose |
|------|---------|
| `/dashboard/:workspaceId` | Main chat UI (composer, streaming via `POST /api/chat`, source drawer). |
| `/admin`, `/admin/connectors` | Admin dashboards (platform owner or Clerk org admin). |
| `/workspaces/:id` | Redirects to `/dashboard/:id`. |

Streaming uses **SSE** from the FastAPI RAG pipeline (not the Vercel AI SDK protocol). tRPC is not in this repo; use REST + typed clients until a BFF exists.
