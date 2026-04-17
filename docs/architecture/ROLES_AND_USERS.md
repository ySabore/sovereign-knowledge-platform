# Sovereign Knowledge Platform RBAC: Roles and Users

This document is the product-facing RBAC source of truth for SKP, recreated from the architecture guide in `Sovereign Knowledge Platform - RBAC Role Guide.pdf`.

The core principle is strict scope separation:

- Platform concerns stay at platform level.
- Organization concerns stay inside one organization.
- Workspace concerns stay inside assigned workspaces.
- Retrieval access is enforced in backend query filters, not only in UI.

## 1) Role hierarchy (5 tiers)

| Tier | Role | Scope | Primary purpose |
|---|---|---|---|
| Tier 0 | Platform Owner | Entire platform (all orgs/workspaces) | Operate and support the SaaS platform. |
| Tier 1 | Org Admin | One organization and all its workspaces | Run org operations, billing, and team management. |
| Tier 2 | Workspace Admin | Assigned workspace(s) only | Manage workspace users, content, and workspace settings. |
| Tier 3 | Editor / Contributor | Assigned workspace(s) only | Curate knowledge content without admin ownership. |
| Tier 4 | Member (Read-only / Chat User) | Assigned workspace(s) only | Ask questions and consume answers only. |

## 2) Role definitions

### Platform Owner (Tier 0)

Platform-level operator with full multi-tenant visibility and controls.

Can do:

- View platform overview across organizations.
- Create, suspend, archive organizations.
- View platform billing, usage, and global audit data.
- Manage platform settings (models, infra, global flags).
- Enter org support/impersonation flows with audit logging.

Cannot do (by policy):

- Bypass auditing for support actions.
- Use high-privilege access casually for day-to-day workspace operations.

### Org Admin (Tier 1)

Owns one organization end-to-end.

Can do:

- See org dashboard rollups and org-wide analytics.
- Create, rename, archive workspaces in their org.
- Invite/remove org users and assign roles up to workspace scope.
- Manage org billing and SSO configuration.
- View org audit logs and org-wide connector status.

Cannot do:

- Access platform overview or other organizations.
- Assign Platform Owner.
- Hard-delete organization (Platform Owner only).

### Workspace Admin (Tier 2)

Admin within assigned workspace(s), not org-wide.

Can do:

- Manage workspace members in assigned workspaces.
- Manage documents and connectors in assigned workspaces.
- Configure workspace-level AI/settings.
- View workspace analytics and workspace audit log (scoped to managed workspace events).

Cannot do:

- Access org billing, org SSO, org-wide team controls.
- Create or delete workspaces at org scope (Org Admin+ only).
- Access workspaces they are not assigned to.
- Access platform settings.
- View org-level audit events outside managed workspace scope.

### Editor / Contributor (Tier 3)

Content power user without admin controls.

Can do:

- Upload documents/files.
- Delete documents they own (not any document in workspace).
- Re-index content they manage.
- Use chat against their assigned workspace knowledge base.
- View connector sync status as read-only.

Cannot do:

- Invite/remove members.
- Change workspace/org/platform settings.
- Manage integrations.
- View other users' chats.

### Member (Tier 4)

Primary end user with a clean chat-first experience.

Can do:

- Ask questions in assigned workspace(s).
- View own conversation history.
- Give answer feedback (thumbs up/down).
- Export own answers.
- Share conversation links within permitted workspace scope.
- Upload files from chat for immediate indexing/query in assigned workspace(s).

Cannot do:

- Delete documents.
- Manage users, connectors, analytics, or audit settings.
- Access org/platform controls.
- View data outside assigned workspace scope.

## 3) Navigation and UX rules

- Hide inaccessible navigation items entirely (do not show locked entries).
- Member UX should default to chat-first with minimal admin chrome.
- Sidebar breadth grows with responsibility:
  - Platform Owner: full platform + org + workspace nav.
  - Org Admin: full org + workspace nav (no platform nav).
  - Workspace Admin: workspace-scoped nav only.
  - Editor: chat + documents + read-only connector status.
  - Member: chat + own history + profile only.

Scope clarity in UI:

- When a Workspace Admin opens `Audit` or `Settings`, the UI shows a `Workspace-scoped access` badge.
- This indicates the panel is intentionally limited to managed workspace scope, not org-wide controls.

## 4) Permission matrix (condensed)

| Capability area | Platform Owner | Org Admin | Workspace Admin | Editor | Member |
|---|---|---|---|---|---|
| Platform management | Yes | No | No | No | No |
| Org management (one org) | Yes | Yes | No | No | No |
| Workspace member/admin management | Yes | Yes | Yes (assigned only) | No | No |
| Document upload/manage | Yes | Yes | Yes | Yes (content only) | No |
| Connector config/sync control | Yes | Yes | Yes | Read-only | No |
| Chat query access | Yes | Yes | Yes | Yes | Yes |
| Cross-user chat visibility | Yes | Yes | Yes (assigned ws) | No | No |

Additional matrix nuances from the HTML guide:

- Editor can delete documents with `Own only` semantics.
- Editor connector visibility is `Read-only` (no connect/disconnect/settings/sync actions).
- Member `Share conversation link` is limited to workspace-scoped sharing.

## 5) Critical security requirements

1. Enforce RBAC at API/middleware level for every route.
2. Enforce retrieval filtering at query time (`workspace_id`, plus document-level ACL when enabled).
3. Never rely on UI hiding as a security boundary.
4. Audit log all state-changing admin actions:
   - role changes
   - user membership changes
   - connector connect/disconnect/sync
   - document upload/delete/re-index
   - org/workspace create/archive/delete
   - impersonation events

## 6) Data model recommendation

Define canonical role values:

- `platform_owner`
- `org_admin`
- `workspace_admin`
- `editor`
- `member`

Recommended storage model:

- Platform-level ownership on user record or equivalent privileged binding.
- `org_members` with `(user_id, org_id, role)`.
- `workspace_members` with `(user_id, workspace_id, role)`.
- Optional per-document ACL table for full retrieval RBAC.

## 7) Default landing routes by role

- Platform Owner -> `/platform/overview`
- Org Admin -> `/dashboard`
- Workspace Admin -> `/workspaces/{workspace_id}/chat`
- Editor -> `/workspaces/{workspace_id}/chat`
- Member -> `/chat` (or workspace chat with minimal UI)

## 8) Implementation checklist

1. Define role enums and membership tables for org/workspace scope.
2. Add role/scope middleware guards to all API routes.
3. Filter vector/document retrieval by accessible scope every query.
4. Render navigation from effective role and accessible workspaces only.
5. Implement default post-login routing per role.
6. Add structured audit event logging for admin actions.
7. Test each role in isolation for UI, API authorization, and retrieval scope.

## 9) Notes for current code alignment

If implementation currently uses role names like `org_owner` or `member`, map them explicitly to this product model during migration to avoid ambiguity.

If source materials conflict, treat the detailed permission matrix and critical security rules as authoritative over any conflicting narrative bullet text.

## 10) Backend enforcement status

Implemented in backend:

- `WorkspaceMemberRole` includes `editor`.
- Workspace access is now strict: platform owner, org owner, or assigned workspace member.
- Org members without workspace assignment cannot access workspace-scoped resources.
- Document upload/ingest requires contributor role (`workspace_admin` or `editor`) or org/platform admin.
- Document deletion policy:
  - `platform_owner`, `org_owner`, `workspace_admin` => can delete any workspace document.
  - `editor` => can delete only documents they created.
  - `member` => cannot delete.
- Connector policy:
  - View/list connectors: `platform_owner`, `org_owner`, `workspace_admin`, `editor`.
  - Manage connectors (activate/sync/delete/permission sync): `platform_owner`, `org_owner`, `workspace_admin`.
  - `member` denied.
- Chat session visibility:
  - `org_owner` and `workspace_admin` can list all sessions in a workspace.
  - `editor` and `member` see only their own sessions.
- Chat upload + feedback:
  - `POST /chat/workspaces/{workspace_id}/upload` allows workspace members to upload/index from chat.
  - `PUT /chat/messages/{message_id}/feedback` persists thumbs up/down on assistant answers.
- Audit visibility:
  - `platform_owner` and `org_owner` can view full org audit stream.
  - `workspace_admin` can view only audit events for workspaces they manage.

Verification tests:

- `tests/test_rbac_membership_visibility.py`
- `tests/test_rbac_role_enforcement.py`

Run:

- `python -m pytest tests/test_rbac_membership_visibility.py tests/test_rbac_role_enforcement.py -q`

Route-level enforcement map:

- See `docs/architecture/RBAC_ROUTE_MATRIX.md` for endpoint-by-endpoint role guards and frontend parity notes.
