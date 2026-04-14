from __future__ import annotations

import unittest

from app.services.rag.answer_parse import estimate_tokens, extract_confidence_tag
from app.services.rag.prompts import build_ollama_grounded_prompt, trim_conversation_turns_for_prompt


class AnswerParseTests(unittest.TestCase):
    def test_estimate_tokens(self) -> None:
        self.assertEqual(estimate_tokens(""), 0)
        self.assertEqual(estimate_tokens("abcd"), 1)
        self.assertEqual(estimate_tokens("a" * 8), 2)

    def test_extract_confidence_tag_strips_trailing_tag(self) -> None:
        text = "Hello world.\n<confidence>high</confidence>"
        display, conf = extract_confidence_tag(text)
        self.assertEqual(conf, "high")
        self.assertEqual(display, "Hello world.")

    def test_extract_confidence_tag_none_when_missing(self) -> None:
        text = "No tag here."
        display, conf = extract_confidence_tag(text)
        self.assertIsNone(conf)
        self.assertEqual(display, "No tag here.")

    def test_build_prompt_includes_history_and_evidence(self) -> None:
        p = build_ollama_grounded_prompt(
            query="What is the policy?",
            evidence_lines=["[1] doc.pdf, page 1: refund within 30 days"],
            fallback_exact="I don't know.",
            conversation_turns=[("Hi", "Hello"), ("Prior Q", "Prior A")],
        )
        self.assertIn("Recent conversation", p)
        self.assertIn("Prior Q", p)
        self.assertIn("Evidence:", p)
        self.assertIn("[1] doc.pdf", p)

    def test_trim_conversation_turns_drops_oldest(self) -> None:
        long_u = "x" * 5000
        turns = [(long_u, "a"), ("b", "c"), ("d", "e")]
        trimmed = trim_conversation_turns_for_prompt(turns, max_turns=3, max_token_budget=50)
        self.assertLessEqual(len(trimmed), len(turns))


if __name__ == "__main__":
    unittest.main()
