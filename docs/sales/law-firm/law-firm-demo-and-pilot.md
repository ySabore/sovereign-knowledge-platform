# law-firm demo and pilot guide

## what is demoable now vs mocked

### demoable now
Based on the current Sovereign Knowledge Platform MVP definition, the following is a credible live demo story:

- secure login for defined user roles
- organization and workspace structure
- pdf upload into a workspace
- document parsing, chunking, embeddings, and indexing
- workspace-scoped chat over uploaded documents
- grounded answers with citations
- strict fallback when evidence is insufficient: `I don't know based on the documents in this workspace.`
- tenant/workspace isolation as a core product requirement and test target
- docker compose deployment for a controlled environment demo

### likely mocked, lightly staged, or best shown as a guided workflow
These should be presented carefully unless already implemented in the codebase and validated end to end:

- polished law-firm-specific UI branding and matter dashboards
- advanced admin analytics and usage reporting
- external connectors like iManage, NetDocuments, SharePoint, Google Drive, Jira, or email systems
- enterprise SSO and mature identity integrations
- automated OCR for messy scans and complex multimodal files
- advanced reranking, hybrid retrieval, or sophisticated search tuning
- production-grade legal hold, retention, or records-management workflows
- deep audit/compliance reporting beyond core logs and access controls

## recommended law-firm pilot scope

### pilot goal
Prove that a private AI knowledge assistant can save attorney and staff time on a narrow, high-value document set while preserving trust through document scoping and citations.

### recommended first pilot shape
Choose **one firm**, **one practice group or operational team**, and **one narrow document corpus**.

Best pilot options:
- employment law playbooks and templates
- m&a or commercial contract precedent library
- litigation motions, briefs, and internal research memos
- internal policies, SOPs, billing rules, and onboarding materials

### recommended pilot boundaries
- 1 organization
- 1 to 2 workspaces
- 5 to 15 pilot users
- 50 to 500 PDFs depending on document quality
- one agreed use case with measurable time savings
- internal-only use during pilot

### success criteria to align on up front
- users can find answers faster than manual search
- answers cite the source material clearly
- the assistant stays within the pilot document set
- the fallback behavior is acceptable when evidence is weak
- pilot users report real value in at least one recurring workflow

## likely implementation timeline

### option a: fast founder-led pilot in 2 to 4 weeks
Use this when the goal is a strong proof-of-value with a narrow dataset and limited user group.

**week 1**
- align on pilot use case
- choose document set
- prepare deployment environment
- configure demo/pilot stack

**week 2**
- ingest documents
- validate answer quality
- tune chunking/prompting basics
- run internal walkthrough

**week 3 to 4**
- onboard pilot users
- gather questions and quality feedback
- tighten prompts, data organization, and source quality
- produce pilot readout

### option b: more production-minded pilot in 4 to 8 weeks
Use this when the firm wants stronger access controls, more validation, more data hygiene, and a cleaner operational setup.

This version allows time for:
- environment hardening
- role and workspace setup review
- better seed content curation
- user onboarding
- iterative tuning based on real legal questions

## positioning notes for venture

### strongest near-term sales message
- private ai for firm knowledge, not a public chatbot
- answers grounded in the firm’s own documents
- citations for attorney verification
- matter or practice-group scoping to reduce leakage risk
- practical pilot path without requiring a huge transformation program

### best realistic promise
“We can stand up a narrow pilot quickly, focused on one document set and one workflow, and show whether the firm can save time while keeping control of its knowledge base.”

### promise to avoid
Avoid promising full document-management replacement, perfect legal reasoning, broad connector coverage, or enterprise-grade compliance maturity on day one.
