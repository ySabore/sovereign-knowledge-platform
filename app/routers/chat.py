from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.limiter import limiter
from app.models import (
    AuditAction,
    ChatMessage,
    ChatMessageRole,
    ChatSession,
    Organization,
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
    ChatMessagePublic,
    ChatSessionCreateRequest,
    ChatSessionDetailResponse,
    ChatSessionPublic,
    ChatTurnResponse,
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
from app.services.embeddings import EmbeddingServiceError
from app.services.rag import resolve_top_k, run_retrieval_pipeline
from app.services.rate_limits import enforce_org_query_limits
from app.services.workspace_access import resolve_workspace_for_user

router = APIRouter(prefix="/chat", tags=["chat"])


def _can_delete_chat_session(db: Session, session: ChatSession, user: User) -> bool:
    if user.is_platform_owner:
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
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


def _serialize_message(message: ChatMessage) -> ChatMessagePublic:
    raw_citations = message.citations_json or []
    citations = [ChatCitationPublic.model_validate(citation) for citation in raw_citations]
    return ChatMessagePublic(
        id=message.id,
        session_id=message.session_id,
        user_id=message.user_id,
        role=message.role,
        content=message.content,
        citations=citations,
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

    session = ChatSession(
        organization_id=workspace.organization_id,
        workspace_id=workspace.id,
        user_id=user.id,
        title=body.title.strip() if body.title else None,
    )
    db.add(session)
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

    sessions = (
        db.query(ChatSession)
        .filter(ChatSession.workspace_id == workspace_id, ChatSession.user_id == user.id)
        .order_by(ChatSession.updated_at.desc(), ChatSession.created_at.desc())
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


@router.post("/sessions/{session_id}/messages", response_model=ChatTurnResponse, status_code=status.HTTP_201_CREATED)
def create_chat_message(
    request: Request,
    session_id: UUID,
    body: ChatMessageCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ChatTurnResponse:
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

    try:
        if is_low_intent_chitchat(query):
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

    assistant_message = ChatMessage(
        session_id=session.id,
        user_id=None,
        role=ChatMessageRole.assistant.value,
        content=answer_text,
        citations_json=citations,
    )
    db.add(assistant_message)

    if not session.title:
        session.title = query[:120]
    session.updated_at = utcnow()

    db.commit()
    db.refresh(session)
    db.refresh(user_message)
    db.refresh(assistant_message)

    return ChatTurnResponse(
        session=_serialize_session(session),
        user_message=_serialize_message(user_message),
        assistant_message=_serialize_message(assistant_message),
        generation_mode=generation_mode,
        generation_model=generation_model_for_mode(
            generation_mode, preferred_chat_model=preferred_chat_model_from_org(org)
        ),
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
