"""
Index demo PDFs + sample RAG questions for the Sterling & Vale law-firm seed org.

Uses the same pipeline as POST /documents/workspaces/{id}/upload: extract text, chunk,
embed via Ollama, persist documents + chunks. Requires a running embedding service
(EMBEDDING_OLLAMA_BASE_URL / same as API container → ollama).

Also inserts QueryLog rows and ChatMessage pairs so the demo has ready-made questions.

Prerequisites:
  - scripts/seed_law_firm.py has been run (org sterling-vale-llp exists)
  - Ollama reachable with EMBEDDING_MODEL pulled (e.g. nomic-embed-text)

Usage:
  SEED_LAW_FIRM_RAG=true python scripts/seed_law_firm_rag.py

Docker (after API image rebuild includes fpdf2):
  docker compose exec -e SEED_LAW_FIRM_RAG=true api python scripts/seed_law_firm_rag.py
"""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path
from uuid import UUID, uuid4

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))
except ImportError:
    pass

_scripts = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _scripts)
from law_firm_demo_pdf_catalog import DEMO_PDFS, write_demo_pdf
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models import (
    ChatMessage,
    ChatMessageRole,
    ChatSession,
    Document,
    DocumentChunk,
    DocumentPermission,
    DocumentStatus,
    IngestionJob,
    IngestionJobStatus,
    Organization,
    QueryLog,
    User,
    Workspace,
    utcnow,
)
from app.services.embeddings import EmbeddingServiceError, get_embedding_client
from app.services.ingestion import build_chunks, extract_pdf_pages


def _ensure_upload_permission_row(db: Session, *, document: Document) -> None:
    """Mirror app.services.permissions.ensure_upload_permission_row (avoid circular imports)."""
    if settings.rbac_mode.strip().lower() != "full":
        return
    exists = (
        db.query(DocumentPermission)
        .filter(
            DocumentPermission.document_id == document.id,
            DocumentPermission.source == "upload",
            DocumentPermission.external_id == str(document.id),
        )
        .one_or_none()
    )
    if exists:
        return
    db.add(
        DocumentPermission(
            document_id=document.id,
            organization_id=document.organization_id,
            user_id=None,
            can_read=True,
            source="upload",
            external_id=str(document.id),
            connector_id=None,
        )
    )
    db.flush()


def _truthy(v: str | None) -> bool:
    return (v or "").strip().lower() in ("1", "true", "yes", "y", "on")


def _ingest_pdf_file(
    db: Session,
    *,
    workspace: Workspace,
    owner: User,
    pdf_path: Path,
    filename: str,
) -> Document:
    pages = extract_pdf_pages(str(pdf_path))
    if not pages:
        raise RuntimeError(f"No extractable text in {filename}")
    chunks = build_chunks(pages)
    if not chunks:
        raise RuntimeError(f"No chunks from {filename}")

    try:
        embeddings = get_embedding_client().embed_texts_batched([c.content for c in chunks])
    except EmbeddingServiceError as exc:
        raise RuntimeError(f"Embedding failed (is Ollama running with {settings.embedding_model}?): {exc}") from exc

    hasher = hashlib.sha256()
    data = pdf_path.read_bytes()
    hasher.update(data)
    checksum = hasher.hexdigest()

    ingestion_job = IngestionJob(
        organization_id=workspace.organization_id,
        workspace_id=workspace.id,
        created_by=owner.id,
        status=IngestionJobStatus.completed.value,
        source_filename=filename,
    )
    db.add(ingestion_job)
    db.flush()

    document = Document(
        organization_id=workspace.organization_id,
        workspace_id=workspace.id,
        ingestion_job_id=ingestion_job.id,
        created_by=owner.id,
        filename=filename,
        content_type="application/pdf",
        storage_path=str(pdf_path.resolve()),
        checksum_sha256=checksum,
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

    _ensure_upload_permission_row(db, document=document)
    return document


def _session_for_workspace(
    db: Session, *, org_id: UUID, workspace_id: UUID, user_id: UUID
) -> ChatSession | None:
    return (
        db.query(ChatSession)
        .filter(
            ChatSession.organization_id == org_id,
            ChatSession.workspace_id == workspace_id,
            ChatSession.user_id == user_id,
        )
        .order_by(ChatSession.created_at.asc())
        .first()
    )


def main() -> None:
    if not _truthy(os.environ.get("SEED_LAW_FIRM_RAG")):
        print("Set SEED_LAW_FIRM_RAG=true to run this script.")
        return

    org_slug = os.environ.get("LAW_FIRM_ORG_SLUG", "sterling-vale-llp").strip().lower()
    owner_email = os.environ.get("SEED_PLATFORM_OWNER_EMAIL", "owner@example.com").lower().strip()

    storage_root = Path(settings.document_storage_root)

    db = SessionLocal()
    try:
        owner = db.execute(select(User).where(User.email == owner_email)).scalar_one_or_none()
        if owner is None:
            print(f"No user {owner_email}; run scripts/seed.py first.")
            sys.exit(1)

        org = db.execute(select(Organization).where(Organization.slug == org_slug)).scalar_one_or_none()
        if org is None:
            print(f"No organization with slug {org_slug}; run SEED_LAW_FIRM=true scripts/seed_law_firm.py first.")
            sys.exit(1)

        ws_by_name = {
            w.name: w
            for w in db.query(Workspace).filter(Workspace.organization_id == org.id).all()
        }

        indexed = 0
        for spec in DEMO_PDFS:
            ws = ws_by_name.get(spec["workspace"])
            if ws is None:
                print(f"Skip missing workspace: {spec['workspace']}")
                continue

            fname = spec["filename"]
            existing = (
                db.query(Document)
                .filter(Document.workspace_id == ws.id, Document.filename == fname)
                .one_or_none()
            )
            if existing is not None:
                print(f"Already indexed: {fname} in {ws.name}")
                continue

            dest_dir = storage_root / str(ws.id)
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest_path = dest_dir / f"{uuid4()}-{fname}"
            write_demo_pdf(dest=dest_path, doc_title=spec["title"], body=spec["body"])

            try:
                doc = _ingest_pdf_file(db, workspace=ws, owner=owner, pdf_path=dest_path, filename=fname)
            except RuntimeError as exc:
                dest_path.unlink(missing_ok=True)
                print(f"ERROR {fname}: {exc}")
                sys.exit(1)

            # Sample QueryLog rows (grounded in PDF text above)
            for pair in spec["questions"]:
                db.add(
                    QueryLog(
                        organization_id=org.id,
                        workspace_id=ws.id,
                        user_id=owner.id,
                        question=pair["q"],
                        answer=pair["a"],
                        citations_json=[{"document_id": str(doc.id), "filename": fname}],
                        confidence="high",
                        duration_ms=650,
                        token_count=180,
                        feedback=None,
                    )
                )

            # Chat transcript snippets for the workspace session
            sess = _session_for_workspace(db, org_id=org.id, workspace_id=ws.id, user_id=owner.id)
            if sess is not None and spec["questions"]:
                pair = spec["questions"][0]
                db.add(
                    ChatMessage(
                        session_id=sess.id,
                        user_id=owner.id,
                        role=ChatMessageRole.user.value,
                        content=pair["q"],
                        citations_json=None,
                    )
                )
                db.add(
                    ChatMessage(
                        session_id=sess.id,
                        user_id=owner.id,
                        role=ChatMessageRole.assistant.value,
                        content=pair["a"],
                        citations_json=[{"filename": fname, "document_id": str(doc.id)}],
                    )
                )

            indexed += 1
            print(f"Indexed {fname} -> document {doc.id} ({len(spec['questions'])} sample questions)")

        db.commit()
        print(f"Done. New PDFs indexed this run: {indexed}")
        print("Try RAG chat or POST /documents/workspaces/{id}/search with questions similar to the samples.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
