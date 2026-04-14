# NEXT_TASK.md — Single Most Important Task

**Date:** Friday, April 10, 2026 — 12:14 PM Update

## The One Task: Live API Verification of `/admin/documents/{org_id}`

### Why This Matters Most
While the admin endpoints exist in code and are registered in OpenAPI, they need **live verification** with real authentication tokens to confirm:
1. The endpoints return expected data shapes
2. Auth enforcement works correctly (403 for non-owners)
3. The frontend `/admin/documents` page can successfully consume the API

### Verification Steps
1. **Login as seeded owner** (`owner@example.com` / `password123`) to get JWT
2. **Call `GET /admin/documents/{organization_id}`** with the token
3. **Verify response shape** matches frontend expectations
4. **Test with member token** to confirm 403 enforcement

### Expected Request
```bash
GET http://localhost:8000/admin/documents/{org_id}
Authorization: Bearer {jwt_token}
```

### Expected Response (200)
```json
[
  {
    "id": "...",
    "workspace_id": "...",
    "workspace_name": "...",
    "filename": "...",
    "source_type": "...",
    "status": "indexed",
    "page_count": 10,
    "chunk_count": 25,
    "updated_at": "...",
    "last_indexed_at": "..."
  }
]
```

### Acceptance Criteria
- [ ] Endpoint returns 200 with document list for org_owner
- [ ] Endpoint returns 403 for org_member (non-owner)
- [ ] Response shape matches frontend `AdminDocumentsPage` expectations
- [ ] Documented in fresh verification artifact

### After This
Proceed to `/admin/metrics/summary` live verification, then frontend `/organizations` page verification.

---
*Updated: 2026-04-10 12:14 PM*
