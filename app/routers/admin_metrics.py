"""Admin analytics — aggregates from `query_logs` + `documents` for stakeholder dashboard."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_admin_metrics_viewer, require_org_owner_or_platform
from app.models import User
from app.services.admin_metrics import (
    build_admin_metrics_summary,
    list_audit_events_for_org,
    list_connectors_for_org,
    list_documents_for_org,
)
from app.services.rate_limits import enforce_admin_api_limit

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/metrics/summary")
def admin_metrics_summary(
    request: Request,
    viewer: tuple[User, UUID | None] = Depends(require_admin_metrics_viewer),
    db: Session = Depends(get_db),
) -> dict:
    """Org-scoped or global (platform owner) metrics: queries, documents, gaps, 30d chart."""
    user, organization_id = viewer
    enforce_admin_api_limit(request, user)
    return build_admin_metrics_summary(db, organization_id=organization_id)


@router.get("/connectors/{organization_id}")
def admin_list_connectors(
    request: Request,
    organization_id: UUID,
    user: User = Depends(require_org_owner_or_platform),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Connector rows for an org: type, status, last sync — for admin / stakeholder demo."""
    enforce_admin_api_limit(request, user)
    return list_connectors_for_org(db, organization_id)


@router.get("/documents/{organization_id}")
def admin_list_documents(
    request: Request,
    organization_id: UUID,
    workspace_id: UUID | None = Query(default=None),
    q: str | None = Query(default=None, description="Optional filename/source search"),
    limit: int = Query(default=200, ge=1, le=1000),
    user: User = Depends(require_org_owner_or_platform),
    db: Session = Depends(get_db),
) -> list[dict]:
    enforce_admin_api_limit(request, user)
    return list_documents_for_org(
        db,
        organization_id=organization_id,
        workspace_id=workspace_id,
        q=q,
        limit=limit,
    )


@router.get("/audit/{organization_id}")
def admin_list_audit(
    request: Request,
    organization_id: UUID,
    action: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    user: User = Depends(require_org_owner_or_platform),
    db: Session = Depends(get_db),
) -> list[dict]:
    enforce_admin_api_limit(request, user)
    return list_audit_events_for_org(
        db,
        organization_id=organization_id,
        action=action,
        limit=limit,
    )
