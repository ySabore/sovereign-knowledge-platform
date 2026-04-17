# FRONTEND_ARCHITECTURE.md

## Purpose

This document describes the **actual SPA architecture** of SKP: where responsibilities live, why the shape works, and where structural risk remains.

### Source tree (cutover target)

- **Production cutover target:** `frontend/` — this is the SPA built by `frontend/Dockerfile` and referenced from `docker-compose.prod.yml` / `docker-compose.gpu.yml` as the `web` service.
- **Legacy tree:** `frontend-legacy-20260416/` — archived pre-refactor snapshot kept as rollback backup.

Unless a path is explicitly labeled *legacy*, file paths below refer to **`frontend/src/...`**.

It is intentionally grounded in the current codebase, especially:
- `frontend/src/App.tsx`
- `frontend/src/layouts/ProtectedAppShell.tsx`
- `frontend/src/pages/HomePage.tsx`
- `frontend/src/pages/app/DashboardPage.tsx`
- `frontend/src/context/AuthContext.tsx`
- `frontend/src/features/home-shell/*` — extracted shell routing, nav/workspace/knowledge hooks, org panel, sidebar/topbar

This is not a future-state redesign doc.
It is a map of the frontend as it exists now, with clear guidance for the next refactor steps.

---

## 1. Frontend role in the system

The frontend is not just a thin chat client.
It is a multi-surface application UI for:
- authentication
- protected application bootstrap
- organization and workspace administration
- document and ingestion workflows
- connector management
- analytics and billing surfaces
- grounded workspace chat

The frontend therefore has two major jobs:
1. provide a usable operator/admin shell for the knowledge platform
2. provide a workspace chat experience for end users

That split explains much of the current shape.

---

## 2. High-level frontend structure

## Routing layer

At a high level, the app is organized around:
- public routes
- protected routes
- a protected app bootstrap shell
- large page-level surfaces underneath that shell

### Important files
- `frontend/src/App.tsx`
  - route registration and major page composition
- `frontend/src/layouts/ProtectedAppShell.tsx`
  - authenticated bootstrap for org list / platform navigation context
- `frontend/src/pages/HomePage.tsx`
  - organization/workspace admin shell (orchestration + composition; heavy logic moved into `features/home-shell` hooks and panels)
- `frontend/src/pages/app/DashboardPage.tsx`
  - workspace chat experience, standalone or embedded

---

## 3. Authentication and session model

## `AuthContext.tsx`

`frontend/src/context/AuthContext.tsx` is the frontend auth spine.

It is responsible for:
- current user state
- access token lifecycle
- login/logout behavior
- exposing auth state to protected UI
- bridging frontend behavior to backend auth expectations

### Architectural role

This context is foundational and cross-cutting.
Most other frontend concerns assume auth is already resolved before major protected surfaces render.

### Why this matters

Because auth is centralized, most frontend complexity is not about identity itself.
It is about **what authenticated scope the user is operating in**:
- platform scope
- organization scope
- workspace scope

That scope complexity is what dominates the current shell design.

---

## 4. Protected bootstrap shell

## `ProtectedAppShell.tsx`

`ProtectedAppShell.tsx` is a lightweight but important architectural boundary.

It is responsible for:
- fetching organizations once for the current protected session
- exposing org list via outlet context
- exposing reload behavior for org list
- establishing platform navigation context

### What it gets right

This file already reflects a healthier architecture than `HomePage.tsx`:
- it has a narrow purpose
- it centralizes shared org bootstrap
- it avoids re-fetching org membership independently inside every child page
- it gives child routes a common org context

### Current limitation

It stops at bootstrap.
After that, shell behavior still composes in `HomePage.tsx`, but substantial pieces now live in `features/home-shell` (nav locks, workspace state, knowledge gate, panel router, sidebar/topbar).

---

## 5. Current shell architecture: `HomePage.tsx`

## What `HomePage.tsx` really is

Despite the filename, `HomePage.tsx` behaves less like a simple page and more like an **application shell for org/workspace operations**.

In `frontend`, much of the former inline orchestration has been extracted into `src/features/home-shell/` (e.g. `HomePanelRouter`, `OrganizationsPanel`, `useHomeWorkspaceState`, `useOrgKnowledgeGate`, `useHomeNavState`, `HomeSidebar`, `HomeTopBar`). The page remains the wiring root for org creation state and panel composition.

It currently acts as the control layer for:
- platform-owner scope switching
- organization selection
- workspace selection
- navigation between major panels
- documents surface
- connectors surface
- team management surface
- analytics surface
- billing surface
- organization settings
- upload modal flows
- theme token use for org shell UI
- refresh/load orchestration
- embedded chat handoff into `DashboardPage`

### Architectural reality

**Legacy `frontend/`:** a strong center of gravity still sits in one very large file.

**`frontend/`:** the same product surface is preserved while the shell is modularized; remaining risk is continued discipline (avoid re-inflating `HomePage.tsx` and keep contracts in `features/home-shell/contracts.ts` / `types.ts`).

### Why this happened

This is a common shape in fast-moving product builds:
- one page becomes the trusted place to add the next admin feature
- feature-specific state and UI stay local for speed
- eventually the page becomes the de facto app shell

That is exactly what happened here.

---

## 6. Chat architecture: `DashboardPage.tsx`

`DashboardPage.tsx` is much closer to a dedicated feature surface.

It is responsible for:
- workspace chat session listing
- active session selection
- message rendering
- SSE streaming chat turns
- citation side panel behavior
- embedded vs standalone chat mode
- workspace-switch behavior when hosted under the broader shell

### Important architectural trait

`DashboardPage.tsx` already supports two usage modes:
- standalone dashboard route
- embedded chat panel inside the broader org shell

That is a strong design decision because it allows the chat experience to remain a reusable feature surface instead of being permanently trapped inside one route.

### Current coupling

The coupling problem is not mainly inside `DashboardPage.tsx`.
The coupling is in the host logic around it, especially in `HomePage.tsx`, where chat handoff and wider shell state are mixed together.

---

## 7. Current frontend responsibility map

## Healthy boundaries already present

### Auth boundary
- `AuthContext.tsx`
- clear and foundational

### Protected bootstrap boundary
- `ProtectedAppShell.tsx`
- clear and useful

### Dedicated chat feature boundary
- `DashboardPage.tsx`
- stronger than the rest of the shell surfaces

## Weak boundaries today

### Org/workspace shell boundary
- mostly concentrated in `HomePage.tsx`
- too many responsibilities mixed together

### Feature ownership boundaries
Several backend-backed features exist, but their frontend ownership is still blended into the shell:
- org settings
- uploads
- documents
- connectors
- admin panels
- topbar/scope selection controls

### Reusable shell primitives
Small UI primitives and helper components exist inline where they should increasingly live in feature-local or shared component modules.

---

## 8. Data flow shape today

The current frontend generally follows this flow:

1. auth resolves
2. protected shell loads org membership
3. large page surfaces fetch feature-specific data
4. shell state and render logic are interleaved within major page files
5. child panels sometimes receive data from the shell and sometimes load independently

### What works
- practical and direct
- easy to iterate quickly
- backend contracts are explicit in the page code

### What hurts
- data loading and rendering logic are often interwoven
- page files become hard to scan
- refresh behavior becomes fragile and repetitive
- feature extraction gets harder over time

---

## 9. Primary architectural risk

The biggest frontend architectural risk is **not** that the frontend is broken.
It is that the frontend is becoming expensive to change safely.

**Legacy `frontend/`:** that risk is concentrated in `HomePage.tsx` because it combines:
- navigation logic
- scope logic
- backend-backed admin features
- UI primitives
- modal logic
- embedded feature hosting

### Practical consequences
- higher regression risk
- slower onboarding for any engineer touching the frontend
- harder testing strategy
- increased chance that unrelated features interfere with each other

**`frontend/`:** risk is reduced by extraction and logic tests, but parity and operational burn-in remain the real production gate (see `docs/frontend-parity-checklist.md`).

---

## 10. Recommended frontend architecture direction

The correct next move is **modularization, not redesign**.

### Keep
- route behavior
- backend contracts
- current UX shape unless intentionally changed later
- `ProtectedAppShell.tsx` as the authenticated bootstrap boundary
- `DashboardPage.tsx` as the primary chat feature surface

### Change
- reduce `HomePage.tsx` to a thin shell composer (**largely done in `frontend`** via `features/home-shell`)
- extract scope selectors into dedicated components
- extract org settings into a feature module
- extract upload modal into a dedicated feature component
- move panel switching into a `HomePanelRouter` (**done in `frontend`**)
- gradually move shell state into dedicated hooks (**workspace, knowledge gate, nav: done in `frontend`**)

This direction is detailed in:
- `FRONTEND_REFACTOR_PLAN_HOMEPAGE.md`

---

## 11. Suggested conceptual module model

The frontend is easiest to reason about if treated as four layers:

### Layer 1: app bootstrap
- auth
- route protection
- initial org bootstrap

### Layer 2: platform/org shell
- active org scope
- active workspace scope
- shell navigation
- admin panel hosting

### Layer 3: feature surfaces
- documents
- connectors
- team management
- analytics
- billing
- organization settings
- chat host

### Layer 4: shared primitives
- shell-specific buttons/inputs/badges/dropdowns
- generic shared UI pieces where reuse is real

In legacy `frontend/`, layer 2 and layer 3 were too collapsed into `HomePage.tsx`.

In `frontend/`, layer 2 vs 3 separation is **materially improved**; keep new feature work in feature modules rather than the page file.

---

## 12. Near-term refactor priority

**`frontend` status (high level):** panel router, nav/workspace/knowledge hooks, organizations panel, sidebar, and topbar are extracted; continue with any remaining inline chunks in `HomePage.tsx`, upload/documents coupling, and broader route-level code splitting.

Legacy `frontend/` highest-value extractions (if that tree is still maintained):
1. organization selector
2. workspace selector
3. organization settings panel
4. upload modal
5. `HomePanelRouter`

After that:
6. sidebar and topbar extraction
7. consolidated shell state hook(s)
8. feature-specific data hooks where they reduce real duplication

---

## 13. Architecture bottom line

The frontend already supports a much richer product surface than a simple RAG demo UI.

Its strongest current architectural pieces are:
- centralized auth
- protected bootstrap shell
- reusable chat surface

Its weakest architectural point in **legacy `frontend/`** is:
- the oversized, multi-responsibility `HomePage.tsx` shell

In **`frontend/`**, the same product intent applies: **preserve behavior** while keeping the shell thin and feature-owned. Operational readiness is tracked in `docs/frontend-parity-checklist.md` and `docs/frontend-cutover-runbook.md`.

