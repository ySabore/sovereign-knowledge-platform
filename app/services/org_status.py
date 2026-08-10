"""Organization lifecycle status guards (active vs suspended)."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import Organization, OrgStatus, User


def ensure_organization_not_suspended(db: Session, org_id: UUID, user: User) -> Organization | None:
    """
    Block non-platform users from using a suspended organization.

    Platform owners retain access for support/recovery. Returns the org row when found,
    or None when the organization does not exist (callers handle 404).
    """
    org = db.get(Organization, org_id)
    if org is None:
        return None
    if user.is_platform_owner:
        return org
    if (org.status or "").strip().lower() == OrgStatus.suspended.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization is suspended",
        )
    return org
