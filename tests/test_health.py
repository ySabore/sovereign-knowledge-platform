"""API health endpoints (no external services required for /health)."""

from __future__ import annotations

import os
import unittest

# Rate limiting middleware would slow or block rapid test requests.
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

from fastapi.testclient import TestClient

from app.main import app


class HealthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)

    def test_health_returns_ok(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get("status"), "ok")

    def test_health_live_returns_ok(self) -> None:
        response = self.client.get("/health/live")
        self.assertEqual(response.status_code, 200)

    def test_public_config_returns_json(self) -> None:
        response = self.client.get("/config/public")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("environment", body)
        self.assertIn("embedding_model", body)
        self.assertNotIn("jwt_secret", body)

    def test_health_ai_returns_shape(self) -> None:
        response = self.client.get("/health/ai")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("status", body)
        self.assertIn("checks", body)


if __name__ == "__main__":
    unittest.main()
