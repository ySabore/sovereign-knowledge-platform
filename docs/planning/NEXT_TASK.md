# NEXT_TASK.md — Single Most Important Task

*Last updated: 2026-04-15 America/New_York*

## The one task

Finish documentation consolidation and feature-documentation cleanup so the repo has a clear, current, low-drift source of truth before further implementation or refactor work.

## Why this matters most now

The codebase has advanced faster than the documentation.
That creates three problems:
1. inaccurate understanding for anyone reading the repo fresh
2. duplicated status files with conflicting information
3. avoidable confusion before deeper engineering cleanup or frontend refactor work

## Acceptance criteria

- [ ] root-level duplicate status docs are converted into pointers or removed safely
- [ ] `docs/README.md` exists and explains canonical doc locations
- [ ] current sprint and next-task docs reflect present reality
- [ ] remaining outdated docs are identified for keep / merge / remove decisions
- [ ] feature documentation is easier to navigate from the docs root

## Concrete subtasks

1. inventory duplicate or stale docs under `docs/`
2. keep product truth in `docs/product/`
3. keep execution truth in `docs/planning/`
4. keep architecture truth in `docs/architecture/`
5. keep delivery/status truth in `docs/deliverables/`
6. convert root duplicates into compatibility pointers
7. flag remaining low-value or outdated docs for merge/delete follow-up

## After this

Once documentation structure is clean, the best next engineering move is:
1. update remaining feature docs with current behavior
2. then begin implementing the `HomePage.tsx` frontend refactor in low-risk extraction phases
