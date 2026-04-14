from __future__ import annotations

import unittest

from app.services.text_cleaner import clean_text_for_ingestion, strip_html_tags


class TextCleanerTests(unittest.TestCase):
    def test_strip_html_basic(self) -> None:
        self.assertEqual(strip_html_tags("<p>Hello</p>").strip(), "Hello")

    def test_clean_ingestion_preserves_paragraph_breaks(self) -> None:
        self.assertEqual(clean_text_for_ingestion("  a \n\n  b  "), "a\n\nb")


if __name__ == "__main__":
    unittest.main()
