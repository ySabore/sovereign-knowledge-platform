# Sovereign Knowledge Platform — Pilot V1 Definition

## 1) Target user
**Primary buyer/user:** owner or operations lead at a privacy-sensitive small/mid-sized business (roughly 20–200 employees) who has a messy internal document base and needs staff to get reliable answers without sending company knowledge to public AI tools.

**Best first pilot profile:** a professional services firm, small manufacturer, compliance-heavy back office, or specialized operations team with:
- a bounded document set
- a clear internal knowledge bottleneck
- one internal champion
- tolerance for a simple, private, internal-only v1

## 2) Target pain
Teams lose time hunting through PDFs, SOPs, policy documents, proposals, manuals, and internal reference files. Public AI tools are either disallowed or untrusted for sensitive content. Search is too keyword-based, tribal knowledge lives in a few people’s heads, and staff need faster answers with source proof.

**Pilot pain statement:**
> “We need a private internal AI assistant that can answer questions from our company documents, show where the answer came from, and stay inside our environment.”

## 3) Core workflow
1. Admin uploads a small, curated set of internal PDFs for one team or one use case.
2. Platform indexes those documents.
3. Staff open a simple chat UI.
4. Staff ask natural-language questions about the uploaded knowledge.
5. System returns a grounded answer with citations/snippets from the source documents.
6. If the answer is not supported, the system says it does not know based on the workspace documents.

**V1 principle:** one workspace, one document collection, one high-value internal use case, one trusted answer path.

## 4) Input data types
**Pilot positioning for v1:**
- PDF-first

**Implementation note:**
The current codebase has moved beyond strict PDF-only handling in several ingestion paths, but the recommended pilot story remains **PDF-first** because it is easier to explain, validate, support, and demo cleanly.

**Recommended pilot document set:**
- SOPs
- internal policy manuals
- product/service reference PDFs
- onboarding guides
- process documentation
- compliance/reference binders exported as PDF

This keeps the pilot easier to operate even though the underlying platform is already evolving toward broader ingestion support.

## 5) Demo flow
**10-minute buyer demo:**
1. Show private deployment boundary: “This runs in your environment / controlled instance.”
2. Open a workspace preloaded with customer-relevant sample PDFs.
3. Ask a common operational question.
4. Show a concise answer with citations to exact source passages.
5. Ask a follow-up question that requires combining multiple document sections.
6. Click the citation/source reference to prove grounding.
7. Ask a question not covered by the documents.
8. Show the safe fallback: *“I don't know based on the documents in this workspace.”*
9. Upload one new PDF and show that it becomes available after indexing.
10. Close with the value proposition: faster internal answers, less dependency on tribal knowledge, private deployment.

## 6) Recommended initial deployment model
**Best initial deployment:** single-tenant pilot deployment for one customer, using Docker Compose on a customer-controlled VM or a dedicated managed host.

Why this is the right first sale:
- simpler security story
- easier support and debugging
- cleaner buyer trust model
- avoids premature multi-tenant complexity in the first pilot engagement
- still aligns with later product expansion

**Recommended commercial framing:**
- paid pilot
- fixed document volume cap
- fixed user group or team
- fixed implementation/setup window
- optional managed hosting if the customer is comfortable with it

## 7) Explicit out-of-scope items
To keep v1 saleable and finishable, **exclude from the pilot promise**:
- Google Drive, SharePoint, Jira, Confluence, Bitbucket, email, or other connectors as required pilot commitments
- web crawling / internet search
- OCR / scanned-document recovery as a required promise
- broad multi-format ingestion as a required pilot promise
- advanced admin analytics dashboards
- agent workflows / task automation
- cross-tenant shared platform operations for the first customer deployment
- enterprise SSO / SCIM
- billing/self-serve provisioning
- model routing / advanced retrieval tuning as a required sales promise
- broad company-wide rollout beyond the pilot team

Important nuance: some of these surfaces may already exist partially in the codebase, but they should not be treated as committed pilot-scope promises unless explicitly packaged and validated.

## 8) Crisp v1 positioning paragraph
**Sovereign Knowledge Platform v1** is a private AI knowledge assistant for teams that need fast, trustworthy answers from internal documents without exposing company knowledge to public AI tools. For the first pilot, it focuses on one high-value use case: upload a curated set of PDFs, ask natural-language questions, and get grounded answers with citations inside a customer-controlled deployment. It is intentionally narrow: private, reliable, and easy to prove in a real business workflow.
