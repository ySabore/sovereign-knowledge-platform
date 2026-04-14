"""Fernet encryption for org-scoped secrets (e.g. cloud LLM API keys)."""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings


def fernet_or_none() -> Fernet | None:
    raw = (settings.org_llm_fernet_key or "").strip()
    if not raw:
        return None
    try:
        return Fernet(raw.encode("ascii"))
    except ValueError as exc:
        raise ValueError(
            "ORG_LLM_FERNET_KEY must be a Fernet key from Fernet.generate_key().decode()"
        ) from exc


def encrypt_org_secret(plaintext: str | None) -> str | None:
    if plaintext is None or not str(plaintext).strip():
        return None
    f = fernet_or_none()
    if f is None:
        raise RuntimeError("ORG_LLM_FERNET_KEY is not set; cannot store org API keys")
    return f.encrypt(str(plaintext).strip().encode("utf-8")).decode("ascii")


def decrypt_org_secret(token: str | None) -> str | None:
    if not token or not str(token).strip():
        return None
    f = fernet_or_none()
    if f is None:
        raise RuntimeError("ORG_LLM_FERNET_KEY is not set; cannot decrypt org API keys")
    try:
        return f.decrypt(str(token).strip().encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Could not decrypt org secret (wrong ORG_LLM_FERNET_KEY?)") from exc
