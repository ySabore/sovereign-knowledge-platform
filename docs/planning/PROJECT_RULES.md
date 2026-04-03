# PROJECT_RULES.md

## Product name

**Sovereign Knowledge Platform** (SKP) — canonical planning and delivery docs live in this workspace. Absorbed spec: `SOURCES.md`.

## Mandatory reads before shipping code (Forge)

1. `PRODUCT_REQUIREMENTS.md`  
2. `MVP_IMPLEMENTATION_PLAN.md`  
3. `DELIVERY_SPEC.md`  
4. `ARCHITECTURE.md`  

Implementation order defaults to **`MVP_IMPLEMENTATION_PLAN.md`** unless King explicitly reprioritizes.

## Default real-project root

Use this folder for actual project repositories and codebases:

- `C:\Users\Yeshi\ProjectRepo`

## Separation rule

- `workspace-architect` is for planning, architecture, roadmaps, notes, ADRs, and internal agent documentation.
- `C:\Users\Yeshi\ProjectRepo\<project-name>` is for real source code, Docker files, tests, app structure, and project Git history.

## Git rule

When working on a real project:
1. Prefer creating or using a repo under `C:\Users\Yeshi\ProjectRepo`.
2. Commit and push in the **project repo**, not in `.openclaw`, unless the change is to agent workspace docs.
3. Keep architecture and planning docs in `workspace-architect` unless the user wants project-local docs duplicated in the project repo.

## Example repo path

For the Sovereign Knowledge Platform codebase, use something like:

- `C:\Users\Yeshi\ProjectRepo\sovereign-knowledge-platform`

Then use normal Git workflow there:
- `git init` or existing repo
- `git add .`
- `git commit -m "..."`
- `git push`
