import unittest

from app.services.rag.query_normalize import normalize_for_retrieval


class QueryNormalizeTests(unittest.TestCase):
    def test_general_chat_maps_to_workspace(self) -> None:
        self.assertEqual(
            normalize_for_retrieval("What is the purpose of General chat?"),
            "What is the purpose of General workspace?",
        )


if __name__ == "__main__":
    unittest.main()
