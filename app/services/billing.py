"""
Stripe Checkout / Portal, plan resolution (with Redis cache), and org resource entitlements.

Requires `stripe` package and STRIPE_SECRET_KEY for live calls. Webhooks require STRIPE_WEBHOOK_SECRET.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.models import AuditLog, Organization, OrganizationConnector, OrganizationMembership, OrgMembershipRole, User, utcnow
from app.services.audit_actor import infer_actor_role

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

# UI list-price hints when BILLING_PLAN_PRICE_LABELS_JSON is unset. Anchored to common SMB / mid-market
# SaaS + AI search bundles (flat org/month positioning, not a binding quote). Override via env JSON.
DEFAULT_PLAN_PRICE_DISPLAY: dict[str, str] = {
    "free": "$0",
    "starter": "From $79 / month",
    "team": "From $299 / month",
    "business": "From $799 / month",
    "scale": "From $1,499 / month",
    "admin": "Custom pricing",
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


def _plan_price_display_labels() -> dict[str, str]:
    raw = (settings.billing_plan_price_labels_json or "").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return {str(k).strip().lower(): str(v).strip() for k, v in data.items() if str(v).strip()}
    except (json.JSONDecodeError, TypeError):
        logger.warning("billing_plan_price_labels_json invalid JSON; ignoring")
    return {}


def list_plan_catalog() -> list[dict[str, int | str | None]]:
    """Stable plan tiers for UI comparison tables."""
    order = ["free", "starter", "team", "business", "scale", "admin"]
    price_map: dict[str, str | None] = {
        "starter": (settings.stripe_price_starter or "").strip() or None,
        "team": (settings.stripe_price_team or "").strip() or None,
        "business": (settings.stripe_price_business or "").strip() or None,
        "scale": (settings.stripe_price_scale or "").strip() or None,
    }
    display_labels = _plan_price_display_labels()
    out: list[dict[str, int | str | None]] = []
    for plan_key in order:
        ent = PLAN_ENTITLEMENTS[plan_key]
        label = display_labels.get(plan_key) or DEFAULT_PLAN_PRICE_DISPLAY.get(plan_key) or None
        out.append(
            {
                "plan": plan_key,
                "price_id": price_map.get(plan_key),
                "price_display": label,
                "connectors_max": ent.connectors,
                "seats_max": ent.seats,
                "queries_per_month": ent.queries_per_month,
                "queries_per_day": ent.queries_per_day,
                "queries_per_hour": ent.queries_per_hour,
            }
        )
    return out


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


def write_billing_audit_event(
    db: Session,
    *,
    organization_id: UUID,
    action: str,
    target_type: str,
    actor_user: User | None = None,
    actor_role: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    resolved_role = actor_role
    if resolved_role is None and actor_user is not None:
        resolved_role = infer_actor_role(db, actor_user, organization_id=organization_id, workspace_id=None)
    db.add(
        AuditLog(
            actor_user_id=actor_user.id if actor_user is not None else None,
            actor_role=resolved_role,
            organization_id=organization_id,
            workspace_id=None,
            action=action,
            target_type=target_type,
            target_id=None,
            metadata_json=metadata or {},
        )
    )


def _is_missing_subscription_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "no such subscription" in msg or "resource_missing" in msg


def _has_non_canceled_subscription(org: Organization) -> bool:
    sub_id = (org.stripe_subscription_id or "").strip()
    if not sub_id or not stripe_configured():
        return False
    _configure_stripe()
    import stripe

    try:
        sub_obj = stripe.Subscription.retrieve(sub_id)
    except Exception as exc:
        if _is_missing_subscription_error(exc):
            logger.warning(
                "stripe subscription missing for org %s (subscription=%s)",
                getattr(org, "id", "<unknown>"),
                sub_id,
            )
            return False
        # Fail closed on transient Stripe errors to avoid creating duplicate subscriptions.
        raise RuntimeError("Could not verify existing Stripe subscription state; try again shortly.") from exc
    sub = sub_obj.to_dict() if hasattr(sub_obj, "to_dict") else dict(sub_obj)
    status = str(sub.get("status") or "").strip().lower()
    return status not in {"canceled", "incomplete_expired"}


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
    if _has_non_canceled_subscription(org):
        raise RuntimeError(
            "This organization already has an active Stripe subscription. "
            "Use the Billing portal to switch plans instead of starting a new checkout.",
        )
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

    portal_kwargs: dict[str, Any] = {
        "customer": org.stripe_customer_id,
        "return_url": return_url,
    }
    conf = (settings.stripe_billing_portal_configuration_id or "").strip()
    if conf:
        portal_kwargs["configuration"] = conf
    session = stripe.billing_portal.Session.create(**portal_kwargs)
    invalidate_plan_cache(org.id)
    return {"portal_url": session.url or ""}


def _unix_to_iso(value: Any) -> str | None:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(n, tz=timezone.utc).isoformat()


def _is_missing_customer_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "no such customer" in msg or "resource_missing" in msg


def list_invoice_history(*, org: Organization, limit: int = 20) -> list[dict[str, Any]]:
    """Return Stripe invoice rows for a customer; empty when unavailable."""
    if not stripe_configured() or not org.stripe_customer_id:
        return []
    _configure_stripe()
    import stripe

    out: list[dict[str, Any]] = []
    try:
        items = stripe.Invoice.list(customer=org.stripe_customer_id, limit=max(1, min(limit, 100)))
    except Exception as exc:
        if _is_missing_customer_error(exc):
            logger.warning(
                "stripe customer missing for org %s (customer=%s): returning empty invoice list",
                getattr(org, "id", "<unknown>"),
                org.stripe_customer_id,
            )
            return []
        raise
    for inv_obj in items.auto_paging_iter():
        inv = inv_obj.to_dict() if hasattr(inv_obj, "to_dict") else dict(inv_obj)
        period_start = None
        period_end = None
        lines = (inv.get("lines") or {}).get("data") or []
        if lines:
            first_period = (lines[0].get("period") or {}) if isinstance(lines[0], dict) else {}
            period_start = _unix_to_iso(first_period.get("start"))
            period_end = _unix_to_iso(first_period.get("end"))
        out.append(
            {
                "invoice_id": str(inv.get("id") or ""),
                "number": str(inv.get("number")) if inv.get("number") else None,
                "status": str(inv.get("status")) if inv.get("status") else None,
                "currency": str(inv.get("currency") or "usd").upper(),
                "total_cents": int(inv.get("total") or 0),
                "amount_due_cents": int(inv.get("amount_due") or 0),
                "amount_paid_cents": int(inv.get("amount_paid") or 0),
                "created_at": _unix_to_iso(inv.get("created")),
                "period_start_at": period_start,
                "period_end_at": period_end,
                "hosted_invoice_url": str(inv.get("hosted_invoice_url")) if inv.get("hosted_invoice_url") else None,
                "invoice_pdf_url": str(inv.get("invoice_pdf")) if inv.get("invoice_pdf") else None,
            }
        )
        if len(out) >= limit:
            break
    return out


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

    write_billing_audit_event(
        db,
        organization_id=org.id,
        action="billing_checkout_completed",
        target_type="billing_checkout",
        actor_role="system",
        metadata={
            "source": "stripe_webhook",
            "checkout_session_id": session.get("id"),
            "stripe_customer_id": org.stripe_customer_id,
            "stripe_subscription_id": sub_id if isinstance(sub_id, str) else None,
            "plan_after": org.plan,
        },
    )
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
    write_billing_audit_event(
        db,
        organization_id=org.id,
        action="billing_subscription_updated",
        target_type="billing_subscription",
        actor_role="system",
        metadata={
            "source": "stripe_webhook",
            "stripe_subscription_id": sub.get("id"),
            "stripe_customer_id": sub.get("customer"),
            "status": sub.get("status"),
            "plan_after": org.plan,
        },
    )
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
    write_billing_audit_event(
        db,
        organization_id=org.id,
        action="billing_subscription_deleted",
        target_type="billing_subscription",
        actor_role="system",
        metadata={
            "source": "stripe_webhook",
            "stripe_subscription_id": sub_id,
            "status": sub.get("status"),
            "plan_after": org.plan,
        },
    )
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
    write_billing_audit_event(
        db,
        organization_id=org.id,
        action="billing_invoice_payment_failed",
        target_type="billing_invoice",
        actor_role="system",
        metadata={
            "source": "stripe_webhook",
            "stripe_invoice_id": invoice.get("id"),
            "stripe_subscription_id": sub_id,
            "billing_grace_until": org.billing_grace_until.isoformat() if org.billing_grace_until else None,
        },
    )
    db.commit()
    logger.warning(
        "invoice.payment_failed for org %s — grace until %s (email notify TODO)",
        org.id,
        org.billing_grace_until,
    )
