"""
Org-scoped rate limits backed by Redis (compatible with Upstash: use `rediss://` in REDIS_URL).

Sliding-window-style behavior via fixed UTC day/hour buckets with INCR + TTL.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

import redis
from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Organization, User
from app.services.billing import get_plan_entitlements

logger = logging.getLogger(__name__)

_redis: redis.Redis | None = None

CONNECTOR_SYNC_PER_HOUR = max(1, int(settings.connector_sync_per_hour))
PRIVILEGED_READ_API_PER_HOUR = 1000


def _client() -> redis.Redis | None:
    global _redis
    if not settings.rate_limit_redis_enabled:
        return None
    if _redis is None:
        try:
            _redis = redis.from_url(settings.redis_url, decode_responses=True, socket_timeout=settings.redis_socket_timeout_seconds)
            _redis.ping()
        except redis.RedisError as exc:
            logger.warning("Redis rate limit unavailable: %s", exc)
            return None
    return _redis


def get_redis_client() -> redis.Redis | None:
    """Shared Redis connection for rate limits, billing plan cache, etc."""
    return _client()


def get_org_query_month_usage(organization_id: UUID) -> int:
    """Queries counted this UTC calendar month (same Redis key as enforce_org_query_limits)."""
    r = _client()
    if r is None:
        return 0
    now = datetime.now(timezone.utc)
    month_key = f"rl:{organization_id}:query:month:{now.strftime('%Y%m')}"
    try:
        raw = r.get(month_key)
        return max(0, int(raw or 0))
    except (redis.RedisError, ValueError, TypeError):
        return 0


def _ttl_until_end_of_utc_day() -> int:
    now = datetime.now(timezone.utc)
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return max(1, int((tomorrow - now).total_seconds()))


def _json_429(limit: int, remaining: int, reset_at: datetime) -> dict:
    return {
        "error": "rate_limit_exceeded",
        "limit": limit,
        "remaining": remaining,
        "resetAt": reset_at.isoformat(),
    }


def _enforce_bucket(
    r: redis.Redis,
    key: str,
    limit: int,
    ttl_seconds: int,
) -> tuple[int, datetime]:
    """INCR key; if over limit, DECR and raise. Returns (count, reset_at approximate)."""
    n = int(r.incr(key))
    if n == 1:
        r.expire(key, ttl_seconds)
    reset_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
    if n > limit:
        r.decr(key)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=_json_429(limit, 0, reset_at),
            headers={"Retry-After": str(ttl_seconds)},
        )
    return n, reset_at


def enforce_org_query_limits(request: Request, db: Session, organization_id: UUID, user: User) -> None:
    """Apply per-org plan limits for chat/search query endpoints."""
    _ = request
    if user.is_platform_owner:
        return
    org = db.get(Organization, organization_id)
    if org is None:
        return

    ent = get_plan_entitlements(org.plan)
    day_limit = ent.queries_per_day
    hour_limit = ent.queries_per_hour
    month_limit = ent.queries_per_month

    r = _client()
    if r is None:
        return

    now = datetime.now(timezone.utc)
    month_key = f"rl:{organization_id}:query:month:{now.strftime('%Y%m')}"
    day_key = f"rl:{organization_id}:query:day:{now.strftime('%Y%m%d')}"
    hour_key = f"rl:{organization_id}:query:hour:{now.strftime('%Y%m%d%H')}"

    try:
        month_incr = int(r.incr(month_key))
        if month_incr == 1:
            r.expire(month_key, 40 * 86400)
        if month_incr > month_limit:
            r.decr(month_key)
            reset_at = datetime.now(timezone.utc) + timedelta(days=32)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=_json_429(month_limit, 0, reset_at),
                headers={"Retry-After": str(86400 * 30)},
            )

        hour_incr = 0
        if hour_limit is not None:
            hour_incr = int(r.incr(hour_key))
            if hour_incr == 1:
                r.expire(hour_key, 3600)
            if hour_incr > hour_limit:
                r.decr(hour_key)
                r.decr(month_key)
                reset_at = datetime.now(timezone.utc) + timedelta(seconds=3600)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=_json_429(hour_limit, 0, reset_at),
                    headers={"Retry-After": "3600"},
                )

        day_incr = int(r.incr(day_key))
        if day_incr == 1:
            r.expire(day_key, _ttl_until_end_of_utc_day())
        if day_incr > day_limit:
            r.decr(day_key)
            if hour_limit is not None:
                r.decr(hour_key)
            r.decr(month_key)
            reset_at = datetime.now(timezone.utc) + timedelta(seconds=_ttl_until_end_of_utc_day())
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=_json_429(day_limit, 0, reset_at),
                headers={"Retry-After": str(_ttl_until_end_of_utc_day())},
            )
    except HTTPException:
        raise
    except redis.RedisError as exc:
        logger.warning("rate limit redis error: %s", exc)


def enforce_connector_sync_limit(request: Request, db: Session, organization_id: UUID, user: User) -> None:
    _ = request
    if user.is_platform_owner:
        return
    _ = db.get(Organization, organization_id)
    r = _client()
    if r is None:
        return
    now = datetime.now(timezone.utc)
    key = f"rl:{organization_id}:connector:sync:hour:{now.strftime('%Y%m%d%H')}"
    try:
        _enforce_bucket(r, key, CONNECTOR_SYNC_PER_HOUR, 3600)
    except HTTPException:
        raise
    except redis.RedisError as exc:
        logger.warning("rate limit redis error: %s", exc)


def enforce_privileged_read_api_limit(request: Request, user: User) -> None:
    """Limiter for privileged read endpoints (e.g. /metrics/summary)."""
    _ = request
    if user.is_platform_owner:
        return
    r = _client()
    if r is None:
        return
    now = datetime.now(timezone.utc)
    key = f"rl:user:{user.id}:privileged:read:hour:{now.strftime('%Y%m%d%H')}"
    try:
        _enforce_bucket(r, key, PRIVILEGED_READ_API_PER_HOUR, 3600)
    except HTTPException:
        raise
    except redis.RedisError as exc:
        logger.warning("rate limit redis error: %s", exc)
