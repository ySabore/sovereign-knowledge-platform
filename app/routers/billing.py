"""Stripe Checkout / Customer Portal + plan summary (org owners)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Organization, User
from app.routers.organizations import _require_org_owner
from app.schemas.billing import (
    BillingCheckoutRequest,
    BillingCheckoutResponse,
    BillingPlanResponse,
    BillingPortalRequest,
    BillingPortalResponse,
)
from app.services.billing import (
    count_org_connectors,
    count_org_members,
    create_checkout_session,
    create_portal_session,
    get_current_plan_payload,
    stripe_configured,
)

router = APIRouter(prefix="/organizations", tags=["billing"])


@router.get("/{org_id}/billing/plan", response_model=BillingPlanResponse)
def get_billing_plan(
    org_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> BillingPlanResponse:
    _require_org_owner(db, org_id, user)
    org = db.get(Organization, org_id)
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    payload = get_current_plan_payload(db, org, use_cache=True)
    return BillingPlanResponse(
        organization_id=org.id,
        plan=payload["plan"],
        subscription_status=payload.get("subscription_status"),
        connectors_max=int(payload["connectors_max"]),
        seats_max=int(payload["seats_max"]),
        queries_per_month=int(payload["queries_per_month"]),
        queries_per_day=int(payload["queries_per_day"]),
        queries_per_hour=payload.get("queries_per_hour"),
        connectors_used=count_org_connectors(db, org_id),
        seats_used=count_org_members(db, org_id),
        billing_grace_until=payload.get("billing_grace_until"),
    )


@router.post("/{org_id}/billing/checkout", response_model=BillingCheckoutResponse)
def post_billing_checkout(
    org_id: UUID,
    body: BillingCheckoutRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> BillingCheckoutResponse:
    _require_org_owner(db, org_id, user)
    if not stripe_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe billing is not configured on this server",
        )
    org = db.get(Organization, org_id)
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    try:
        out = create_checkout_session(
            db,
            org=org,
            price_id=body.price_id,
            success_url=body.success_url.strip(),
            cancel_url=body.cancel_url.strip(),
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return BillingCheckoutResponse(**out)


@router.post("/{org_id}/billing/portal", response_model=BillingPortalResponse)
def post_billing_portal(
    org_id: UUID,
    body: BillingPortalRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> BillingPortalResponse:
    _require_org_owner(db, org_id, user)
    if not stripe_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe billing is not configured on this server",
        )
    org = db.get(Organization, org_id)
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    try:
        out = create_portal_session(db, org=org, return_url=body.return_url.strip())
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return BillingPortalResponse(**out)
