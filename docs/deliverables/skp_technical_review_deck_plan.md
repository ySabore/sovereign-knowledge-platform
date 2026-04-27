# SKP Technical Review Deck Plan

Audience: engineering leadership, product stakeholders, and delivery owners

Objective: explain what the current codebase is, where it is strong, where it is risky, and the recommended cloud deployment path for pilot-to-production.

Narrative arc:

1. What SKP is today
2. How the system is structured
3. What was validated in review
4. What the highest-priority technical findings are
5. What should run where in cloud
6. What must change before production
7. How to stage rollout

Slide list:

1. Title and review scope
2. Current platform snapshot
3. Codebase and runtime architecture
4. Data and AI flow
5. Verified review findings
6. Cloud deployment target architecture
7. Component placement by environment
8. Production readiness scorecard
9. Recommended hardening backlog
10. Release path and decision ask

Source plan:

- `docs/deliverables/TECHNICAL_REVIEW_AND_CLOUD_READINESS_2026-04-24.md`
- `docs/deliverables/EXECUTIVE_SUMMARY_RETRIEVAL_AND_PLATFORM_IMPROVEMENTS_2026-04.md`
- `docs/deliverables/TECH_LEAD_SUMMARY_RETRIEVAL_AND_PLATFORM_IMPROVEMENTS_2026-04.md`
- `docs/deliverables/CUSTOMER_SUMMARY_RETRIEVAL_AND_PLATFORM_IMPROVEMENTS_2026-04.md`
- `docs/deliverables/RETRIEVAL_AND_PLATFORM_IMPROVEMENTS_2026-04.md`
- `app/main.py`
- `app/models.py`
- `app/services/rag/pipeline.py`
- `app/services/chat_sse.py`
- `app/routers/chat.py`
- `app/routers/connectors.py`
- `app/services/sync_orchestrator.py`
- `docker-compose.prod.yml`
- `frontend/src/pages/WorkspaceChatPage.tsx`

Meeting-fit guide:

- Executive stakeholders / steering updates:
  - start with `docs/deliverables/EXECUTIVE_SUMMARY_RETRIEVAL_AND_PLATFORM_IMPROVEMENTS_2026-04.md`
- Engineering leadership / architecture reviews:
  - use `docs/deliverables/TECH_LEAD_SUMMARY_RETRIEVAL_AND_PLATFORM_IMPROVEMENTS_2026-04.md`
  - then deep-dive into `docs/deliverables/TECHNICAL_REVIEW_AND_CLOUD_READINESS_2026-04-24.md`
- Customer-facing updates:
  - use `docs/deliverables/CUSTOMER_SUMMARY_RETRIEVAL_AND_PLATFORM_IMPROVEMENTS_2026-04.md`
  - keep technical internals to appendix-only if needed

Quick planning matrix:

| Audience | Meeting goal | Recommended deck length |
|---|---|---|
| Executive stakeholders / steering | Decision confidence, delivery status, risk visibility | 8-12 slides |
| Engineering leadership | Architecture quality, risk burn-down, implementation decisions | 12-20 slides |
| Customer / client update | Outcome clarity, reliability gains, roadmap confidence | 6-10 slides |

Visual system:

- clean enterprise architecture theme
- dark navy and teal accents with amber risk highlights
- minimal diagrams and status cards
- no heavy illustration dependency

Image plan:

- no image generation required
- deck will rely on native shapes, tables, and chart-like diagrams for clarity

Editability plan:

- all titles, bullets, matrices, and diagrams authored as native deck objects
- no screenshot-only slides
