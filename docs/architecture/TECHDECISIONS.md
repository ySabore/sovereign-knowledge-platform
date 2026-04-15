# TECHDECISIONS.md

## TD-001 — FastAPI remains the backend platform for SKP
- **Decision:** Keep FastAPI as the primary backend framework.
- **Why:** It matches the current codebase well, keeps API contracts explicit, and works cleanly with Python-based ingestion, retrieval, and LLM integration code.
- **Consequence:** Continue organizing logic into routers + services so future extraction or decomposition stays possible.

## TD-002 — PostgreSQL + pgvector is the primary persistence and retrieval substrate
- **Decision:** Use Postgres as both system-of-record and vector retrieval store.
- **Why:** It keeps the stack operationally simple for self-hosted pilots, supports strong transactional modeling, and already fits the current domain model well.
- **Consequence:** Retrieval performance and schema evolution need to be managed carefully as corpus size grows.

## TD-003 — Maintain the two-layer tenant boundary: organization + workspace
- **Decision:** Keep organizations as tenant boundaries and workspaces as scoped collaboration/retrieval boundaries inside each tenant.
- **Why:** This is already embedded throughout the backend, frontend, and data model, and it matches the product need for both tenant isolation and intra-tenant segmentation.
- **Consequence:** Every protected endpoint and retrieval flow must continue carrying workspace and organization scope explicitly.

## TD-004 — Support progressive RBAC: simple mode and full document ACL mode
- **Decision:** Keep the current RBAC model with `simple` and `full` modes.
- **Why:** It supports pragmatic pilot deployments while preserving a path to stricter document-level permissioning.
- **Consequence:** Retrieval and ingestion code must preserve document permission hooks even when simple mode is active.

## TD-005 — Retrieval is strategy-based, not single-path
- **Decision:** Treat retrieval as a configurable strategy with `heuristic`, `hybrid`, and `rerank` modes.
- **Why:** The codebase already supports materially different retrieval behaviors, and different tenants/use cases will need different tradeoffs between simplicity, exact matching, and ranking quality.
- **Consequence:** Architecture and docs should describe retrieval as a family of pipelines rather than one canonical algorithm.

## TD-006 — Separate retrieval from answer generation
- **Decision:** Keep retrieval and answer generation as distinct layers.
- **Why:** This allows grounded search to remain stable while answer generation can vary across extractive, Ollama, OpenAI, and Anthropic modes.
- **Consequence:** Evidence sufficiency checks and fallback behavior must remain independent of the chosen generation provider.

## TD-007 — Preserve the exact no-evidence fallback as a product invariant
- **Decision:** Keep the exact fallback text when evidence is insufficient:
  `I don't know based on the documents in this workspace.`
- **Why:** This is a core trust and grounding behavior for SKP.
- **Consequence:** Changes to retrieval or answer generation must not weaken this contract.

## TD-008 — Docker-first deployment is the canonical operational path
- **Decision:** Treat Docker Compose, especially `docker-compose.gpu.yml`, as the primary deployment artifact.
- **Why:** It matches the current demo/pilot workflow, the local GPU target environment, and the documented deployment direction.
- **Consequence:** All validation and deployment documentation should continue to assume Docker-first unless explicitly noted otherwise.

## TD-009 — Ollama-first local inference, with optional cloud providers
- **Decision:** Keep local Ollama as the primary self-hosted inference path, while supporting OpenAI and Anthropic as configurable answer-generation providers.
- **Why:** This aligns with the sovereign/self-hosted value proposition while giving flexibility for pilot or customer-specific tradeoffs.
- **Consequence:** Config, docs, and UI must clearly distinguish local provider defaults from per-org cloud overrides.

## TD-010 — Cohere rerank is optional enhancement, not core dependency
- **Decision:** Treat Cohere hosted rerank as an optional quality-improvement layer.
- **Why:** It improves ranking quality in some cases, but SKP should remain functional without it.
- **Consequence:** Hosted rerank must always degrade gracefully back to heuristic reranking.

## TD-011 — Ingestion is already multi-format and should be documented that way
- **Decision:** Update architectural assumptions from PDF-only to current multi-format ingestion reality.
- **Why:** The current code and tests already support substantially more than PDF-only ingestion.
- **Consequence:** Product docs may still describe phased messaging, but architecture docs should reflect implemented capability accurately.

## TD-012 — Frontend should be treated as an operator shell, not a thin demo UI
- **Decision:** Recognize the frontend as a substantial administrative and workspace shell.
- **Why:** The React app now includes org/workspace operations, connectors, billing, analytics, document management, and chat flows.
- **Consequence:** Future frontend work should move toward component and page decomposition, especially around the large `HomePage.tsx` surface.

## TD-013 — Auditability remains a first-class platform concern
- **Decision:** Keep audit logging wired into sensitive org/workspace/document/chat administrative actions.
- **Why:** Multi-tenant knowledge systems need operational traceability and trust.
- **Consequence:** New sensitive mutations should default to adding audit log entries rather than treating audit as optional.

## TD-014 — The architecture should stay boring, explainable, and self-hostable
- **Decision:** Prefer a conservative, explainable stack over premature service sprawl.
- **Why:** SKP’s product value is privacy, sovereignty, and deployability, not architectural novelty.
- **Consequence:** New dependencies or platform components should be justified against that principle.
