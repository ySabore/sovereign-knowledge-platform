# DELIVERY_SPEC.md — OpenClaw agents (strict)

Non-negotiable delivery contract for **Sovereign Knowledge Platform**, absorbed from `Downloads\SME-RAG\OPENCLAW_AGENT_PROMPT.md`.

**Forge (architect)** must read this before writing or changing product code. **Main (Apex)** uses this when coordinating builds. Other agents reference `shared/COMPANY.md` and this file for product truth.

## Goal

Build a production-leaning MVP: **multi-tenant**, self-hosted where specified, **strict tenant isolation**, workspace-scoped access, **PDF ingestion (MVP1)**, grounded chat with citations, and when evidence is insufficient respond **exactly**:

`I don't know based on the documents in this workspace.`

## Tech stack (MVP)

**Frontend:** React + Vite, Tailwind, shadcn/ui, Axios, React Router.  

**Backend:** FastAPI, Pydantic, SQLAlchemy, Alembic, JWT, password hashing.  

**Data:** PostgreSQL, pgvector, Redis.  

**AI:** Ollama embeddings; local or configured generation; LangChain or LlamaIndex acceptable for orchestration if kept maintainable.  

**Infra:** Docker Compose, Nginx reverse proxy, persistent volumes, GPU-capable host when applicable.

## MVP includes

1. Platform owner creates organizations.  
2. Org owner creates workspaces and invites users.  
3. Roles: `platform_owner`, `org_owner`, `workspace_admin`, `member`.  
4. PDF-only upload (MVP1).  
5. Parse, chunk, embed, index with org/workspace metadata on chunks.  
6. Retrieval **always** filtered by `org_id` and `workspace_id`.  
7. Chat returns citations; insufficient evidence → exact fallback string.  
8. Redis for hot session/cache as per plan.  
9. Health, logging, rate limiting.  
10. Seed data + **isolation tests**.  
11. README: architecture, local setup, Compose, env vars, demo walkthrough, tenant model, limitations.

## MVP excludes

External connectors (Drive/Jira/etc.), billing, SSO (MVP1), web search, multimodal OCR, Kubernetes, public embed widget, heavy analytics.

## Authorization rules

- Verify membership on **every** protected route.  
- Never authorize using client-supplied org/workspace ids alone.  
- Vector search and SQL queries always scoped per user’s effective org/workspace access.

## Data model (minimum entities)

`organizations`, `users`, `memberships`, `workspaces`, `workspace_members`, `documents`, `document_chunks`, `chat_sessions`, `chat_messages`, `audit_logs`.

Chunk metadata must support: `org_id`, `workspace_id`, `document_id`, `chunk_index`, `source_type`, `source_name`.

## Tests required

Authentication, authorization, tenant isolation, workspace isolation, PDF ingest smoke, fallback exactness, citations present, unauthorized access blocked.

## Refinement priority (if iterating)

1. Tenant isolation bugs first.  
2. Retrieval scoping.  
3. Exact fallback + tests.  
4. Reliable observable ingest.  
5. UX polish after correctness.
