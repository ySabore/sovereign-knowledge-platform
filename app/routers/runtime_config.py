"""Non-secret runtime configuration for operators and UIs."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.config import settings
from app.limiter import limiter

router = APIRouter(tags=["configuration"])


@router.get("/config/public")
@limiter.exempt
def get_public_config() -> dict:
    """Return safe, non-secret tunables (for SPA feature flags and operator visibility)."""
    if not settings.expose_public_config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Public configuration is disabled")
    return settings.public_config()
