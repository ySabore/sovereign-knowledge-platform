"""Stripe webhooks — subscription lifecycle and invoice events."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.limiter import limiter
from app.services.billing import (
    handle_checkout_session_completed,
    handle_invoice_payment_failed,
    handle_subscription_deleted,
    handle_subscription_updated,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/stripe")
@limiter.exempt
async def stripe_webhook(request: Request, db: Session = Depends(get_db)) -> dict[str, bool]:
    secret = (settings.stripe_webhook_secret or "").strip()
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe webhooks are not configured (STRIPE_WEBHOOK_SECRET)",
        )

    payload = await request.body()
    sig = request.headers.get("stripe-signature")
    if not sig:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Stripe-Signature")

    import stripe

    try:
        event = stripe.Webhook.construct_event(payload, sig, secret)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid payload") from exc
    except Exception as exc:
        # stripe raises SignatureVerificationError (module path varies by stripe-python version)
        name = type(exc).__name__
        if "Signature" not in name and "signature" not in str(exc).lower():
            raise
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid signature") from exc

    etype = event.get("type")
    obj = event.get("data", {}).get("object") or {}

    try:
        if etype == "checkout.session.completed":
            handle_checkout_session_completed(db, obj)
        elif etype == "customer.subscription.updated":
            handle_subscription_updated(db, obj)
        elif etype == "customer.subscription.deleted":
            handle_subscription_deleted(db, obj)
        elif etype == "invoice.payment_failed":
            handle_invoice_payment_failed(db, obj)
        else:
            logger.debug("stripe webhook ignored: %s", etype)
    except HTTPException:
        raise
    except Exception:
        logger.exception("stripe webhook handler failed for %s", etype)
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Webhook handler error") from None

    return {"received": True}
