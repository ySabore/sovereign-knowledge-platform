"""Map Clerk identities to internal `User` rows (link-by-email on first sign-in)."""

from __future__ import annotations

import logging
import secrets

from sqlalchemy.orm import Session

from app.auth.security import hash_password
from app.models import User

logger = logging.getLogger(__name__)


def _extract_email(claims: dict) -> str | None:
    """Resolve primary email from Clerk session claims (shape varies by Dashboard token template)."""
    email = claims.get("email")
    if isinstance(email, str) and email.strip() and "@" in email:
        return email.strip().lower()
    # Clerk docs often use these names in "Customize session token" examples
    primary_email = claims.get("primaryEmail")
    if isinstance(primary_email, str) and primary_email.strip() and "@" in primary_email:
        return primary_email.strip().lower()
    # Template may serialize primary_email_address as an object or a string
    pea = claims.get("primary_email_address")
    if isinstance(pea, str) and "@" in pea:
        return pea.strip().lower()
    if isinstance(pea, dict):
        addr = pea.get("email_address")
        if isinstance(addr, str) and addr.strip():
            return addr.strip().lower()
    for key in ("email_address", "primary_email"):
        v = claims.get(key)
        if isinstance(v, str) and v.strip() and "@" in v:
            return v.strip().lower()
    raw = claims.get("email_addresses")
    if isinstance(raw, list) and raw:
        first = raw[0]
        if isinstance(first, dict):
            addr = first.get("email_address")
            if isinstance(addr, str) and addr.strip():
                return addr.strip().lower()
    return None


def get_or_create_user_from_clerk(db: Session, claims: dict) -> User | None:
    """
    Resolve Clerk `sub` to a user. Links an existing email/password user on first Clerk login.

    Requires an `email` claim in the session JWT (enable in Clerk Dashboard → Sessions → Customize session token).
    """
    sub = claims.get("sub")
    if not isinstance(sub, str) or not sub.strip():
        return None

    user = db.query(User).filter(User.clerk_user_id == sub).one_or_none()
    if user is not None:
        return user if user.is_active else None

    email = _extract_email(claims)
    if not email:
        logger.warning(
            "Clerk session JWT has no usable email claim; cannot provision user. JWT keys: %s",
            sorted(claims.keys()),
        )
        return None

    existing = db.query(User).filter(User.email == email).one_or_none()
    if existing is not None:
        if existing.clerk_user_id and existing.clerk_user_id != sub:
            return None
        existing.clerk_user_id = sub
        db.commit()
        db.refresh(existing)
        return existing if existing.is_active else None

    full_name = claims.get("name")
    if full_name is not None and not isinstance(full_name, str):
        full_name = None

    placeholder_pw = hash_password(secrets.token_hex(32))
    user = User(
        email=email,
        clerk_user_id=sub,
        password_hash=placeholder_pw,
        full_name=full_name,
        is_active=True,
        is_platform_owner=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
