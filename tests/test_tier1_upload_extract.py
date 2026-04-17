"""Tier 1 upload text extraction (non-PDF paths)."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from app.services.ingestion import TIER1_UPLOAD_EXTENSIONS, extract_pages_from_upload


def test_tier1_extensions_cover_tier1_set() -> None:
    assert ".pdf" in TIER1_UPLOAD_EXTENSIONS
    assert ".docx" in TIER1_UPLOAD_EXTENSIONS
    assert ".markdown" in TIER1_UPLOAD_EXTENSIONS


def test_extract_plain_text_and_html() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "note.txt"
        p.write_text("Hello world.\n\nSecond paragraph.", encoding="utf-8")
        pages = extract_pages_from_upload(str(p), "note.txt")
        assert len(pages) == 1
        assert "Hello world" in pages[0].text

        h = Path(tmp) / "page.html"
        h.write_text("<html><body><p>Hi</p></body></html>", encoding="utf-8")
        hp = extract_pages_from_upload(str(h), "page.html")
        assert len(hp) == 1
        assert "Hi" in hp[0].text


def test_extract_rejects_unknown_extension() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "x.bin"
        p.write_bytes(b"abc")
        assert extract_pages_from_upload(str(p), "x.bin") == []


def test_extract_docx_minimal() -> None:
    from docx import Document as DocxDocument

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "w.docx"
        doc = DocxDocument()
        doc.add_paragraph("Tier one docx body.")
        doc.save(path)
        pages = extract_pages_from_upload(str(path), "w.docx")
        assert len(pages) == 1
        assert "Tier one docx" in pages[0].text
