from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy import delete, func
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.database import get_db
from app.deps import get_current_user
from app.models import (
    AuditAction,
    Document,
    DocumentChunk,
    DocumentStatus,
    IngestionJob,
    IngestionJobStatus,
    Organization,
    OrganizationMembership,
    OrgMembershipRole,
    User,
    Workspace,
    WorkspaceMember,
    WorkspaceMemberRole,
    utcnow,
)
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
from app.services.ingestion import build_chunks, extract_pages_from_upload, persist_upload_file
from app.services.ingestion_service import IngestDocumentParams, ingest_document
from app.services.permissions import ensure_upload_permission_row
from app.services.storage import cleanup_temp_extraction_file
from app.services.rag import build_grounded_answer, resolve_top_k, run_retrieval_pipeline
from app.services.rate_limits import enforce_org_query_limits
from app.services.workspace_access import resolve_workspace_for_user

router = APIRouter(prefix="/documents", tags=["documents"])


def _source_type_for_upload_filename(filename: str) -> str:
    """Preserve legacy `pdf-upload` for PDFs; other uploads use `file-upload`."""
    name = (filename or "").strip().lower()
    return "pdf-upload" if name.endswith(".pdf") else "file-upload"


def _content_type_for_upload(filename: str, reported: str | None) -> str:
    if reported and reported.strip():
        return reported.strip()
    lower = (filename or "").lower()
    if lower.endswith(".pdf"):
        return "application/pdf"
    if lower.endswith(".docx"):
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if lower.endswith(".txt"):
        return "text/plain"
    if lower.endswith(".md") or lower.endswith(".markdown"):
        return "text/markdown"
    if lower.endswith(".html") or lower.endswith(".htm"):
        return "text/html"
    if lower.endswith(".pptx"):
        return "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    if lower.endswith(".xlsx"):
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    if lower.endswith(".xls"):
        return "application/vnd.ms-excel"
    if lower.endswith(".csv"):
        return "text/csv"
    if lower.endswith(".rtf"):
        return "application/rtf"
    return "application/octet-stream"


def _get_document_for_user(db: Session, document_id: UUID, user: User) -> Document | None:
    document = db.get(Document, document_id)
    if document is None:
        return None
    workspace = resolve_workspace_for_user(db, document.workspace_id, user)
    if workspace is None:
        return None
    return document


def _get_ingestion_job_for_user(db: Session, job_id: UUID, user: User) -> IngestionJob | None:
    job = db.get(IngestionJob, job_id)
    if job is None:
        return None
    workspace = resolve_workspace_for_user(db, job.workspace_id, user)
    if workspace is None:
        return None
    return job


def _workspace_membership_for_user(db: Session, workspace_id: UUID, user_id: UUID) -> WorkspaceMember | None:
    return (
        db.query(WorkspaceMember)
        .filter(WorkspaceMember.workspace_id == workspace_id, WorkspaceMember.user_id == user_id)
        .one_or_none()
    )


def _is_org_owner_for_workspace(db: Session, workspace: Workspace, user: User) -> bool:
    membership = (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.organization_id == workspace.organization_id,
            OrganizationMembership.user_id == user.id,
            OrganizationMembership.role == OrgMembershipRole.org_owner.value,
        )
        .one_or_none()
    )
    return membership is not None


def _require_workspace_contributor(db: Session, workspace_id: UUID, user: User) -> Workspace:
    workspace = resolve_workspace_for_user(db, workspace_id, user)
    if workspace is None:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")
    if user.is_platform_owner or _is_org_owner_for_workspace(db, workspace, user):
        return workspace
    membership = _workspace_membership_for_user(db, workspace_id, user.id)
    if membership is None:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")
    if membership.role not in {
        WorkspaceMemberRole.workspace_admin.value,
        WorkspaceMemberRole.editor.value,
    }:
        raise HTTPException(status_code=403, detail="Workspace contributor role required")
    return workspace


def _can_delete_document(db: Session, document: Document, user: User) -> bool:
    if user.is_platform_owner:
        return True
    workspace = db.get(Workspace, document.workspace_id)
    if workspace is None:
        return False
    if _is_org_owner_for_workspace(db, workspace, user):
        return True
    membership = _workspace_membership_for_user(db, document.workspace_id, user.id)
    if membership is None:
        return False
    if membership.role == WorkspaceMemberRole.workspace_admin.value:
        return True
    if membership.role == WorkspaceMemberRole.editor.value and document.created_by == user.id:
        return True
    return False


def _chunk_count_for_document(db: Session, document_id: UUID) -> int:
    return int(db.query(func.count(DocumentChunk.id)).filter(DocumentChunk.document_id == document_id).scalar() or 0)


def _document_to_status(db: Session, document: Document) -> DocumentStatusResponse:
    chunk_count = _chunk_count_for_document(db, document.id)
    job = getattr(document, "ingestion_job", None)
    if job is None and document.ingestion_job_id is not None:
        job = db.get(IngestionJob, document.ingestion_job_id)
    job_status = job.status if job is not None else None
    job_error = job.error_message if job is not None else None
    return DocumentStatusResponse(
        id=document.id,
        organization_id=document.organization_id,
        workspace_id=document.workspace_id,
        ingestion_job_id=document.ingestion_job_id,
        ingestion_job_status=job_status,
        ingestion_job_error=job_error,
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
    workspace = _require_workspace_contributor(db, workspace_id, user)

    stored = await persist_upload_file(file, settings.document_storage_root, workspace_id)
    upload_name = (file.filename or "document").strip() or "document"
    try:
        pages = extract_pages_from_upload(stored.extraction_path, upload_name)
    finally:
        cleanup_temp_extraction_file(stored.extraction_path, stored.storage_path)
    if not pages:
        raise HTTPException(
            status_code=422,
            detail="No extractable text found in this file. Check that the document is not empty or image-only.",
        )

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

    src_label = _source_type_for_upload_filename(upload_name)
    ingestion_job = IngestionJob(
        organization_id=workspace.organization_id,
        workspace_id=workspace.id,
        created_by=user.id,
        status=IngestionJobStatus.completed.value,
        source_filename=upload_name,
    )
    db.add(ingestion_job)
    db.flush()

    document = Document(
        organization_id=workspace.organization_id,
        workspace_id=workspace.id,
        ingestion_job_id=ingestion_job.id,
        created_by=user.id,
        filename=upload_name,
        content_type=_content_type_for_upload(upload_name, file.content_type),
        storage_path=stored.storage_path,
        storage_provider=stored.storage_provider,
        storage_bucket=stored.storage_bucket,
        storage_key=stored.storage_key,
        storage_size_bytes=stored.size_bytes,
        storage_etag=stored.storage_etag,
        checksum_sha256=stored.checksum_sha256,
        source_type=src_label,
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
    workspace = _require_workspace_contributor(db, workspace_id, user)

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
        .options(joinedload(Document.ingestion_job))
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
    """Delete policy: platform/org/workspace admins may delete any doc; editors may delete only their own docs."""
    document = _get_document_for_user(db, document_id, user)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    if not _can_delete_document(db, document, user):
        raise HTTPException(status_code=403, detail="Not allowed to delete this document")
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
    org = db.get(Organization, workspace.organization_id)
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
            org=org,
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
