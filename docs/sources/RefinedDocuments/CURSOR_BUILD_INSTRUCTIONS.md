# AI Knowledge Assistant — Cursor Agent Build Instructions

> Complete component-by-component implementation guide.
> Use this file as your reference when prompting Cursor agent for each build task.
> Work top-down through each section. Each component block is a self-contained Cursor prompt.

---

## Project Setup (Run First)

```bash
# 1. Bootstrap monorepo
npx create-next-app@latest ai-knowledge-assistant --typescript --tailwind --eslint --app --src-dir
cd ai-knowledge-assistant

# 2. Install core dependencies
npm install @clerk/nextjs @supabase/supabase-js @supabase/ssr
npm install ai @ai-sdk/anthropic openai
npm install llamaindex @llamaindex/supabase
npm install trpc @trpc/server @trpc/client @trpc/react-query @trpc/next
npm install inngest
npm install nango
npm install stripe @stripe/stripe-js
npm install @upstash/redis @upstash/ratelimit
npm install zod react-hook-form @hookform/resolvers
npm install lucide-react class-variance-authority clsx tailwind-merge
npm install slack-bolt @slack/web-api

# 3. Dev dependencies
npm install -D prisma @prisma/client
npm install -D @types/node tsx dotenv-cli

# 4. Init Prisma with Supabase connection
npx prisma init --datasource-provider postgresql
```

### Environment variables template — create `.env.local`

```env
# Supabase
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=

# Clerk
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=
CLERK_SECRET_KEY=
NEXT_PUBLIC_CLERK_SIGN_IN_URL=/sign-in
NEXT_PUBLIC_CLERK_SIGN_UP_URL=/sign-up
NEXT_PUBLIC_CLERK_AFTER_SIGN_IN_URL=/dashboard
NEXT_PUBLIC_CLERK_AFTER_SIGN_UP_URL=/onboarding

# AI
ANTHROPIC_API_KEY=
OPENAI_API_KEY=

# Stripe
STRIPE_SECRET_KEY=
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=
STRIPE_WEBHOOK_SECRET=

# Upstash
UPSTASH_REDIS_REST_URL=
UPSTASH_REDIS_REST_TOKEN=

# Inngest
INNGEST_EVENT_KEY=
INNGEST_SIGNING_KEY=

# Nango
NANGO_SECRET_KEY=
NEXT_PUBLIC_NANGO_PUBLIC_KEY=

# App
NEXT_PUBLIC_APP_URL=http://localhost:3000
```

---

## LAYER 1 — CLIENT LAYER

### Component 1.1 — Web App (Next.js)

**Cursor Prompt:**

```
Build the main Next.js 14 app shell with App Router. Create the following route structure:

src/app/
  (marketing)/
    page.tsx              # Landing page (import from components/landing)
    sign-in/[[...sign-in]]/page.tsx
    sign-up/[[...sign-up]]/page.tsx
  (app)/
    layout.tsx            # Auth-protected layout with sidebar
    dashboard/page.tsx    # Main chat interface
    dashboard/[workspaceId]/page.tsx
    admin/page.tsx        # Admin panel
    admin/connectors/page.tsx
    admin/usage/page.tsx
    onboarding/page.tsx   # Post-signup setup flow
  api/
    trpc/[trpc]/route.ts  # tRPC handler
    webhooks/stripe/route.ts
    webhooks/inngest/route.ts
    webhooks/clerk/route.ts

Requirements:
- Clerk middleware in middleware.ts protecting all (app) routes
- Sidebar with: workspace switcher, chat history, settings link
- Dark theme matching the design system (bg: #080C14)
- Responsive — works on mobile
- Loading states with skeleton components
- Error boundary components

Tech: Next.js 14 App Router, TypeScript, Tailwind CSS, Clerk, shadcn/ui
```

---

### Component 1.2 — Chat UI (Core Product Screen)

**Cursor Prompt:**

```
Build the main chat interface at src/app/(app)/dashboard/page.tsx

Features required:
1. Query input bar (bottom-pinned, like Claude.ai)
   - Multi-line textarea that grows with content
   - Submit on Enter (Shift+Enter for newline)
   - Character count and token estimate
   - Workspace selector dropdown inline

2. Message thread (scrollable, top-to-bottom)
   - User messages: right-aligned, dark bubble
   - Assistant messages: left-aligned with:
     a. Streamed text response (word-by-word using Vercel AI SDK)
     b. Citation pills: clickable pills like [📄 Policy v3 · p.12]
     c. Confidence badge: High / Medium / Low with color coding
     d. "Show sources" expandable panel below each answer

3. Source panel (slide-in from right)
   - Shows document name, page/section, relevant passage highlighted
   - Link to open original document
   - Confidence score bar

4. Empty state: suggested questions based on connected sources

Use: Vercel AI SDK useChat hook, tRPC for non-streaming queries
Stream endpoint: POST /api/chat (create this route too)
The chat route should call: Query Service → Retriever → Prompt Builder → Anthropic API
```

---

### Component 1.3 — Admin Dashboard

**Cursor Prompt:**

```
Build the admin dashboard at src/app/(app)/admin/page.tsx

Sections:
1. Overview cards row:
   - Total queries this month
   - Active users (7-day)
   - Documents indexed
   - Avg response time (ms)

2. Top queries table:
   - Query text, frequency, avg confidence, last asked
   - Sortable columns

3. Unanswered queries panel:
   - Queries where confidence < 0.4
   - Used to identify knowledge gaps
   - Export to CSV button

4. Connector status cards:
   - Per connector: name, last sync, doc count, status badge (syncing/healthy/error)
   - Manual resync button per connector
   - Green/red status indicator

5. Usage chart:
   - Queries per day (last 30 days)
   - Line chart using recharts

Only accessible to users with role="admin" in Clerk org metadata.
Fetch all data via tRPC admin router.
```

---

### Component 1.4 — Connector Management UI

**Cursor Prompt:**

```
Build connector management at src/app/(app)/admin/connectors/page.tsx

Show a grid of available connectors (Confluence, Google Drive, Notion, GitHub, Jira, Zendesk, SharePoint, Slack).

For each connector tile:
- Logo/icon
- Name and description
- Status: "Not connected" | "Connected" | "Syncing" | "Error"
- "Connect" button → triggers Nango OAuth flow
- If connected: "Disconnect", "Sync now", last sync time, doc count

Connect flow:
1. User clicks "Connect"
2. Open Nango.auth() popup for that integration
3. On success, call POST /api/connectors/activate with {integrationId, connectionId}
4. Backend creates connector record, triggers first sync via Inngest

Nango integration IDs to use:
- confluence: "confluence"
- google-drive: "google-drive"  
- notion: "notion"
- github: "github"
- jira: "jira"
- zendesk: "zendesk"
- sharepoint: "sharepoint"
- slack: "slack"
```

---

### Component 1.5 — Slack Bot

**Cursor Prompt:**

```
Create src/slack/index.ts — a Slack Bolt app that runs as a Next.js API route.

Create src/app/api/slack/events/route.ts

Features:
1. Slash command /ask <question>
   - Immediately reply with "Searching your knowledge base..."
   - Call the Query + Answer API internally
   - Edit the reply with the full cited answer
   - Format citations as Slack blocks: bold doc name + page

2. App mention @KnowledgeBot <question>
   - Same as /ask but triggered by mention in any channel
   - Reply in thread

3. Answer format in Slack:
   *Answer:* [streamed text]
   
   *Sources:*
   • 📄 Vendor Policy v3 — page 12
   • 📋 IT Compliance Guide — section 3.2

4. Workspace scoping:
   - Map Slack workspace ID to org ID in database
   - Only search documents the Slack user has permission to access
   - Return "I don't have access to answer that" if no matching docs

Config: SLACK_BOT_TOKEN, SLACK_SIGNING_SECRET in env
```

---

## LAYER 2 — API GATEWAY & AUTH

### Component 2.1 — Clerk Auth Setup

**Cursor Prompt:**

```
Set up Clerk authentication with organization support.

1. Create src/middleware.ts:
   - Protect all routes under /dashboard, /admin, /onboarding, /api/trpc
   - Public routes: /, /sign-in, /sign-up, /api/webhooks/*, /api/slack/*

2. Create src/lib/auth.ts:
   - Helper: getCurrentUser() → returns Clerk user + org + role
   - Helper: requireAdmin() → throws if user role !== "admin"
   - Helper: getOrgId() → returns current organization ID

3. Clerk webhook handler at src/app/api/webhooks/clerk/route.ts:
   - On user.created → create user record in Postgres
   - On organization.created → create org + default workspace in Postgres
   - On organizationMembership.created → sync role to Postgres
   - Verify webhook with CLERK_WEBHOOK_SECRET

4. Onboarding flow at src/app/(app)/onboarding/page.tsx:
   - Step 1: Create/join organization
   - Step 2: Connect first data source
   - Step 3: Ask first question (demo the value immediately)
   
Roles to define in Clerk org metadata: "admin", "member"
```

---

### Component 2.2 — tRPC API Setup

**Cursor Prompt:**

```
Set up tRPC v11 with the following router structure:

src/server/
  trpc.ts              # tRPC init, context, middleware
  routers/
    _app.ts            # Root router merging all sub-routers
    query.ts           # Query + answer endpoints
    documents.ts       # Document management
    connectors.ts      # Connector CRUD + status
    workspace.ts       # Workspace management
    admin.ts           # Admin-only analytics endpoints
    billing.ts         # Stripe billing endpoints

Context (src/server/trpc.ts):
- Extract Clerk session → user, orgId, role
- Inject Supabase client (with RLS user context)
- Add prisma client

Middleware:
- protectedProcedure: requires valid session
- adminProcedure: requires role="admin"
- orgProcedure: requires active organization

Key procedures to scaffold (full implementation in component sections):
- query.ask: input: {question, workspaceId} → streaming answer
- query.history: paginated chat history per workspace  
- connectors.list: list org's connectors + status
- connectors.activate: create connector after OAuth
- admin.getStats: usage metrics for admin dashboard
- billing.createCheckout: Stripe checkout session
```

---

### Component 2.3 — RBAC & Permission System

**Cursor Prompt:**

```
Build the permission system in src/lib/permissions.ts

Database schema needed (add to Prisma schema):

model DocumentPermission {
  id           String   @id @default(cuid())
  documentId   String
  orgId        String
  userId       String?  // null = org-wide access
  canRead      Boolean  @default(true)
  source       String   // "confluence" | "google-drive" etc
  externalId   String   // ID in the source system
  createdAt    DateTime @default(now())
  updatedAt    DateTime @updatedAt
  
  @@index([orgId, userId])
  @@index([documentId])
}

Functions to implement:
1. syncPermissions(connectorId, documents[]) 
   → upsert DocumentPermission rows from connector's permission data

2. getAccessibleDocumentIds(userId, orgId, workspaceId)
   → returns array of document IDs the user can access
   → used to filter vector search results

3. filterChunksByPermission(chunks[], userId, orgId)
   → post-retrieval filter to remove unauthorized chunks
   → failsafe: if no permission record exists, DENY access

4. hasDocumentAccess(userId, documentId)
   → boolean check for single document

Simple mode (Phase 1-2): admin sees all, members see all within their workspace.
Full mode (Phase 3): per-document ACL from connector permission sync.
Toggle via feature flag: RBAC_MODE = "simple" | "full"
```

---

### Component 2.4 — Rate Limiting & API Gateway

**Cursor Prompt:**

```
Implement rate limiting using Upstash Redis at src/lib/rate-limit.ts

Rate limit tiers:
- Free trial: 20 queries/day, 5 queries/hour
- Starter: 100 queries/day, 20 queries/hour  
- Team: 500 queries/day, 100 queries/hour
- Business: 2000 queries/day, unlimited/hour
- Admin API calls: 1000/hour

Implementation:
1. Create rateLimitMiddleware for tRPC procedures
   - Check plan from org metadata
   - Apply appropriate limits
   - Return 429 with retryAfter header when exceeded

2. Create src/lib/rate-limit.ts:
   import { Ratelimit } from "@upstash/ratelimit"
   import { Redis } from "@upstash/redis"
   - Sliding window algorithm
   - Key format: "rl:{orgId}:{type}:{window}"

3. Apply to:
   - query.ask procedure (per org, per day + per hour)
   - connectors.sync (max 10 manual syncs/hour per org)
   - Public API routes (per API key)

4. Rate limit response format:
   { error: "rate_limit_exceeded", limit: 100, remaining: 0, resetAt: "ISO timestamp" }
```

---

## LAYER 3 — APPLICATION SERVICES

### Component 3.1 — Query + Answer Service

**Cursor Prompt:**

```
Build the core query service at src/server/services/query.service.ts

This is the most critical service — own it carefully.

Flow: user question → retrieve chunks → rerank → build prompt → stream from Claude → parse citations → return

async function answerQuestion({
  question: string,
  workspaceId: string,
  userId: string,
  orgId: string,
  conversationHistory?: Message[]
}): Promise<AsyncIterableIterator<AnswerChunk>>

Steps to implement:

STEP 1 — Retrieve relevant chunks
  const accessibleIds = await getAccessibleDocumentIds(userId, orgId, workspaceId)
  const chunks = await vectorSearch(question, { 
    filter: { documentId: { in: accessibleIds } },
    topK: 8,
    minScore: 0.72
  })

STEP 2 — Rerank (optional, feature flagged)
  if (RERANKER_ENABLED) {
    chunks = await cohereRerank(question, chunks, { topN: 5 })
  }

STEP 3 — Build prompt (see Prompt Builder component 3.2)
  const prompt = buildPrompt(question, chunks, conversationHistory)

STEP 4 — Stream from Claude
  const stream = await anthropic.messages.stream({
    model: "claude-sonnet-4-20250514",
    max_tokens: 1024,
    messages: prompt,
    system: SYSTEM_PROMPT
  })

STEP 5 — Parse and yield
  Yield text chunks as they stream
  On completion, parse citation references from final text
  Map [DOC_1] style refs back to actual document metadata
  Yield final { citations, confidence, sources } object

STEP 6 — Log to audit table
  await logQuery({ question, answer, citations, userId, orgId, duration })

Return type: AsyncIterableIterator yielding:
  | { type: "text", content: string }
  | { type: "done", citations: Citation[], confidence: number, sources: Source[] }
  | { type: "error", message: string }
```

---

### Component 3.2 — Prompt Builder

**Cursor Prompt:**

```
Build src/server/services/prompt-builder.ts

This controls answer quality. Get the system prompt and citation format exactly right.

const SYSTEM_PROMPT = `You are a precise knowledge assistant. You answer questions using ONLY information from the provided source documents.

Rules you must follow:
1. Every factual claim must be cited using [DOC_N] notation where N matches the source number
2. If the answer is not in the provided sources, say: "I couldn't find information about this in your connected knowledge base."
3. Never invent, extrapolate, or use external knowledge
4. Keep answers concise and direct — 2-4 sentences for simple questions, up to 8 for complex ones
5. Use [DOC_N, page P] when the source includes a page number
6. Confidence: end every response with <confidence>high|medium|low</confidence> based on how directly the sources answer the question`

function buildPrompt(
  question: string,
  chunks: RetrievedChunk[],
  history: Message[]
): AnthropicMessage[]

Format each chunk as:
---
[DOC_1] Source: {document.name} | Page: {chunk.pageNumber} | Section: {chunk.section}
{chunk.text}
---

Include up to last 3 conversation turns in history for context.
Total context must stay under 80,000 tokens — truncate oldest history first, then reduce chunks.

Export also:
- parseCitations(responseText, chunks): Citation[]  
  → finds all [DOC_N] refs in text, maps to source metadata
- extractConfidence(responseText): "high" | "medium" | "low"
  → extracts from <confidence> tag, strips tag from display text
- estimateTokens(text): number
  → rough estimate: chars / 4
```

---

### Component 3.3 — Ingestion Service

**Cursor Prompt:**

```
Build src/server/services/ingestion.service.ts

This processes raw documents into searchable vector chunks.

Main function:
async function ingestDocument(doc: {
  content: string,        // raw text
  name: string,
  sourceType: string,     // "confluence" | "google-drive" | "pdf-upload" etc
  externalId: string,     // ID in source system
  orgId: string,
  workspaceId: string,
  metadata: {
    pageCount?: number,
    lastModified: Date,
    author?: string,
    url?: string,
    permissions?: string[]  // user IDs who can access
  }
}): Promise<{ chunksCreated: number, documentId: string }>

Steps:

1. CLEAN — strip HTML, normalize whitespace, remove boilerplate
   Use: src/lib/text-cleaner.ts (create this too)

2. CHUNK — split into overlapping chunks
   Strategy: 
   - Target: 400-600 tokens per chunk
   - Overlap: 10% (40-60 tokens)
   - Respect paragraph and section boundaries
   - Keep heading context with each chunk: prepend "Section: {nearest heading}"
   - Tag each chunk with: chunkIndex, pageNumber (estimate from position), sectionTitle

3. EMBED — batch embed all chunks
   const embeddings = await openai.embeddings.create({
     model: "text-embedding-3-large",
     input: chunks.map(c => c.text),
     dimensions: 1536
   })
   Batch size: max 100 chunks per API call
   Add 200ms delay between batches to respect rate limits

4. UPSERT — store in Supabase pgvector
   Upsert into document_chunks table (schema below)
   If document already exists: delete old chunks, insert new ones (re-index)

5. UPDATE — mark document as indexed in documents table

Prisma schema additions:
model Document {
  id          String   @id @default(cuid())
  orgId       String
  workspaceId String
  name        String
  sourceType  String
  externalId  String
  url         String?
  status      String   @default("pending") // pending|indexing|indexed|error
  chunkCount  Int      @default(0)
  lastIndexed DateTime?
  metadata    Json     @default("{}")
  createdAt   DateTime @default(now())
  updatedAt   DateTime @updatedAt
  
  @@unique([orgId, sourceType, externalId])
  @@index([orgId, workspaceId])
}

Supabase SQL for vector table (run in Supabase SQL editor):
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE document_chunks (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  document_id TEXT NOT NULL,
  org_id TEXT NOT NULL,
  workspace_id TEXT NOT NULL,
  chunk_index INTEGER NOT NULL,
  text TEXT NOT NULL,
  page_number INTEGER,
  section_title TEXT,
  embedding vector(1536),
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX ON document_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX ON document_chunks (org_id, workspace_id);
```

---

### Component 3.4 — Sync Orchestrator (Inngest Jobs)

**Cursor Prompt:**

```
Build the background sync system using Inngest at src/inngest/

File structure:
src/inngest/
  client.ts           # Inngest client init
  functions/
    sync-connector.ts  # Main sync function
    sync-document.ts   # Per-document processing
    embed-chunks.ts    # Chunking + embedding
    cleanup.ts         # Delete removed documents

src/inngest/client.ts:
import { Inngest } from "inngest"
export const inngest = new Inngest({ id: "ai-knowledge-assistant" })

src/inngest/functions/sync-connector.ts:
export const syncConnector = inngest.createFunction(
  { 
    id: "sync-connector",
    concurrency: { limit: 3 },           // max 3 connectors syncing at once
    retries: 3
  },
  { event: "connector/sync.requested" },
  async ({ event, step }) => {
    const { connectorId, orgId, fullSync } = event.data
    
    // Step 1: Fetch document list from Nango
    const docs = await step.run("fetch-doc-list", async () => {
      return await nango.listDocuments(connectorId)
    })
    
    // Step 2: Diff against existing indexed docs
    const { toAdd, toUpdate, toDelete } = await step.run("diff-documents", ...)
    
    // Step 3: Fan out per-document ingestion (parallel, max 10 at once)
    await step.sendEvent("fan-out-ingestion", 
      toProcess.map(doc => ({
        name: "document/ingest.requested",
        data: { doc, connectorId, orgId }
      }))
    )
    
    // Step 4: Update connector last_synced_at
    await step.run("update-sync-time", ...)
    
    return { processed: toProcess.length, deleted: toDelete.length }
  }
)

Also create cron trigger — sync all active connectors every 4 hours:
export const scheduledSync = inngest.createFunction(
  { id: "scheduled-sync" },
  { cron: "0 */4 * * *" },
  async ({ step }) => { ... }
)

Register all functions in src/app/api/webhooks/inngest/route.ts
```

---

### Component 3.5 — Billing Service

**Cursor Prompt:**

```
Build Stripe billing at src/server/services/billing.service.ts

Plans to create in Stripe dashboard first:
- price_starter: $49/mo
- price_team: $149/mo  
- price_business: $299/mo
- price_scale: $599/mo

Functions:

1. createCheckoutSession(orgId, priceId, successUrl, cancelUrl)
   → Stripe checkout.sessions.create with org metadata
   → Store stripeCustomerId on org after creation

2. createPortalSession(orgId)
   → Stripe billingPortal.sessions.create
   → For plan changes, cancellation, invoice history

3. getCurrentPlan(orgId): Plan
   → Look up active subscription from Stripe
   → Cache in Redis for 1 hour (avoid Stripe API calls on every request)

4. Webhook handler at src/app/api/webhooks/stripe/route.ts:
   Handle these events:
   - checkout.session.completed → activate subscription, set plan in org metadata
   - customer.subscription.updated → update plan
   - customer.subscription.deleted → downgrade to free, notify user
   - invoice.payment_failed → send email, set grace period flag

5. Plan limits enforcement in tRPC middleware:
   const plan = await getCurrentPlan(orgId)
   const limits = PLAN_LIMITS[plan]
   Check: connectors count, user seats, queries this month

PLAN_LIMITS constant:
export const PLAN_LIMITS = {
  free:     { connectors: 1,  seats: 1,   queriesPerMonth: 50  },
  starter:  { connectors: 2,  seats: 3,   queriesPerMonth: 500 },
  team:     { connectors: 5,  seats: 25,  queriesPerMonth: 2000 },
  business: { connectors: 10, seats: 100, queriesPerMonth: 10000 },
  scale:    { connectors: 20, seats: 200, queriesPerMonth: 50000 },
}
```

---

## LAYER 4 — AI / RAG PIPELINE

### Component 4.1 — Vector Search (Retriever)

**Cursor Prompt:**

```
Build src/server/services/retriever.ts

async function vectorSearch(
  query: string,
  options: {
    orgId: string,
    workspaceId: string,
    accessibleDocumentIds: string[],
    topK?: number,           // default 8
    minScore?: number,       // default 0.70
    filters?: {
      sourceType?: string,
      dateAfter?: Date,
    }
  }
): Promise<RetrievedChunk[]>

Steps:
1. Embed the query (same model as documents: text-embedding-3-large)
   Cache query embeddings in Redis for 1 hour (same query asked repeatedly)

2. Run similarity search via Supabase RPC:
   Create this Postgres function in Supabase:
   
   CREATE OR REPLACE FUNCTION match_chunks(
     query_embedding vector(1536),
     match_threshold float,
     match_count int,
     p_org_id text,
     p_workspace_id text,
     p_document_ids text[]
   )
   RETURNS TABLE (
     id uuid, document_id text, text text,
     page_number int, section_title text,
     metadata jsonb, similarity float
   )
   LANGUAGE plpgsql AS $$
   BEGIN
     RETURN QUERY
     SELECT dc.id, dc.document_id, dc.text,
            dc.page_number, dc.section_title,
            dc.metadata,
            1 - (dc.embedding <=> query_embedding) AS similarity
     FROM document_chunks dc
     WHERE dc.org_id = p_org_id
       AND dc.workspace_id = p_workspace_id
       AND dc.document_id = ANY(p_document_ids)
       AND 1 - (dc.embedding <=> query_embedding) > match_threshold
     ORDER BY dc.embedding <=> query_embedding
     LIMIT match_count;
   END;
   $$;

3. Join with documents table to get full metadata
4. Apply MMR (Maximal Marginal Relevance) to reduce redundancy:
   - Don't return 3 chunks from the same document if 1 is sufficient
   - Diversity factor: 0.5 (balance relevance vs diversity)
5. Return chunks sorted by relevance score

RetrievedChunk type:
{
  id: string,
  documentId: string,
  documentName: string,
  documentUrl: string,
  sourceType: string,
  text: string,
  pageNumber: number | null,
  sectionTitle: string | null,
  similarity: number,
  metadata: Record<string, any>
}
```

---

### Component 4.2 — Reranker (Optional / Phase 2)

**Cursor Prompt:**

```
Build src/server/services/reranker.ts

Feature-flagged — only active if RERANKER_ENABLED=true in env.

async function rerank(
  query: string,
  chunks: RetrievedChunk[],
  options: { topN?: number }  // default 5
): Promise<RetrievedChunk[]>

Implementation using Cohere Rerank API:

import { CohereClient } from "cohere-ai"
const cohere = new CohereClient({ token: process.env.COHERE_API_KEY })

const result = await cohere.rerank({
  model: "rerank-english-v3.0",
  query: query,
  documents: chunks.map(c => c.text),
  topN: options.topN ?? 5,
  returnDocuments: false
})

Map result.results back to original chunks using the index field.
Update similarity score with relevanceScore from Cohere.
Return reranked chunks in new order.

Fallback: if Cohere API fails, log error and return original chunks unchanged.
Timeout: 3 seconds max — fall back if exceeded.
```

---

## LAYER 5 — DATA LAYER

### Component 5.1 — Prisma Schema & Migrations

**Cursor Prompt:**

```
Create the complete Prisma schema at prisma/schema.prisma

Full schema:

generator client {
  provider = "prisma-client-js"
}

datasource db {
  provider  = "postgresql"
  url       = env("DATABASE_URL")
  directUrl = env("DIRECT_URL")
}

model Organization {
  id              String       @id @default(cuid())
  clerkOrgId      String       @unique
  name            String
  plan            String       @default("free")
  stripeCustomerId String?
  stripeSubId     String?
  seats           Int          @default(1)
  createdAt       DateTime     @default(now())
  updatedAt       DateTime     @updatedAt
  workspaces      Workspace[]
  connectors      Connector[]
  users           OrgUser[]
}

model OrgUser {
  id        String       @id @default(cuid())
  orgId     String
  clerkUserId String
  role      String       @default("member")  // "admin" | "member"
  org       Organization @relation(fields: [orgId], references: [id])
  createdAt DateTime     @default(now())
  
  @@unique([orgId, clerkUserId])
}

model Workspace {
  id          String       @id @default(cuid())
  orgId       String
  name        String
  description String?
  isDefault   Boolean      @default(false)
  org         Organization @relation(fields: [orgId], references: [id])
  documents   Document[]
  queries     Query[]
  createdAt   DateTime     @default(now())
  updatedAt   DateTime     @updatedAt
}

model Connector {
  id             String       @id @default(cuid())
  orgId          String
  type           String       // "confluence" | "google-drive" etc
  nangoConnectionId String
  status         String       @default("pending")
  lastSyncedAt   DateTime?
  documentCount  Int          @default(0)
  config         Json         @default("{}")
  org            Organization @relation(fields: [orgId], references: [id])
  documents      Document[]
  createdAt      DateTime     @default(now())
  updatedAt      DateTime     @updatedAt
  
  @@unique([orgId, type])
}

model Document {
  id          String     @id @default(cuid())
  orgId       String
  workspaceId String
  connectorId String?
  name        String
  sourceType  String
  externalId  String
  url         String?
  status      String     @default("pending")
  chunkCount  Int        @default(0)
  lastIndexed DateTime?
  metadata    Json       @default("{}")
  workspace   Workspace  @relation(fields: [workspaceId], references: [id])
  connector   Connector? @relation(fields: [connectorId], references: [id])
  createdAt   DateTime   @default(now())
  updatedAt   DateTime   @updatedAt
  
  @@unique([orgId, sourceType, externalId])
  @@index([orgId, workspaceId])
}

model Query {
  id           String    @id @default(cuid())
  orgId        String
  workspaceId  String
  userId       String    // Clerk user ID
  question     String
  answer       String?
  citations    Json      @default("[]")
  confidence   String?   // "high" | "medium" | "low"
  durationMs   Int?
  tokenCount   Int?
  feedback     String?   // "positive" | "negative" | null
  workspace    Workspace @relation(fields: [workspaceId], references: [id])
  createdAt    DateTime  @default(now())
  
  @@index([orgId, workspaceId, createdAt])
  @@index([orgId, createdAt])
}

model AuditLog {
  id        String   @id @default(cuid())
  orgId     String
  userId    String
  action    String   // "query.asked" | "document.indexed" | "connector.synced" etc
  resource  String?
  metadata  Json     @default("{}")
  createdAt DateTime @default(now())
  
  @@index([orgId, createdAt])
}

Run: npx prisma migrate dev --name init
```

---

## LAYER 6 — CONNECTORS

### Component 6.1 — Nango Connector Setup

**Cursor Prompt:**

```
Build the connector integration layer using Nango at src/lib/nango.ts

import Nango from "@nangohq/node"
const nango = new Nango({ secretKey: process.env.NANGO_SECRET_KEY })

Functions to implement:

1. getNangoAuthUrl(integrationId, connectionId)
   Used on frontend to trigger OAuth popup via Nango

2. async fetchDocuments(connectorType, connectionId, cursor?)
   Switch on connectorType and call appropriate fetch function:
   
   case "confluence":
     → GET /wiki/rest/api/content?type=page&expand=body.storage
     → Parse HTML body to plain text
     → Return { documents, nextCursor }
     
   case "google-drive":
     → GET https://www.googleapis.com/drive/v3/files?q=mimeType contains 'document'
     → For each file: GET file content as text
     → Return { documents, nextCursor }
     
   case "notion":
     → POST https://api.notion.com/v1/search
     → For each page: GET blocks and flatten to text
     → Return { documents, nextCursor }
     
   case "github":
     → GET /repos/{owner}/{repo}/git/trees/{branch}?recursive=1
     → Filter for .md, .mdx, .txt, .rst files
     → Fetch file content via raw.githubusercontent.com
     → Return { documents, nextCursor }
     
   case "jira":
     → GET /rest/api/3/search?jql=project={project}&fields=summary,description,comment
     → Combine summary + description + comments as document text
     → Return { documents, nextCursor }

3. async getPermissions(connectorType, connectionId, documentExternalId)
   → Fetch who can access this document in the source system
   → Return array of user emails / IDs

All API calls go through Nango proxy:
nango.get({ endpoint: "/...", providerConfigKey: connectorType, connectionId })
This handles token refresh automatically.

DocumentFetchResult type:
{
  externalId: string,
  name: string,
  content: string,      // plain text
  url: string,
  lastModified: Date,
  metadata: Record<string, any>
  permissions?: string[]
}
```

---

## Testing Checklist

**Scope:** *Sovereign Knowledge Platform* repo — **FastAPI** API, **Alembic** migrations, **Vite** frontend, **Postgres + pgvector** (e.g. `pgvector/pgvector` Docker image). The generic prompts elsewhere in this file mention Prisma/Next/Inngest/Supabase; use the items below for this codebase.

**Legend (last verified session):** `[x]` = implemented in SKP **and** verified here via **automated tests** (`python -m pytest tests/ -q`), **`alembic upgrade head`** on Postgres, and/or **FastAPI `TestClient`** spot checks. `[ ]` = **manual / integration-only** (browser, `scripts/e2e_chat_smoke.py` with API+DB+Ollama), **not covered by pytest**, or **intentionally stubbed** pending further work.

**Automated (verify first)**

```
[x] pytest: `python -m pytest tests/ -q` — 24 passed (RAG, chat fallback, health, billing helpers, text cleaner, answer parse, heuristic rerank, etc.)
[ ] Optional E2E (API up + DB + Ollama): `python scripts/e2e_chat_smoke.py` — not run in CI; run locally when stack is up (covers upload, search, chat, DB assertions)
```

**Layer 1 — Client (Vite)**

```
[x] User can authenticate: `POST /auth/login` (JWT) implemented; `GET /auth/me` returns **401** without `Authorization` (TestClient). Clerk JWT path implemented behind `CLERK_ENABLED` + `deps.get_current_user` (not exercised in pytest).
[x] Chat UI + `frontend/src/lib/chatSse.ts` consume `text/event-stream` from `/chat/...` (manual browser QA recommended).
[x] Assistant message + citations: backend persists `citations_json`; UI renders citation UX (manual QA recommended).
[x] `/admin` + `GET /admin/metrics/summary` implemented (`AdminDashboardPage`, placeholder metrics JSON until telemetry).
[x] `/admin/connectors` lists static catalog + activation UI (`AdminConnectorsPage`).
```

**Layer 2 — Auth / gateway**

```
[x] Protected API routes return **401** without `Authorization: Bearer` (verified: `GET /auth/me` → 401).
[x] Admin UI: `RequireAdmin` gates `/admin/*`; API uses `enforce_admin_api_limit` after auth (platform owner bypass; Redis hourly cap for others).
[ ] Tiered **429** rate limits: implemented (`slowapi` + Redis tier helpers) but **not asserted in pytest** (tests set `RATE_LIMIT_ENABLED=false`). Verify under load with `RATE_LIMIT_REDIS_ENABLED=true`.
[ ] `POST /webhooks/clerk` — **placeholder only** (200 + `status: ignored`); Svix verification and org/user sync **not implemented**.
```

**Layer 3 — App services**

```
[x] Ask question → streaming + final `done` with citations/confidence: grounded pipeline covered in `tests/test_chat_service.py` (SSE transport itself is integration-tested via `e2e_chat_smoke.py` when run).
[x] Evidence markers `[1]..[n]` / prompts — `tests/test_answer_parse.py`, `tests/test_chat_service.py`.
[ ] PDF/upload **end-to-end** through embeddings: implemented (`POST .../upload`, ingestion) but **not covered by pytest**; use README path or `e2e_chat_smoke.py`.
[x] Connector sync **without Inngest**: `POST /connectors/{connector_id}/sync`, `run_connector_sync`, `scheduled_sync_all_connectors` in `app/services/sync_orchestrator.py`.
[x] Stripe (optional): billing routes + `tests/test_billing_entitlements.py`; live Checkout/Portal needs real `STRIPE_*` keys (not called in unit tests).
```

**Layer 4 — AI / RAG**

```
[x] Vector retrieval workspace-scoped (`app/services/rag/retrieval.py`, cosine on `document_chunks.embedding`) — exercised via chat/RAG unit tests using `RetrievalHit`.
[x] Confidence + low-evidence fallback — `tests/test_chat_service.py`, `FALLBACK_NO_EVIDENCE` behavior.
[x] No hits / weak hits — exact fallback enforced — `tests/test_chat_service.py`.
[x] Heuristic rerank modes — `tests/test_rag_heuristic_rerank.py`.
```

**Layer 5 — Data**

```
[x] `alembic upgrade head` — verified applying **001 → 007** on Postgres (chain includes pgvector-backed chunks, connectors, `query_logs`).
[x] `pgvector` — required by migrations (`002`+); use a Postgres image with the extension (e.g. `pgvector/pgvector`).
[x] Chunk search via **SQLAlchemy + pgvector** (`cosine_distance`); no separate `match_chunks()` RPC in shipped code.
[ ] `query_logs` rows after chat: **`record_query_log` is implemented** in `chat_sse` but **no dedicated pytest** — verify with DB inspection or extend tests. `audit_logs` for org flows: partial coverage only.
```

**Layer 6 — Connectors (Nango)**

```
[x] Without `NANGO_SECRET_KEY`, `run_connector_sync` returns **`skipped`** (see `sync_orchestrator`); proxy requires secret (`nango_client.nango_configured()`).
[x] `POST /connectors/activate` upserts `IntegrationConnector` + optional `workspace_id`; `POST /connectors/{id}/sync` → Nango fetch → `ingest_document` (integration test with real Nango + provider is manual).
[x] Re-sync upsert: `ingest_document` keys on `(organization_id, source_type, external_id)` and replaces chunks — implemented in `app/services/ingestion_service.py`.
[ ] Source permissions: `get_permissions` **stub** (`[]`); connector ACL mapping + enforcement **not done** (see `RBAC_MODE` / `document_permissions` when wired).
```

---

## Cursor Agent Tips

1. **Work one component at a time.** Paste one prompt block, let Cursor build it, review, then move to the next.
2. **Reference this file at the start of each session:**
  "I am building the AI Knowledge Assistant. Here is the full architecture: [paste CURSOR_BUILD_INSTRUCTIONS.md]. Today I am working on Component [X.Y]."
3. **When Cursor gets stuck**, provide the relevant type definitions and ask it to implement just one function at a time.
4. **Test before moving layers.** Don't build Layer 3 until Layer 2 auth is working — every service depends on having a valid orgId and userId.
5. **Database first.** In SKP run `alembic upgrade head` (or generate revisions under `alembic/versions/`) before services depend on new tables — not Prisma in this repo.

