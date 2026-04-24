from __future__ import annotations

import json
import re
from collections import Counter
from statistics import mean
from uuid import UUID

from app.database import SessionLocal
from app.models import Organization, User
from app.services.chat import FALLBACK_NO_EVIDENCE, generate_grounded_answer
from app.services.chat_stream import confidence_label_from_hits
from app.services.rag.pipeline import run_retrieval_pipeline


WORKSPACE_ID = UUID("c96accae-9a3c-457b-bfab-970a7b0d2b57")
ORG_ID = UUID("44ef0de6-05ac-4dd8-bc08-30713903891f")
USER_ID = UUID("83f335d5-c038-49c2-a5f5-2e75f6f24135")


CASES = [
    {"id": "RBAC-01", "q": "Can Workspace Admin create workspaces?", "expect": r"cannot create workspaces|only org admin"},
    {"id": "RBAC-02", "q": "Who can create and delete workspaces?", "expect": r"only org admin.*create/delete workspaces|org admin.*create/delete workspaces"},
    {"id": "RBAC-03", "q": "Can Org Admin delete an organization?", "expect": r"only platform owner.*delete.*organization|org admin.*except.*deletion"},
    {"id": "RBAC-04", "q": "Can Platform Owner delete an organization?", "expect": r"platform owner.*can.*delete.*organization"},
    {"id": "RBAC-05", "q": "Can Workspace Admin assign Platform Owner role?", "expect": r"cannot assign platform owner|assign platform owner role.*✗"},
    {"id": "RBAC-06", "q": "Can Workspace Admin access platform billing settings?", "expect": r"cannot.*platform billing|no platform overview"},
    {"id": "RBAC-07", "q": "What role is assigned workspaces only with no org/platform scope?", "expect": r"workspace admin.*assigned workspaces only"},
    {"id": "RBAC-08", "q": "What role can create, rename, and archive workspaces in the org?", "expect": r"org admin.*create, rename, and archive workspaces"},
    {"id": "RBAC-09", "q": "Can Workspace Admin view all users conversations?", "expect": r"workspace admin.*✗|cannot.*all users"},
    {"id": "RBAC-10", "q": "Who can view platform overview page?", "expect": r"platform owner|only platform owner"},
    {"id": "RBAC-11", "q": "What is default landing route for Org Admin?", "expect": r"org admin.*?/dashboard|/dashboard"},
    {"id": "RBAC-12", "q": "What is default landing route for Workspace Admin?", "expect": r"/workspaces/\{first_ws\}/chat|workspace admin.*workspaces?.*chat"},
    {"id": "RBAC-13", "q": "What is default landing route for Platform Owner?", "expect": r"platform owner.*?/platform/overview|/platform/overview"},
    {"id": "RBAC-14", "q": "Should locked nav items be hidden or shown disabled?", "expect": r"hide.*locked nav items|never show locked nav items"},
    {"id": "RBAC-15", "q": "Should permissions be enforced in API or only UI?", "expect": r"api layer|not just the ui"},
    {"id": "RBAC-16", "q": "Can query return docs from outside user workspace?", "expect": r"never return documents from outside.*workspace|data breach"},
    {"id": "RBAC-17", "q": "Should app render disabled admin nav items?", "expect": r"do not render|simply don't render|hide.*no access"},
    {"id": "RBAC-18", "q": "What should audit logging middleware capture?", "expect": r"audit_events|actor_id|event_type|target_type"},
    {"id": "RBAC-19", "q": "Can Org Admin assign roles up to Workspace Admin?", "expect": r"assign roles.*up to workspace admin|invite users.*assign roles"},
    {"id": "RBAC-20", "q": "Does Workspace Admin manage assigned workspaces documents connectors members?", "expect": r"full control within.*workspaces.*documents.*connectors.*members"},
    {"id": "RBAC-21", "q": "Can Workspace Admin see org level data?", "expect": r"cannot see org-level data|no org"},
    {"id": "RBAC-22", "q": "Can Workspace Admin manage other unassigned workspaces?", "expect": r"cannot.*other workspaces.*not assigned"},
    {"id": "RBAC-23", "q": "Can Editor upload and edit documents?", "expect": r"editor|contributor|upload"},
    {"id": "RBAC-24", "q": "What hierarchy mirrors Platform Owner Org Admin Workspace Admin?", "expect": r"site admin.*space admin|confluence|notion"},
    {"id": "RBAC-25", "q": "Is showing billing link to Workspace Admin recommended?", "expect": r"confusing|hide sections.*no access"},
    {"id": "RBAC-26", "q": "Can Workspace Admin delete organization?", "expect": r"cannot.*delete.*organization|only platform owner"},
    {"id": "RBAC-27", "q": "Can Org Admin access platform-level infrastructure settings?", "expect": r"cannot.*platform-level billing|no platform"},
    {"id": "RBAC-28", "q": "Which role should be used for member fullscreen no sidebar chrome?", "expect": r"member.*\/chat|fullscreen"},
    {"id": "RBAC-29", "q": "What role can suspend organization?", "expect": r"platform owner.*suspend organization"},
    {"id": "RBAC-30", "q": "Should role test verify unauthorized API calls return 403?", "expect": r"return 403|unauthorized roles"},
]


def main() -> None:
    db = SessionLocal()
    try:
        user = db.get(User, USER_ID)
        org = db.get(Organization, ORG_ID)
        if user is None or org is None:
            raise RuntimeError("Could not resolve user/org for evaluation run")

        rows: list[dict] = []
        mode_counts: Counter[str] = Counter()
        conf_counts: Counter[str] = Counter()
        top_scores: list[float] = []
        fallbacks = 0
        passes = 0

        for case in CASES:
            q = case["q"]
            expect = case["expect"]
            hits = run_retrieval_pipeline(
                db,
                workspace_id=WORKSPACE_ID,
                organization_id=ORG_ID,
                user_id=USER_ID,
                user=user,
                query=q,
                requested_top_k=5,
                org=org,
            )
            top_score = float(hits[0].score) if hits else 0.0
            top_scores.append(top_score)

            answer, citations, mode = generate_grounded_answer(
                q,
                hits,
                answer_provider=org.preferred_chat_provider,
                org=org,
            )
            mode_counts[mode] += 1
            conf = confidence_label_from_hits(hits) if hits else "low"
            conf_counts[conf] += 1
            is_fallback = answer.strip() == FALLBACK_NO_EVIDENCE
            if is_fallback:
                fallbacks += 1

            ok = bool(re.search(expect, answer, flags=re.IGNORECASE))
            if ok:
                passes += 1

            rows.append(
                {
                    "id": case["id"],
                    "question": q,
                    "pass": ok,
                    "fallback": is_fallback,
                    "mode": mode,
                    "confidence_from_hits": conf,
                    "top_score": round(top_score, 4),
                    "citations": [f"{c.get('document_filename')} p.{c.get('page_number')}" for c in citations[:3]],
                    "answer_excerpt": " ".join(answer.split())[:300],
                }
            )

        out = {
            "cases": len(CASES),
            "pass_count": passes,
            "pass_rate": round((passes / len(CASES)) * 100, 1),
            "fallback_count": fallbacks,
            "fallback_rate": round((fallbacks / len(CASES)) * 100, 1),
            "avg_top_score": round(mean(top_scores), 4) if top_scores else 0.0,
            "mode_counts": dict(mode_counts),
            "confidence_from_hits_counts": dict(conf_counts),
            "results": rows,
        }
        print(json.dumps(out, indent=2))
    finally:
        db.close()


if __name__ == "__main__":
    main()
