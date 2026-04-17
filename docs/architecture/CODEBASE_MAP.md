# CODEBASE_MAP.md — Sovereign Knowledge Platform

## What SKP is, in plain English

SKP is not just a chatbot app.

It is a **multi-tenant knowledge platform** with four major product surfaces fused together:

1. **tenant administration**
   - organizations
   - workspaces
   - memberships
   - invites
   - admin views

2. **knowledge ingestion**
   - file upload ingestion
   - connector-driven ingestion
   - chunking, embedding, indexing
   - document permissions

3. **grounded retrieval and chat**
   - workspace-scoped retrieval
   - citation-bearing answers
   - session history
   - SSE streaming
   - configurable answer providers

4. **operator / pilot platform controls**
   - metrics
   - billing scaffolding
   - connector activation and sync
   - public runtime config
   - deployment and demo support

That matters because the repo should be read as a platform codebase, not a simple RAG demo.

---

## Top-level repo shape

### Backend
- `app/`
- `alembic/`
- `tests/`
- `scripts/`

### Frontend
- `frontend/src/` — **production cutover SPA** (compose `web` service builds from `frontend/Dockerfile`)
- `frontend/src/` — legacy SPA tree (retained until archive; same product intent, pre-refactor layout)

### Deployment / docs
- `docker-compose*.yml`
- `Dockerfile`
- `deploy/`
- `docs/`

---

## Backend architecture map

## 1. Application shell

### `app/main.py`
This is the backend composition root.

Responsibilities:
- create FastAPI app
- wire middleware
- register routers
- configure limiter / exception handling

This file answers the question: **what is actually exposed by the backend right now?**

---

## 2. Configuration and infrastructure

### `app/config.py`
Central runtime configuration.

Key areas:
- database / Redis
- JWT / Clerk auth
- CORS / trusted hosts
- logging and rate limiting
- ingestion chunking knobs
- embedding configuration
- retrieval strategy defaults
- rerank configuration
- answer-generation provider selection
- org-level cloud model support

This is the operational control plane of the app.

### `app/database.py`
Database engine / session wiring.

### `app/logging_config.py`
Structured logging setup.

### `app/limiter.py`
SlowAPI limiter wiring.

### `app/middleware/*`
Cross-cutting request concerns:
- request ID propagation
- security headers

---

## 3. Data model layer

### `app/models.py`
This is the core platform model.

Main clusters:

#### Identity / tenancy
- `User`
- `Organization`
- `OrganizationMembership`
- `OrganizationInvite`
- `Workspace`
- `WorkspaceMember`

#### Knowledge / ingestion
- `IngestionJob`
- `Document`
- `DocumentChunk`
- `DocumentPermission`

#### Chat / audit / analytics
- `ChatSession`
- `ChatMessage`
- `QueryLog`
- `AuditLog`

#### Integrations
- `OrganizationConnector`
- `IntegrationConnector`

If you want to understand SKP’s real product boundaries, start here.

---

## 4. Auth and request identity

### `app/deps.py`
Contains route dependency logic, including:
- current user resolution
- platform-owner requirements
- admin visibility requirements
- authz helpers used by routers

### `app/auth/security.py`
Local JWT/password security primitives.

### `app/auth/clerk_jwt.py`
Optional Clerk JWT verification path.

Interpretation:
SKP supports both its own local auth flow and a Clerk-backed external identity mode.

---

## 5. Router layer

The routers are relatively clean and map well to product domains.

### `app/routers/auth.py`
Handles:
- login
- current-user profile
- auth entrypoints

### `app/routers/organizations.py`
This is one of the most important backend files.

Handles:
- organization creation and update
- organization membership
- workspace creation and update
- workspace membership
- invites
- destructive delete flows
- audit logging hooks
- default workspace provisioning

This file is the **tenant administration core** of the product.

### `app/routers/documents.py`
This is the **knowledge ingestion and retrieval API** surface.

Handles:
- file upload
- text ingestion
- list/get document status
- ingestion job status
- document delete
- workspace document search

Important note:
this router shows the codebase has already moved beyond PDF-only messaging.

### `app/routers/chat.py`
This is the **workspace chat domain**.

Handles:
- create/list/get/delete chat sessions
- create persisted chat messages
- stream chat over SSE

This is not just inference, it is sessionized grounded chat with persistence.

### `app/routers/api_chat.py`
A simplified SPA-friendly alias for streaming chat.

Purpose:
- lets frontend call `POST /api/chat` style flow cleanly
- thin alias over chat streaming behavior

### `app/routers/connectors.py`
This is the **integration activation + sync control surface**.

Handles:
- connector activation
- connector listing
- sync trigger
- permission sync
- connector deletion

This shows SKP is aiming beyond manual uploads into synced knowledge sources.

### `app/routers/metrics.py`
This is the **operator / stakeholder summary metrics** API.

Handles:
- summary metrics (`/metrics/summary`)

Org-scoped document and audit lists now live under `app/routers/organizations.py`.

### `app/routers/billing.py`
Billing surface and plan logic entrypoint.

### `app/routers/runtime_config.py`
Exposes safe runtime config for frontend behavior.

### `app/routers/health.py`
Health and readiness endpoints.

### `app/routers/webhooks_clerk.py`
Clerk webhook handling.

### `app/routers/webhooks_stripe.py`
Stripe webhook handling.

---

## 6. Service layer

The backend’s real behavior lives here.

## 6.1 Ingestion services

### `app/services/ingestion.py`
Lower-level ingestion utilities.

Responsibilities include:
- upload persistence
- page/text extraction
- chunk construction
- content cleaning helpers

### `app/services/ingestion_service.py`
Higher-level ingestion orchestration.

This is the key reusable ingestion engine for:
- connector ingestion
- raw text ingestion
- re-indexing existing logical documents

Important behavior:
- create/update document by source identity
- delete old chunks
- embed new chunks in batch
- mark document indexed/failed
- apply ACL behavior

### `app/services/text_cleaner.py`
Content cleanup helpers before chunking/indexing.

---

## 6.2 Embeddings and LLM services

### `app/services/embeddings.py`
Embedding provider client abstraction.

### `app/services/chat.py`
This is the answer-generation brain.

Responsibilities:
- determine whether evidence is sufficient
- build citations
- enforce exact fallback behavior
- route to answer provider:
  - extractive
  - ollama
  - openai
  - anthropic
- downgrade to extractive when model output is not citation-safe

This file is one of the most product-critical parts of the repo.

### `app/services/llm/cloud_chat.py`
Cloud LLM wrappers for OpenAI / Anthropic style calls.

### `app/services/org_chat_credentials.py`
Resolves provider credentials and base URLs at org/platform scope.

This is what enables per-org model/provider configuration.

---

## 6.3 Retrieval services

There are two retrieval-related namespaces in the repo:
- `app/services/retrieval.py`
- `app/services/rag/*`

The real retrieval engine is in `app/services/rag/*`.

### `app/services/rag/pipeline.py`
Top-level retrieval orchestration.

Responsibilities:
- resolve retrieval strategy
- embed query
- fetch candidate chunks
- apply reranking
- enforce permission filtering

### `app/services/rag/retrieval.py`
Lower-level retrieval functions.

Responsibilities:
- vector retrieval
- hybrid retrieval
- strategy resolution
- query embedding helpers

### `app/services/rag/heuristic_rerank.py`
Heuristic post-processing and reranking.

### `app/services/rag/cohere_rerank.py`
Optional hosted rerank integration.

### `app/services/rag/rrf.py`
Reciprocal rank fusion for hybrid retrieval.

### `app/services/rag/prompts.py`
Prompt builders for grounded LLM answers.

### `app/services/rag/query_normalize.py`
Normalizes user query text for retrieval.

### `app/services/rag/types.py`
Typed retrieval result objects.

Interpretation:
SKP already has a fairly modular RAG engine, not a hardcoded retrieval function.

---

## 6.4 Access control, billing, and operations services

### `app/services/permissions.py`
Document permission helpers and permission sync.

### `app/services/workspace_access.py`
Workspace resolution for authenticated users.

### `app/services/rate_limits.py`
Org-aware rate limits and admin/sync/query throttling.

### `app/services/billing.py`
Plan enforcement helpers such as seat and connector limits.

### `app/services/metrics.py`
Aggregations for operator dashboards.

### `app/services/query_log.py`
Query analytics persistence helpers.

### `app/services/resource_cleanup.py`
Cascade-style cleanup for stored files and related resources.

---

## 6.5 Connector and sync services

### `app/services/nango_client.py`
Connector API client abstraction.

### `app/services/sync_orchestrator.py`
Background-ish orchestration for connector sync.

Responsibilities:
- resolve target workspace
- fetch remote documents
- ingest each into SKP
- update connector sync status

Important architectural note:
this is currently worker-friendly code but still relatively simple orchestration. It is a good candidate for a real job runner later.

---

## 6.6 Chat UX support services

### `app/services/chat_history.py`
Loads recent conversation context.

### `app/services/chat_sse.py`
Server-side SSE event emission for streaming chat.

### `app/services/chat_stream.py`
Streaming support logic.

### `app/services/chitchat.py`
Low-intent / greeting handling so trivial chat does not need retrieval.

---

## Frontend architecture map

Paths below use **`frontend/src/`** as the primary reference. The legacy tree under `frontend/src/` mirrors many of the same files until it is archived.

## 1. Frontend shell

### `frontend/src/App.tsx`
Top-level route map.

Public routes:
- landing / marketing
- login
- Clerk sign-in / sign-up

Protected routes:
- home
- organizations
- dashboard workspace routes
- enterprise demo route

### `frontend/src/layouts/ProtectedAppShell.tsx`
Loads org membership once and provides org context to the protected app.

This is the main protected shell bootstrap layer.

### `frontend/src/context/AuthContext.tsx`
Frontend auth state manager.

Responsibilities:
- hold JWT token
- load `/auth/me`
- support login/logout
- recover from session failures
- coordinate local JWT and Clerk-backed flows

This is the main frontend identity state source.

---

## 2. Frontend major pages

### `frontend/src/pages/HomePage.tsx`
Acts as the org/workspace shell inside the protected app. In **`frontend`**, large parts of navigation, workspace state, knowledge gating, and panel routing live under **`src/features/home-shell/`** (`HomePanelRouter`, hooks, `HomeSidebar`, `HomeTopBar`, etc.). The legacy **`frontend/`** copy may still be a single oversized file.

It handles large parts of:
- org selection
- workspace selection
- dashboards
- team management
- connectors
- document surfaces
- analytics
- billing
- settings
- embedded chat routing

Interpretation:
in legacy `frontend/`, this page became a mini frontend platform on its own. In `frontend/`, that surface is intentionally decomposed while preserving UX.

### `frontend/src/pages/app/DashboardPage.tsx`
This is the modern workspace chat experience.

Responsibilities:
- workspace conversation list
- session switching
- SSE chat streaming
- citations side panel
- message rendering
- lightweight generation metadata display

This is the cleanest expression of the end-user knowledge assistant UX.

### `frontend/src/pages/WorkspaceChatPage.tsx`
Older or simpler workspace chat flow.

Still useful as a simpler reference implementation, but the richer dashboard chat appears to be the primary current UX direction.

Admin functionality is now absorbed into the main shell (`HomePage` + home-shell feature modules) with role-based panel visibility.

---

## 3. Frontend components and supporting libraries

### Components
Notable areas:
- `components/chat/*`
- `KnowledgeAnalyticsPanel.tsx`
- `PlatformOwnerDashboard.tsx`
- `TeamManagementPanel.tsx`
- `WorkspaceConnectorsPanel.tsx`

### Contexts
- `AuthContext.tsx`
- `PlatformNavigationContext.tsx`
- `OrgShellThemeContext.tsx`

### Libraries
- `lib/chatSse.ts`
- `lib/publicConfig.ts`
- `lib/nangoConnect.ts`
- `lib/clerkTokenBridge.ts`
- `lib/permissions.ts`

These show the frontend is handling real operational concerns, not just a static UI.

---

## Current system strengths

### Strength 1: backend boundaries are fairly sane
The router/service split is mostly good.

### Strength 2: data model is strong
The tenant, workspace, document, chat, and permission model is credible for a real product.

### Strength 3: retrieval architecture is ahead of the docs
The retrieval stack is already modular and extensible.

### Strength 4: deployment model is practical
Docker-first, GPU-friendly, self-hosted aligned.

### Strength 5: frontend already demonstrates product breadth
The product is not vapor. There is real admin and operator surface area.

---

## Current hotspots and likely refactor priorities

### 1. Org/workspace shell maintainability
- **Legacy `frontend/`:** `HomePage.tsx` remains the single biggest structural hotspot (size and mixed concerns).
- **`frontend/`:** risk shifts to **contract discipline** across `features/home-shell` and **parity** with the legacy app; run `npm run verify:readiness` in `frontend` and follow `docs/frontend-parity-checklist.md`.

### 2. docs lagging implementation
Several docs still describe earlier product assumptions.

### 3. mixed maturity in ingestion messaging vs implementation
Public/product docs and architectural docs should be aligned about what is actually supported today versus what is marketed as the MVP lane.

### 4. sync orchestration is ready for a worker lane later
`sync_orchestrator.py` is good enough for now, but if connector volume grows this should move behind a more explicit async job execution model.

---

## Mental model for reading this repo efficiently

If you want to understand SKP fast, read in this order:

1. `app/models.py`
2. `app/main.py`
3. `app/routers/organizations.py`
4. `app/routers/documents.py`
5. `app/routers/chat.py`
6. `app/services/ingestion_service.py`
7. `app/services/rag/pipeline.py`
8. `app/services/chat.py`
9. `frontend/src/App.tsx`
10. `frontend/src/layouts/ProtectedAppShell.tsx`
11. `frontend/src/pages/HomePage.tsx` (+ `frontend/src/features/home-shell/`)
12. `frontend/src/pages/app/DashboardPage.tsx`

That order gives the fastest path from platform model to user experience.

---

## Bottom line

SKP is already a real platform-shaped codebase with these identities at once:
- tenant-admin SaaS core
- self-hosted RAG engine
- document ingestion/indexing system
- workspace knowledge assistant
- operator/demo platform

The codebase’s main issue right now is not lack of substance.
It is **keeping structure and docs aligned as the product expands.**

