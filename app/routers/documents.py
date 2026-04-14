from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy import delete, func
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import get_current_user
from app.models import AuditAction, Document, DocumentChunk, DocumentStatus, IngestionJob, IngestionJobStatus, User, Workspace, WorkspaceMember, utcnow
from app.routers.organizations import _require_workspace_admin, _write_audit_log
from app.services.resource_cleanup import unlink_document_file
from app.schemas.auth import (
    DocumentChunkPublic,
    DocumentIngestionResponse,
    DocumentStatusResponse,
    IngestTextRequest,
    IngestTextResponse,
    IngestionJobStatusResponse,
    RetrievalHitPublic,
    RetrievalQueryRequest,
    RetrievalQueryResponse,
)
from app.services.embeddings import EmbeddingServiceError, get_embedding_client
from app.services.ingestion import build_chunks, extract_pdf_pages, persist_upload_file
from app.services.ingestion_service import IngestDocumentParams, ingest_document
from app.services.permissions import ensure_upload_permission_row
from app.services.rag import build_grounded_answer, resolve_top_k, run_retrieval_pipeline
from app.services.rate_limits import enforce_org_query_limits
from app.services.workspace_access import resolve_workspace_for_user

router = APIRouter(prefix="/documents", tags=["documents"])


def _get_document_for_user(db: Session, document_id: UUID, user: User) -> Document | None:
    if user.is_platform_owner:
        return db.get(Document, document_id)
    return (
        db.query(Document)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Document.workspace_id)
        .filter(Document.id == document_id, WorkspaceMember.user_id == user.id)
        .one_or_none()
    )


def _get_ingestion_job_for_user(db: Session, job_id: UUID, user: User) -> IngestionJob | None:
    if user.is_platform_owner:
        return db.get(IngestionJob, job_id)
    return (
        db.query(IngestionJob)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == IngestionJob.workspace_id)
        .filter(IngestionJob.id == job_id, WorkspaceMember.user_id == user.id)
        .one_or_none()
    )


def _chunk_count_for_document(db: Session, document_id: UUID) -> int:
    return int(db.query(func.count(DocumentChunk.id)).filter(DocumentChunk.document_id == document_id).scalar() or 0)


def _document_to_status(db: Session, document: Document) -> DocumentStatusResponse:
    chunk_count = _chunk_count_for_document(db, document.id)
    return DocumentStatusResponse(
        id=document.id,
        organization_id=document.organization_id,
        workspace_id=document.workspace_id,
        ingestion_job_id=document.ingestion_job_id,
        filename=document.filename,
        content_type=document.content_type,
        status=document.status,
        page_count=document.page_count,
        chunk_count=chunk_count,
        checksum_sha256=document.checksum_sha256,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


@router.post("/workspaces/{workspace_id}/upload", response_model=DocumentIngestionResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    workspace_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DocumentIngestionResponse:
    workspace = resolve_workspace_for_user(db, workspace_id, user)
    if workspace is None:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")

    stored = await persist_upload_file(file, settings.document_storage_root, workspace_id)
    pages = extract_pdf_pages(stored.storage_path)
    if not pages:
        raise HTTPException(status_code=422, detail="No extractable text found in PDF")

    chunks = build_chunks(pages)
    if not chunks:
        raise HTTPException(status_code=422, detail="No chunks could be created from extracted text")

    try:
        embeddings = get_embedding_client().embed_texts_batched([chunk.content for chunk in chunks])
    except EmbeddingServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Embedding service unavailable: {exc}",
        ) from exc

    ingestion_job = IngestionJob(
        organization_id=workspace.organization_id,
        workspace_id=workspace.id,
        created_by=user.id,
        status=IngestionJobStatus.completed.value,
        source_filename=file.filename or "document.pdf",
    )
    db.add(ingestion_job)
    db.flush()

    document = Document(
        organization_id=workspace.organization_id,
        workspace_id=workspace.id,
        ingestion_job_id=ingestion_job.id,
        created_by=user.id,
        filename=file.filename or "document.pdf",
        content_type=file.content_type or "application/pdf",
        storage_path=stored.storage_path,
        checksum_sha256=stored.checksum_sha256,
        source_type="pdf-upload",
        status=DocumentStatus.indexed.value,
        page_count=len(pages),
        last_indexed_at=utcnow(),
    )
    db.add(document)
    db.flush()
    document.external_id = str(document.id)

    for chunk, embedding in zip(chunks, embeddings, strict=True):
        db.add(
            DocumentChunk(
                document_id=document.id,
                chunk_index=chunk.chunk_index,
                page_number=chunk.page_number,
                section_title=chunk.section_title,
                content=chunk.content,
                token_count=chunk.char_count,
                embedding_model=settings.embedding_model,
                embedding=embedding,
            )
        )

    ensure_upload_permission_row(db, document=document)
    db.commit()

    preview_limit = 6
    return DocumentIngestionResponse(
        ingestion_job_id=ingestion_job.id,
        document_id=document.id,
        organization_id=document.organization_id,
        workspace_id=document.workspace_id,
        filename=document.filename,
        status=document.status,
        page_count=document.page_count or 0,
        chunk_count=len(chunks),
        checksum_sha256=stored.checksum_sha256,
        storage_path=stored.storage_path,
        chunks=[
            DocumentChunkPublic(
                chunk_index=chunk.chunk_index,
                page_number=chunk.page_number,
                char_count=chunk.char_count,
                content_preview=(chunk.content[:160] + "...") if len(chunk.content) > 160 else chunk.content,
            )
            for chunk in chunks[:preview_limit]
        ],
    )


@router.post(
    "/workspaces/{workspace_id}/ingest-text",
    response_model=IngestTextResponse,
    status_code=status.HTTP_201_CREATED,
)
def ingest_text_document(
    workspace_id: UUID,
    body: IngestTextRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> IngestTextResponse:
    """
    Index raw text (e.g. from Confluence/Google Drive connectors). HTML is cleaned server-side.
    Idempotent on (organization_id, source_type, external_id): re-ingest replaces chunks.
    """
    workspace = resolve_workspace_for_user(db, workspace_id, user)
    if workspace is None:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")

    try:
        doc_id, n = ingest_document(
            db,
            IngestDocumentParams(
                content=body.content,
                name=body.name,
                source_type=body.source_type,
                external_id=body.external_id,
                organization_id=workspace.organization_id,
                workspace_id=workspace.id,
                created_by=user.id,
                metadata=body.metadata,
                permission_user_ids=body.permission_user_ids,
                source_url=body.source_url,
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except EmbeddingServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Embedding service unavailable: {exc}",
        ) from exc

    return IngestTextResponse(document_id=doc_id, chunks_created=n)


@router.get("/workspaces/{workspace_id}", response_model=list[DocumentStatusResponse])
def list_workspace_documents(
    workspace_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[DocumentStatusResponse]:
    """List indexed documents in a workspace (used by the org shell UI)."""
    workspace = resolve_workspace_for_user(db, workspace_id, user)
    if workspace is None:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")
    rows = (
        db.query(Document)
        .filter(Document.workspace_id == workspace_id)
        .order_by(Document.created_at.desc())
        .all()
    )
    return [_document_to_status(db, document) for document in rows]


@router.get("/ingestion-jobs/{job_id}", response_model=IngestionJobStatusResponse)
def get_ingestion_job_status(
    job_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> IngestionJobStatusResponse:
    job = _get_ingestion_job_for_user(db, job_id, user)
    if job is None:
        raise HTTPException(status_code=404, detail="Ingestion job not found")

    document_ids = [d.id for d in db.query(Document).filter(Document.ingestion_job_id == job_id).all()]
    return IngestionJobStatusResponse(
        id=job.id,
        organization_id=job.organization_id,
        workspace_id=job.workspace_id,
        status=job.status,
        source_filename=job.source_filename,
        error_message=job.error_message,
        created_at=job.created_at,
        updated_at=job.updated_at,
        document_ids=document_ids,
    )


@router.get("/{document_id}", response_model=DocumentStatusResponse)
def get_document_status(
    document_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DocumentStatusResponse:
    document = _get_document_for_user(db, document_id, user)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    return _document_to_status(db, document)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document_route(
    document_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    """Workspace admins (or platform owner) may remove an indexed document and its chunks; PDF file is deleted from storage when present."""
    document = _get_document_for_user(db, document_id, user)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    _require_workspace_admin(db, document.workspace_id, user)
    _write_audit_log(
        db,
        actor_user_id=user.id,
        action=AuditAction.document_deleted.value,
        target_type="document",
        target_id=document.id,
        organization_id=document.organization_id,
        workspace_id=document.workspace_id,
        metadata={"filename": document.filename},
    )
    unlink_document_file(db, document.id)
    db.execute(delete(Document).where(Document.id == document_id))
    db.commit()


@router.post("/workspaces/{workspace_id}/search", response_model=RetrievalQueryResponse)
def search_workspace_documents(
    request: Request,
    workspace_id: UUID,
    body: RetrievalQueryRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RetrievalQueryResponse:
    workspace = resolve_workspace_for_user(db, workspace_id, user)
    if workspace is None:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")

    enforce_org_query_limits(request, db, workspace.organization_id, user)

    query = body.query.strip()
    try:
        top_k = resolve_top_k(body.top_k)
        hits = run_retrieval_pipeline(
            db,
            workspace_id=workspace_id,
            organization_id=workspace.organization_id,
            user_id=user.id,
            user=user,
            query=query,
            requested_top_k=top_k,
        )
    except EmbeddingServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Embedding service unavailable: {exc}",
        ) from exc
    return RetrievalQueryResponse(
        workspace_id=workspace_id,
        query=query,
        top_k=top_k,
        embedding_model=settings.embedding_model,
        answer=build_grounded_answer(query, hits),
        hits=[
            RetrievalHitPublic(
                chunk_id=hit.chunk_id,
                document_id=hit.document_id,
                document_filename=hit.document_filename,
                chunk_index=hit.chunk_index,
                page_number=hit.page_number,
                score=hit.score,
                content=hit.content,
            )
            for hit in hits
        ],
    )
