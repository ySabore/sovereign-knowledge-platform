"""Verify Clerk session JWTs (RS256 + JWKS) for optional external authentication."""

from __future__ import annotations

import logging

import jwt
from jwt import PyJWKClient

from app.config import settings

logger = logging.getLogger(__name__)

_jwks_client: PyJWKClient | None = None


def _norm_issuer(url: str) -> str:
    """Strip whitespace and trailing slashes so env vs JWT iss compare equal."""
    return url.strip().rstrip("/")


def _jwks_url() -> str:
    issuer = _norm_issuer(settings.clerk_issuer)
    return f"{issuer}/.well-known/jwks.json"


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = PyJWKClient(_jwks_url())
    return _jwks_client


def verify_clerk_session_jwt(token: str) -> dict:
    """
    Validate a Clerk-issued session token and return claims.

    Expects `clerk_enabled` and `clerk_issuer` to be configured.
    Session tokens are RS256; `CLERK_ISSUER` must match the JWT `iss` claim (after normalizing slashes).
    Verification uses the **exact** `iss` string from the token for PyJWT issuer checks.
    """
    try:
        unverified = jwt.decode(
            token,
            options={
                "verify_signature": False,
                "verify_exp": False,
                "verify_aud": False,
            },
            algorithms=["RS256"],
        )
    except jwt.PyJWTError as exc:
        logger.debug("Clerk JWT parse (unverified) failed: %s", exc)
        raise

    token_iss = unverified.get("iss")
    if not isinstance(token_iss, str) or not token_iss.strip():
        raise jwt.InvalidTokenError("Clerk JWT is missing an iss claim")

    configured = settings.clerk_issuer.strip()
    if _norm_issuer(token_iss) != _norm_issuer(configured):
        raise jwt.InvalidTokenError(
            f"JWT iss {token_iss!r} does not match CLERK_ISSUER {configured!r}. "
            f"Set CLERK_ISSUER in the API env to the Clerk Frontend API URL (Dashboard → API keys); "
            f"it must match the iss claim (only trailing-slash differences are ignored)."
        )

    jwks = _get_jwks_client()
    signing_key = jwks.get_signing_key_from_jwt(token)

    decode_kwargs: dict = {
        "algorithms": ["RS256"],
        "issuer": token_iss,
        "options": {"verify_aud": False},
    }
    aud = settings.clerk_audience.strip() if settings.clerk_audience else ""
    if aud:
        decode_kwargs["audience"] = aud
        decode_kwargs["options"] = {"verify_aud": True}

    try:
        # Leeway avoids "token is not yet valid (iat)" when the API container clock is slightly behind Clerk / host
        # (common with Docker Desktop on Windows/WSL2).
        return jwt.decode(
            token,
            signing_key.key,
            leeway=settings.clerk_jwt_leeway_seconds,
            **decode_kwargs,
        )
    except jwt.PyJWTError as exc:
        logger.debug("Clerk JWT verification failed: %s", exc)
        raise
