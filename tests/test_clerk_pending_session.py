"""Clerk session JWTs with sts=pending must not authenticate API access."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import jwt

from app.auth.clerk_jwt import verify_clerk_session_jwt


class ClerkPendingSessionTests(unittest.TestCase):
    def _run_verify(self, unverified: dict, verified: dict):
        token = "header.payload.sig"
        with (
            patch("app.auth.clerk_jwt.settings") as settings,
            patch("app.auth.clerk_jwt.jwt.decode") as decode,
            patch("app.auth.clerk_jwt._get_jwks_client") as get_jwks,
        ):
            settings.clerk_issuer = "https://clerk.example.com"
            settings.clerk_audience = ""
            settings.clerk_jwt_leeway_seconds = 5
            get_jwks.return_value.get_signing_key_from_jwt.return_value = MagicMock(key="public-key")
            # First decode is unverified iss peek; second is signature-verified claims.
            decode.side_effect = [unverified, verified]
            return verify_clerk_session_jwt(token)

    def test_pending_sts_is_rejected(self) -> None:
        claims = {
            "iss": "https://clerk.example.com",
            "sub": "user_abc",
            "sts": "pending",
        }
        with self.assertRaises(jwt.InvalidTokenError) as ctx:
            self._run_verify(claims, claims)
        self.assertIn("pending", str(ctx.exception).lower())

    def test_active_or_missing_sts_is_accepted(self) -> None:
        claims_active = {
            "iss": "https://clerk.example.com",
            "sub": "user_abc",
            "sts": "active",
        }
        claims_legacy = {
            "iss": "https://clerk.example.com",
            "sub": "user_abc",
        }
        self.assertEqual(self._run_verify(claims_active, claims_active)["sts"], "active")
        self.assertNotIn("sts", self._run_verify(claims_legacy, claims_legacy))


if __name__ == "__main__":
    unittest.main()
