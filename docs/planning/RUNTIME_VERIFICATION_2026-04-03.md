# Phase 1 Runtime Verification — 2026-04-03

## Verified runtime proof obtained
Source: manual execution reported from `C:\Users\Yeshi\ProjectRepo\sovereign-knowledge-platform`.

### Proven checks
1. **Alembic migration connectivity** — succeeded (`alembic upgrade head` connected successfully).
2. **Dev seed path** — succeeded with exact proof: `Seeded platform owner: owner@example.com`.
3. **API runtime health** — succeeded: `GET /health` returned `{"status":"ok"}`.
4. **Login flow** — succeeded: `POST /auth/login` returned a bearer token.
5. **Protected identity flow** — succeeded: `GET /auth/me` returned the platform owner with `is_platform_owner=true`.

## Repo-grounded meaning
These proofs confirm the Phase 1 backend foundation is live enough to:
- connect app + migration layer to PostgreSQL,
- create the seeded platform owner user through `scripts/seed.py`, and
- serve the FastAPI app health endpoint from `app.main`.

Relevant repo grounding:
- `scripts/seed.py` seeds `owner@example.com` by default and prints `Seeded platform owner: <email>` on first insert.
- `app/routers/auth.py` exposes `POST /auth/login` and `GET /auth/me`.
- `app/auth/security.py` issues HS256 JWTs with issuer from config.
- `app/deps.py` enforces Bearer auth and rejects missing/invalid/expired tokens.
- `.env.example` defines default dev seed credentials:
  - `SEED_PLATFORM_OWNER_EMAIL=owner@example.com`
  - `SEED_PLATFORM_OWNER_PASSWORD=ChangeMeNow!`

## Auth proof outcome
The seeded owner successfully:
1. obtained a bearer token from `POST /auth/login`, and
2. resolved identity through protected `GET /auth/me`.

This closes the remaining auth proof gap for Phase 1.

## Exact auth proof procedure (now matched by reported successful execution)
Assumption used for the validation path: API running at `http://127.0.0.1:8000`.

### 1) Login proof
Request:
```powershell
curl.exe -X POST http://127.0.0.1:8000/auth/login ^
  -H "Content-Type: application/json" ^
  -d "{\"email\":\"owner@example.com\",\"password\":\"ChangeMeNow!\"}"
```

Expected success:
- HTTP `200 OK`
- JSON body shape:
```json
{
  "access_token": "<jwt>",
  "token_type": "bearer"
}
```

Why this is expected:
- `app/routers/auth.py::login()` lowercases/trims email, verifies bcrypt password hash, checks `is_active`, then returns `TokenResponse`.
- `app/schemas/auth.py` defines `TokenResponse` as `access_token` plus `token_type` defaulting to `bearer`.

Expected failure cases if proof does not pass:
- `401 {"detail":"Invalid credentials"}` for wrong email/password.
- `403 {"detail":"Inactive user"}` if the user exists but is inactive.

### 2) Protected identity proof
Use the JWT returned by `/auth/login`.

Request:
```powershell
curl.exe http://127.0.0.1:8000/auth/me ^
  -H "Authorization: Bearer <paste_access_token_here>"
```

Expected success:
- HTTP `200 OK`
- JSON body containing the seeded owner identity, shaped like:
```json
{
  "id": "<uuid>",
  "email": "owner@example.com",
  "full_name": "Platform Owner",
  "is_platform_owner": true
}
```

Why this is expected:
- `app/deps.py::get_current_user()` requires Bearer auth, decodes JWT with issuer + expiry checks, loads the user, and rejects inactive/missing users.
- `app/routers/auth.py::me()` returns the authenticated `User`.
- `scripts/seed.py` creates the seeded user with `full_name="Platform Owner"`, `is_active=True`, and `is_platform_owner=True` by default.

Expected failure cases if proof does not pass:
- `401 {"detail":"Not authenticated"}` if header is missing or not Bearer.
- `401 {"detail":"Invalid or expired token"}` if JWT is malformed, expired, or issuer/secret mismatch exists.
- `401 {"detail":"User not found"}` if token decodes but user no longer exists or is inactive.

## Completion condition for auth proof
Phase 1 auth verification is now complete because the validation captured:
- successful `/auth/login` response with bearer token returned, and
- successful `/auth/me` response resolving the platform owner with `is_platform_owner=true`.

## Current status
No remaining Phase 1 blocker is left in this lane; the next move is Phase 2 / ingestion execution on top of the verified runtime base.
