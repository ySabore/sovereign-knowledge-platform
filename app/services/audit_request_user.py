"""Optional user resolution for audit middleware (no HTTPException)."""

from __future__ import annotations

import logging

import jwt
from sqlalchemy.orm import Session

from app.auth.clerk_jwt import verify_clerk_session_jwt
from app.auth.security import decode_token
from app.config import settings
from app.models import User
from app.services.clerk_users import get_or_create_user_from_clerk

logger = logging.getLogger(__name__)


def get_user_for_audit_middleware(db: Session, authorization: str | None) -> User | None:
    """Mirror get_current_user without raising — used after successful mutating requests."""
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError:
        return None
    alg = header.get("alg")
    if alg == "HS256":
        user_id = decode_token(token)
        if user_id is None:
            return None
        user = db.get(User, user_id)
        if user is None or not user.is_active:
            return None
        return user
    if alg == "RS256":
        if not settings.clerk_enabled or not settings.clerk_issuer.strip():
            return None
        try:
            claims = verify_clerk_session_jwt(token)
        except jwt.PyJWTError as exc:
            logger.debug("audit middleware: clerk jwt not verified: %s", exc)
            return None
        try:
            return get_or_create_user_from_clerk(db, claims)
        except Exception as exc:  # noqa: BLE001
            logger.warning("audit middleware: clerk user resolution failed: %s", exc)
            return None
    return None
