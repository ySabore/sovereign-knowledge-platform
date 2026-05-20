from __future__ import annotations

import unittest
import tempfile
from pathlib import Path
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

    def test_delete_storage_uri_dispatches_s3_by_uri(self) -> None:
        with patch("app.services.storage.S3Storage") as storage_cls:
            delete_storage_uri("s3://my-bucket/a/b/file.pdf")

        storage_cls.assert_called_once_with(require_bucket=False)
        storage_cls.return_value.delete_by_uri.assert_called_once_with("s3://my-bucket/a/b/file.pdf")

    def test_delete_storage_uri_removes_local_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "document.txt"
            path.write_text("hello", encoding="utf-8")

            delete_storage_uri(str(path))

            self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()

