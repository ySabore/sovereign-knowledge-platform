# Executive Summary: Retrieval and Platform Improvements (April 2026)

## What changed

SKP moved from "feature complete on paper" to "reliable under real admin/member workflows," with focused improvements in retrieval quality, connector sync precision, RBAC consistency, and operational stability.

## Business impact

- Better answer quality and trust through stronger retrieval controls and grounded fallback guarantees.
- Lower support burden by fixing high-friction invite/admin UX and reducing accidental 429 failures.
- Higher admin autonomy: organization admins can now manage cloud LLM credentials directly.
- Clearer scope model in UI (`Organization / Org / Workspace`) improves operator confidence and reduces navigation confusion.

## Key delivery themes

### 1) Retrieval accuracy and grounding
- Stabilized strategy-based retrieval (`heuristic`, `hybrid`, `rerank`).
- Preserved strict no-evidence behavior for trust and hallucination control.
- Improved citation/source handling in chat experience.

### 2) Connector sync quality (Google Drive + Nango)
- Completed connect-session auth migration (deprecation-safe path).
- Added configurable Drive sync scope:
  - multiple folder roots
  - optional recursive subfolders
- Improved sync cursor handling and error surfacing to avoid partial/opaque failures.

### 3) Admin and invite workflow reliability
- Fixed invite acceptance retry-loop/flicker failure mode.
- Added pending invite delete/revoke capability in Team Management.
- Clarified mismatch/acceptance behavior and reduced token-flow confusion.

### 4) RBAC and settings consistency
- Enabled Cloud LLM credentials for organization admins (not platform-owner only).
- Aligned frontend visibility with backend authorization behavior.
- Preserved stricter operations where required (e.g., owner-only destructive actions).

### 5) Navigation and scope clarity
- Standardized top-scope labels for org-scoped users:
  - `Organization / {Org}`
  - `Organization / {Org} / {Workspace}`
- Reserved `Platform` label for true platform-wide context only.

## Current outcome

The platform now demonstrates stronger production readiness in the areas that most affect stakeholder confidence:

- retrieval relevance and grounding behavior
- connector correctness under real sync patterns
- predictable admin/member role behavior
- clearer, lower-friction operational UX

## Suggested next step (executive)

Run a short validation pass against three representative tenant scenarios (small, medium, high-doc-volume) and publish before/after KPI snapshots for:

- answer relevance (manual QA rubric)
- invite-to-productive-user time
- connector sync success rate / error-rate
- admin configuration success without platform-owner escalation

