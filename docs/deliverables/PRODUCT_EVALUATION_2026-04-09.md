# Product Evaluation: SKP RAG Workspace Assistant

**Evaluator mindset:** Org buyer comparing against Glean, Guru, or similar RAG workspace products  
**Date:** 2026-04-09  
**Test environment:** Docker stack on RTX 5090

---

## Summary Grade: B+ (Competitive with gaps)

### What's Working Well (Competitive)
- Core RAG pipeline: upload, index, retrieve, cite
- Docker-first deployment is solid
- Multi-tenant org/workspace structure
- RBAC member-list restrictions now correct
- Graceful no-evidence fallback

### Critical Gaps for Demo
- [ ] Frontend browser automation not verified
- [ ] Admin UI may break on missing endpoints
- [ ] No real connector integrations proven
- [ ] Stripe/Clerk external integrations not validated

---

## Detailed Walkthrough

### 1. First Impression (Marketing/Landing)
**Status:** ✓ EXISTS
- Vite/React frontend with dark enterprise UI
- Landing page exists in `frontend/src/pages/MarketingLandingPage.tsx`
- Professional appearance matching enterprise-ui-screens.html spec

**Competitive comparison:**
- Glean has stronger brand presence
- SKP UI looks modern but needs copy/polish

### 2. Authentication Flow
**Status:** ✓ WORKING

Tested via API:
- Login with seeded org-admin: ✓ Success
- JWT token returned: ✓ Working
- User profile with role info: ✓ Working
- Clerk integration: Configured but not validated

**Competitive comparison:**
- Standard JWT auth on par with competitors
- Clerk option adds enterprise SSO compatibility

### 3. Organization & Workspace Management
**Status:** ✓ WORKING

Tested capabilities:
- Create organization via API: ✓ Working
- List my organizations: ✓ Working
- Create workspace in org: ✓ Working
- List workspaces: ✓ Working
- RBAC: org_owner only can see member lists: ✓ Fixed

**Gap identified:**
- Member management UI may expect broader access than API allows
- Need to verify UI gracefully handles 403s on member lists

### 4. Document Upload & Ingestion
**Status:** ✓ WORKING

Tested capabilities:
- PDF upload endpoint exists: ✓ /documents/workspaces/{id}/upload
- PDF parsing with page extraction: ✓ Working
- Chunking and embedding: ✓ Working with nomic-embed-text
- Document status tracking: ✓ Working

**Competitive comparison:**
- Standard PDF ingestion comparable to Guru
- Lacks advanced connectors (Confluence, Drive) - only static catalog shown

### 5. Chat & Retrieval Experience
**Status:** ✓ WORKING (Core RAG)

Tested capabilities:
- Grounded chat with citations: ✓ Working
- Retrieval search endpoint: ✓ Working
- Exact no-evidence fallback: ✓ "I don't know based on the documents"
- Workspace isolation: ✓ Proven in smoke test
- Chat sessions with persistence: ✓ Working

**Competitive comparison:**
- Core RAG comparable to Glean
- Citations with source documents: ✓ Good
- Missing: inline highlighting, multi-turn context depth unclear

### 6. Admin & Analytics Surfaces
**Status:** ⚠️ PARTIAL

Backend capabilities exist:
- /admin/metrics/summary: ✓ In code
- /admin/documents/{org_id}: ✓ In code
- /admin/connectors/{org_id}: ✓ In code

Gap: Frontend may not gracefully handle endpoint availability

### 7. Team Collaboration Features
**Status:** ⚠️ UNVERIFIED

What's in code:
- Org members can be added/removed
- Workspace members with roles
- Audit logging exists

Not verified:
- Real-time collaboration
- Notifications
- Permission enforcement in UI

### 8. External Integrations
**Status:** ✗ NOT PROVEN

Configured but not validated:
- Stripe billing: Code exists, no live test
- Clerk webhooks: Code exists, no live test
- Nango connectors: Code exists, no active integrations

---

## Critical Issues to Fix Before Demo

### Issue 1: Frontend Contract Validation ✓ FIXED
**Severity:** HIGH  
**Problem:** Admin pages may crash if backend endpoints unavailable  
**Fix:** 
- Created `AdminPermissionGuard` component that probes admin access before rendering
- Added specific 403/404 error handling in AdminDocumentsPage and AdminDashboardPage
- Pages now show graceful "Admin Access Required" message instead of crashing

### Issue 2: Real Connector Proof
**Severity:** MEDIUM  
**Problem:** Static connector catalog looks good but none are live  
**Fix:** Either activate one connector (Confluence/Notion) or hide catalog until ready

### Issue 3: Billing Flow
**Severity:** MEDIUM  
**Problem:** Stripe integration is code-only, no demo path  
**Fix:** Add test mode billing flow or disable for demo

---

## What Makes This Competitive

1. **Docker-first deployment** - Easier than Glean's cloud-only
2. **Local GPU inference** - Cost advantage with Ollama
3. **Clean multi-tenant model** - Org/workspace isolation done right
4. **Fast iteration** - Can redeploy full stack in minutes

## What Needs Work to Win

1. **Frontend polish** - Need smooth UI walkthrough
2. **One live connector** - Prove integration capability
3. **Clear pricing/billing demo** - Show business model
4. **Performance benchmarks** - Query latency vs competitors

---

## Recommendation

**Ship the core RAG demo** (org → workspace → upload → chat) **it's competitive.**  
**Defer** admin analytics, connectors, and billing to v1.1 unless critical for this client.
