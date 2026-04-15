# INGESTION_AND_RETRIEVAL.md — Sovereign Knowledge Platform

## Purpose

This document explains how SKP turns uploaded or synced knowledge into searchable indexed chunks, and how it turns user questions into grounded answers with citations.

This is the practical architecture of the current codebase.

---

## High-level pipeline

SKP’s knowledge flow has two halves:

### Ingestion half
1. accept source content
2. persist document metadata
3. extract or normalize text
4. chunk content
5. embed chunks
6. store vectors and metadata
7. mark document indexed
8. optionally sync ACLs

### Retrieval half
1. accept question
2. normalize query
3. resolve accessible documents
4. embed query
5. retrieve candidate chunks
6. rerank candidates
7. filter by permission again
8. generate grounded answer with citations
9. fallback exactly if evidence is insufficient

---

## Ingestion architecture

## Source entrypoints

SKP currently supports two main ingestion paths.

### 1. File upload ingestion
Primary API route:
- `POST /documents/workspaces/{workspace_id}/upload`

Implemented in:
- `app/routers/documents.py`
- `app/services/ingestion.py`

This path is used for user-uploaded documents.

### 2. Raw text / connector ingestion
Primary API/service path:
- `POST /documents/workspaces/{workspace_id}/ingest-text`
- `app/services/ingestion_service.py`

This path is used for:
- connectors
- synced knowledge sources
- normalized non-file content
- source-aware re-ingestion

---

## Ingestion data model

Main persistence objects:

### `IngestionJob`
Tracks the indexing lifecycle.

Fields of interest:
- org scope
- workspace scope
- source filename
- status
- error message
- timestamps

### `Document`
Represents the logical source document.

Important fields:
- `organization_id`
- `workspace_id`
- `ingestion_job_id`
- `filename`
- `content_type`
- `storage_path`
- `checksum_sha256`
- `source_type`
- `external_id`
- `source_url`
- `ingestion_metadata`
- `integration_connector_id`
- `status`
- `page_count`
- `last_indexed_at`

### `DocumentChunk`
Represents the actual retrieval unit.

Important fields:
- `document_id`
- `chunk_index`
- `page_number`
- `section_title`
- `content`
- `token_count`
- `embedding_model`
- `embedding`

### `DocumentPermission`
Optional per-document ACL enforcement.

Used more heavily in full RBAC mode.

---

## File upload ingestion flow

## Step 1: authenticate and resolve workspace
The upload route verifies the caller is a member of the target workspace.

### Why it matters
This is the first tenant boundary and prevents cross-workspace writes.

---

## Step 2: persist uploaded file
Implemented in lower-level ingestion helpers.

Responsibilities:
- store file under document storage root
- preserve original filename metadata
- calculate checksum
- provide a durable file path

---

## Step 3: extract pages or text
The ingestion helpers attempt to extract text from the uploaded source.

At a high level, the system supports a broader content set than the original PDF-only MVP messaging.

Current repo signals support or active support for:
- PDF
- DOCX
- TXT
- Markdown
- HTML
- PPTX
- XLSX / XLS
- CSV
- RTF
- email-style and OCR-adjacent assets in test/demo lanes

If no extractable text is found, ingestion fails early.

---

## Step 4: build chunks
Chunking happens before embedding.

Configured via `app/config.py` with knobs such as:
- `ingestion_chunk_size`
- `ingestion_chunk_overlap`
- `ingestion_target_tokens`
- `ingestion_overlap_ratio`

### Purpose
Chunking creates retrieval-sized units that balance:
- semantic coherence
- recall quality
- citation usability
- embedding cost

---

## Step 5: batch embedding generation
Embeddings are produced through `app/services/embeddings.py`.

Current default shape:
- provider: Ollama
- model: `nomic-embed-text`
- dimension: 768

Batching is explicitly configurable so ingestion does not issue one embedding request per chunk unnecessarily.

---

## Step 6: persist ingestion results
The route/service creates:
- `IngestionJob`
- `Document`
- `DocumentChunk` rows

For uploads, the document typically becomes:
- `status = indexed`
- `last_indexed_at = now`

---

## Step 7: apply upload permissions when relevant
In simple RBAC mode, upload permission helpers ensure the uploaded document is readable in the expected scope.

In full RBAC mode, permission rows become more explicit and important.

---

## Raw text / connector ingestion flow

This flow is more reusable and is implemented in `app/services/ingestion_service.py`.

## Key difference from upload flow
Instead of treating every ingest as a new opaque file, this flow can treat content as a logical document identity keyed by:
- organization
- source type
- external id

That means re-ingestion can replace content for the same source rather than duplicating it.

---

## Flow steps

### 1. resolve logical document identity
If a document with the same `(organization_id, source_type, external_id)` exists:
- update it
- replace its chunks

Otherwise:
- create new job and document rows

### 2. clean and chunk text
Raw content is normalized and chunked.

### 3. delete prior chunks
If this is a re-ingest, old chunk rows are removed.

### 4. embed new chunks
Batch embeddings are generated.

### 5. persist chunks and mark indexed
Document becomes `indexed` if successful.

### 6. apply ACLs
If full RBAC mode is active, permission rows are synced or applied.

---

## Connector sync architecture

Primary files:
- `app/routers/connectors.py`
- `app/services/nango_client.py`
- `app/services/sync_orchestrator.py`

### Connector lifecycle
1. connector is activated for an org
2. connector row is persisted
3. sync can be triggered
4. remote documents are fetched
5. each remote item is passed into `ingest_document()`
6. connector status and sync timestamps are updated

### Important design point
Connector sync currently reuses the main ingestion engine instead of inventing a second indexing pipeline.

That is a good architectural choice.

---

## Retrieval architecture

Primary files:
- `app/services/rag/pipeline.py`
- `app/services/rag/retrieval.py`
- `app/services/rag/heuristic_rerank.py`
- `app/services/rag/cohere_rerank.py`
- `app/services/rag/rrf.py`
- `app/services/permissions.py`

SKP retrieval is strategy-based.

---

## Step 1: resolve accessible documents
Before retrieval runs, SKP determines which document IDs the current user may access.

This uses:
- organization scope
- workspace scope
- user identity
- RBAC mode
- document permissions when required

### Why this matters
Security is not just enforced at the HTTP layer. It is also carried into retrieval itself.

---

## Step 2: normalize query
The raw query is normalized before embedding and lexical comparison.

This improves:
- retrieval consistency
- lexical overlap checks
- hybrid strategy behavior

---

## Step 3: embed query
The normalized query is embedded with the configured embedding provider.

This gives the semantic search vector.

---

## Step 4: choose retrieval strategy
SKP supports three major retrieval strategies.

### `heuristic`
- vector retrieval for candidate chunks
- heuristic rerank after retrieval

### `hybrid`
- vector retrieval plus Postgres full-text search
- merged with reciprocal rank fusion (RRF)

### `rerank`
- vector retrieval for candidate pool
- hosted rerank with Cohere when configured
- fallback to heuristic rerank if Cohere is unavailable

This is resolved per org using org settings plus platform defaults.

---

## Step 5: candidate retrieval
Candidate chunks are fetched from Postgres/pgvector.

For hybrid mode, candidates also include lexical/full-text matches.

The system deliberately over-fetches candidates before reranking.

### Why
Better final ranking usually comes from:
- broader initial recall
- stronger post-ranking

rather than returning the raw nearest vectors directly.

---

## Step 6: rerank

### Heuristic rerank
Used in the default path.

Signals include:
- semantic similarity
- lexical overlap
- diversity / MMR behavior

### Cohere rerank
Used when:
- org or platform Cohere key exists
- org retrieval settings choose rerank or hosted rerank path

If Cohere fails or is unavailable, SKP degrades safely to heuristic rerank.

---

## Step 7: permission filter again
After ranking, SKP runs a post-filter via the permissions layer.

This is a good safety pattern because it avoids relying only on pre-filter assumptions.

---

## Search API behavior

Primary route:
- `POST /documents/workspaces/{workspace_id}/search`

This returns:
- workspace id
- query
- chosen `top_k`
- embedding model
- grounded answer stub
- retrieval hits

This is useful for debugging and non-chat search experiences.

---

## Chat retrieval and answer generation

Primary backend files:
- `app/routers/chat.py`
- `app/services/chat.py`
- `app/services/chat_history.py`
- `app/services/chat_sse.py`

### Chat flow
1. session is resolved
2. org query limits are checked
3. recent conversation context may be loaded
4. low-intent chitchat can be short-circuited
5. retrieval pipeline returns hits
6. citations are built
7. evidence sufficiency is evaluated
8. answer generation provider is selected
9. response is stored with citations

---

## Evidence sufficiency logic

This is one of the most important product behaviors in SKP.

The chat layer does **not** blindly answer whenever retrieval returns something.

It checks whether evidence is sufficient using:
- hit scores
- top-hit thresholds
- lexical overlap safety checks

If evidence is not strong enough, it returns the exact fallback.

### Exact fallback invariant

> I don't know based on the documents in this workspace.

This should be treated as a product contract.

---

## Answer generation providers

Implemented in `app/services/chat.py`.

Supported modes:
- `extractive`
- `ollama`
- `openai`
- `anthropic`
- fallback variants when model output is invalid
- `no_evidence`
- `chitchat`

### Extractive mode
The safest and simplest grounded answer mode.

It assembles an answer directly from the citations rather than using generative paraphrasing.

### Ollama mode
Uses local generation for grounded answers.

### OpenAI / Anthropic modes
Use cloud generation with org-aware credentials and base URLs.

### Safety guard
If model output does not properly reference available citations, SKP degrades back to extractive grounded output.

This is a very good trust-preserving design choice.

---

## Streaming architecture

Streaming chat uses SSE.

Main pieces:
- `app/routers/chat.py`
- `app/routers/api_chat.py`
- `app/services/chat_sse.py`
- frontend `lib/chatSse.ts`

The frontend can receive:
- delta events
- done event with citations and metadata
- error events

This lets the UX feel modern without abandoning grounded persistence.

---

## Observability and control points

Important knobs affecting ingestion and retrieval live in `app/config.py`.

### Ingestion knobs
- chunk size
- overlap
- target tokens
- embedding batch size
- embedding batch delay
- max upload size

### Retrieval knobs
- top_k
- candidate_k
- rerank mode
- lexical weight
- MMR lambda
- retrieval strategy default
- RRF k
- Cohere config
- minimum citation score
- lexical overlap minimum

### Why this matters
SKP is not just hardcoded behavior. It is already tunable enough to support product experimentation.

---

## Current strengths of the ingestion/retrieval design

### 1. One reusable ingestion core
Connector ingestion and direct text ingest reuse the same main indexing engine.

### 2. Retrieval is modular
The strategy-based retrieval design is already credible.

### 3. Tenant safety is carried into retrieval
Not just endpoint auth.

### 4. Grounding discipline is real
The exact fallback and citation validation rules are meaningful.

### 5. Postgres-first simplicity
The system avoids unnecessary extra infrastructure for the current stage.

---

## Current limitations and likely next improvements

### 1. Mostly synchronous ingestion path
Large files or large sync batches will eventually want background jobs.

### 2. Connector sync orchestration is still relatively lightweight
Good enough now, but should evolve as scale increases.

### 3. Public docs may understate implemented ingestion breadth
Architecture docs should reflect code truth clearly.

### 4. Retrieval tuning likely needs corpus-specific validation
Especially for legal, financial, or mixed-format corpora.

---

## Bottom line

SKP’s ingestion and retrieval system is already more mature than a typical MVP.

It has:
- reusable ingestion flows
- document-level persistence model
- configurable retrieval strategies
- grounded answer generation
- permission-aware search
- streaming chat
- trust-preserving fallback behavior

The next challenge is less about inventing the pipeline and more about:
- scaling it cleanly
- documenting it accurately
- validating it against real client corpora
