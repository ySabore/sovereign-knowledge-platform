from __future__ import annotations

import unittest
from pathlib import Path
import tempfile

import app.services.storage as storage
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

    def test_delete_storage_uri_routes_s3_by_uri_scheme(self) -> None:
        calls: list[str] = []

        class FakeS3Storage:
            def delete_by_uri(self, storage_uri: str) -> None:
                calls.append(storage_uri)

        original = storage.S3Storage
        try:
            storage.S3Storage = FakeS3Storage
            delete_storage_uri("s3://bucket/path/doc.pdf")
        finally:
            storage.S3Storage = original

        self.assertEqual(calls, ["s3://bucket/path/doc.pdf"])

    def test_delete_storage_uri_deletes_plain_local_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "doc.txt"
            path.write_text("important")
            delete_storage_uri(str(path))
            self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()

