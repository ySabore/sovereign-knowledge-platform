from __future__ import annotations

import unittest
from unittest.mock import patch
from uuid import uuid4

from app.services.rag.heuristic_rerank import apply_heuristic_rerank, lexical_overlap_score
from app.services.rag.types import RetrievalHit


def _hit(content: str, score: float) -> RetrievalHit:
    return RetrievalHit(
        chunk_id=uuid4(),
        document_id=uuid4(),
        document_filename="doc.pdf",
        chunk_index=0,
        page_number=1,
        score=score,
        content=content,
    )


class HeuristicRerankTests(unittest.TestCase):
    def test_lexical_overlap_is_zero_for_unrelated_text(self) -> None:
        self.assertEqual(lexical_overlap_score("quantum physics", "the contract termination clause"), 0.0)

    def test_lexical_overlap_detects_shared_terms(self) -> None:
        s = lexical_overlap_score("payment schedule and deadlines", "payment must be made on schedule")
        self.assertGreater(s, 0.2)

    def test_none_mode_truncates_without_resorting(self) -> None:
        h1 = _hit("alpha beta", 0.9)
        h2 = _hit("gamma delta", 0.5)
        with patch("app.services.rag.heuristic_rerank.settings.rag_rerank_mode", "none"):
            out = apply_heuristic_rerank("payment schedule", [h1, h2], output_top_k=1)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].content, "alpha beta")

    def test_lexical_blend_prefers_keyword_over_pure_semantic_order(self) -> None:
        # High semantic but irrelevant text vs lower semantic but query-relevant.
        irrelevant = _hit("lorem ipsum dolor sit amet", 0.95)
        relevant = _hit("payment schedule is due on the first of each month", 0.55)
        with patch("app.services.rag.heuristic_rerank.settings.rag_rerank_mode", "lexical_blend"), patch(
            "app.services.rag.heuristic_rerank.settings.rag_lexical_weight", 0.85
        ):
            out = apply_heuristic_rerank("payment schedule", [irrelevant, relevant], output_top_k=2)
        self.assertEqual(out[0].content, relevant.content)

    def test_mmr_promotes_diverse_chunks(self) -> None:
        dup_a = _hit("the refund policy applies to all users who request refund", 0.92)
        dup_b = _hit("the refund policy applies to all users who request refund within 30 days", 0.91)
        other = _hit("shipping costs are non-refundable unless damaged", 0.65)
        with patch("app.services.rag.heuristic_rerank.settings.rag_rerank_mode", "lexical_mmr"), patch(
            "app.services.rag.heuristic_rerank.settings.rag_mmr_lambda", 0.6
        ):
            out = apply_heuristic_rerank("refund policy shipping", [dup_a, dup_b, other], output_top_k=2)
        texts = {x.content for x in out}
        self.assertIn(other.content, texts)


if __name__ == "__main__":
    unittest.main()
