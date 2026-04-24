import unittest

from app.services.nango_client import (
    _DRIVE_EXPORT_SPECS,
    _DRIVE_SHEET_MIME,
    _DRIVE_SLIDES_MIME,
    _drive_filename_for_binary,
    _extract_text_from_bytes_for_ingestion,
)


class NangoDriveIngestionTests(unittest.TestCase):
    def test_drive_export_specs_include_sheet_and_slides(self) -> None:
        self.assertIn(_DRIVE_SHEET_MIME, _DRIVE_EXPORT_SPECS)
        self.assertIn(_DRIVE_SLIDES_MIME, _DRIVE_EXPORT_SPECS)

    def test_drive_filename_uses_extension_when_missing(self) -> None:
        out = _drive_filename_for_binary({"name": "Quarterly Report", "fileExtension": "pdf"})
        self.assertEqual(out, "Quarterly Report.pdf")

    def test_extract_text_from_bytes_for_plain_text(self) -> None:
        raw = b"line one\nline two\n"
        text = _extract_text_from_bytes_for_ingestion(raw, "notes.txt")
        self.assertIn("line one", text)
        self.assertIn("line two", text)


if __name__ == "__main__":
    unittest.main()
