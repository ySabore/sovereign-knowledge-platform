from __future__ import annotations

import logging
from typing import Any

import httpx
import redis
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.limiter import limiter

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health")
@limiter.exempt
def health() -> dict[str, str]:
    """Liveness: process is up (orchestrators use this for restart decisions)."""
    return {"status": "ok"}


@router.get("/health/live")
@limiter.exempt
def health_live() -> dict[str, str]:
    """Alias for liveness probes."""
    return {"status": "ok"}


@router.get("/health/ready")
@limiter.exempt
def health_ready(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Readiness: database and Redis reachable."""
    checks: dict[str, str] = {}

    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        logger.exception("Readiness check failed: database")
        checks["database"] = f"error: {exc}"
        return {"status": "not_ready", "checks": checks}

    try:
        r = redis.Redis.from_url(settings.redis_url, socket_timeout=settings.redis_socket_timeout_seconds)
        r.ping()
        checks["redis"] = "ok"
    except Exception as exc:
        logger.exception("Readiness check failed: redis")
        checks["redis"] = f"error: {exc}"
        return {"status": "not_ready", "checks": checks}

    return {"status": "ready", "checks": checks}


@router.get("/health/ai")
@limiter.exempt
def health_ai() -> dict[str, Any]:
    """AI readiness: Ollama reachable and embedding model discoverable."""
    base = settings.embedding_ollama_base_url.rstrip("/")
    model = settings.embedding_model.strip()
    try:
        with httpx.Client(timeout=settings.ollama_http_timeout_seconds) as client:
            response = client.get(f"{base}/api/tags")
            response.raise_for_status()
            payload = response.json()
    except Exception as exc:
        logger.exception("AI readiness check failed")
        return {
            "status": "not_ready",
            "checks": {"ollama": f"error: {exc}"},
            "expected_embedding_model": model,
            "expected_embedding_dimensions": settings.embedding_dimensions,
        }

    names: list[str] = []
    for item in payload.get("models") or []:
        if isinstance(item, dict) and isinstance(item.get("name"), str):
            names.append(item["name"])
    base_name = model.split(":")[0]
    present = any(n == model or n == base_name or n.startswith(base_name + ":") for n in names)
    if not present:
        return {
            "status": "not_ready",
            "checks": {"ollama": "ok", "model": "missing"},
            "expected_embedding_model": model,
            "expected_embedding_dimensions": settings.embedding_dimensions,
            "available_models": names[:20],
        }
    return {
        "status": "ready",
        "checks": {"ollama": "ok", "model": "ok"},
        "expected_embedding_model": model,
        "expected_embedding_dimensions": settings.embedding_dimensions,
        "available_models": names[:20],
    }
