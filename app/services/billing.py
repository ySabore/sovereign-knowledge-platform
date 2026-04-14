"""
Stripe Checkout / Portal, plan resolution (with Redis cache), and org resource entitlements.

Requires `stripe` package and STRIPE_SECRET_KEY for live calls. Webhooks require STRIPE_WEBHOOK_SECRET.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Organization, OrganizationConnector, OrganizationMembership, OrgMembershipRole, User, utcnow

logger = logging.getLogger(__name__)

PLAN_CACHE_PREFIX = "billing:plan:"
PLAN_CACHE_TTL_SECONDS = 3600


@dataclass(frozen=True)
class PlanEntitlements:
    connectors: int
    seats: int
    queries_per_month: int
    queries_per_day: int
    queries_per_hour: int | None


# Product spec (connectors / seats / monthly queries) + burst day/hour caps for Redis.
PLAN_ENTITLEMENTS: dict[str, PlanEntitlements] = {
    "free": PlanEntitlements(1, 1, 50, 20, 5),
    "free_trial": PlanEntitlements(1, 1, 50, 20, 5),
    "starter": PlanEntitlements(2, 3, 500, 100, 20),
    "team": PlanEntitlements(5, 25, 2000, 500, 100),
    "business": PlanEntitlements(10, 100, 10000, 2000, None),
    "scale": PlanEntitlements(20, 200, 50000, 8000, None),
    "admin": PlanEntitlements(999, 999, 999_999, 2000, 1000),
}


def normalize_plan_key(plan: str | None) -> str:
    p = (plan or "free").strip().lower()
    if p == "free_trial":
        return "free"
    if p not in PLAN_ENTITLEMENTS:
        return "free"
    return p


def get_plan_entitlements(plan: str | None) -> PlanEntitlements:
    return PLAN_ENTITLEMENTS[normalize_plan_key(plan)]


def stripe_configured() -> bool:
    key = (settings.stripe_secret_key or "").strip()
    return bool(key.startswith("sk_") or key.startswith("rk_"))


def _configure_stripe() -> None:
    import stripe

    stripe.api_key = settings.stripe_secret_key


def price_id_to_plan(price_id: str) -> str | None:
    if not price_id:
        return None
    pid = price_id.strip()
    mapping = {
        (settings.stripe_price_starter or "").strip(): "starter",
        (settings.stripe_price_team or "").strip(): "team",
        (settings.stripe_price_business or "").strip(): "business",
        (settings.stripe_price_scale or "").strip(): "scale",
    }
    return mapping.get(pid)


def invalidate_plan_cache(organization_id: UUID) -> None:
    from app.services.rate_limits import get_redis_client

    r = get_redis_client()
    if r:
        try:
            r.delete(f"{PLAN_CACHE_PREFIX}{organization_id}")
        except Exception as exc:
            logger.warning("billing cache delete failed: %s", exc)


def get_current_plan_payload(db: Session, org: Organization, *, use_cache: bool = True) -> dict[str, Any]:
    """Resolved plan + caps; may call Stripe when subscription id exists. Cached 1h in Redis."""
    from app.services.rate_limits import get_redis_client

    r = get_redis_client()
    cache_key = f"{PLAN_CACHE_PREFIX}{org.id}"
    if use_cache and r:
        try:
            raw = r.get(cache_key)
            if raw:
                return json.loads(raw)
        except Exception as exc:
            logger.warning("billing cache read failed: %s", exc)

    plan = normalize_plan_key(org.plan)
    sub_status: str | None = None
    if stripe_configured() and org.stripe_subscription_id:
        try:
            _configure_stripe()
            import stripe

            sub_obj = stripe.Subscription.retrieve(org.stripe_subscription_id)
            sub = sub_obj.to_dict() if hasattr(sub_obj, "to_dict") else dict(sub_obj)
            sub_status = sub.get("status")
            items = (sub.get("items") or {}).get("data", [])
            if items:
                price_id = items[0].get("price", {}).get("id")
                mapped = price_id_to_plan(price_id or "")
                if mapped:
                    plan = mapped
        except Exception as exc:
            logger.warning("stripe subscription fetch failed: %s", exc)

    ent = get_plan_entitlements(plan)
    payload: dict[str, Any] = {
        "plan": plan,
        "subscription_status": sub_status,
        "connectors_max": ent.connectors,
        "seats_max": ent.seats,
        "queries_per_month": ent.queries_per_month,
        "queries_per_day": ent.queries_per_day,
        "queries_per_hour": ent.queries_per_hour,
        "billing_grace_until": org.billing_grace_until.isoformat() if org.billing_grace_until else None,
    }
    if r:
        try:
            r.setex(cache_key, PLAN_CACHE_TTL_SECONDS, json.dumps(payload, default=str))
        except Exception as exc:
            logger.warning("billing cache write failed: %s", exc)
    return payload


def org_owner_email(db: Session, organization_id: UUID) -> str | None:
    row = (
        db.query(User.email)
        .join(OrganizationMembership, OrganizationMembership.user_id == User.id)
        .filter(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.role == OrgMembershipRole.org_owner.value,
        )
        .first()
    )
    return str(row[0]) if row else None


def create_checkout_session(
    db: Session,
    *,
    org: Organization,
    price_id: str,
    success_url: str,
    cancel_url: str,
) -> dict[str, str]:
    if not stripe_configured():
        raise RuntimeError("Stripe is not configured (STRIPE_SECRET_KEY)")
    email = org_owner_email(db, org.id)
    if not email:
        raise RuntimeError("No org owner email found for Checkout customer_email")
    _configure_stripe()
    import stripe

    kwargs: dict[str, Any] = {
        "mode": "subscription",
        "line_items": [{"price": price_id.strip(), "quantity": 1}],
        "success_url": success_url,
        "cancel_url": cancel_url,
        "metadata": {"organization_id": str(org.id)},
        "subscription_data": {"metadata": {"organization_id": str(org.id)}},
    }
    if org.stripe_customer_id:
        kwargs["customer"] = org.stripe_customer_id
    else:
        kwargs["customer_email"] = email

    session = stripe.checkout.Session.create(**kwargs)
    invalidate_plan_cache(org.id)
    return {"checkout_url": session.url or "", "session_id": session.id}


def create_portal_session(db: Session, *, org: Organization, return_url: str) -> dict[str, str]:
    if not stripe_configured():
        raise RuntimeError("Stripe is not configured (STRIPE_SECRET_KEY)")
    if not org.stripe_customer_id:
        raise RuntimeError("No Stripe customer yet — complete Checkout first")
    _configure_stripe()
    import stripe

    session = stripe.billing_portal.Session.create(
        customer=org.stripe_customer_id,
        return_url=return_url,
    )
    invalidate_plan_cache(org.id)
    return {"portal_url": session.url or ""}


def count_org_members(db: Session, organization_id: UUID) -> int:
    n = (
        db.query(func.count(OrganizationMembership.id))
        .filter(OrganizationMembership.organization_id == organization_id)
        .scalar()
    )
    return int(n or 0)


def count_org_connectors(db: Session, organization_id: UUID) -> int:
    n = (
        db.query(func.count(OrganizationConnector.id))
        .filter(OrganizationConnector.organization_id == organization_id)
        .scalar()
    )
    return int(n or 0)


def ensure_seat_available(db: Session, organization_id: UUID) -> None:
    from fastapi import HTTPException, status

    org = db.get(Organization, organization_id)
    if org is None:
        return
    ent = get_plan_entitlements(org.plan)
    current = count_org_members(db, organization_id)
    if current >= ent.seats:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Seat limit reached for this plan ({ent.seats} seats). Upgrade billing to add members.",
        )


def ensure_connector_slot(db: Session, organization_id: UUID) -> None:
    from fastapi import HTTPException, status

    org = db.get(Organization, organization_id)
    if org is None:
        return
    ent = get_plan_entitlements(org.plan)
    current = count_org_connectors(db, organization_id)
    if current >= ent.connectors:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Connector limit reached for this plan ({ent.connectors}). Upgrade billing to add integrations.",
        )


def register_connector_integration(db: Session, organization_id: UUID, integration_key: str) -> None:
    key = integration_key.strip()
    if not key:
        return
    existing = (
        db.query(OrganizationConnector)
        .filter(
            OrganizationConnector.organization_id == organization_id,
            OrganizationConnector.integration_key == key,
        )
        .one_or_none()
    )
    if existing:
        return
    db.add(OrganizationConnector(organization_id=organization_id, integration_key=key))


def apply_subscription_object_to_org(db: Session, org: Organization, sub: dict[str, Any]) -> None:
    """Update org plan + Stripe ids from a Subscription object."""
    sid = sub.get("id")
    if isinstance(sid, str):
        org.stripe_subscription_id = sid
    cust = sub.get("customer")
    if isinstance(cust, str):
        org.stripe_customer_id = cust

    items = (sub.get("items") or {}).get("data", [])
    if items:
        price_id = items[0].get("price", {}).get("id")
        mapped = price_id_to_plan(price_id or "")
        if mapped:
            org.plan = mapped

    status = sub.get("status")
    if status in ("canceled", "unpaid", "incomplete_expired"):
        org.plan = "free"
        org.stripe_subscription_id = None

    invalidate_plan_cache(org.id)


def handle_checkout_session_completed(db: Session, session: dict[str, Any]) -> None:
    meta = session.get("metadata") or {}
    org_id_str = meta.get("organization_id")
    if not org_id_str:
        return
    try:
        oid = UUID(str(org_id_str))
    except ValueError:
        logger.warning("checkout.session.completed: bad organization_id %s", org_id_str)
        return
    org = db.get(Organization, oid)
    if org is None:
        return

    cust = session.get("customer")
    if isinstance(cust, str):
        org.stripe_customer_id = cust

    sub_id = session.get("subscription")
    if isinstance(sub_id, str) and stripe_configured():
        _configure_stripe()
        import stripe

        sub_obj = stripe.Subscription.retrieve(sub_id)
        sub_dict = sub_obj.to_dict() if hasattr(sub_obj, "to_dict") else dict(sub_obj)
        apply_subscription_object_to_org(db, org, sub_dict)
    else:
        invalidate_plan_cache(org.id)

    db.commit()


def handle_subscription_updated(db: Session, sub: dict[str, Any]) -> None:
    sub_id = sub.get("id")
    cust_id = sub.get("customer") if isinstance(sub.get("customer"), str) else None
    org = None
    if isinstance(sub_id, str):
        org = (
            db.query(Organization)
            .filter(Organization.stripe_subscription_id == sub_id)
            .one_or_none()
        )
    if org is None and cust_id:
        org = (
            db.query(Organization)
            .filter(Organization.stripe_customer_id == cust_id)
            .one_or_none()
        )
    if org is None:
        return
    apply_subscription_object_to_org(db, org, sub)
    db.commit()


def handle_subscription_deleted(db: Session, sub: dict[str, Any]) -> None:
    sub_id = sub.get("id")
    if not isinstance(sub_id, str):
        return
    org = (
        db.query(Organization)
        .filter(Organization.stripe_subscription_id == sub_id)
        .one_or_none()
    )
    if org is None:
        return
    org.plan = "free"
    org.stripe_subscription_id = None
    org.billing_grace_until = None
    invalidate_plan_cache(org.id)
    db.commit()
    logger.info("Subscription %s canceled; org %s downgraded to free (notify user via email — TODO)", sub_id, org.id)


def handle_invoice_payment_failed(db: Session, invoice: dict[str, Any]) -> None:
    sub_id = invoice.get("subscription")
    if not isinstance(sub_id, str):
        return
    org = (
        db.query(Organization)
        .filter(Organization.stripe_subscription_id == sub_id)
        .one_or_none()
    )
    if org is None:
        return
    org.billing_grace_until = utcnow() + timedelta(days=7)
    invalidate_plan_cache(org.id)
    db.commit()
    logger.warning(
        "invoice.payment_failed for org %s — grace until %s (email notify TODO)",
        org.id,
        org.billing_grace_until,
    )
