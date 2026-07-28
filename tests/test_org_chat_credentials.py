from __future__ import annotations

import unittest
from unittest.mock import patch
from uuid import uuid4

from app.models import Organization
from app.services.org_chat_credentials import resolve_anthropic_for_org, resolve_openai_for_org


def _org(**kwargs) -> Organization:
    return Organization(
        id=uuid4(),
        name="Test",
        slug="test",
        tenant_key="t",
        **kwargs,
    )


class ResolveOpenAIForOrgTests(unittest.TestCase):
    def test_platform_key_ignores_org_base_url(self) -> None:
        """Tenant must not redirect the platform OpenAI key to a custom endpoint."""
        org = _org(openai_api_base_url="https://attacker.example/v1")
        with (
            patch("app.services.org_chat_credentials.settings.openai_api_key", "platform-openai-key"),
            patch("app.services.org_chat_credentials.settings.openai_api_base", "https://api.openai.com/v1"),
            patch("app.services.org_chat_credentials.settings.openai_default_chat_model", "gpt-4o-mini"),
        ):
            key, _model, base = resolve_openai_for_org(org)
        self.assertEqual(key, "platform-openai-key")
        self.assertEqual(base, "https://api.openai.com/v1")

    def test_org_key_allows_custom_base_url(self) -> None:
        org = _org(
            openai_api_key_encrypted="enc",
            openai_api_base_url="https://gateway.example/v1/",
        )
        with (
            patch("app.services.org_chat_credentials.settings.openai_api_key", "platform-openai-key"),
            patch("app.services.org_chat_credentials.settings.openai_api_base", "https://api.openai.com/v1"),
            patch("app.services.org_chat_credentials.settings.openai_default_chat_model", "gpt-4o-mini"),
            patch("app.services.org_chat_credentials.decrypt_org_secret", return_value="org-openai-key"),
        ):
            key, _model, base = resolve_openai_for_org(org)
        self.assertEqual(key, "org-openai-key")
        self.assertEqual(base, "https://gateway.example/v1")

    def test_org_key_without_base_falls_back_to_platform_base(self) -> None:
        org = _org(openai_api_key_encrypted="enc")
        with (
            patch("app.services.org_chat_credentials.settings.openai_api_key", ""),
            patch("app.services.org_chat_credentials.settings.openai_api_base", "https://api.openai.com/v1"),
            patch("app.services.org_chat_credentials.settings.openai_default_chat_model", "gpt-4o-mini"),
            patch("app.services.org_chat_credentials.decrypt_org_secret", return_value="org-openai-key"),
        ):
            key, _model, base = resolve_openai_for_org(org)
        self.assertEqual(key, "org-openai-key")
        self.assertEqual(base, "https://api.openai.com/v1")


class ResolveAnthropicForOrgTests(unittest.TestCase):
    def test_platform_key_ignores_org_base_url(self) -> None:
        """Tenant must not redirect the platform Anthropic key to a custom endpoint."""
        org = _org(anthropic_api_base_url="https://attacker.example")
        with (
            patch("app.services.org_chat_credentials.settings.anthropic_api_key", "platform-anthropic-key"),
            patch("app.services.org_chat_credentials.settings.anthropic_api_base", "https://api.anthropic.com"),
            patch(
                "app.services.org_chat_credentials.settings.anthropic_default_chat_model",
                "claude-3-5-haiku-20241022",
            ),
        ):
            key, _model, base = resolve_anthropic_for_org(org)
        self.assertEqual(key, "platform-anthropic-key")
        self.assertEqual(base, "https://api.anthropic.com")

    def test_org_key_allows_custom_base_url(self) -> None:
        org = _org(
            anthropic_api_key_encrypted="enc",
            anthropic_api_base_url="https://gateway.example/",
        )
        with (
            patch("app.services.org_chat_credentials.settings.anthropic_api_key", "platform-anthropic-key"),
            patch("app.services.org_chat_credentials.settings.anthropic_api_base", "https://api.anthropic.com"),
            patch(
                "app.services.org_chat_credentials.settings.anthropic_default_chat_model",
                "claude-3-5-haiku-20241022",
            ),
            patch("app.services.org_chat_credentials.decrypt_org_secret", return_value="org-anthropic-key"),
        ):
            key, _model, base = resolve_anthropic_for_org(org)
        self.assertEqual(key, "org-anthropic-key")
        self.assertEqual(base, "https://gateway.example")


if __name__ == "__main__":
    unittest.main()
