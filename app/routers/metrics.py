"""Privileged analytics endpoints (org owner/platform owner)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_metrics_viewer
from app.limiter import limiter
from app.models import User
from app.services.metrics import build_metrics_summary
from app.services.rate_limits import enforce_privileged_read_api_limit

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/summary")
@limiter.exempt
def metrics_summary(
    request: Request,
    viewer: tuple[User, UUID | None] = Depends(require_metrics_viewer),
    db: Session = Depends(get_db),
) -> dict:
    """Org-scoped or global (platform owner) metrics: queries, documents, gaps, 30d chart."""
    user, organization_id = viewer
    enforce_privileged_read_api_limit(request, user)
    return build_metrics_summary(db, organization_id=organization_id)
