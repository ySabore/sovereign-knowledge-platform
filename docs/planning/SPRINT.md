# SPRINT.md — Current Execution Sprint

*Last updated: 2026-04-15 America/New_York*

## Sprint window
- **Sprint start:** 2026-04-15
- **Sprint focus window:** documentation consolidation, architecture clarity, and repo hygiene support for the current SKP codebase

## Sprint goal
Create a clean, current, trustworthy documentation set that matches the actual implementation, reduces drift, and makes the repo easier to operate, explain, and continue building.

## What is already complete in this sprint

### Architecture documentation refresh
- Updated top-level architecture to reflect the live codebase
- Updated technical decisions to match current implementation reality
- Added a full codebase map
- Added an ingestion and retrieval architecture document
- Added a targeted frontend refactor plan for `HomePage.tsx`

### Documentation truth correction
- Identified major drift between old root-level status docs and current implementation
- Confirmed current implementation is materially ahead of older MVP wording in several areas
- Established clearer distinction between:
  - product docs
  - planning docs
  - architecture docs
  - deliverable/status docs

## Active sprint objectives

### 1. Consolidate and clean documentation structure
- convert stale duplicate root docs into pointers
- define canonical source-of-truth locations
- reduce multi-file status drift
- remove or quarantine outdated/low-value documents where safe

### 2. Refresh current execution docs
- update `planning/SPRINT.md`
- update `planning/NEXT_TASK.md`
- align roadmap and status framing with current code truth
- keep `deliverables/PHASE_STATUS.md` consistent with actual implementation

### 3. Improve feature documentation clarity
- make current capabilities easier to find
- make architecture easier to follow
- separate historical artifacts from living docs
- clarify what is implemented vs what is planned

### 4. Prepare for subsequent engineering cleanup
- create a documentation base strong enough to support frontend refactor work
- reduce ambiguity before working-tree cleanup and commit organization

## In progress now
- docs consolidation and duplicate reduction
- sprint/status doc refresh
- docs index and canonical-file rules

## Next after this sprint slice
1. review remaining outdated docs for merge/remove decisions
2. refresh feature-facing docs for connectors, admin surfaces, and chat behavior
3. review `deliverables/PHASE_STATUS.md` and `README.md` for wording drift around ingestion scope
4. optionally begin implementation of the `HomePage.tsx` refactor plan

## Risks
- older docs still reference earlier product assumptions, especially around PDF-only MVP framing
- demo assets under `docs/demo/` are large and noisy, so cleanup should be selective and careful
- broad working tree changes mean documentation updates should avoid creating confusion about code status

## Definition of done for this sprint slice
- there is one obvious place to find current sprint status
- there is one obvious place to find current next task
- there is one obvious place to find product roadmap
- architecture docs reflect current implementation reality
- stale root duplicates are reduced to pointers or removed safely
- documentation is substantially easier to navigate than before
