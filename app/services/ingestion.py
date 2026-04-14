from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import HTTPException, UploadFile, status
from pypdf import PdfReader

from app.config import settings
from app.services.text_cleaner import clean_text_for_ingestion

_ALLOWED_CONTENT_TYPES = {"application/pdf", "application/x-pdf"}
_WHITESPACE_RE = re.compile(r"\s+")
_MD_HEADER = re.compile(r"^\s{0,3}(#{1,6})\s+(.+?)\s*$")
_PARA_SPLIT = re.compile(r"\n\s*\n+")


@dataclass(slots=True)
class ExtractedPage:
    page_number: int
    text: str


@dataclass(slots=True)
class ChunkRecord:
    chunk_index: int
    page_number: int | None
    section_title: str | None
    content: str
    char_count: int


@dataclass(slots=True)
class StoredUpload:
    storage_path: str
    checksum_sha256: str
    size_bytes: int


def validate_pdf_upload(upload: UploadFile) -> None:
    filename = (upload.filename or "").strip()
    if not filename:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Filename is required")
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Only PDF uploads are supported")
    if upload.content_type and upload.content_type.lower() not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Unsupported content type for PDF")


async def persist_upload_file(upload: UploadFile, storage_root: Path, workspace_id: UUID) -> StoredUpload:
    validate_pdf_upload(upload)
    safe_name = Path(upload.filename or "document.pdf").name
    destination_dir = storage_root / str(workspace_id)
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination_path = destination_dir / f"{uuid4()}-{safe_name}"

    hasher = hashlib.sha256()
    size_bytes = 0
    max_bytes = settings.max_upload_size_bytes
    with destination_path.open("wb") as out:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            size_bytes += len(chunk)
            if size_bytes > max_bytes:
                out.close()
                destination_path.unlink(missing_ok=True)
                await upload.close()
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"Upload exceeds maximum size of {settings.max_upload_size_mb} MB",
                )
            out.write(chunk)
            hasher.update(chunk)

    await upload.close()
    return StoredUpload(
        storage_path=str(destination_path.resolve()),
        checksum_sha256=hasher.hexdigest(),
        size_bytes=size_bytes,
    )


def extract_pdf_pages(file_path: str) -> list[ExtractedPage]:
    reader = PdfReader(file_path)
    pages: list[ExtractedPage] = []
    for index, page in enumerate(reader.pages, start=1):
        raw_text = page.extract_text() or ""
        normalized = normalize_text(raw_text)
        cleaned = clean_text_for_ingestion(normalized, strip_html=False)
        if cleaned:
            pages.append(ExtractedPage(page_number=index, text=cleaned))
    return pages


def normalize_text(value: str) -> str:
    return _WHITESPACE_RE.sub(" ", value).strip()


def _paragraphs(text: str) -> list[str]:
    parts = _PARA_SPLIT.split(text)
    return [p.strip() for p in parts if p.strip()]


def _sliding_chunks(text: str, *, chunk_size: int, step: int) -> list[str]:
    if not text:
        return []
    out: list[str] = []
    pos = 0
    while pos < len(text):
        piece = text[pos : pos + chunk_size].strip()
        if piece:
            out.append(piece)
        pos += step
    return out


def _effective_chunk_params() -> tuple[int, int]:
    """~400–600 token targets (chars/4 heuristic) with ~10% overlap by default."""
    chunk_size = max(400, int(settings.ingestion_target_tokens * 4))
    overlap = int(chunk_size * settings.ingestion_overlap_ratio)
    overlap = max(40, min(overlap, chunk_size - 1))
    return chunk_size, overlap


def build_chunks(
    pages: list[ExtractedPage],
    *,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[ChunkRecord]:
    if chunk_size is None or chunk_overlap is None:
        chunk_size, chunk_overlap = _effective_chunk_params()
    if chunk_size <= 0:
        raise ValueError("chunk_size must be > 0")
    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be >= 0 and < chunk_size")

    step = chunk_size - chunk_overlap
    chunks: list[ChunkRecord] = []
    chunk_index = 0

    for page in pages:
        current_section: str | None = None
        paras = _paragraphs(page.text)
        buf: list[str] = []
        buf_len = 0

        def flush_buf() -> None:
            nonlocal chunk_index, buf, buf_len
            if not buf:
                return
            body = "\n\n".join(buf)
            prefix = f"Section: {current_section}\n\n" if current_section else ""
            full = (prefix + body).strip()
            chunks.append(
                ChunkRecord(
                    chunk_index=chunk_index,
                    page_number=page.page_number,
                    section_title=current_section,
                    content=full,
                    char_count=len(full),
                )
            )
            chunk_index += 1
            buf = []
            buf_len = 0

        for para in paras:
            hm = _MD_HEADER.match(para)
            if hm:
                flush_buf()
                current_section = hm.group(2).strip()
                continue

            if len(para) > chunk_size:
                flush_buf()
                for piece in _sliding_chunks(para, chunk_size=chunk_size, step=step):
                    prefix = f"Section: {current_section}\n\n" if current_section else ""
                    full = (prefix + piece).strip()
                    chunks.append(
                        ChunkRecord(
                            chunk_index=chunk_index,
                            page_number=page.page_number,
                            section_title=current_section,
                            content=full,
                            char_count=len(full),
                        )
                    )
                    chunk_index += 1
                continue

            add_len = len(para) if not buf else len(para) + 2
            if buf_len + add_len <= chunk_size:
                buf.append(para)
                buf_len += add_len
            else:
                flush_buf()
                if len(para) > chunk_size:
                    for piece in _sliding_chunks(para, chunk_size=chunk_size, step=step):
                        prefix = f"Section: {current_section}\n\n" if current_section else ""
                        full = (prefix + piece).strip()
                        chunks.append(
                            ChunkRecord(
                                chunk_index=chunk_index,
                                page_number=page.page_number,
                                section_title=current_section,
                                content=full,
                                char_count=len(full),
                            )
                        )
                        chunk_index += 1
                else:
                    buf = [para]
                    buf_len = len(para)

        flush_buf()

    return chunks


def build_chunks_from_plain_text(
    text: str,
    *,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
    page_number: int | None = None,
) -> list[ChunkRecord]:
    """Chunk arbitrary cleaned text (connector/HTML body) with the same paragraph + section strategy."""
    cleaned = clean_text_for_ingestion(text, strip_html=True)
    if not cleaned:
        return []
    page = ExtractedPage(page_number=page_number or 1, text=cleaned)
    return build_chunks([page], chunk_size=chunk_size, chunk_overlap=chunk_overlap)
