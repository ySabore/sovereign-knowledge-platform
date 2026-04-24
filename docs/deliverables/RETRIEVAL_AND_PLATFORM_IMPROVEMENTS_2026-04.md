# Retrieval Accuracy and Platform Improvements (April 2026)

This document summarizes the key implementation work completed recently, with emphasis on retrieval quality and related product/platform hardening.

## 1) Retrieval Accuracy Improvements

- Added and stabilized strategy-based retrieval modes:
  - `heuristic`
  - `hybrid` (vector + keyword blending)
  - `rerank` (hosted reranking path with graceful fallback)
- Preserved grounded-answer safety behavior:
  - No-evidence contract remains enforced (`I don't know based on the documents in this workspace.`).
- Improved citation and source UX alignment:
  - Citation-aware answer rendering and source-panel behavior updates in chat surfaces.
- Expanded metadata-aware and history-aware chat behavior:
  - Session/message metadata improvements for better retrieval/generation traceability.
- Kept retrieval scope isolation intact:
  - Retrieval remains org/workspace scoped with existing RBAC constraints.

## 2) Google Drive Connector Scope and Sync Accuracy

- Migrated to Nango connect-session auth flow (deprecation-safe path).
- Added safer Drive querying and improved error handling in connector sync flow.
- Added configurable Drive sync scope:
  - Multiple root folder IDs
  - Optional subfolder recursion
  - Persisted connector config for folder scope
- Added UI controls for folder scope management in workspace connector panel.
- Improved connector sync loop behavior:
  - Cursor-draining with safety cap to avoid partial syncs.

## 3) Invite and Team Management UX/Flow Fixes

- Fixed invite accept page retry-loop behavior that caused repeated 429/flicker.
- Improved invite acceptance diagnostics for email mismatch cases.
- Added pending invite delete/revoke action in Team Management.
- Refined pending invite action layout for constrained side-panel width.
- Confirmed invite lifecycle semantics:
  - Resend rotates token hash (older links become invalid by design).

## 4) Role/Permissions and Settings Improvements

- Expanded cloud LLM credential management to organization admins (not platform-owner only).
- Updated settings UI gating to match backend authorization.
- Preserved owner-level constraints where intended (danger-zone org delete remains owner-scoped).
- Continued RBAC tightening and verification across org/workspace management routes.

## 5) Navigation and Scope Clarity Improvements

- Unified breadcrumb/scope labeling behavior across chat and non-chat screens.
- Changed org-scoped label from `Platform / ...` to:
  - `Organization / {Org}`
  - `Organization / {Org} / {Workspace}`
- Retained `Platform / {Screen}` only when no organization scope is selected.
- Added account section consistency in main left navigation for role visibility.

## 6) Operational/Rate-Limit Hardening

- Reduced accidental 429 impact in invite/connector workflows by tightening where sync limits apply.
- Added configurable connector hourly sync limit.
- Kept global + org-scoped rate limiting model while removing unintended pressure points in user flows.

## 7) Documentation and Product Surface Alignment

- Updated architecture/decision/status docs to better match implemented behavior.
- Closed drift between "documented intent" and "live code paths" for connectors, retrieval, and RBAC-sensitive UX.

## Current Outcome

The platform moved from "feature exists" to "feature behaves reliably under real admin/member flows":

- Better retrieval relevance controls
- Better connector scoping and sync correctness
- Better invite/admin UX under realistic usage
- Better permission consistency between backend and frontend
- Clearer organization/workspace scope signaling in navigation

