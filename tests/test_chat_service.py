from __future__ import annotations

import unittest
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import patch

from app.services.chat import FALLBACK_NO_EVIDENCE, generate_grounded_answer
from app.services.retrieval import RetrievalHit


class ChatServiceTests(unittest.TestCase):
    def _hit(self, *, score: float = 0.91, content: str = "Grounded evidence") -> RetrievalHit:
        return RetrievalHit(
            chunk_id=uuid4(),
            document_id=uuid4(),
            document_filename="evidence.pdf",
            chunk_index=0,
            page_number=1,
            score=score,
            content=content,
        )

    def test_generate_grounded_answer_returns_exact_fallback_when_no_hits(self) -> None:
        answer, citations, _mode = generate_grounded_answer("What does the contract say?", [])

        self.assertEqual(answer, FALLBACK_NO_EVIDENCE)
        self.assertEqual(citations, [])

    def test_generate_grounded_answer_returns_exact_fallback_when_top_hit_is_below_threshold(self) -> None:
        weak_hit = self._hit(score=0.2)

        answer, citations, _mode = generate_grounded_answer("What does the contract say?", [weak_hit])

        self.assertEqual(answer, FALLBACK_NO_EVIDENCE)
        self.assertEqual(citations, [])

    def test_generate_grounded_answer_accepts_strong_hit_in_top_three_when_first_is_weak(self) -> None:
        """has_sufficient_evidence checks top 3 scores (rerank order is not always best-first)."""
        weak_first = self._hit(score=0.2, content="Irrelevant")
        strong_second = self._hit(score=0.85, content="The policy requires countersigned engagement letters.")

        with patch("app.services.chat.settings.answer_generation_provider", "extractive"):
            answer, citations, _mode = generate_grounded_answer(
                "What does the contract say?", [weak_first, strong_second]
            )

        self.assertNotEqual(answer, FALLBACK_NO_EVIDENCE)
        self.assertGreaterEqual(len(citations), 1)

    def test_generate_grounded_answer_returns_extractive_answer_with_citations(self) -> None:
        with patch("app.services.chat.settings.answer_generation_provider", "extractive"):
            answer, citations, _mode = generate_grounded_answer(
                "Summarize the policy",
                [self._hit(), self._hit(content="Second supporting passage")],
            )

        self.assertIn("Answer grounded in retrieved workspace documents for: Summarize the policy", answer)
        self.assertIn("[1] evidence.pdf, page 1: Grounded evidence", answer)
        self.assertEqual(len(citations), 2)

    def test_ollama_answers_without_inline_citations_fall_back_to_extractive_output(self) -> None:
        fake_response = SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"response": "Here is an answer with no citations."},
        )

        with patch("app.services.chat.settings.answer_generation_provider", "ollama"), patch(
            "app.services.chat.httpx.post", return_value=fake_response
        ):
            answer, citations, _mode = generate_grounded_answer("Summarize the policy", [self._hit()])

        self.assertIn("Answer grounded in retrieved workspace documents for: Summarize the policy", answer)
        self.assertIn("[1] evidence.pdf, page 1: Grounded evidence", answer)
        self.assertEqual(len(citations), 1)

    def test_ollama_exact_fallback_is_preserved(self) -> None:
        fake_response = SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"response": FALLBACK_NO_EVIDENCE},
        )

        with patch("app.services.chat.settings.answer_generation_provider", "ollama"), patch(
            "app.services.chat.httpx.post", return_value=fake_response
        ):
            answer, citations, _mode = generate_grounded_answer("Summarize the policy", [self._hit()])

        self.assertEqual(answer, FALLBACK_NO_EVIDENCE)
        self.assertEqual(citations, [])


if __name__ == "__main__":
    unittest.main()
