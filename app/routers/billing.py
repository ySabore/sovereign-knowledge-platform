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
    BillingInvoicesResponse,
    BillingPlanResponse,
    BillingPlansCatalogResponse,
    BillingPortalRequest,
    BillingPortalResponse,
)
from app.services.billing import (
    count_org_connectors,
    count_org_members,
    create_checkout_session,
    create_portal_session,
    get_current_plan_payload,
    list_invoice_history,
    list_plan_catalog,
    normalize_plan_key,
    stripe_configured,
    write_billing_audit_event,
)
from app.services.rate_limits import get_org_query_month_usage

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
        queries_used_month=get_org_query_month_usage(org_id),
        connectors_used=count_org_connectors(db, org_id),
        seats_used=count_org_members(db, org_id),
        billing_grace_until=payload.get("billing_grace_until"),
    )


@router.get("/{org_id}/billing/plans", response_model=BillingPlansCatalogResponse)
def get_billing_plans_catalog(
    org_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> BillingPlansCatalogResponse:
    _require_org_owner(db, org_id, user)
    org = db.get(Organization, org_id)
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return BillingPlansCatalogResponse(
        organization_id=org.id,
        current_plan=normalize_plan_key(org.plan),
        plans=list_plan_catalog(),
    )


@router.get("/{org_id}/billing/invoices", response_model=BillingInvoicesResponse)
def get_billing_invoices(
    org_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> BillingInvoicesResponse:
    _require_org_owner(db, org_id, user)
    org = db.get(Organization, org_id)
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    if not stripe_configured():
        return BillingInvoicesResponse(
            organization_id=org.id,
            stripe_enabled=False,
            customer_id=org.stripe_customer_id,
            invoices=[],
        )
    try:
        invoices = list_invoice_history(org=org, limit=20)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Failed to load invoices: {exc}") from exc
    return BillingInvoicesResponse(
        organization_id=org.id,
        stripe_enabled=True,
        customer_id=org.stripe_customer_id,
        invoices=invoices,
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
    write_billing_audit_event(
        db,
        organization_id=org.id,
        action="billing_checkout_started",
        target_type="billing_checkout",
        actor_user=user,
        metadata={
            "price_id": body.price_id,
            "checkout_session_id": out.get("session_id"),
            "stripe_customer_id": org.stripe_customer_id,
        },
    )
    db.commit()
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
    write_billing_audit_event(
        db,
        organization_id=org.id,
        action="billing_portal_opened",
        target_type="billing_portal",
        actor_user=user,
        metadata={
            "return_url": body.return_url.strip(),
            "stripe_customer_id": org.stripe_customer_id,
        },
    )
    db.commit()
    return BillingPortalResponse(**out)
