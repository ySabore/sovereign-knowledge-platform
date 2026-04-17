# Deploy on RTX 5090 + local Ollama (Windows / Docker Desktop)

This path runs **Ollama inside Docker with GPU access**, plus **Postgres (pgvector)**, **Redis**, and the **SKP API**.

## Prerequisites

- Windows 11 with **Docker Desktop** (WSL2 backend)
- **NVIDIA driver** for RTX 5090 (latest Studio or Game Ready)
- Docker Desktop: **Use the WSL 2 based engine** enabled; GPU support enabled in Settings → Resources → GPU
- NVIDIA Container Toolkit / WSL integration as required by your Docker Desktop version

## One-command bootstrap

From the repo root:

```powershell
copy .env.example .env
# Edit .env: set JWT_SECRET and SEED_PLATFORM_OWNER_PASSWORD (and match seed email if you change it)
powershell -ExecutionPolicy Bypass -File .\scripts\setup_gpu_stack.ps1
```

The script:

1. Builds and starts `docker-compose.gpu.yml`
2. **Waits for** `http://127.0.0.1:8000/health` (API runs migrations on first boot; can take 1–3 minutes)
3. Pulls `nomic-embed-text` and `llama3.2` (override via script parameters)
4. Runs `scripts/seed.py` inside the API container
5. Leaves the stack in the same deployment shape used for demo validation

## Verify

### Demo smoke, Docker-first

After the stack is up, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\demo_chat_smoke.ps1
```

This wrapper now assumes Docker is the source of truth. It:
- starts or reuses the compose stack
- verifies the required OpenAPI routes on the running API
- seeds the owner inside the API container
- runs the end-to-end chat smoke using host-reachable ports that map to the Docker services

Artifacts are written under `data/smoke/`.


| URL | Meaning |
|-----|---------|
| http://127.0.0.1:8000/health | Process up |
| http://127.0.0.1:8000/health/ready | Postgres + Redis |
| http://127.0.0.1:8000/health/ai | Ollama up + embedding model present |
| http://127.0.0.1:8000/docs | Swagger |

Frontend (dev) — use the **refactor** app (recommended; port **5174** by default):

```powershell
cd frontend
npm install
npm run dev
```

Open http://127.0.0.1:5174 (or the port Vite prints if 5174 is busy) and sign in with the seeded owner from `.env`.

Legacy local dev (optional, port **5173**): `cd frontend` then `npm run dev`.

**Docker UI:** with Compose up, the static SPA is usually at http://localhost:8080 (or `WEB_PORT`); ensure `CORS_ORIGINS` includes your dev origins (see `docs/configuration.md`).

## Configuration

- **Ollama URL inside API container:** `EMBEDDING_OLLAMA_BASE_URL=http://ollama:11434` (default in compose)
- **Host Ollama:** if you run Ollama on Windows instead of Docker, point URLs to `http://host.docker.internal:11434` and remove or stop the `ollama` service (use `docker-compose.prod.yml` pattern)
- **Models:** set `EMBEDDING_MODEL`, `ANSWER_GENERATION_MODEL`, and `ANSWER_GENERATION_PROVIDER=ollama` in `.env` for LLM answers (see `docs/configuration.md`)

## Troubleshooting

### `service "api" is not running`

The API container exited or never became healthy. Check:

```powershell
docker compose -f docker-compose.gpu.yml ps -a
docker compose -f docker-compose.gpu.yml logs api --tail 200
```

Common causes:

- **Invalid or missing `JWT_SECRET` / `SEED_PLATFORM_OWNER_PASSWORD`** in `.env` (compose requires them)
- **Port 8000 in use** — change `API_PORT` in `.env` or stop the other process
- **Database not ready** — wait and retry; Postgres healthcheck should gate startup

### GPU not used by Ollama

- Confirm Docker Desktop GPU support and `nvidia-smi` works in WSL
- `docker compose` file uses `gpus: all` on the `ollama` service; if your Compose version rejects it, see Docker docs for your platform and adjust

### `/health/ai` reports model missing

Pull the model names matching `EMBEDDING_MODEL` in `.env`:

```powershell
docker compose -f docker-compose.gpu.yml exec ollama ollama pull nomic-embed-text
```

### Re-run bootstrap safely

`setup_gpu_stack.ps1` is idempotent for seed (skips existing user). Migrations run in the API entrypoint on each start.

## Files

- `scripts/demo_chat_smoke.ps1` — Docker-first end-to-end demo smoke wrapper

- `docker-compose.gpu.yml` — GPU Ollama + stack
- `scripts/setup_gpu_stack.ps1` — bootstrap with health wait
- `docker-compose.prod.yml` — API + DB + Redis; Ollama on host via `host.docker.internal`
