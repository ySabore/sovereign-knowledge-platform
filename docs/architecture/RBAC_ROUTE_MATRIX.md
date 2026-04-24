# RBAC Route Matrix

This document maps API routes to enforced RBAC rules and current frontend parity.

Source of truth:

- Backend route guards in `app/routers/*` and `app/deps.py`.
- Role model in `app/models.py`.
- Product policy in `docs/architecture/ROLES_AND_USERS.md`.

## Role legend

- `PO` = `platform_owner`
- `OO` = `org_owner`
- `WA` = `workspace_admin`
- `ED` = `editor`
- `MB` = `member`

## Backend route matrix

| Route | Guard summary | Allowed roles |
|---|---|---|
| `POST /organizations` | `require_platform_owner` | `PO` |
| `GET /organizations/me` | own memberships or all for platform owner | `PO`, `OO`, `WA`, `ED`, `MB` |
| `GET /organizations/{org_id}` | org membership or platform bypass | `PO`, `OO`, `WA`, `ED`, `MB` in org |
| `GET /organizations/{org_id}/overview-stats` | org membership | `PO`, `OO`, `WA`, `ED`, `MB` in org |
| `PATCH /organizations/{org_id}` | `_require_org_owner` | `PO`, `OO` |
| `DELETE /organizations/{org_id}` | `_require_org_owner` + confirmation | `PO`, `OO` |
| `GET /organizations/{org_id}/members` | `_require_org_owner` | `PO`, `OO` |
| `PUT /organizations/{org_id}/members` | `_require_org_owner` | `PO`, `OO` |
| `DELETE /organizations/{org_id}/members/{user_id}` | `_require_org_owner` | `PO`, `OO` |
| `GET /organizations/{org_id}/invites` | `_require_org_owner` | `PO`, `OO` |
| `POST /organizations/{org_id}/invites` | `_require_org_owner` | `PO`, `OO` |
| `POST /organizations/{org_id}/invites/{invite_id}/resend` | `_require_org_owner` | `PO`, `OO` |
| `DELETE /organizations/{org_id}/invites/{invite_id}` | `_require_org_owner` | `PO`, `OO` |
| `POST /organizations/invites/accept` | invite token + matching email | invited user |
| `POST /workspaces/org/{org_id}` | `_require_org_owner` | `PO`, `OO` |
| `GET /workspaces/org/{org_id}` | org membership | `PO`, `OO`, `WA`, `ED`, `MB` in org |
| `GET /workspaces/me` | workspace member or org owner or platform owner | `PO`, `OO`, `WA`, `ED`, `MB` (scoped) |
| `GET /workspaces/{workspace_id}` | `resolve_workspace_for_user` | `PO`, `OO`, assigned `WA/ED/MB` |
| `PATCH /workspaces/{workspace_id}` | `_require_workspace_admin` (org owner accepted) | `PO`, `OO`, `WA` |
| `DELETE /workspaces/{workspace_id}` | `_require_org_owner` + confirmation | `PO`, `OO` |
| `GET /workspaces/{workspace_id}/members` | `_require_workspace_admin` | `PO`, `OO`, `WA` |
| `PUT /workspaces/{workspace_id}/members` | `_require_workspace_admin` | `PO`, `OO`, `WA` |
| `DELETE /workspaces/{workspace_id}/members/{user_id}` | `_require_workspace_admin` | `PO`, `OO`, `WA` |
| `POST /documents/workspaces/{workspace_id}/upload` | contributor guard (`WA` or `ED`) + owner/platform bypass | `PO`, `OO`, `WA`, `ED` |
| `POST /documents/workspaces/{workspace_id}/ingest-text` | contributor guard (`WA` or `ED`) + owner/platform bypass | `PO`, `OO`, `WA`, `ED` |
| `GET /documents/workspaces/{workspace_id}` | workspace access guard | `PO`, `OO`, assigned `WA/ED/MB` |
| `POST /documents/workspaces/{workspace_id}/search` | workspace access + retrieval ACL filter | `PO`, `OO`, assigned `WA/ED/MB` |
| `GET /documents/{document_id}` | workspace access for document workspace | `PO`, `OO`, assigned `WA/ED/MB` |
| `DELETE /documents/{document_id}` | delete policy in router | `PO`, `OO`, `WA`, `ED` (own docs only) |
| `GET /documents/ingestion-jobs/{job_id}` | workspace access for job workspace | `PO`, `OO`, assigned `WA/ED/MB` |
| `GET /connectors/organization/{organization_id}` | connector view access | `PO`, `OO`, `WA`, `ED` |
| `POST /connectors/activate` | connector manage access | `PO`, `OO`, `WA` |
| `POST /connectors/{connector_id}/sync` | connector manage access | `PO`, `OO`, `WA` |
| `POST /connectors/sync-permissions` | connector manage access | `PO`, `OO`, `WA` |
| `DELETE /connectors/{connector_id}` | connector manage access | `PO`, `OO`, `WA` |
| `POST /chat/workspaces/{workspace_id}/sessions` | workspace access | `PO`, `OO`, assigned `WA/ED/MB` |
| `POST /chat/workspaces/{workspace_id}/upload` | workspace access + in-chat indexing | `PO`, `OO`, assigned `WA/ED/MB` |
| `GET /chat/workspaces/{workspace_id}/sessions` | workspace access + role-based list policy | `PO`, `OO`, `WA` (all sessions), `ED/MB` (own only) |
| `GET /chat/sessions/{session_id}` | session access via org owner/workspace membership | `PO`, `OO`, assigned `WA/ED/MB` |
| `PATCH /chat/sessions/{session_id}` | rename / pin; same guard as `DELETE` chat session | same as delete chat session |
| `POST /chat/sessions/{session_id}/messages` | session access | `PO`, `OO`, assigned `WA/ED/MB` |
| `POST /chat/sessions/{session_id}/messages/stream` | session access | `PO`, `OO`, assigned `WA/ED/MB` |
| `PUT /chat/messages/{message_id}/feedback` | session access + assistant-only feedback target | `PO`, `OO`, assigned `WA/ED/MB` |
| `POST /chat` | same as stream session route | `PO`, `OO`, assigned `WA/ED/MB` |
| `DELETE /chat/sessions/{session_id}` | own session or workspace admin/org owner/platform owner | `PO`, `OO`, `WA` (or owner of session) |
| `GET /organizations/{org_id}/billing/plan` | `_require_org_owner` | `PO`, `OO` |
| `POST /organizations/{org_id}/billing/checkout` | `_require_org_owner` | `PO`, `OO` |
| `POST /organizations/{org_id}/billing/portal` | `_require_org_owner` | `PO`, `OO` |
| `GET /metrics/summary` | `require_metrics_viewer` | `PO`, `OO` |
| `GET /organizations/{org_id}/documents` | `_require_org_owner` | `PO`, `OO` |
| `GET /organizations/{org_id}/audit` | org owner full scope; workspace admin limited to managed workspaces | `PO`, `OO`, `WA` (workspace-scoped) |

## Frontend parity status

### Implemented

- Home shell enterprise links are role-aware:
  - Billing: platform owner or selected org owner.
  - Audit: platform owner, selected org owner, or workspace admin in selected org.
  - Settings: platform owner/selected org owner (org settings) or workspace admin (workspace settings).
- `/admin/*` route surfaces have been removed from the active shell; role-aware navigation now lives in `/home` panels only.
- Main-shell Audit panel enhancements include workspace filter, failures-only toggle, severity tagging, expandable metadata, and filtered CSV export.
- Audit and Settings headers now show a `Workspace-scoped access` badge when a workspace admin is operating in scoped mode.
- Member chat supports in-composer `Upload file`, persisted answer feedback, PDF export, and metadata-backed workspace operational Q&A (counts/status/source mix/recent files).

### Partial / known gaps

- Home shell currently uses org-level workspace-admin claims for enterprise panel visibility; final enforcement still happens in backend RBAC guards.
- Final authority remains backend RBAC: direct API calls are blocked if UI permits accidental navigation.

## Verification

Current RBAC regression tests:

- `tests/test_rbac_membership_visibility.py`
- `tests/test_rbac_role_enforcement.py`

Run:

- `python -m pytest tests/test_rbac_membership_visibility.py tests/test_rbac_role_enforcement.py -q`
