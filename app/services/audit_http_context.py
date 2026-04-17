"""Resolve org/workspace scope from HTTP paths for audit middleware."""

from __future__ import annotations

import re
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import ChatSession, Workspace

_UUID_RE = r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})"


def resolve_audit_org_workspace(db: Session, path: str) -> tuple[UUID | None, UUID | None]:
    """
    Best-effort (org_id, workspace_id) for tying HTTP mutations to an organization audit stream.
    Returns (None, None) when scope cannot be determined (middleware will skip insert).
    """
    p = path.split("?", 1)[0]

    m = re.search(rf"/organizations/{_UUID_RE}(?:/|$)", p)
    if m:
        return UUID(m.group(1)), None

    m = re.search(rf"/workspaces/org/{_UUID_RE}(?:/|$)", p)
    if m:
        return UUID(m.group(1)), None

    m = re.search(rf"/workspaces/{_UUID_RE}(?:/|$)", p)
    if m:
        wid = UUID(m.group(1))
        ws = db.get(Workspace, wid)
        if ws is not None:
            return ws.organization_id, wid
        return None, None

    m = re.search(rf"/documents/workspaces/{_UUID_RE}(?:/|$)", p)
    if m:
        wid = UUID(m.group(1))
        ws = db.get(Workspace, wid)
        if ws is not None:
            return ws.organization_id, wid
        return None, wid

    m = re.search(rf"/chat/workspaces/{_UUID_RE}(?:/|$)", p)
    if m:
        wid = UUID(m.group(1))
        ws = db.get(Workspace, wid)
        if ws is not None:
            return ws.organization_id, wid
        return None, wid

    m = re.search(rf"/chat/sessions/{_UUID_RE}(?:/|$)", p)
    if m:
        sid = UUID(m.group(1))
        sess = db.get(ChatSession, sid)
        if sess is not None:
            return sess.organization_id, sess.workspace_id
        return None, None

    m = re.search(rf"/connectors/organization/{_UUID_RE}(?:/|$)", p)
    if m:
        return UUID(m.group(1)), None

    return None, None
