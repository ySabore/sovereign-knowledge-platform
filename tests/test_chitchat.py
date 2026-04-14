from __future__ import annotations

import unittest

from app.services.chitchat import CHITCHAT_REPLY, is_low_intent_chitchat


class ChitchatTests(unittest.TestCase):
    def test_greetings_match(self) -> None:
        for q in (
            "Hello",
            "hello!",
            "Hi",
            "Hi there",
            "Hey",
            "Good morning",
            "Good afternoon team",
            "How are you",
            "Thanks",
            "Thank you",
            "Thx",
            "Bye",
            "Okay",
        ):
            with self.subTest(q=q):
                self.assertTrue(is_low_intent_chitchat(q), msg=q)

    def test_reply_constant_non_empty(self) -> None:
        self.assertGreater(len(CHITCHAT_REPLY), 20)

    def test_real_questions_not_chitchat(self) -> None:
        for q in (
            "Hello, what is the billing policy?",
            "Hi I need help with matter 123",
            "Thanks and can you also summarize the NDA",
            "Good morning please find the retainer rules",
            "Hey how do I file a time entry",
        ):
            with self.subTest(q=q):
                self.assertFalse(is_low_intent_chitchat(q), msg=q)

    def test_long_or_numeric_not_chitchat(self) -> None:
        self.assertFalse(is_low_intent_chitchat("Hi " * 30))
        self.assertFalse(is_low_intent_chitchat("Hello version 2"))


if __name__ == "__main__":
    unittest.main()
