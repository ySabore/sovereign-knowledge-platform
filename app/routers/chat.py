from __future__ import annotations

import time
from uuid import NAMESPACE_URL, UUID, uuid5

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from pydantic import ValidationError
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, desc
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.limiter import limiter
from app.models import (
    AuditAction,
    ChatMessage,
    ChatMessageRole,
    ChatSession,
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
from app.routers.organizations import _write_audit_log
from app.schemas.auth import (
    ChatCitationPublic,
    ChatMessageCreateRequest,
    ChatMessageFeedbackRequest,
    ChatMessagePublic,
    ChatSessionCreateRequest,
    ChatSessionDetailResponse,
    ChatSessionPublic,
    ChatSessionUpdateRequest,
    ChatTurnResponse,
    DocumentChunkPublic,
    DocumentIngestionResponse,
)
from app.services.chat import (
    AnswerGenerationError,
    generate_grounded_answer,
    generation_model_for_mode,
    preferred_chat_model_from_org,
)
from app.services.chitchat import CHITCHAT_REPLY, is_low_intent_chitchat
from app.services.chat_history import load_recent_conversation_turns
from app.services.chat_sse import sse_chat_turn_lines
from app.services.chat_titles import derive_chat_session_title, should_replace_chat_title
from app.services.chat_workspace_facts import answer_workspace_fact_query
from app.services.embeddings import EmbeddingServiceError, get_embedding_client
from app.services.ingestion import build_chunks, extract_pages_from_upload, persist_upload_file
from app.services.permissions import ensure_upload_permission_row
from app.services.rag import resolve_top_k, run_retrieval_pipeline
from app.services.rag.answer_parse import extract_confidence_tag
from app.services.query_log import record_chat_turn_query_log
from app.services.rate_limits import enforce_org_query_limits
from app.services.workspace_access import resolve_workspace_for_user

router = APIRouter(prefix="/chat", tags=["chat"])
def _source_type_for_upload_filename(filename: str) -> str:
    name = filename.lower()
    return "pdf-upload" if name.endswith(".pdf") else "file-upload"


def _content_type_for_upload(filename: str, reported: str | None) -> str:
    if reported and reported.strip():
        return reported.strip()
    if filename.lower().endswith(".pdf"):
        return "application/pdf"
    return "application/octet-stream"




def _is_org_owner(db: Session, organization_id: UUID, user_id: UUID) -> bool:
    membership = (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_id == user_id,
            OrganizationMembership.role == OrgMembershipRole.org_owner.value,
        )
        .one_or_none()
    )
    return membership is not None


def _can_delete_chat_session(db: Session, session: ChatSession, user: User) -> bool:
    if user.is_platform_owner:
        return True
    if _is_org_owner(db, session.organization_id, user.id):
        return True
    if session.user_id is not None and session.user_id == user.id:
        return True
    wm = (
        db.query(WorkspaceMember)
        .filter(WorkspaceMember.workspace_id == session.workspace_id, WorkspaceMember.user_id == user.id)
        .one_or_none()
    )
    return wm is not None and wm.role == WorkspaceMemberRole.workspace_admin.value


def _require_session_for_user(db: Session, session_id: UUID, user: User) -> ChatSession:
    if user.is_platform_owner:
        session = db.get(ChatSession, session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Chat session not found")
        return session
    session = db.get(ChatSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Chat session not found")
    if _is_org_owner(db, session.organization_id, user.id):
        return session
    session = (
        db.query(ChatSession)
        .join(Workspace, Workspace.id == ChatSession.workspace_id)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
        .filter(ChatSession.id == session_id, WorkspaceMember.user_id == user.id)
        .one_or_none()
    )
    if session is None:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return session


def _serialize_session(session: ChatSession) -> ChatSessionPublic:
    return ChatSessionPublic(
        id=session.id,
        organization_id=session.organization_id,
        workspace_id=session.workspace_id,
        user_id=session.user_id,
        title=session.title,
        pinned=bool(session.pinned),
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


def _parse_chat_citation(raw: object) -> ChatCitationPublic | None:
    """Map stored citation JSON to the public schema.

    Full RAG turns use :meth:`Citation.to_dict`. Older seed/demo rows and legacy
    clients may only persist ``document_id`` + ``filename``.
    """
    if not isinstance(raw, dict):
        return None
    try:
        return ChatCitationPublic.model_validate(raw)
    except ValidationError:
        pass
    doc_id_val = raw.get("document_id")
    if doc_id_val is None:
        return None
    try:
        document_id = UUID(str(doc_id_val))
    except ValueError:
        return None
    filename = raw.get("document_filename") or raw.get("filename") or "unknown"
    chunk_id_val = raw.get("chunk_id")
    if chunk_id_val is not None:
        try:
            chunk_id = UUID(str(chunk_id_val))
        except ValueError:
            chunk_id = uuid5(NAMESPACE_URL, f"skp:legacy-chat-citation:{document_id}:{filename}")
    else:
        chunk_id = uuid5(NAMESPACE_URL, f"skp:legacy-chat-citation:{document_id}:{filename}")
    chunk_raw = raw.get("chunk_index")
    try:
        chunk_index = int(chunk_raw) if chunk_raw is not None else 0
    except (TypeError, ValueError):
        chunk_index = 0
    page_raw = raw.get("page_number")
    try:
        page_number = int(page_raw) if page_raw is not None else None
    except (TypeError, ValueError):
        page_number = None
    score_raw = raw.get("score")
    try:
        score = float(score_raw) if score_raw is not None else 0.0
    except (TypeError, ValueError):
        score = 0.0
    quote = str(raw.get("quote") or "")
    return ChatCitationPublic(
        chunk_id=chunk_id,
        document_id=document_id,
        document_filename=filename,
        chunk_index=chunk_index,
        page_number=page_number,
        score=score,
        quote=quote,
    )


def _serialize_message(message: ChatMessage) -> ChatMessagePublic:
    raw_citations = message.citations_json or []
    citations: list[ChatCitationPublic] = []
    for item in raw_citations:
        parsed = _parse_chat_citation(item)
        if parsed is not None:
            citations.append(parsed)
    return ChatMessagePublic(
        id=message.id,
        session_id=message.session_id,
        user_id=message.user_id,
        role=message.role,
        content=message.content,
        citations=citations,
        feedback=message.feedback if message.feedback in {"up", "down"} else None,
        confidence=message.confidence,
        generation_mode=message.generation_mode,
        generation_model=message.generation_model,
        created_at=message.created_at,
    )


@router.post(
    "/workspaces/{workspace_id}/sessions",
    response_model=ChatSessionPublic,
    status_code=status.HTTP_201_CREATED,
)
def create_chat_session(
    workspace_id: UUID,
    body: ChatSessionCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ChatSessionPublic:
    workspace = resolve_workspace_for_user(db, workspace_id, user)
    if workspace is None:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")

    normalized_title = body.title.strip() if body.title else None
    if normalized_title and normalized_title.lower() in {"conversation", "new conversation", "chat"}:
        normalized_title = None
    session = ChatSession(
        organization_id=workspace.organization_id,
        workspace_id=workspace.id,
        user_id=user.id,
        title=normalized_title,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return _serialize_session(session)


_SESSION_TITLE_DISALLOWED = frozenset({"conversation", "new conversation", "chat"})


@router.patch("/sessions/{session_id}", response_model=ChatSessionPublic)
def update_chat_session(
    session_id: UUID,
    body: ChatSessionUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ChatSessionPublic:
    session = _require_session_for_user(db, session_id, user)
    if not _can_delete_chat_session(db, session, user):
        raise HTTPException(status_code=403, detail="Not allowed to update this chat session")
    payload = body.model_dump(exclude_unset=True)
    if "title" in payload:
        raw_title = payload["title"]
        if raw_title is None:
            session.title = None
        else:
            normalized = raw_title.strip()
            if not normalized or normalized.lower() in _SESSION_TITLE_DISALLOWED:
                session.title = None
            else:
                session.title = normalized
    if "pinned" in payload:
        session.pinned = bool(payload["pinned"])
    db.commit()
    db.refresh(session)
    return _serialize_session(session)


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_chat_session(
    session_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    session = db.get(ChatSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Chat session not found")
    if not _can_delete_chat_session(db, session, user):
        raise HTTPException(status_code=403, detail="Not allowed to delete this chat session")
    _write_audit_log(
        db,
        actor_user_id=user.id,
        action=AuditAction.chat_session_deleted.value,
        target_type="chat_session",
        target_id=session.id,
        organization_id=session.organization_id,
        workspace_id=session.workspace_id,
        metadata={"title": session.title},
    )
    db.execute(delete(ChatSession).where(ChatSession.id == session_id))
    db.commit()


@router.get("/workspaces/{workspace_id}/sessions", response_model=list[ChatSessionPublic])
def list_chat_sessions(
    workspace_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ChatSessionPublic]:
    workspace = resolve_workspace_for_user(db, workspace_id, user)
    if workspace is None:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")
    is_org_admin = _is_org_owner(db, workspace.organization_id, user.id)
    if user.is_platform_owner or is_org_admin:
        sessions = (
            db.query(ChatSession)
            .filter(ChatSession.workspace_id == workspace_id)
            .order_by(desc(ChatSession.pinned), ChatSession.updated_at.desc(), ChatSession.created_at.desc())
            .all()
        )
    else:
        wm = (
            db.query(WorkspaceMember)
            .filter(WorkspaceMember.workspace_id == workspace_id, WorkspaceMember.user_id == user.id)
            .one_or_none()
        )
        if wm is not None and wm.role == WorkspaceMemberRole.workspace_admin.value:
            sessions = (
                db.query(ChatSession)
                .filter(ChatSession.workspace_id == workspace_id)
                .order_by(desc(ChatSession.pinned), ChatSession.updated_at.desc(), ChatSession.created_at.desc())
                .all()
            )
        else:
            sessions = (
                db.query(ChatSession)
                .filter(ChatSession.workspace_id == workspace_id, ChatSession.user_id == user.id)
                .order_by(desc(ChatSession.pinned), ChatSession.updated_at.desc(), ChatSession.created_at.desc())
                .all()
            )
    return [_serialize_session(session) for session in sessions]


@router.get("/sessions/{session_id}", response_model=ChatSessionDetailResponse)
def get_chat_session(
    session_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ChatSessionDetailResponse:
    session = _require_session_for_user(db, session_id, user)
    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session.id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )
    return ChatSessionDetailResponse(
        session=_serialize_session(session),
        messages=[_serialize_message(message) for message in messages],
    )


@router.post("/workspaces/{workspace_id}/upload", response_model=DocumentIngestionResponse, status_code=status.HTTP_201_CREATED)
async def upload_document_from_chat(
    workspace_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DocumentIngestionResponse:
    workspace = resolve_workspace_for_user(db, workspace_id, user)
    if workspace is None:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")

    stored = await persist_upload_file(file, settings.document_storage_root, workspace_id)
    upload_name = (file.filename or "document").strip() or "document"
    pages = extract_pages_from_upload(stored.storage_path, upload_name)
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

    ingestion_job = IngestionJob(
        organization_id=workspace.organization_id,
        workspace_id=workspace.id,
        created_by=user.id,
        status=IngestionJobStatus.completed.value,
        source_filename=upload_name,
    )
    db.add(ingestion_job)
    db.flush()

    src_label = _source_type_for_upload_filename(upload_name)
    document = Document(
        organization_id=workspace.organization_id,
        workspace_id=workspace.id,
        ingestion_job_id=ingestion_job.id,
        created_by=user.id,
        filename=upload_name,
        content_type=_content_type_for_upload(upload_name, file.content_type),
        storage_path=stored.storage_path,
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


@router.put("/messages/{message_id}/feedback", response_model=ChatMessagePublic)
def set_chat_message_feedback(
    message_id: UUID,
    body: ChatMessageFeedbackRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ChatMessagePublic:
    message = db.get(ChatMessage, message_id)
    if message is None:
        raise HTTPException(status_code=404, detail="Chat message not found")
    _require_session_for_user(db, message.session_id, user)
    if message.role != ChatMessageRole.assistant.value:
        raise HTTPException(status_code=400, detail="Feedback is only supported for assistant messages")
    if body.feedback not in {"up", "down", None}:
        raise HTTPException(status_code=400, detail="Invalid feedback value")
    message.feedback = body.feedback
    db.commit()
    db.refresh(message)
    return _serialize_message(message)


@router.post("/sessions/{session_id}/messages", response_model=ChatTurnResponse, status_code=status.HTTP_201_CREATED)
def create_chat_message(
    request: Request,
    session_id: UUID,
    body: ChatMessageCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ChatTurnResponse:
    t0 = time.perf_counter()
    session = _require_session_for_user(db, session_id, user)
    enforce_org_query_limits(request, db, session.organization_id, user)
    query = body.content.strip()
    org = db.get(Organization, session.organization_id)
    answer_provider = org.preferred_chat_provider if org else None

    conversation_turns = load_recent_conversation_turns(db, session.id)

    user_message = ChatMessage(
        session_id=session.id,
        user_id=user.id,
        role=ChatMessageRole.user.value,
        content=query,
        citations_json=None,
    )
    db.add(user_message)
    db.flush()
    user_turn_count = (
        db.query(ChatMessage)
        .filter(
            ChatMessage.session_id == session.id,
            ChatMessage.role == ChatMessageRole.user.value,
        )
        .count()
    )

    from_fact = False
    try:
        fact_answer = answer_workspace_fact_query(db, session, user.id, query)
        if fact_answer is not None:
            answer_text, citations, generation_mode = fact_answer
            from_fact = True
        elif is_low_intent_chitchat(query):
            answer_text, citations, generation_mode = CHITCHAT_REPLY, [], "chitchat"
        else:
            hits = run_retrieval_pipeline(
                db,
                workspace_id=session.workspace_id,
                organization_id=session.organization_id,
                user_id=user.id,
                user=user,
                query=query,
                requested_top_k=resolve_top_k(body.top_k),
                org=org,
            )
            answer_text, citations, generation_mode = generate_grounded_answer(
                query,
                hits,
                conversation_turns=conversation_turns or None,
                answer_provider=answer_provider,
                org=org,
            )
    except EmbeddingServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Embedding service unavailable: {exc}",
        ) from exc
    except AnswerGenerationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Answer generation unavailable: {exc}",
        ) from exc

    gen_model = generation_model_for_mode(
        generation_mode, preferred_chat_model=preferred_chat_model_from_org(org)
    )
    _, conf_tag = extract_confidence_tag(answer_text)
    ct = str(conf_tag).lower() if conf_tag else ""
    if ct in ("high", "medium", "low"):
        conf_val = ct
    elif generation_mode == "no_evidence":
        conf_val = "low"
    elif generation_mode == "chitchat" or from_fact:
        conf_val = "high"
    else:
        conf_val = "medium"

    assistant_message = ChatMessage(
        session_id=session.id,
        user_id=None,
        role=ChatMessageRole.assistant.value,
        content=answer_text,
        citations_json=citations,
        confidence=conf_val,
        generation_mode=generation_mode,
        generation_model=gen_model,
    )
    db.add(assistant_message)

    if should_replace_chat_title(session.title, query, user_turn_count=user_turn_count):
        session.title = derive_chat_session_title(query)
    session.updated_at = utcnow()
    duration_ms = int((time.perf_counter() - t0) * 1000)
    record_chat_turn_query_log(
        db,
        organization_id=session.organization_id,
        workspace_id=session.workspace_id,
        user_id=user.id,
        question=query,
        answer=answer_text,
        citations=citations if isinstance(citations, list) else [],
        confidence=conf_val,
        duration_ms=duration_ms,
    )

    db.commit()
    db.refresh(session)
    db.refresh(user_message)
    db.refresh(assistant_message)

    return ChatTurnResponse(
        session=_serialize_session(session),
        user_message=_serialize_message(user_message),
        assistant_message=_serialize_message(assistant_message),
        generation_mode=generation_mode,
        generation_model=gen_model,
    )


@router.post("/sessions/{session_id}/messages/stream")
@limiter.exempt
async def stream_chat_message(
    request: Request,
    session_id: UUID,
    body: ChatMessageCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    """SSE stream of assistant tokens (`data: {"type":"delta","text":...}`) ending with `type: done` + citations."""
    session = _require_session_for_user(db, session_id, user)
    enforce_org_query_limits(request, db, session.organization_id, user)
    query = body.content.strip()

    async def event_stream():
        async for line in sse_chat_turn_lines(
            db,
            session=session,
            user=user,
            query=query,
            top_k=body.top_k,
        ):
            yield line

    return StreamingResponse(event_stream(), media_type="text/event-stream")
