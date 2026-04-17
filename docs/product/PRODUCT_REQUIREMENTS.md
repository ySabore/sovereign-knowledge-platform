# PRODUCT_REQUIREMENTS.md — Sovereign Knowledge Platform

## Product name

**Sovereign Knowledge Platform** — private, self-hosted RAG for privacy-sensitive SMEs.  
(Internal lineage: absorbs the **SME-RAG** / RackRAG specification from `Downloads\SME-RAG`.)

## Product summary

Sovereign Knowledge Platform is a self-hosted, multi-organization RAG system for SMBs that want document search and Q&A on **their** infrastructure. Organizations use workspaces, upload internal documents, and ask grounded questions using local embeddings and local (or configured) LLM inference.

The system must support **strong multi-tenant isolation**, workspace-level access control, **grounded answers with citations**, and a **strict fallback** when evidence is insufficient.

## Primary goals

- Support multiple organizations on one shared platform (where deployed that way).
- Isolate each organization’s data from all others.
- Support workspace-level document scoping.
- Allow local document ingestion and configurable inference.
- Return grounded responses with citations.
- Return a safe fallback when evidence is insufficient.
- Run on a target host (including local GPU server) using Docker Compose for MVP.

## Target users

### Platform owner

- Creates and manages organizations.
- Oversees platform-wide operations.
- Can suspend or deactivate organizations.
- Can view high-level system health and usage.

### Organization owner

- Manages one organization.
- Creates workspaces.
- Invites users.
- Uploads and manages organization/workspace documents.
- Views organization-level usage and activity.

### Workspace admin

- Manages assigned workspaces.
- Adds/removes workspace members.
- Uploads and manages workspace documents.

### Member

- Chats within assigned workspaces.
- Views responses and citations.
- Cannot manage settings unless granted additional role permissions.

## MVP1 scope

### Included

- Multi-organization support.
- Role-based login and JWT authentication.
- Organization creation by platform owner.
- Workspace creation by org owner.
- Member invitation and assignment.
- **PDF-only** upload for MVP1 (extend to DOCX/TXT/Markdown in a follow-up release per architecture notes).
- PDF parsing, chunking, embedding, indexing.
- Workspace-scoped chat with retrieval.
- Grounded answers with citations.
- Exact fallback answer when evidence is insufficient (see below).
- React frontend.
- FastAPI backend.
- PostgreSQL with pgvector.
- Redis-based chat/session caching.
- Docker Compose deployment.
- Basic health checks, logging, and rate limiting.
- Seed/demo data and isolation tests.

### Exact fallback text (MVP1)

When evidence is insufficient, the system must return exactly:

> I don't know based on the documents in this workspace.

### Excluded from MVP1

- Google Drive, Jira, Bitbucket ingestion.
- URL crawling.
- Billing and Stripe.
- Public chatbot embedding.
- Enterprise SSO.
- Web search fallback.
- OCR and multimodal ingestion.
- Kubernetes deployment (Compose first).
- Advanced analytics dashboards.
- Cross-encoder reranking.
- Multi-model routing.

## Functional requirements

### Authentication and authorization

- JWT-based authentication.
- Role-based authorization.
- Organization and workspace membership verified on every protected endpoint.
- Never trust client-supplied tenant authority without server-side verification.

### Organization and workspace management

- Platform owner can create organizations.
- Org owner manages org and creates workspaces.
- Workspace membership tracked separately from org membership where required by spec.

### Document ingestion

- MVP1 accepts **PDF only** (unless build explicitly extends types).
- Validate MIME/type and configurable size limits.
- Parse, chunk, embed; track indexing status per document.

### Retrieval and chat

- Embed user questions; retrieve top-k with **org_id** and **workspace_id** filters on every search.
- Answers grounded in retrieved context; citations returned.
- Insufficient evidence → exact fallback string above.
- Workspace operational questions should be answered from trusted metadata when possible
  (for example document counts, indexing state counts, recent uploads, and source breakdown).
- Chat should support direct in-context file upload for workspace members so new files can be
  indexed and queried without leaving the chat experience.

### Chat history

- Sessions associated with org, workspace, and user.
- Persisted; Redis may be used for hot state per implementation plan.
- Session titles should be derived from user context (first substantive prompt, with optional
  second-turn refinement when first prompt is generic).
- Users should be able to provide per-answer feedback (thumbs up/down) and have it persisted.
- Users should be able to export conversation content to PDF from chat.

### Audit and logging

- Important actions audit-logged.
- Structured logs for operations.

## Non-functional requirements

- HTTPS in production; password hashing; CORS; file validation; rate limiting; audit logs for sensitive operations.
- Strong logical tenant isolation; no cross-org leakage; workspace access enforced in API and retrieval.

## Success criteria (MVP1)

- Platform owner can create organizations.
- Org owner can create workspaces and invite users.
- PDFs upload and reach indexed state.
- Members chat in assigned workspaces with citations.
- Empty/weak retrieval yields the **exact** fallback response.
- Isolation tests prove one org cannot access another org’s documents.

## Future enhancements

- Additional file types and connectors.
- Stronger retrieval (rerank, hybrid search).
- Analytics, billing, SSO, dedicated vector DB at scale.
