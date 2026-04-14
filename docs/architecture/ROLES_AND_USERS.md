# Users and roles (platform model)

This document is the **canonical** description of how people map to permissions in Sovereign Knowledge Platform (SKP). Implementation lives in `app/models.py` (`OrgMembershipRole`, `WorkspaceMemberRole`, `User.is_platform_owner`) and guards in `app/deps.py` and `app/routers/`.

## Layers

SKP uses **three independent layers**. A single person can hold several at once (for example: platform operator **and** org owner in one tenant).

| Layer | Stored on | Purpose |
|--------|-----------|---------|
| **Platform** | `users.is_platform_owner` | Product-wide administration across all organizations. |
| **Organization** | `organization_memberships.role` | Tenant administration and membership inside one org. |
| **Workspace** | `workspace_members.role` | Access and admin duties inside one knowledge workspace. |

Lower layers do **not** automatically grant platform powers. **Platform owner** is a separate flag and is checked first in several API dependencies.

---

## 1. Platform-level: `User.is_platform_owner`

| Field | Type | Meaning |
|--------|------|---------|
| `is_platform_owner` | `bool` on `users` | **Platform owner** (sometimes called *platform operator* or *super-admin*): can act across tenants when the API allows it. |

**Typical capabilities (as enforced in code):**

- **`GET /organizations/me`** returns **every organization** in the database (ordered by creation time) when `is_platform_owner` is true—no `organization_memberships` row is required. Non–platform users only receive organizations they belong to (membership join).
- Create organizations and other cross-tenant operations guarded by `require_platform_owner` (`app/deps.py`).
- **Org-scoped routes** (e.g. `GET /organizations/{org_id}`, `GET /workspaces/org/{org_id}`): the signed-in platform owner may access any existing org without being a member; invitees and other users still require membership where applicable (`organizations.py` `_require_org_membership`).
- Optional `organization_id` when viewing **admin metrics**; org-scoped users must pass their org id (`require_admin_metrics_viewer`).
- Treated like an org owner for **org-scoped admin surfaces** when combined with `require_org_owner_or_platform` (e.g. connector status for an org).

**How it is set:** operational / database (or seed), not derived from org membership. The API exposes it on `UserPublic` as `is_platform_owner`; `/auth/me` returns `org_ids_as_owner` for org-level admin UX when the user is **not** a platform owner.

---

## 2. Organization-level: `OrgMembershipRole`

Stored in `organization_memberships.role` (string values below).

| Enum value (`OrgMembershipRole`) | Label (UI) | Meaning |
|----------------------------------|------------|---------|
| `org_owner` | Organization owner | Full admin for that **organization**: members, workspaces (as implemented in `organizations` router), billing hooks, etc. |
| `member` | Member | Belongs to the org; **not** an org-wide admin. Further access is usually via workspace membership. |

**Notes:**

- Org owners are listed in `UserPublic.org_ids_as_owner` for the frontend (e.g. default org context for admin pages).
- **Admin metrics** for non–platform users require `organization_id` and membership with role `org_owner` (`require_admin_metrics_viewer`).
- At least one `org_owner` should remain; the API prevents removing the last org owner when demoting/removing members (see `organizations.py`).

---

## 3. Workspace-level: `WorkspaceMemberRole`

Stored in `workspace_members.role`.

| Enum value (`WorkspaceMemberRole`) | Label (UI) | Meaning |
|------------------------------------|------------|---------|
| `workspace_admin` | Workspace admin | Can manage **workspace membership** (invite/change/remove) and other workspace-admin actions guarded by `_require_workspace_admin` in `organizations.py`. |
| `member` | Member | Can use the workspace for **chat**, **documents**, and related APIs that only require being a workspace member (any role in `workspace_members`). |

**Notes:**

- Creating a workspace typically adds the creator as `workspace_admin` (see workspace creation in `organizations.py`).
- Workspace **member** (either role) is required for document/chat routes that join on `WorkspaceMember` (e.g. `documents.py`, `chat.py`).
- At least one `workspace_admin` should remain when demoting/removing members.

---

## 4. Clerk and the React admin shell (parallel path)

Some UI gates use **Clerk organization roles** (see `RequireAdmin.tsx`): e.g. `org:admin` or `admin` in Clerk org membership. That is **orthogonal** to Postgres roles: the backend source of truth for data access remains `users` + `organization_memberships` + `workspace_members`. Keep Clerk roles aligned with org/workspace roles in production to avoid confusion.

---

## 5. Document access (retrieval RBAC)

Beyond “is this user in the workspace?”, **document read** can be restricted by `DocumentPermission` rows when RBAC mode is *full* (connector-synced ACLs). See ingestion/permissions services and env/config for mode. This is **not** the same as org/workspace role enums; it is **per-document** (and optional user lists) on top of workspace membership.

---

## 6. Chat message roles (different domain)

`ChatMessageRole` (`system`, `user`, `assistant`) describes **messages inside a conversation**, not product RBAC. Do not confuse with `OrgMembershipRole` / `WorkspaceMemberRole`.

---

## Quick reference: string values in API/DB

| Concept | Stored value(s) |
|---------|------------------|
| Platform owner | `users.is_platform_owner == true` |
| Org owner | `organization_memberships.role == "org_owner"` |
| Org member | `"member"` |
| Workspace admin | `workspace_members.role == "workspace_admin"` |
| Workspace member | `"member"` |

Use these exact strings in API payloads for member upserts unless extended in `models.py`.
