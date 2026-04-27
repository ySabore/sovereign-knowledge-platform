# Sovereign Knowledge Platform

## Technical Review, Cloud Deployment Recommendation, and Production Readiness Assessment

Date: 2026-04-24

## Companion Summaries (Audience-Specific)

- Executive (1-page): `docs/deliverables/EXECUTIVE_SUMMARY_RETRIEVAL_AND_PLATFORM_IMPROVEMENTS_2026-04.md`
- Technical leadership: `docs/deliverables/TECH_LEAD_SUMMARY_RETRIEVAL_AND_PLATFORM_IMPROVEMENTS_2026-04.md`
- Customer-facing: `docs/deliverables/CUSTOMER_SUMMARY_RETRIEVAL_AND_PLATFORM_IMPROVEMENTS_2026-04.md`
- Detailed implementation log: `docs/deliverables/RETRIEVAL_AND_PLATFORM_IMPROVEMENTS_2026-04.md`

## 1. Executive Summary

The current repository is no longer a simple RAG prototype. It is a multi-tenant knowledge platform with:

- a FastAPI backend
- a React/Vite frontend
- PostgreSQL with pgvector as both transactional store and vector store
- Redis for readiness, rate limiting, and plan/burst enforcement
- a configurable retrieval and answer-generation layer
- connector activation and sync flows through Nango
- organization/workspace RBAC, document ACL support, billing, audit logging, and operator analytics

The platform is materially ahead of the older MVP documentation in `README.md` and parts of `docs/`. In particular, the codebase now includes:

- broader file ingestion beyond PDFs
- Clerk and local JWT auth modes
- Stripe billing scaffolding
- connector catalog and workspace-scoped connector assignment
- hosted/cloud model support for OpenAI, Anthropic, and Cohere
- chat streaming, analytics, and audit surfaces

The codebase is viable for a pilot or controlled cloud deployment after several targeted hardening steps. It is not yet cloud-production ready in its current form because the most important background and storage concerns are still shaped around local Docker deployment.

Primary recommendation:

- use managed cloud services for data plane components
- move document storage off the local container filesystem into object storage
- move connector sync and heavy ingestion out of synchronous API requests into background workers
- use managed cloud LLM APIs for the first production release unless strict sovereignty requires dedicated GPU hosting

## 2. What The Application Actually Is Today

At runtime, SKP behaves as a tenant-aware enterprise knowledge system with these layers:

### Frontend

- React 19 + TypeScript SPA in `frontend/`
- App shell, org/workspace navigation, billing, analytics, documents, chat, and connector management
- Production packaging through `frontend/Dockerfile` and nginx

### Backend API

- FastAPI composition root in `app/main.py`
- Router groups for auth, organizations/workspaces, documents, chat, connectors, metrics, runtime config, billing, Clerk webhooks, and Stripe webhooks
- Cross-cutting middleware for request IDs, security headers, and mutation audit logging

### Data plane

- PostgreSQL 16 + pgvector
- Redis for rate-limit and plan enforcement
- local filesystem document storage today

### AI and retrieval layer

- embeddings via Ollama today by default
- answer generation providers: `extractive`, `ollama`, `openai`, `anthropic`
- optional hosted rerank with Cohere
- workspace-scoped retrieval with optional document-level ACL enforcement

### Integration layer

- Nango-backed connectors
- connector-to-workspace assignment
- sync orchestration that ingests external content into the same RAG index

## 3. Current Backend Architecture

### 3.1 Composition root

`app/main.py` wires:

- CORS
- trusted hosts
- security headers
- request IDs
- SlowAPI
- audit mutation middleware
- all routers

This file is a good representation of current product scope. The repository has clearly moved past the older phase descriptions.

### 3.2 Domain model

The core persistent model in `app/models.py` includes:

- `User`
- `Organization`
- `OrganizationMembership`
- `OrganizationInvite`
- `Workspace`
- `WorkspaceMember`
- `IngestionJob`
- `Document`
- `DocumentChunk`
- `DocumentPermission`
- `ChatSession`
- `ChatMessage`
- `QueryLog`
- `AuditLog`
- `OrganizationConnector`
- `IntegrationConnector`

This is a strong platform model. The organization and workspace boundary is implemented consistently through most routes and services.

### 3.3 Ingestion and retrieval

The ingestion subsystem is implemented through:

- `app/routers/documents.py`
- `app/services/ingestion.py`
- `app/services/ingestion_service.py`

Current ingestion supports more than the older docs imply:

- PDF
- DOCX
- TXT
- Markdown
- HTML
- PPTX
- XLSX/XLS
- CSV
- RTF
- email formats
- some OCR-backed image paths

Retrieval and grounded answer generation are implemented through:

- `app/services/rag/pipeline.py`
- `app/services/chat.py`
- `app/services/chat_sse.py`

The code supports:

- vector retrieval
- hybrid retrieval
- rerank mode
- grounded citations
- deterministic fallback when evidence is weak

### 3.4 Auth and security model

Auth is split between:

- local JWT/password auth
- optional Clerk JWT validation

RBAC is split between:

- org membership
- workspace membership
- optional document-level ACLs in `RBAC_MODE=full`

This is directionally strong for enterprise tenancy, but some production controls still need cloud-hardening.

### 3.5 Frontend architecture

The active frontend is in `frontend/src/`. The current shell is concentrated in:

- `frontend/src/pages/HomePage.tsx`
- `frontend/src/components/WorkspaceConnectorsPanel.tsx`
- `frontend/src/features/*`

Observations:

- the UI exposes mature admin/operator surfaces
- the connector management component already uses `/config/public` dynamically
- some higher-level home-shell connector presentation still contains duplicated static catalog assumptions

## 4. Existing Documentation Drift

The repository documentation is useful, but parts of it are stale relative to the code.

Examples of drift found during review:

- `README.md` still frames some capabilities as if the system were earlier-phase and PDF-first, while `app/services/ingestion.py` now supports many more file types.
- `docs/configuration.md` contains values that do not match current defaults in `app/config.py`, including retrieval/chat defaults.
- older architecture notes still reference a narrower router/service set than the code currently exposes.

Recommendation:

- treat code as the source of truth
- keep a dated technical review document like this one in `docs/deliverables/`
- update the top-level docs after release-hardening so external readers are not onboarded onto stale assumptions

## 5. Review Findings

### Finding 1: Configurable embedding dimensions are not actually deployable

Severity: High

`app/config.py` exposes `EMBEDDING_DIMENSIONS`, but `app/models.py` hardcodes `DocumentChunk.embedding` as `Vector(768)`.

Impact:

- any attempt to switch to a non-768 embedding model will break writes or retrieval behavior
- the deployment/config surface currently implies portability that the schema does not actually support

Recommendation:

- make embedding dimensions an explicit schema-level invariant per deployment
- either remove the runtime configurability or add a migration strategy and model/schema alignment for alternate vector sizes

### Finding 2: The non-streaming chat path does not write `QueryLog`, but the current workspace chat UI uses that path

Severity: High

Evidence:

- `frontend/src/pages/WorkspaceChatPage.tsx` posts to `POST /chat/sessions/{id}/messages`
- `app/routers/chat.py` persists chat messages on that route but does not call `record_query_log`
- `app/services/chat_sse.py` does call `record_query_log`
- `app/services/metrics.py` builds dashboard analytics from `QueryLog`

Impact:

- operator analytics undercount or miss normal chat usage
- product decisions based on top queries, unanswered queries, and usage trends will be distorted
- billing/usage views can diverge from actual user behavior

Recommendation:

- centralize query logging for both streaming and non-streaming chat paths
- add regression tests covering analytics visibility after a normal non-streaming chat turn

### Finding 3: Connector sync runs inline on the API request path

Severity: Medium to High

Evidence:

- `app/routers/connectors.py` calls `run_connector_sync(...)` directly inside `POST /connectors/{id}/sync`
- `app/services/sync_orchestrator.py` performs a potentially long-running fetch/ingest loop in-process

Impact:

- long syncs will tie up API workers
- cloud load balancers and ingress timeouts can terminate sync requests
- retries can create duplicate or overlapping sync behavior
- production scaling becomes harder because request capacity and ingestion capacity are coupled

Recommendation:

- move sync execution to background workers
- use a durable queue and idempotent job records
- keep the API route as an enqueue/status trigger, not the work executor

## 6. Recommended Cloud Target Architecture

## Recommended first production target: AWS managed services

This codebase maps cleanly onto AWS without requiring Kubernetes as the first step.

### Component placement

#### Public edge

- CloudFront for SPA delivery
- AWS WAF in front of public app/API if external-facing
- ACM-managed TLS certificates

#### Frontend

Preferred:

- S3 + CloudFront hosting for the built SPA

Alternative:

- keep nginx container only if you need same-origin `/api` proxy behavior during transition

#### API

- ECS Fargate service for FastAPI containers
- Application Load Balancer in front of the API
- separate services for `api-web` traffic and `worker` traffic if background jobs are introduced

#### Database

- Amazon RDS for PostgreSQL with pgvector enabled
- Multi-AZ for production
- automated backups and point-in-time recovery enabled

#### Redis

- ElastiCache for Redis
- used for rate limiting, plan cache, and future coordination

#### Document storage

Current state:

- local volume at `/app/data/documents`

Recommended state:

- Amazon S3 bucket for uploaded and synced document binaries
- signed URL or server-side SDK access
- versioning and lifecycle policies enabled

This is one of the most important changes before production. Container-local document storage is not suitable for resilient cloud deployment.

#### Background jobs

Recommended:

- SQS queue
- worker service on ECS Fargate
- scheduled jobs through EventBridge for recurring sync

Use this for:

- connector sync
- re-ingestion
- OCR-heavy processing
- document cleanup and retry workflows

#### Secrets and config

- AWS Secrets Manager for API secrets and provider credentials
- SSM Parameter Store for non-secret environment config

#### Observability

- CloudWatch logs and metrics
- OpenTelemetry or similar tracing if expanded later
- alarms for API latency, 5xx rate, queue backlog, sync failures, DB saturation, and Redis errors

### AI provider recommendation

For first cloud production:

- prefer hosted OpenAI/Anthropic/Cohere APIs

Why:

- lower operational burden
- easier scaling
- avoids GPU scheduling and model lifecycle management
- better fit for a SaaS pilot or early production release

Use dedicated Ollama/GPU hosting only if:

- strict data-sovereignty rules prohibit hosted model APIs, or
- the product specifically differentiates on local/private inference

If private inference is mandatory, deploy it as a separate inference service, not as a hidden dependency on `host.docker.internal`.

## 7. Cloud Deployment Blueprint

### Environment split

Use at least three environments:

- `dev`
- `staging`
- `production`

### Deployment units

#### Unit 1: Frontend build artifact

- built by CI
- published to S3
- invalidated through CloudFront

#### Unit 2: API container

- built once per commit
- deployed via ECS task definition update
- runs migrations as a controlled release step, not ad hoc on container boot forever

#### Unit 3: Worker container

- same codebase, different entrypoint
- consumes sync/ingestion jobs

#### Unit 4: Managed data services

- RDS PostgreSQL
- ElastiCache Redis
- S3 documents bucket

### Networking

- private subnets for RDS, Redis, and workers
- public ALB only for the API
- tightly scoped security groups

## 8. Production Readiness Assessment

### Ready or mostly ready

- multi-tenant domain model
- role-based access model
- API layering and configuration organization
- testable backend service boundaries
- local-to-cloud container packaging starting point
- rate limit primitives
- audit model
- billing scaffolding

### Not ready yet

- durable object storage abstraction
- background job architecture
- full production observability
- release automation and migration discipline
- disaster recovery runbooks
- secret rotation and credential lifecycle management
- full frontend and backend end-to-end cloud smoke coverage

### Specific release blockers

1. Replace local document storage with object storage abstraction.
2. Move connector sync and heavy ingestion out of the request path.
3. Align embedding dimension config with actual schema behavior.
4. Make analytics consistent across all chat entry paths.
5. Add production-grade logging, alarms, and tracing.
6. Define migration, rollback, and backup procedures.

## 9. Recommended Production Hardening Backlog

### Priority 0

- object storage abstraction for documents
- async job queue and worker for connector sync and ingestion
- fix query logging parity between streaming and non-streaming chat
- make vector dimension handling explicit and safe

### Priority 1

- structured audit and application log shipping
- health/readiness checks for external providers beyond Ollama-only assumptions
- API timeout, retry, and circuit-breaker strategy for Nango and model providers
- idempotent sync jobs with job status persistence

### Priority 2

- SSO/enterprise identity production hardening
- row-level retention policies for audit/query logs
- per-tenant operational dashboards
- formal data retention and deletion workflows

## 10. Suggested Release Path

### Phase A: Cloud pilot

- frontend on S3/CloudFront
- API on ECS Fargate
- RDS PostgreSQL
- ElastiCache Redis
- S3 for documents
- hosted model providers
- manual or limited connectors

### Phase B: Production baseline

- worker service and queue
- automated connector scheduling
- observability and alarms
- blue/green or rolling deployment workflow
- staging gate with migration verification

### Phase C: Sovereign/private inference option

- dedicated inference service with GPU-backed deployment
- private networking between API and model service
- model pull, capacity, and failover runbooks

## 11. Verification Performed For This Review

Validated during this review:

- backend test suite: `67` tests passed
- frontend TypeScript typecheck passed
- repository inspection covered backend routers, core services, deployment assets, frontend shell, and existing documentation

## 12. Final Recommendation

The strongest path to cloud deployment is:

1. keep the app architecture largely intact
2. replace local infrastructure assumptions with managed cloud primitives
3. separate API request handling from long-running ingestion/sync work
4. standardize operational truth across code, analytics, and documentation

This codebase is close to a credible pilot platform. With the storage, worker, and analytics corrections above, it can become a much stronger production candidate without a full rewrite.
