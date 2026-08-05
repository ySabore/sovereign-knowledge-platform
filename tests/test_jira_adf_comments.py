import unittest
from unittest.mock import patch

from app.services.nango_client import _fetch_jira, _jira_adf_to_text, _jira_body_to_text


class JiraAdfCommentTests(unittest.TestCase):
    def test_adf_to_text_extracts_nested_paragraphs(self) -> None:
        adf = {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "Hello from ADF"}],
                },
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": "Second line"}],
                },
            ],
        }
        text = _jira_adf_to_text(adf)
        self.assertIn("Hello from ADF", text)
        self.assertIn("Second line", text)

    def test_body_to_text_accepts_plain_string(self) -> None:
        self.assertEqual(_jira_body_to_text("plain comment"), "plain comment")

    def test_fetch_jira_handles_adf_comment_bodies(self) -> None:
        """Jira Cloud API v3 returns ADF dicts for comment.body; must not TypeError."""
        payload = {
            "startAt": 0,
            "total": 1,
            "issues": [
                {
                    "key": "ENG-1",
                    "fields": {
                        "summary": "Broken sync repro",
                        "updated": "2026-08-05T10:00:00.000+0000",
                        "description": {
                            "type": "doc",
                            "version": 1,
                            "content": [
                                {
                                    "type": "paragraph",
                                    "content": [{"type": "text", "text": "Issue description"}],
                                }
                            ],
                        },
                        "comment": {
                            "comments": [
                                {
                                    "body": {
                                        "type": "doc",
                                        "version": 1,
                                        "content": [
                                            {
                                                "type": "paragraph",
                                                "content": [
                                                    {"type": "text", "text": "Need a fix ASAP"}
                                                ],
                                            }
                                        ],
                                    }
                                }
                            ]
                        },
                    },
                }
            ],
        }
        with patch("app.services.nango_client.nango_proxy_get_json", return_value=payload):
            docs, cursor = _fetch_jira("conn-1", "jira", None, {})
        self.assertIsNone(cursor)
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0].external_id, "ENG-1")
        self.assertIn("Issue description", docs[0].content)
        self.assertIn("Need a fix ASAP", docs[0].content)


if __name__ == "__main__":
    unittest.main()
