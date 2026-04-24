# RBAC Role Guide QA Checklist

Use this checklist to regression-test retrieval + answer quality for the ingested RBAC PDF in the Sterling & Vale workspace.

## How To Run Automated Stats

From project root:

`docker compose -f docker-compose.prod.yml --env-file .env exec -T api sh -lc "PYTHONPATH=/app python /app/scripts/eval_rbac_role_guide.py"`

The script returns JSON with:
- `pass_rate`
- `fallback_rate`
- `confidence_from_hits_counts`
- per-question answer excerpts and citations

## Manual Question Pack (30)

Expected intent is included so you can quickly score pass/fail.

1. Can Workspace Admin create workspaces?  
   - Expect: **No**; only Org Admin and above.
2. Who can create and delete workspaces?  
   - Expect: **Org Admin** (not Workspace Admin).
3. Can Org Admin delete an organization?  
   - Expect: **No**; only Platform Owner.
4. Can Platform Owner delete an organization?  
   - Expect: **Yes**.
5. Can Workspace Admin assign Platform Owner role?  
   - Expect: **No**.
6. Can Workspace Admin access platform billing settings?  
   - Expect: **No**.
7. What role is assigned workspaces only with no org/platform scope?  
   - Expect: Workspace Admin.
8. What role can create, rename, and archive workspaces in the org?  
   - Expect: Org Admin.
9. Can Workspace Admin view all users conversations?  
   - Expect: No.
10. Who can view platform overview page?  
    - Expect: Platform Owner.
11. What is default landing route for Org Admin?  
    - Expect: `/dashboard`.
12. What is default landing route for Workspace Admin?  
    - Expect: `/workspaces/{first_ws}/chat`.
13. What is default landing route for Platform Owner?  
    - Expect: `/platform/overview`.
14. Should locked nav items be hidden or shown disabled?  
    - Expect: Hidden.
15. Should permissions be enforced in API or only UI?  
    - Expect: API layer.
16. Can query return docs from outside user workspace?  
    - Expect: No (data breach risk).
17. Should app render disabled admin nav items?  
    - Expect: No; do not render inaccessible items.
18. What should audit logging middleware capture?  
    - Expect: actor/action/target context metadata.
19. Can Org Admin assign roles up to Workspace Admin?  
    - Expect: Yes.
20. Does Workspace Admin manage assigned workspaces documents/connectors/members?  
    - Expect: Yes (within assigned workspaces).
21. Can Workspace Admin see org-level data?  
    - Expect: No.
22. Can Workspace Admin manage other unassigned workspaces?  
    - Expect: No.
23. Can Editor upload and edit documents?  
    - Expect: Yes (editor/contributor scope).
24. What hierarchy mirrors Platform Owner → Org Admin → Workspace Admin?  
    - Expect: Comparable admin tier models (e.g. Confluence Site/Space Admin).
25. Is showing billing link to Workspace Admin recommended?  
    - Expect: No; hide inaccessible nav.
26. Can Workspace Admin delete organization?  
    - Expect: No.
27. Can Org Admin access platform-level infrastructure settings?  
    - Expect: No.
28. Which role should use member fullscreen chat with no sidebar chrome?  
    - Expect: Member.
29. What role can suspend organization?  
    - Expect: Platform Owner.
30. Should role tests verify unauthorized API calls return 403?  
    - Expect: Yes.

## Suggested Acceptance Thresholds

- Pass rate: **>= 90%** on this pack
- Fallback rate: **<= 5%**
- RBAC critical negatives (Q1, Q2, Q3, Q5, Q6, Q16, Q26, Q27): **100% pass**
