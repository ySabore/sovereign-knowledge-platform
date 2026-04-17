# Docker Compose quick reference

Run these from the repository root (`sovereign-knowledge-platform`). Copy `.env.example` to `.env` and set at least `JWT_SECRET`, `SEED_PLATFORM_OWNER_PASSWORD`, and any Ollama URLs you need.

| File | Purpose |
|------|---------|
| `docker-compose.prod.yml` | Production-shaped stack: Postgres, Redis, API, static UI. Default Ollama URL targets the **host** (`host.docker.internal:11434` on Docker Desktop). |
| `docker-compose.gpu.yml` | Same shape; optional **bundled Ollama** can use **NVIDIA GPUs** (`gpus: all`). Default API URLs target the `ollama` **service** when you use that profile. |

Optional **in-compose Ollama** is on Compose profile **`bundled-ollama`** in both files. With that profile enabled, point the API at the service:

- `EMBEDDING_OLLAMA_BASE_URL=http://ollama:11434`
- `ANSWER_GENERATION_OLLAMA_BASE_URL=http://ollama:11434`

After first boot with bundled Ollama, pull models (adjust names to match `EMBEDDING_MODEL` / `ANSWER_GENERATION_MODEL` in `.env`):

```powershell
docker compose -f docker-compose.prod.yml --profile bundled-ollama exec ollama ollama pull nomic-embed-text
docker compose -f docker-compose.prod.yml --profile bundled-ollama exec ollama ollama pull llama3.2
```

(Use `docker-compose.gpu.yml` in the `-f` argument if that is the stack you started.)

## Commands

**1. Prod — Ollama on the host**

```powershell
docker compose -f docker-compose.prod.yml --env-file .env up --build -d
```

**2. Prod + bundled Ollama (CPU inside Compose)**

Set the two `*_OLLAMA_BASE_URL` values to `http://ollama:11434` in `.env`, then:

```powershell
docker compose -f docker-compose.prod.yml --env-file .env --profile bundled-ollama up --build -d
```

**3. GPU + bundled Ollama (NVIDIA)**

Same URL overrides as (2), then:

```powershell
docker compose -f docker-compose.gpu.yml --env-file .env --profile bundled-ollama up --build -d
```

## Notes

- **PowerShell:** If `&&` fails, run one command per line or separate with `;`.
- **Orphan containers:** Add `--remove-orphans` to `up` if Compose warns about old containers from a different compose file for this project.
- **GPU setup:** See [`docs/deploy/GPU_RTX5090.md`](docs/deploy/GPU_RTX5090.md) and `scripts/setup_gpu_stack.ps1`.
- **Env reference:** [`.env.example`](.env.example), [`docs/configuration.md`](docs/configuration.md).
