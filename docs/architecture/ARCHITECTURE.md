# ARCHITECTURE.md — Sovereign Knowledge Platform

## Objective
Sovereign Knowledge Platform (SKP) is a private, multi-tenant knowledge and RAG platform for privacy-sensitive organizations. It is designed to run self-hosted, support strong tenant isolation, ingest organizational knowledge into a searchable corpus, and answer questions with grounded citations.

This document reflects the current codebase, not just the original MVP plan.

## Current architecture summary

SKP is a Docker-first full-stack application with these major layers:

- **Frontend**: React + TypeScript single-page app
- **Backend API**: FastAPI application with router and service layers
- **Primary datastore**: PostgreSQL + pgvector
- **Cache / rate-limit backing**: Redis
- **Inference layer**:
  - local embeddings via Ollama
  - answer generation via extractive mode, Ollama, OpenAI, or Anthropic
  - optional hosted rerank via Cohere
- **Deployment**: Docker Compose, with a GPU-oriented compose stack as the canonical deployment path

## Runtime components

### 1. Frontend
Located under `frontend/`.

Responsibilities:
- authentication-aware app shell
- organization and workspace navigation
- platform-owner and org admin views
- document management
- connectors UI
- chat session and workspace chat experience
- analytics and billing views

Key characteristics:
- React Router based navigation
- protected app shell (`frontend/src/layouts/ProtectedAppShell.tsx`)
- dashboard-centered workspace UX
- admin and operator surfaces already exist beyond a simple MVP shell

### 2. FastAPI backend
Located under `app/`.

Responsibilities:
- authentication and identity resolution
- organization/workspace CRUD
- membership and RBAC enforcement
- document upload and ingestion APIs
- retrieval and grounded chat
- connector endpoints
- billing and metrics endpoints
- webhook handling
- runtime/public config exposure

Main application entrypoint:
- `app/main.py`

Registered routers currently include:
- `health`
- `auth`
- `organizations`
- `workspaces`
- `documents`
- `chat`
- `api_chat`
- `connectors`
- `admin_metrics`
- `webhooks_clerk`
- `webhooks_stripe`
- `billing`
- `runtime_config`

### 3. PostgreSQL + pgvector
Postgres is both:
- the system of record for tenants, users, memberships, documents, chats, billing, connectors, and audit data
- the vector store for semantic retrieval via `document_chunks.embedding`

This keeps the architecture simple and operationally coherent for pilots and self-hosted installs.

### 4. Redis
Redis is part of the runtime stack and is used for:
- rate-limiting support
- hot-state / caching support
- future or adjacent coordination use

Even though the current architecture is still largely synchronous request/response, Redis is already part of the standard deployable platform shape.

### 5. Inference and retrieval services
SKP separates retrieval from answer generation.

Current supported capabilities:
- embeddings via Ollama
- retrieval strategies:
  - `heuristic`
  - `hybrid`
  - `rerank`
- answer generation providers:
  - `extractive`
  - `ollama`
  - `openai`
  - `anthropic`
- optional Cohere rerank on top of retrieval candidate sets

This makes SKP a configurable RAG platform rather than a single fixed pipeline.

## Deployment architecture

### Canonical deployment model
The current canonical artifact is:
- `docker-compose.gpu.yml`

Primary services in that stack:
- `postgres`
- `redis`
- optional `ollama` profile (`bundled-ollama`)
- `api`
- `web`

### Deployment notes
- GPU-oriented deployment is the primary path for local or appliance-style demos.
- Ollama can run either:
  - inside Compose via the optional profile, or
  - on the host, referenced through `host.docker.internal`
- The frontend is deployed as a separate web container.
- The API container mounts a persistent document storage volume.

## Domain model

The core domain model lives in `app/models.py`.

### Identity and tenant model
- `User`
- `Organization`
- `OrganizationMembership`
- `OrganizationInvite`
- `Workspace`
- `WorkspaceMember`

Tenant structure is two-layered:
1. **Organization** is the tenant boundary
2. **Workspace** is the scoped collaboration and retrieval boundary within a tenant

### Knowledge ingestion model
- `IngestionJob`
- `Document`
- `DocumentChunk`
- `DocumentPermission`

Important characteristics:
- documents are always tied to `organization_id` and `workspace_id`
- chunks are first-class retrieval units
- per-document ACL support exists through `DocumentPermission`
- ingestion supports both uploaded files and connector-style text ingestion

### Chat and audit model
- `ChatSession`
- `ChatMessage`
- `QueryLog`
- `AuditLog`

This gives SKP durable conversation history plus operational traceability.

### Connectors and integration model
- `OrganizationConnector`
- `IntegrationConnector`

Connectors are modeled at the organization level, with downstream document ingestion tied back to connector sources.

## Request and processing flows

### Authentication flow
SKP supports two auth modes:
- local JWT/email-password auth
- optional Clerk-backed JWT verification

High-level flow:
1. user authenticates
2. API resolves current user from bearer token
3. protected endpoints verify organization/workspace access on the server
4. role checks are applied at org or workspace scope

### Organization and workspace management flow
1. platform owner creates organization
2. system provisions a default workspace
3. creator is assigned as org owner and workspace admin
4. org owners invite or upsert members
5. workspace admins assign workspace access
6. all sensitive membership and admin changes are audit logged

### File upload ingestion flow
Implemented in `app/routers/documents.py` and ingestion services.

Current high-level flow:
1. authenticated workspace member uploads a file to a workspace
2. file is persisted under document storage
3. text/pages are extracted
4. chunking is performed
5. embedding vectors are generated in batch
6. document and chunks are stored in Postgres
7. upload permission row is created where appropriate
8. document status becomes `indexed`

### Connector / raw text ingestion flow
Implemented through `ingest_document()` in `app/services/ingestion_service.py`.

Flow:
1. connector or API submits text content plus source metadata
2. system creates or updates the logical document keyed by source identity
3. previous chunks are replaced
4. new chunks are embedded and stored
5. ACLs are applied if full RBAC mode is active
6. document is marked indexed

### Retrieval flow
Implemented in `app/services/rag/pipeline.py`.

Flow:
1. resolve accessible documents for the requesting user
2. normalize query
3. embed query
4. fetch candidate chunks using configured retrieval strategy
   - vector retrieval
   - or hybrid vector + FTS retrieval
5. rerank candidates using:
   - heuristic rerank, or
   - Cohere rerank when enabled
6. post-filter results against permissions as a failsafe
7. return ranked hits for chat or search APIs

### Chat flow
Implemented primarily in `app/routers/chat.py` and `app/services/chat.py`.

Flow:
1. user creates or opens a chat session in a workspace
2. user submits a message
3. org query limits are enforced
4. recent conversation context is loaded
5. low-intent chitchat is short-circuited when appropriate
6. retrieval pipeline fetches grounded evidence
7. answer generation runs using configured provider
8. citations are attached
9. user and assistant messages are persisted
10. session metadata is updated

Streaming SSE chat is also supported.

## Retrieval architecture

### Retrieval strategies
SKP currently supports three retrieval strategies:

#### 1. Heuristic
- semantic vector retrieval from pgvector
- lexical/MMR heuristic rerank
- simplest default path

#### 2. Hybrid
- semantic vector retrieval plus Postgres full-text search
- merged using reciprocal rank fusion (RRF)
- useful for exact-term, number, and label matching

#### 3. Rerank
- semantic retrieval candidate pool
- hosted rerank with Cohere when configured
- fallback to heuristic rerank if hosted rerank is unavailable

### Grounding and fallback behavior
The answer pipeline enforces evidence sufficiency.

If evidence is insufficient, the system returns the exact fallback:

> I don't know based on the documents in this workspace.

This remains a core product behavior and safety guarantee.

## Ingestion architecture

### Current supported ingestion modes
The old MVP doc said PDF-only, but the current codebase has already moved beyond that.

Current upload/content handling includes support for:
- PDF
- DOCX
- TXT
- Markdown
- HTML
- PPTX
- XLSX / XLS
- CSV
- RTF
- additional connector-oriented text ingestion
- tier-3 / OCR-adjacent test assets and formats are present in the repo, indicating active expansion work

### Ingestion design principles
- normalize content into chunkable text
- persist original document metadata
- batch embedding calls
- replace chunks atomically on re-ingest
- keep document status and ingestion job status explicit
- preserve source identity for connector-driven updates

## Authorization and isolation model

### Isolation boundaries
SKP enforces isolation at multiple levels:
- organization membership
- workspace membership
- optional per-document ACL
- retrieval-time permission filtering
- endpoint-level access checks

### Modes
`settings.rbac_mode` supports:
- `simple`: workspace/org-wide access model
- `full`: document-level ACL enforcement through `DocumentPermission`

### Important enforcement points
- org membership required for org-scoped endpoints
- workspace membership required for workspace-scoped endpoints
- workspace admin checks for workspace admin actions
- org owner checks for org-level admin actions
- retrieval pipeline permission-filtering is applied both before and after candidate retrieval

## Audit and observability architecture

### Audit logging
Sensitive actions write to `AuditLog`, including:
- organization creation and updates
- membership upserts and removals
- invite lifecycle events
- workspace creation and updates
- workspace member changes
- document deletion
- chat session deletion
- connector deletion
- org/workspace deletion

### Other observability elements
- request ID middleware
- security header middleware
- configurable JSON logging
- health endpoints
- admin metrics surface
- query logs for RAG activity

## Configuration architecture

Configuration is centralized in `app/config.py`.

Key categories:
- database and Redis
- JWT and Clerk
- CORS and trusted hosts
- rate limiting
- ingestion chunking and batching
- embedding settings
- retrieval settings
- rerank settings
- answer generation provider/model settings
- cloud LLM credentials
- feature exposure

This design keeps runtime behavior environment-driven and deployable across local, Docker, and future production setups.

## Frontend architecture

The frontend is no longer a thin prototype. It already contains a fairly broad operator shell.

Major frontend concerns:
- auth-aware public vs protected routes
- organization context and platform-owner context
- workspace selection and workspace-specific operations
- admin panels for documents, team, billing, audit, connectors, and analytics
- embedded dashboard/chat flows
- dynamic public runtime config loading

The `HomePage` currently acts as a large application shell and orchestration surface for many admin workflows.

## Architectural strengths

Current strengths of the codebase:
- strong tenant-aware data model
- explicit workspace scoping throughout retrieval and chat
- practical self-hosted deployment path
- configurable answer-generation providers
- retrieval pipeline is already flexible enough for real experiments
- backend and frontend both exceed a toy MVP shape
- Docker-first deployment is aligned with demo and pilot usage

## Current architectural risks / debt

### 1. Documentation drift
The architecture docs were behind the codebase. They described several capabilities as planned that are already implemented.

### 2. Large frontend shell complexity
`frontend/src/pages/HomePage.tsx` has become a very large orchestration component. It works, but it is now an architectural hotspot and should eventually be decomposed.

### 3. Mixed maturity levels
The system combines:
- production-shaped backend patterns
- active feature expansion
- partially complete admin/UI verification paths

That means some surfaces are mature while others are still evolving quickly.

### 4. Synchronous ingestion shape
The current ingestion path is still primarily synchronous in request flow. That is fine for current demos and pilot scale, but background job orchestration may become necessary as file volume and connector sync scale increase.

## Recommended next architecture documentation set

This architecture doc should be the top-level map. The next docs to tighten are:
- `TECHDECISIONS.md` — update to reflect current retrieval, ingestion, and provider decisions
- `ROLES_AND_USERS.md` — verify against actual API/UI behavior
- a new `docs/architecture/INGESTION_AND_RETRIEVAL.md`
- a new `docs/architecture/FRONTEND_ARCHITECTURE.md`
- a new `docs/architecture/DEPLOYMENT_ARCHITECTURE.md`

## Source of truth

For the current implemented architecture, the main source-of-truth files are:
- `app/main.py`
- `app/models.py`
- `app/config.py`
- `app/routers/organizations.py`
- `app/routers/documents.py`
- `app/routers/chat.py`
- `app/services/ingestion_service.py`
- `app/services/rag/pipeline.py`
- `app/services/chat.py`
- `docker-compose.gpu.yml`
- `frontend/src/App.tsx`
- `frontend/src/layouts/ProtectedAppShell.tsx`
- `frontend/src/pages/HomePage.tsx`
