# FRONTEND_REFACTOR_PLAN_HOMEPAGE.md

## Objective

Refactor `frontend/src/pages/HomePage.tsx` from a giant orchestration file into a modular frontend shell that is easier to understand, test, and extend without breaking unrelated admin flows.

This is a **structure and maintainability refactor plan**, not a redesign proposal.

---

## Current problem

`HomePage.tsx` has become the de facto application shell for a large portion of SKP.

It currently mixes too many concerns in one file:
- org selection and platform scope
- workspace selection and routing logic
- dashboard shell
- documents panel
- connectors panel
- team management
- analytics
- billing
- org settings
- upload modal flows
- UI theme and shell token handling
- data loading and refresh logic
- navigation state
- permission gating
- embedded chat handoff into `DashboardPage`

### Why this is risky

- hard to reason about changes safely
- hard to isolate bugs
- hard to onboard a new engineer
- high chance of accidental regressions
- difficult to test at the right granularity
- encourages more features to pile into the same file

This is not a correctness crisis, but it is a **velocity and maintainability risk**.

---

## Refactor goal state

The goal is not “make everything abstract”.
The goal is:
- keep the current UX intact
- reduce cognitive load
- isolate responsibilities
- make each surface independently editable
- preserve the existing backend contracts

### Desired end state

`HomePage.tsx` should become a thin composition shell that mainly does:
- bootstrap app-level org/workspace state
- hold top-level selected panel / shell context
- compose child sections
- pass minimal props down

Target size:
- ideally under ~300 to 500 lines
- current giant inline component definitions should move out

---

## Proposed decomposition

## 1. Keep `HomePage.tsx` as shell composer only

### Responsibility
- read protected-shell org context
- own top-level selected panel state
- own selected org / selected workspace scope state
- wire child panels together
- manage high-level refresh triggers

### What should leave this file
- detailed panel UIs
- dropdown implementations
- org settings form logic
- modal implementations
- repeated small utility UI primitives

---

## 2. Extract shell layout pieces

Create a `frontend/src/features/home-shell/` or `frontend/src/pages/home/` area.

Suggested structure:

```text
frontend/src/features/home-shell/
  HomeShell.tsx
  HomeSidebar.tsx
  HomeTopbar.tsx
  HomePanelRouter.tsx
  home-shell.types.ts
  home-shell.constants.ts
```

### `HomeShell.tsx`
Primary composition wrapper.

### `HomeSidebar.tsx`
Owns left-nav rendering and nav item behavior.

### `HomeTopbar.tsx`
Owns header actions, mode toggles, scope selectors.

### `HomePanelRouter.tsx`
Maps current panel selection to the correct panel component.

This immediately removes a lot of orchestration noise from `HomePage.tsx`.

---

## 3. Extract scope selectors

The org and workspace dropdowns are rich enough to deserve their own components.

Suggested files:

```text
frontend/src/features/scope-select/
  OrganizationSelect.tsx
  WorkspaceSelect.tsx
```

These should own:
- open/close state
- local search
- filtering
- selection rendering
- dropdown UI

They should not own broader page state.

---

## 4. Extract organization settings into a real feature area

The organization settings section already has real business logic and should be treated as a feature, not an inline panel.

Suggested structure:

```text
frontend/src/features/organization-settings/
  OrganizationSettingsPanel.tsx
  OrganizationDangerZone.tsx
  OrganizationProviderSettings.tsx
  OrganizationRetrievalSettings.tsx
  OrganizationProfileSettings.tsx
  organization-settings.types.ts
```

### Why
The settings form includes:
- org metadata
- chat provider choice
- retrieval strategy choice
- Ollama URL
- cloud provider credentials
- dangerous destructive actions

That is enough business logic to justify a first-class feature module.

---

## 5. Separate presentational primitives from page logic

A lot of UI helper pieces appear to be local-only conveniences but have become structural clutter.

Likely extraction candidates:
- `NavItem`
- `StatTile`
- `Btn`
- `Input`
- badge helpers
- dropdown shell pieces

Suggested destination:

```text
frontend/src/components/org-shell/
```

or

```text
frontend/src/features/home-shell/components/
```

Rule:
- if a component is shell-specific, keep it near the shell
- if a component is generic, move it to `components/`

---

## 6. Move panel implementations behind a panel router

Instead of giant inline conditional sections in `HomePage.tsx`, use a router-like component.

### Example conceptual split
- `PlatformOverviewPanel`
- `OrgOverviewPanel`
- `WorkspacePanel`
- `ConnectorsPanel`
- `DocumentsPanel`
- `BillingPanel`
- `AnalyticsPanel`
- `TeamPanel`
- `ChatsPanelHost`

### Benefit
The main shell stops being a monolith and becomes an assembly point.

---

## 7. Introduce a dedicated home-shell state hook

Suggested file:

```text
frontend/src/features/home-shell/useHomeShellState.ts
```

This hook should centralize:
- selected panel
- selected org id
- selected workspace id
- platform owner scope behavior
- default selection rules
- refresh helpers

### Why
Right now page state and rendering logic are tightly interleaved.
Separating the shell state logic makes behavior easier to reason about and test.

---

## 8. Introduce data hooks for major backend-backed areas

Suggested hooks:

```text
frontend/src/features/organizations/useOrganizations.ts
frontend/src/features/workspaces/useWorkspaceScope.ts
frontend/src/features/documents/useOrganizationDocuments.ts
frontend/src/features/connectors/useOrganizationConnectors.ts
```

These should encapsulate:
- loading
- error
- reload
- normalization

### Why
This reduces request logic inside giant render files and creates reusable data contracts.

---

## 9. Keep embedded chat integration, but isolate it

The handoff from org shell into `DashboardPage` is useful and should stay.

But the logic around:
- `chatWorkspaceId`
- embedded dashboard mode
- workspace jump behavior

should move into a small host component like:

```text
frontend/src/features/chat-host/EmbeddedWorkspaceChatPanel.tsx
```

This lets the chat handoff stay powerful without polluting the broader shell.

---

## Refactor phases

## Phase 1 — low-risk extraction

Goal: reduce file size without changing data flow too much.

Do first:
1. extract small presentational components
2. extract org selector
3. extract workspace selector
4. extract org settings panel
5. extract upload modal

### Outcome
- immediate readability gain
- low behavioral risk
- minimal prop reshaping

---

## Phase 2 — shell structure cleanup

Goal: separate composition from feature implementation.

Do next:
1. create `HomePanelRouter`
2. move inline panel render blocks into dedicated components
3. move left nav into `HomeSidebar`
4. move top controls into `HomeTopbar`

### Outcome
- `HomePage.tsx` becomes mostly composition
- easier to scan and reason about page flow

---

## Phase 3 — state and data hook cleanup

Goal: reduce interleaving of state logic and rendering.

Do next:
1. add `useHomeShellState`
2. extract backend-backed data hooks
3. unify reload patterns
4. normalize prop contracts

### Outcome
- better testability
- easier future changes
- less prop drilling chaos

---

## Phase 4 — optional design cleanup after structural stability

Only after the structure is sane:
- unify shell component naming
- simplify style token usage
- remove duplicated logic
- evaluate generic table/list patterns

Do not start here.

---

## Guardrails for the refactor

### 1. Do not redesign the UX during structural refactor
If the UX changes at the same time, it becomes too hard to know whether breakage came from architecture or design.

### 2. Keep backend contracts unchanged
This should be a frontend structure refactor first.

### 3. Preserve route behavior
`/home`, `/organizations`, embedded chat, and admin access behavior should continue working exactly as now unless intentionally changed.

### 4. Extract by coherent responsibility, not by arbitrary line count
Bad extraction just creates prop spaghetti.

### 5. Prefer feature folders over dumping everything into `components/`
This keeps ownership obvious.

---

## Suggested target module layout

```text
frontend/src/features/
  home-shell/
    HomeShell.tsx
    HomeSidebar.tsx
    HomeTopbar.tsx
    HomePanelRouter.tsx
    useHomeShellState.ts
    home-shell.types.ts
  scope-select/
    OrganizationSelect.tsx
    WorkspaceSelect.tsx
  organization-settings/
    OrganizationSettingsPanel.tsx
    OrganizationDangerZone.tsx
    OrganizationProviderSettings.tsx
    OrganizationRetrievalSettings.tsx
  chat-host/
    EmbeddedWorkspaceChatPanel.tsx
  uploads/
    UploadModal.tsx
```

This is only a suggested first pass, not a rigid final taxonomy.

---

## Priority order if you want implementation work next

### Highest value
1. extract `OrganizationSettingsPanel`
2. extract org/workspace selectors
3. extract upload modal
4. add `HomePanelRouter`

### Next
5. move sidebar/topbar into dedicated shell components
6. add `useHomeShellState`

### Later
7. split data-loading hooks by feature
8. normalize shell component APIs

---

## What success looks like

You know this refactor worked when:
- a new engineer can find the connectors panel without hunting through thousands of lines
- changing org settings does not require touching shell nav code
- chat embedding logic is isolated from billing or analytics UI
- most frontend changes happen in feature folders, not the giant page file
- `HomePage.tsx` reads like a map, not a maze

---

## Bottom line

The right move is not to rewrite the frontend.
The right move is to **turn `HomePage.tsx` from an everything-file into a shell composer with feature-owned children**.

That gives SKP a frontend architecture that matches the maturity of the backend.
