"""SSE line generator for one chat turn (shared by /chat/stream paths)."""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from sqlalchemy.orm import Session

from app.models import ChatMessage, ChatMessageRole, ChatSession, Organization, User, utcnow
from app.services.chat import AnswerGenerationError, generation_model_for_mode
from app.services.chat_stream import stream_grounded_answer_events
from app.services.chitchat import CHITCHAT_REPLY, is_low_intent_chitchat
from app.services.embeddings import EmbeddingServiceError
from app.services.chat_history import load_recent_conversation_turns
from app.services.chat_titles import derive_chat_session_title, should_replace_chat_title
from app.services.chat_workspace_facts import answer_workspace_fact_query
from app.services.query_log import record_query_log
from app.services.rag import resolve_top_k, run_retrieval_pipeline


def _data_line(obj: dict) -> str:
    return f"data: {json.dumps(obj, default=str)}\n\n"


async def sse_chat_turn_lines(
    db: Session,
    *,
    session: ChatSession,
    user: User,
    query: str,
    top_k: int | None,
) -> AsyncIterator[str]:
    conversation_turns = load_recent_conversation_turns(db, session.id)
    t0 = time.perf_counter()

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

    fact_answer = answer_workspace_fact_query(db, session, user.id, query)
    if fact_answer is not None:
        answer_text, citations, generation_mode = fact_answer
        assistant_message = ChatMessage(
            session_id=session.id,
            user_id=None,
            role=ChatMessageRole.assistant.value,
            content=answer_text,
            citations_json=citations,
            confidence="high",
            generation_mode=generation_mode,
            generation_model=generation_model_for_mode(generation_mode),
        )
        db.add(assistant_message)
        if should_replace_chat_title(session.title, query, user_turn_count=user_turn_count):
            session.title = derive_chat_session_title(query)
        session.updated_at = utcnow()
        duration_ms = int((time.perf_counter() - t0) * 1000)
        record_query_log(
            db,
            organization_id=session.organization_id,
            workspace_id=session.workspace_id,
            user_id=user.id,
            question=query,
            answer=answer_text,
            citations=citations,
            confidence="high",
            duration_ms=duration_ms,
        )
        db.commit()
        db.refresh(assistant_message)
        db.refresh(session)
        yield _data_line({"type": "delta", "text": answer_text})
        yield _data_line(
            {
                "type": "done",
                "citations": citations,
                "confidence": "high",
                "generation_mode": generation_mode,
                "generation_model": generation_model_for_mode(generation_mode),
                "assistant_message_id": str(assistant_message.id),
                "user_message_id": str(user_message.id),
            }
        )
        return

    if is_low_intent_chitchat(query):
        assistant_message = ChatMessage(
            session_id=session.id,
            user_id=None,
            role=ChatMessageRole.assistant.value,
            content=CHITCHAT_REPLY,
            citations_json=[],
            confidence="high",
            generation_mode="chitchat",
            generation_model=generation_model_for_mode("chitchat"),
        )
        db.add(assistant_message)
        if should_replace_chat_title(session.title, query, user_turn_count=user_turn_count):
            session.title = derive_chat_session_title(query)
        session.updated_at = utcnow()
        duration_ms = int((time.perf_counter() - t0) * 1000)
        record_query_log(
            db,
            organization_id=session.organization_id,
            workspace_id=session.workspace_id,
            user_id=user.id,
            question=query,
            answer=CHITCHAT_REPLY,
            citations=[],
            confidence="high",
            duration_ms=duration_ms,
        )
        db.commit()
        db.refresh(assistant_message)
        db.refresh(session)
        yield _data_line({"type": "delta", "text": CHITCHAT_REPLY})
        yield _data_line(
            {
                "type": "done",
                "citations": [],
                "confidence": "high",
                "generation_mode": "chitchat",
                "generation_model": generation_model_for_mode("chitchat"),
                "assistant_message_id": str(assistant_message.id),
                "user_message_id": str(user_message.id),
            }
        )
        return

    org = db.get(Organization, session.organization_id)
    try:
        hits = run_retrieval_pipeline(
            db,
            workspace_id=session.workspace_id,
            organization_id=session.organization_id,
            user_id=user.id,
            user=user,
            query=query,
            requested_top_k=resolve_top_k(top_k),
            org=org,
        )
    except EmbeddingServiceError as exc:
        db.rollback()
        yield _data_line({"type": "error", "detail": f"Embedding service unavailable: {exc}"})
        return
    answer_provider = org.preferred_chat_provider if org else None

    try:
        async for ev in stream_grounded_answer_events(
            query,
            hits,
            conversation_turns=conversation_turns or None,
            answer_provider=answer_provider,
            org=org,
        ):
            if ev["kind"] == "token":
                yield _data_line({"type": "delta", "text": ev["text"]})
            elif ev["kind"] == "done":
                final_text = ev["full_text"]
                citations = ev["citations"]
                confidence = ev["confidence"]
                generation_mode = ev.get("generation_mode", "unknown")
                generation_model = ev.get("generation_model")

                assistant_message = ChatMessage(
                    session_id=session.id,
                    user_id=None,
                    role=ChatMessageRole.assistant.value,
                    content=final_text,
                    citations_json=citations,
                    confidence=str(confidence).lower() if confidence is not None else None,
                    generation_mode=generation_mode,
                    generation_model=generation_model,
                )
                db.add(assistant_message)

                if should_replace_chat_title(session.title, query, user_turn_count=user_turn_count):
                    session.title = derive_chat_session_title(query)
                session.updated_at = utcnow()

                duration_ms = int((time.perf_counter() - t0) * 1000)
                record_query_log(
                    db,
                    organization_id=session.organization_id,
                    workspace_id=session.workspace_id,
                    user_id=user.id,
                    question=query,
                    answer=final_text,
                    citations=citations if isinstance(citations, list) else [],
                    confidence=str(confidence) if confidence is not None else None,
                    duration_ms=duration_ms,
                )
                db.commit()
                db.refresh(assistant_message)
                db.refresh(session)

                yield _data_line(
                    {
                        "type": "done",
                        "citations": citations,
                        "confidence": confidence,
                        "generation_mode": generation_mode,
                        "generation_model": generation_model,
                        "assistant_message_id": str(assistant_message.id),
                        "user_message_id": str(user_message.id),
                    }
                )
                return
    except AnswerGenerationError as exc:
        db.rollback()
        yield _data_line({"type": "error", "detail": f"Answer generation unavailable: {exc}"})
