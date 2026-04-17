"""Tier 3 upload extraction (email + OCR-backed types)."""

from __future__ import annotations

import tempfile
from io import BytesIO
from pathlib import Path
from email.message import EmailMessage

import pytest

from app.services.ingestion import TIER3_UPLOAD_EXTENSIONS, extract_pages_from_upload


def test_tier3_extensions_include_email_and_images() -> None:
    assert ".eml" in TIER3_UPLOAD_EXTENSIONS
    assert ".msg" in TIER3_UPLOAD_EXTENSIONS
    assert ".epub" in TIER3_UPLOAD_EXTENSIONS
    assert ".mobi" in TIER3_UPLOAD_EXTENSIONS
    assert ".png" in TIER3_UPLOAD_EXTENSIONS
    assert ".jpg" in TIER3_UPLOAD_EXTENSIONS


def test_extract_eml_plaintext() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "note.eml"
        p.write_text(
            "From: sender@example.com\n"
            "To: receiver@example.com\n"
            "Subject: Tier3 EML Test\n"
            "\n"
            "Hello from email body.\n",
            encoding="utf-8",
        )
        pages = extract_pages_from_upload(str(p), p.name)
        assert len(pages) == 1
        assert "Tier3 EML Test" in pages[0].text
        assert "Hello from email body" in pages[0].text


def test_extract_eml_with_text_attachment() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "with-attachment.eml"
        msg = EmailMessage()
        msg["From"] = "sender@example.com"
        msg["To"] = "receiver@example.com"
        msg["Subject"] = "Attachment Coverage"
        msg.set_content("Body line for message.")
        msg.add_attachment(
            "Attachment plain text content with marker SVL-ATTACH-001.",
            subtype="plain",
            filename="note.txt",
        )
        p.write_bytes(msg.as_bytes())

        pages = extract_pages_from_upload(str(p), p.name)
        assert len(pages) == 1
        txt = pages[0].text
        assert "Attachment Coverage" in txt
        assert "Attachment: note.txt" in txt
        assert "SVL-ATTACH-001" in txt


def test_extract_eml_with_docx_attachment() -> None:
    from docx import Document as DocxDocument

    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "with-docx-attachment.eml"

        doc = DocxDocument()
        doc.add_paragraph("Attachment DOCX body marker SVL-DOCX-ATT-101.")
        buf = BytesIO()
        doc.save(buf)
        docx_bytes = buf.getvalue()

        msg = EmailMessage()
        msg["From"] = "sender@example.com"
        msg["To"] = "receiver@example.com"
        msg["Subject"] = "Attachment DOCX Coverage"
        msg.set_content("Body line for message.")
        msg.add_attachment(
            docx_bytes,
            maintype="application",
            subtype="vnd.openxmlformats-officedocument.wordprocessingml.document",
            filename="note.docx",
        )
        p.write_bytes(msg.as_bytes())

        pages = extract_pages_from_upload(str(p), p.name)
        assert len(pages) == 1
        txt = pages[0].text
        assert "Attachment DOCX Coverage" in txt
        assert "Attachment: note.docx" in txt
        assert "SVL-DOCX-ATT-101" in txt


def _tesseract_available() -> bool:
    try:
        import pytesseract

        _ = pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def _ebooklib_available() -> bool:
    try:
        import ebooklib  # noqa: F401

        return True
    except Exception:
        return False


@pytest.mark.skipif(not _ebooklib_available(), reason="ebooklib not installed on test runner")
def test_extract_epub_minimal() -> None:
    from ebooklib import epub

    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "book.epub"
        book = epub.EpubBook()
        book.set_identifier("id123456")
        book.set_title("Tier3 EPUB")
        book.set_language("en")
        chapter = epub.EpubHtml(title="Intro", file_name="intro.xhtml", lang="en")
        chapter.content = "<h1>Tier3 EPUB Test</h1><p>Hello EPUB body.</p>"
        book.add_item(chapter)
        book.toc = (chapter,)
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        book.spine = ["nav", chapter]
        epub.write_epub(str(p), book)

        pages = extract_pages_from_upload(str(p), p.name)
        assert len(pages) >= 1
        joined = " ".join(pg.text for pg in pages)
        assert "Tier3 EPUB Test" in joined or "Hello EPUB body" in joined


@pytest.mark.skipif(not _tesseract_available(), reason="tesseract binary not available on test runner")
def test_extract_png_ocr_minimal() -> None:
    from PIL import Image, ImageDraw

    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "img.png"
        img = Image.new("RGB", (500, 120), color="white")
        d = ImageDraw.Draw(img)
        d.text((10, 40), "STERLING OCR", fill="black")
        img.save(p)
        pages = extract_pages_from_upload(str(p), p.name)
        assert len(pages) == 1
        assert "STERLING" in pages[0].text.upper()

