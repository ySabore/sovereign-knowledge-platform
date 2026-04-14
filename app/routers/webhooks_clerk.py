"""Clerk webhooks — extend to sync users/orgs when you configure Svix signing secret."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.limiter import limiter

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/clerk")
@limiter.exempt
async def clerk_webhook(request: Request) -> dict:
    """
    Placeholder endpoint for Clerk → backend events (user.created, etc.).

    When integrating: verify `svix-id`, `svix-timestamp`, `svix-signature` per Clerk docs,
    then handle JSON payload. Not required for session-JWT authentication.
    """
    _ = await request.body()
    return {"status": "ignored", "detail": "Webhook handler not implemented; JWT auth works without this."}
