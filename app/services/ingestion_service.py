"""
Unified ingestion (Component 3.3): clean → chunk → embed (batched) → replace chunks → index document.

Used by connector/sync workers and the `ingest-text` HTTP API.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Document, DocumentChunk, DocumentStatus, IngestionJob, IngestionJobStatus, utcnow
from app.services.embeddings import EmbeddingServiceError, get_embedding_client
from app.services.ingestion import build_chunks_from_plain_text
from app.services.permissions import apply_ingestion_acl, ensure_upload_permission_row


@dataclass(slots=True)
class IngestDocumentParams:
    content: str
    name: str
    source_type: str
    external_id: str
    organization_id: UUID
    workspace_id: UUID
    created_by: UUID | None = None
    metadata: dict[str, Any] | None = None
    permission_user_ids: list[UUID] | None = None
    source_url: str | None = None
    integration_connector_id: UUID | None = None


def _delete_chunks_for_document(db: Session, document_id: UUID) -> None:
    db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).delete()
    db.flush()


def ingest_document(db: Session, params: IngestDocumentParams) -> tuple[UUID, int]:
    """
    Create or update a document keyed by (organization_id, source_type, external_id),
    replace all chunks, embed, and mark indexed.
    """
    ext = params.external_id.strip()
    st = params.source_type.strip().lower()
    if not ext:
        raise ValueError("external_id is required for ingest_document")

    existing = (
        db.query(Document)
        .filter(
            Document.organization_id == params.organization_id,
            Document.source_type == st,
            Document.external_id == ext,
        )
        .one_or_none()
    )

    if existing is None:
        job = IngestionJob(
            organization_id=params.organization_id,
            workspace_id=params.workspace_id,
            created_by=params.created_by,
            status=IngestionJobStatus.processing.value,
            source_filename=params.name[:255],
        )
        db.add(job)
        db.flush()
        document = Document(
            organization_id=params.organization_id,
            workspace_id=params.workspace_id,
            ingestion_job_id=job.id,
            created_by=params.created_by,
            filename=params.name[:255],
            content_type="text/plain",
            storage_path=f"inline://{st}/{ext}",
            checksum_sha256=None,
            source_type=st,
            external_id=ext,
            source_url=params.source_url,
            ingestion_metadata=params.metadata,
            integration_connector_id=params.integration_connector_id,
            status=DocumentStatus.processing.value,
            page_count=None,
        )
        db.add(document)
        db.flush()
        job.status = IngestionJobStatus.completed.value
    else:
        document = existing
        document.filename = params.name[:255]
        document.source_url = params.source_url
        document.ingestion_metadata = params.metadata
        document.integration_connector_id = params.integration_connector_id
        document.status = DocumentStatus.processing.value
        if document.ingestion_job_id is None:
            job = IngestionJob(
                organization_id=params.organization_id,
                workspace_id=params.workspace_id,
                created_by=params.created_by,
                status=IngestionJobStatus.completed.value,
                source_filename=params.name[:255],
            )
            db.add(job)
            db.flush()
            document.ingestion_job_id = job.id

    _delete_chunks_for_document(db, document.id)

    chunks = build_chunks_from_plain_text(params.content)
    if not chunks:
        document.status = DocumentStatus.failed.value
        db.commit()
        raise ValueError("No chunks produced after cleaning; nothing to index")

    try:
        client = get_embedding_client()
        embeddings = client.embed_texts_batched([c.content for c in chunks])
    except EmbeddingServiceError:
        document.status = DocumentStatus.failed.value
        db.commit()
        raise

    for ch, emb in zip(chunks, embeddings, strict=True):
        db.add(
            DocumentChunk(
                document_id=document.id,
                chunk_index=ch.chunk_index,
                page_number=ch.page_number,
                section_title=ch.section_title,
                content=ch.content,
                token_count=ch.char_count,
                embedding_model=settings.embedding_model,
                embedding=emb,
            )
        )

    document.status = DocumentStatus.indexed.value
    document.page_count = None
    document.last_indexed_at = utcnow()

    if settings.rbac_mode.strip().lower() == "full":
        apply_ingestion_acl(
            db,
            document=document,
            source=st,
            external_id=ext,
            permission_user_ids=params.permission_user_ids,
        )
    elif st in ("pdf-upload", "upload"):
        ensure_upload_permission_row(db, document=document)

    db.commit()
    db.refresh(document)
    return document.id, len(chunks)
