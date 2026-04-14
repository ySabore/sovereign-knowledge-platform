"""Rate limiting (SlowAPI). Disabled when RATE_LIMIT_ENABLED=false."""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

from app.config import settings


def _client_key(request: Request) -> str:
    # Behind reverse proxy: take first X-Forwarded-For hop (configure proxy to set this).
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return get_remote_address(request)


def _default_limits() -> list[str]:
    if not settings.rate_limit_enabled:
        return []
    # Catch-all per IP; stricter per-route decorators override on key endpoints.
    return [f"{settings.rate_limit_per_minute}/minute"]


limiter = Limiter(
    key_func=_client_key,
    default_limits=_default_limits(),
    headers_enabled=True,
)
