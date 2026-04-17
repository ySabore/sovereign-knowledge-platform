from __future__ import annotations

import unittest
from unittest.mock import patch
from uuid import uuid4

from app.models import Organization
from app.services.org_chat_credentials import ollama_base_url_for_org


class OrgOllamaBaseUrlTests(unittest.TestCase):
    def test_falls_back_to_settings_when_org_has_no_override(self) -> None:
        org = Organization(
            id=uuid4(),
            name="Test",
            slug="test",
            tenant_key="t",
        )
        with patch("app.services.org_chat_credentials.settings.answer_generation_ollama_base_url", "http://env:11434"):
            self.assertEqual(ollama_base_url_for_org(org), "http://env:11434")

    def test_strips_trailing_slash_from_org_override(self) -> None:
        org = Organization(
            id=uuid4(),
            name="Test",
            slug="test",
            tenant_key="t",
            ollama_base_url="http://gpu-host:11434/",
        )
        with patch("app.services.org_chat_credentials.settings.answer_generation_ollama_base_url", "http://env:11434"):
            self.assertEqual(ollama_base_url_for_org(org), "http://gpu-host:11434")


if __name__ == "__main__":
    unittest.main()
