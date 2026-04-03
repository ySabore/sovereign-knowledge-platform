# ROADMAP.md — Sovereign Knowledge Platform

## How this file relates to other docs

- **`PRODUCT_REQUIREMENTS.md`** — MVP1 functional scope (multi-tenant, JWT, PDF, isolation, fallback text).  
- **`MVP_IMPLEMENTATION_PLAN.md`** — **default implementation phase order** for Forge.  
- **`DELIVERY_SPEC.md`** — strict OpenClaw delivery checklist.  

Where this roadmap’s release labels (v1, v2, …) overlap with the MVP plan, **MVP plan + product requirements win for what to build next** until reconciled.

## Mission

Ship a production-quality **Sovereign Knowledge Platform** that King can demo to a paying client within 2 months.

**Guiding rule:** tight scope, fast feedback, demoability first, **tenant safety** on any multi-org path.

---

## Product vision

**Sovereign Knowledge Platform** — private RAG for SMEs: ingest documents, answer with citations, deploy via cloud, on-prem, or GPU appliance. MVP1 adds **multi-org / workspace / JWT** per absorbed SME-RAG specification.

---

## Strategic Frame

We are not building a giant AI platform first.
We are building a **credible private RAG product** that:
- works reliably in a demo
- solves a real SME knowledge retrieval problem
- can be deployed simply
- has a clear path to customer hardening

Every roadmap choice should be filtered through one question:

**Does this improve the odds of a successful client demo and early pilot?**

---

## Release Plan Overview

- **v1 - Demo-ready private RAG assistant**
- **v1.5 - Pilot hardening**
- **v2 - Customer-ready multi-tenant platform**
- **v3 - Appliance + operations maturity**

---

## v1 - Demo-Ready Private RAG Assistant

### Goal

Deliver a working end-to-end product that can be shown to a paying client and used in a guided pilot.

### Success Criteria

- User can upload documents through the UI
- Documents are parsed, chunked, embedded, and indexed successfully
- User can ask questions and receive grounded answers with citations
- Product runs via Docker Compose on a single machine
- LLM provider is configurable between local Ollama and hosted API
- Basic deployment guide exists
- Demo dataset is available for repeatable walkthroughs

### Core Features

#### 1. Document ingestion
- Upload PDF, DOCX, TXT, Markdown
- Ingestion status tracking
- Retry failed ingestion manually
- Basic document metadata display

#### 2. Retrieval + chat
- Question answering over indexed documents
- Top-k vector retrieval
- Source citations in UI
- Conversation history per session
- Clear insufficient-context fallback behavior

#### 3. Minimal admin/configuration
- Environment-based configuration
- Health check endpoint
- Model selection through config
- Simple job/status visibility

#### 4. Deployment baseline
- Docker Compose stack
- `.env.example`
- One-command local startup
- Demo install documentation

### Nice-to-have if time allows

- Streaming chat responses
- Document delete/reindex
- Better citation preview snippets
- Basic feedback thumbs up/down
- Seed prompts / sample questions in UI

### Explicitly Out of Scope for v1

- Multi-tenancy
- Full auth/RBAC
- SSO
- External connectors (Google Drive, SharePoint, Notion, Confluence)
- Advanced analytics
- Kubernetes deployment
- Horizontal scaling
- Re-ranking pipelines
- Fine-grained permissions

### Suggested Delivery Sequence

#### Phase 1 - Foundation
- Repository structure
- Docker Compose with Postgres + pgvector
- FastAPI scaffold
- React scaffold
- Config management
- DB migrations baseline

#### Phase 2 - Ingestion pipeline
- File upload API
- File storage layout
- Ingestion jobs table
- Worker process
- Text extraction and chunking
- Embedding write path

#### Phase 3 - Question answering
- Query embedding
- Vector search
- Prompt builder
- LLM abstraction
- Chat API
- Citation rendering in UI

#### Phase 4 - Demo hardening
- Error handling
- Better loading/progress UX
- Seed demo dataset
- Smoke tests
- Deployment docs
- Demo script / golden path

---

## v1.5 - Pilot Hardening

### Goal

Bridge the gap between a good demo and a credible first customer pilot without overcommitting to enterprise scope.

### Success Criteria

- Single-customer deployments are stable
- Basic auth exists
- Admin can manage documents and reindexing
- Backup/restore instructions exist
- Logs and health checks are sufficient for support

### Core Features

- Basic authentication
- Admin document management
- Reindex/delete flows
- Better failure diagnostics
- Deployment profiles for cloud vs on-prem
- Basic usage logging
- Improved citation UX and answer quality tuning

### Why v1.5 exists

This keeps us from jumping directly from demo code to full multi-tenant platform work. It creates a commercially useful middle step.

---

## v2 - Customer-Ready Platform

### Goal

Turn the pilotable product into an early customer platform that can support multiple organizations and administrative controls.

### Success Criteria

- Multiple organizations/workspaces supported
- Authentication enabled
- Admin can manage documents, users, and settings
- Deployment options documented for cloud and on-prem pilots
- Basic auditability and operational controls exist

### Core Features

#### 1. Multi-tenancy
- Tenant/workspace model
- Tenant-level document isolation
- Tenant-aware retrieval

#### 2. Authentication and authorization
- Local auth or OIDC/SSO
- Admin/user roles
- Session management

#### 3. Admin panel
- User management
- Document management
- Reindex controls
- Model/provider settings

#### 4. Operational maturity
- Audit logs
- Better health/status views
- Backup/restore guidance
- Basic usage metrics

#### 5. Deployment options
- Cloud deployment guide
- On-prem deployment guide
- Config profiles for local vs hosted inference

### Nice-to-have for v2

- Hybrid retrieval (keyword + vector)
- Re-ranking
- Usage limits
- Feedback review dashboard
- Basic branding customization per tenant

### Out of Scope for Early v2

- Full marketplace of connectors
- Fine-grained document ACLs
- Massive scale multi-region infrastructure

---

## v3 - GPU Appliance + Mature Deployment Product

### Goal

Package the assistant as a premium private AI appliance and strengthen long-term maintainability.

### Success Criteria

- Product runs on a preconfigured GPU appliance
- Installation and upgrade process is repeatable
- Remote maintenance/support process is documented
- System health dashboard exists

### Core Features

#### 1. GPU appliance packaging
- Preconfigured Ubuntu image or scripted provisioning
- NVIDIA runtime setup
- Local Ollama model strategy
- Appliance-specific update flow

#### 2. Maintenance dashboard
- Service health status
- Storage usage
- Model status
- Background job visibility

#### 3. Supportability
- Backup and disaster recovery procedures
- Log bundle export
- Versioned release process
- Upgrade playbooks

#### 4. Deployment automation
- Install scripts
- Validation scripts
- Environment verification checklist

### Nice-to-have for v3

- Air-gapped update workflow
- Remote support tunnel workflow
- Hardware sizing calculator

---

## Cross-Cutting Milestones

### Milestone A - Demo Skeleton
- UI, API, DB, and worker running together
- Can upload a file and persist ingestion job

### Milestone B - Retrieval Works
- Embedded chunks searchable
- Chat returns grounded answers with citations

### Milestone C - Demo Polish
- Better UX, seed data, docs, smoke tests

### Milestone D - Pilot Readiness
- Auth, admin basics, single-customer stability

### Milestone E - Multi-Tenant Foundations
- Workspace isolation and user management

### Milestone F - Appliance Readiness
- Repeatable GPU deployment and maintenance workflow

---

## 8-Week Delivery View

### Weeks 1-2
- Repo structure
- Compose stack
- Postgres + pgvector setup
- API and UI scaffolds
- Initial schema and migrations

### Weeks 3-4
- Upload flow
- Ingestion jobs
- Parsing/chunking pipeline
- Embedding generation and storage

### Weeks 5-6
- Retrieval pipeline
- Prompt assembly
- Chat API
- Citations in UI
- Provider switching local vs hosted

### Weeks 7-8
- Hardening
- Smoke tests
- Demo dataset
- Deployment docs
- Demo walkthrough refinement

---

## Priority Rules

When trade-offs appear, choose in this order:

1. Demoability
2. Reliability
3. Simplicity of deployment
4. Privacy/control of customer data
5. Feature breadth
6. Architectural elegance

---

## Kill List

If time gets tight, cut these before cutting the core loop:

- streaming responses
- polished feedback system
- advanced UI styling
- hybrid retrieval
- connector experiments
- Kubernetes work
- enterprise auth complexity

---

## Current Recommendation

Focus immediately on **Phase 1 verification**, then continue with **v1 foundation + ingestion + retrieval**.

Right now the roadmap bottleneck is not planning breadth — it is proving the scaffold runs locally.

If a feature does not directly improve the first client demo, it should probably wait.

---

## Next Documents to Create

To operationalize this roadmap, create and maintain:
- `SPRINT.md` - current sprint execution plan
- `TECH_DECISIONS.md` - architecture decision record log
- `DEPLOYMENT.md` - deployment playbooks for local, cloud, on-prem, and appliance paths
