from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from app.services.storage import delete_storage_uri, parse_storage_uri


class StorageUriParseTests(unittest.TestCase):
    def test_parse_s3_uri(self) -> None:
        parsed = parse_storage_uri("s3://my-bucket/a/b/file.pdf")
        self.assertEqual(parsed.provider, "s3")
        self.assertEqual(parsed.bucket, "my-bucket")
        self.assertEqual(parsed.key, "a/b/file.pdf")

    def test_parse_local_plain_path(self) -> None:
        parsed = parse_storage_uri("C:/data/documents/abc.pdf")
        self.assertEqual(parsed.provider, "local")
        self.assertIsNone(parsed.bucket)
        self.assertEqual(parsed.key, "C:/data/documents/abc.pdf")

    def test_parse_empty_uri(self) -> None:
        parsed = parse_storage_uri("")
        self.assertIsNone(parsed.provider)
        self.assertIsNone(parsed.bucket)
        self.assertIsNone(parsed.key)

    def test_parse_inline_uri_keeps_inline_provider(self) -> None:
        parsed = parse_storage_uri("inline://google-drive/external-123")
        self.assertEqual(parsed.provider, "inline")
        self.assertIsNone(parsed.bucket)
        self.assertEqual(parsed.key, "google-drive/external-123")

    def test_delete_storage_uri_deletes_local_path_without_current_backend(self) -> None:
        with TemporaryDirectory() as tmp:
            local_file = Path(tmp) / "artifact.txt"
            local_file.write_text("secret", encoding="utf-8")

            delete_storage_uri(str(local_file))

            self.assertFalse(local_file.exists())

    def test_delete_storage_uri_ignores_inline_artifacts(self) -> None:
        with patch("app.services.storage.S3Storage") as s3_storage:
            delete_storage_uri("inline://google-drive/external-123")

        s3_storage.assert_not_called()


if __name__ == "__main__":
    unittest.main()

