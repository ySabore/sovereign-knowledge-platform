"""SPA-friendly alias: `POST /chat` (with Vite proxy, call `POST /api/chat`)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.limiter import limiter
from app.models import User
from app.routers.chat import _require_session_for_user
from app.services.chat_sse import sse_chat_turn_lines
from app.services.rate_limits import enforce_org_query_limits

router = APIRouter(tags=["chat"])


class ChatStreamApiBody(BaseModel):
    session_id: UUID
    content: str = Field(min_length=1, max_length=8000)
    top_k: int | None = Field(default=None, ge=1, le=20)


@router.post("/chat")
@limiter.exempt
async def post_api_chat_stream(
    request: Request,
    body: ChatStreamApiBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    """Same SSE contract as `POST /chat/sessions/{session_id}/messages/stream`."""
    session = _require_session_for_user(db, body.session_id, user)
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
