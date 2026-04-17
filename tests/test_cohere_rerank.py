from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.services.rag.cohere_rerank import apply_cohere_rerank, cohere_rerank_configured, resolve_cohere_api_key
from app.services.rag.types import RetrievalHit


def _hit(text: str) -> RetrievalHit:
    return RetrievalHit(
        chunk_id=uuid4(),
        document_id=uuid4(),
        document_filename="a.pdf",
        chunk_index=0,
        page_number=1,
        score=0.5,
        content=text,
    )


class CohereRerankTests(unittest.TestCase):
    def test_not_configured_returns_none(self) -> None:
        with patch("app.services.rag.cohere_rerank.settings.cohere_api_key", ""):
            self.assertFalse(cohere_rerank_configured())
            out = apply_cohere_rerank("q", [_hit("a")], top_n=3)
            self.assertIsNone(out)

    def test_maps_results_by_index(self) -> None:
        h0 = _hit("zero")
        h1 = _hit("one")
        h2 = _hit("two")
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "results": [
                {"index": 2, "relevance_score": 0.99},
                {"index": 0, "relevance_score": 0.5},
            ]
        }
        with patch("app.services.rag.cohere_rerank.settings.cohere_api_key", "test-key"):
            with patch("app.services.rag.cohere_rerank.httpx.post", return_value=mock_resp) as post:
                out = apply_cohere_rerank("query", [h0, h1, h2], top_n=2)
        self.assertIsNotNone(out)
        assert out is not None
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0].content, "two")
        self.assertEqual(out[0].score, 0.99)
        self.assertEqual(out[1].content, "zero")
        post.assert_called_once()
        call_kw = post.call_args.kwargs
        self.assertIn("json", call_kw)
        self.assertEqual(call_kw["json"]["query"], "query")

    def test_org_key_used_when_platform_empty(self) -> None:
        h0 = _hit("zero")
        org = MagicMock()
        org.cohere_api_key_encrypted = "enc-blob"
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"results": [{"index": 0, "relevance_score": 0.88}]}
        with patch("app.services.rag.cohere_rerank.settings.cohere_api_key", ""):
            with patch("app.services.rag.cohere_rerank.decrypt_org_secret", return_value="org-cohere-key"):
                with patch("app.services.rag.cohere_rerank.httpx.post", return_value=mock_resp) as post:
                    out = apply_cohere_rerank("query", [h0], top_n=1, org=org)
        self.assertIsNotNone(out)
        post.assert_called_once()
        self.assertEqual(post.call_args.kwargs["headers"]["Authorization"], "Bearer org-cohere-key")

    def test_resolve_prefers_org_over_platform(self) -> None:
        org = MagicMock()
        org.cohere_api_key_encrypted = "x"
        with patch("app.services.rag.cohere_rerank.settings.cohere_api_key", "platform-key"):
            with patch("app.services.rag.cohere_rerank.decrypt_org_secret", return_value="org-key"):
                self.assertEqual(resolve_cohere_api_key(org), "org-key")


if __name__ == "__main__":
    unittest.main()
