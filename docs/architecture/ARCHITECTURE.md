# ARCHITECTURE.md — Sovereign Knowledge Platform

## Objective
Sovereign Knowledge Platform (SKP) is a private, multi-tenant RAG platform for privacy-sensitive SMEs. The MVP is optimized for a fast local demo path while preserving a production-shaped architecture.

## Current system shape

### Runtime components
- **FastAPI API** — auth, tenant management, workspace management, future document/chat APIs
- **PostgreSQL 16 + pgvector** — system of record plus vector retrieval store
- **Redis** — reserved for job coordination, cache, and hot chat/session state
- **Ollama / configurable LLM provider** — planned embedding + generation layer
- **React UI** — planned operator/end-user interface

### Deployment model
Initial packaging is **Docker Compose**:
- `postgres` on host port `5433`
- `redis` on host port `6380`
- app runs locally through `uvicorn` during the current backend-first phase

## Domain model

### Identity and tenancy
- `users`
- `organizations`
- `organization_memberships`
- `workspaces`
- `workspace_members`

**Users and roles** (platform vs org vs workspace) are defined in [ROLES_AND_USERS.md](./ROLES_AND_USERS.md).

This gives SKP two isolation layers:
1. organization boundary for tenant ownership
2. workspace boundary for document/chat scope inside a tenant

### Ingestion and retrieval substrate
Phase-3 schema now targets:
- `ingestion_jobs` — track upload/index lifecycle
- `documents` — source files and indexing state
- `document_chunks` — retrieval units linked to source docs
- `chat_sessions` — per-user/per-workspace conversations
- `chat_messages` — message history plus citation payloads
- `audit_logs` — durable record of sensitive tenant mutations

## Request flows

### Auth flow
1. user logs in with email/password
2. API validates password hash
3. API returns JWT
4. protected routes resolve the current user from the JWT

### Tenant administration flow
1. platform owner creates an organization
2. creator becomes `org_owner`
3. org owner creates one or more workspaces
4. org owner / workspace admin assigns existing users into scope
5. membership changes now also emit audit-log rows

### Planned PDF ingestion flow
1. authenticated workspace member uploads a PDF into a workspace
2. API persists file metadata and creates an `ingestion_job`
3. parser/chunker extracts text
4. embedding adapter generates vectors
5. chunks are stored in Postgres/pgvector
6. document status flips to `indexed`

### Planned chat flow
1. user opens a chat session in a workspace
2. query is embedded
3. top matching chunks are retrieved under tenant/workspace constraints
4. LLM generates grounded answer with citations
5. session + messages are persisted

## Isolation rules
- organization membership gates org visibility
- workspace membership gates workspace visibility
- workspace assignment requires existing org membership
- last org owner / last workspace admin removal is blocked
- ingestion, retrieval, and chat tables are designed to carry both organization/workspace identifiers to simplify scoped queries and enforcement

## Audit logging
Sensitive organization/workspace mutations should create `audit_logs` rows with:
- actor user id
- org/workspace scope
- action name
- target type/id
- metadata payload
- timestamp

Currently wired actions:
- organization create/update/member upsert/member removal
- workspace create/update/member upsert/member removal

## Near-term implementation sequence
1. add Alembic migration for new phase-3 tables
2. add upload endpoint + storage path conventions
3. create ingestion service interfaces (parse/chunk/embed/index)
4. add retrieval endpoint and citation schema
5. add authz/isolation tests across org/workspace/document flows

## Design principles
- boring, explainable stack
- explicit tenant boundaries
- environment-driven config
- local-first demo path
- production-shaped persistence model before UI polish
