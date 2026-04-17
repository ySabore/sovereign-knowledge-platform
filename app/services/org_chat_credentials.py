"""Resolve OpenAI / Anthropic credentials for an org (encrypted org keys + platform env fallbacks)."""

from __future__ import annotations

from app.config import settings
from app.models import Organization
from app.services.field_encryption import decrypt_org_secret


def ollama_base_url_for_org(org: Organization | None) -> str:
    """Base URL for Ollama /api/generate and embeddings routing (no trailing slash)."""
    if org and org.ollama_base_url and str(org.ollama_base_url).strip():
        return str(org.ollama_base_url).strip().rstrip("/")
    return settings.answer_generation_ollama_base_url.rstrip("/")


def resolve_openai_for_org(org: Organization | None) -> tuple[str, str, str]:
    """Returns (api_key, model, base_url_without_trailing_slash)."""
    key: str | None = None
    if org and org.openai_api_key_encrypted:
        try:
            key = decrypt_org_secret(org.openai_api_key_encrypted)
        except (RuntimeError, ValueError) as exc:
            raise RuntimeError(f"Could not read stored OpenAI API key: {exc}") from exc
    if not key:
        key = (settings.openai_api_key or "").strip() or None
    if not key:
        raise RuntimeError(
            "OpenAI is not configured: a platform owner can store an API key in Organization "
            "settings, or set OPENAI_API_KEY for a platform-wide fallback."
        )
    model = (
        (org.preferred_chat_model.strip() if org and org.preferred_chat_model else "")
        or settings.openai_default_chat_model
    )
    base = (
        (org.openai_api_base_url.strip() if org and org.openai_api_base_url else "")
        or settings.openai_api_base
    ).rstrip("/")
    return key, model, base


def resolve_anthropic_for_org(org: Organization | None) -> tuple[str, str, str]:
    """Returns (api_key, model, api_host_base e.g. https://api.anthropic.com)."""
    key: str | None = None
    if org and org.anthropic_api_key_encrypted:
        try:
            key = decrypt_org_secret(org.anthropic_api_key_encrypted)
        except (RuntimeError, ValueError) as exc:
            raise RuntimeError(f"Could not read stored Anthropic API key: {exc}") from exc
    if not key:
        key = (settings.anthropic_api_key or "").strip() or None
    if not key:
        raise RuntimeError(
            "Anthropic is not configured: a platform owner can store an API key in Organization "
            "settings, or set ANTHROPIC_API_KEY for a platform-wide fallback."
        )
    model = (
        (org.preferred_chat_model.strip() if org and org.preferred_chat_model else "")
        or settings.anthropic_default_chat_model
    )
    base = (
        (org.anthropic_api_base_url.strip() if org and org.anthropic_api_base_url else "")
        or settings.anthropic_api_base
    ).rstrip("/")
    return key, model, base
