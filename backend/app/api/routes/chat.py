import json
import logging
import uuid
from typing import Annotated, AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.chat.rag import (
    detect_verdict_language,
    load_passages_for_document,
    parse_citations,
    stream_response,
)
from app.db.session import get_db
from app.models.chat import Conversation, Message
from app.models.user import User
from app.schemas.chat import (
    ConversationCreate,
    ConversationListItem,
    ConversationListResponse,
    ConversationResponse,
    SendMessageRequest,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])


@router.post(
    "/conversations",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_conversation(
    body: ConversationCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ConversationResponse:
    # V1 supports document scope only — result_set scope is deferred to V1.1
    if body.scope_type == "result_set":
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="result_set scope is not yet implemented (Phase 6.1).",
        )
    if body.scope_type == "document" and body.scope_document_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="scope_document_id is required for document scope.",
        )

    conv = Conversation(
        user_id=current_user.id,
        scope_type=body.scope_type,
        scope_document_id=body.scope_document_id,
        scope_query=body.scope_query,
        scope_filters=body.scope_filters,
        title=None,
    )
    db.add(conv)
    await db.commit()
    await db.refresh(conv)

    logger.info(
        "Conversation created",
        extra={
            "conversation_id": str(conv.id),
            "scope_type": conv.scope_type,
            "user_id": str(current_user.id),
        },
    )

    return ConversationResponse(
        id=conv.id,
        user_id=conv.user_id,
        scope_type=conv.scope_type,
        scope_document_id=conv.scope_document_id,
        scope_query=conv.scope_query,
        scope_filters=conv.scope_filters,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        messages=[],
    )


@router.get(
    "/conversations",
    response_model=ConversationListResponse,
)
async def list_conversations(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> ConversationListResponse:
    """
    List the current user's conversations, most-recently-updated first.
    Joins documents + document_metadata so the list shows what each chat
    was about without N additional queries.
    """
    from sqlalchemy import text

    # Total count for pagination
    total_q = await db.execute(
        select(func.count(Conversation.id)).where(Conversation.user_id == current_user.id)
    )
    total = total_q.scalar_one()

    rows = await db.execute(
        text("""
            SELECT
                c.id,
                c.scope_type,
                c.scope_document_id,
                c.title,
                c.created_at,
                c.updated_at,
                (SELECT COUNT(*) FROM messages m WHERE m.conversation_id = c.id) AS message_count,
                d.doc_type AS scope_doc_type,
                d.original_name AS scope_doc_original_name,
                dm.facility_name AS scope_doc_facility_name,
                dm.jurisdiction AS scope_doc_jurisdiction
            FROM conversations c
            LEFT JOIN documents d ON d.id = c.scope_document_id
            LEFT JOIN document_metadata dm ON dm.document_id = c.scope_document_id
            WHERE c.user_id = :user_id
            ORDER BY c.updated_at DESC
            LIMIT :limit OFFSET :offset
        """),
        {
            "user_id": current_user.id,
            "limit": page_size,
            "offset": (page - 1) * page_size,
        },
    )

    items = [
        ConversationListItem(
            id=r[0],
            scope_type=r[1],
            scope_document_id=r[2],
            title=r[3],
            created_at=r[4],
            updated_at=r[5],
            message_count=int(r[6] or 0),
            scope_doc_type=r[7],
            scope_doc_original_name=r[8],
            scope_doc_facility_name=r[9],
            scope_doc_jurisdiction=r[10],
        )
        for r in rows.fetchall()
    ]
    return ConversationListResponse(items=items, total=total)


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationResponse,
)
async def get_conversation(
    conversation_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ConversationResponse:
    result = await db.execute(
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(Conversation.id == conversation_id)
    )
    conv = result.scalar_one_or_none()
    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    if conv.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return ConversationResponse.model_validate(conv)


@router.post("/conversations/{conversation_id}/messages")
async def send_message(
    conversation_id: uuid.UUID,
    body: SendMessageRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> StreamingResponse:
    """
    Send a user message and stream the assistant response via Server-Sent
    Events. Events emitted:
      - `event: token`        data: {"delta": "..."}
      - `event: citations`    data: [{cit_id, document_id, section, snippet}, ...]
      - `event: done`         data: {"message_id": "..."}
      - `event: error`        data: {"detail": "..."}
    """
    result = await db.execute(
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(Conversation.id == conversation_id)
    )
    conv = result.scalar_one_or_none()
    if conv is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    if conv.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    if conv.scope_type != "document" or conv.scope_document_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only document-scoped conversations are supported in V1.",
        )

    # Persist the user message
    user_msg = Message(
        conversation_id=conv.id,
        role="user",
        content=body.content,
        citations=None,
    )
    db.add(user_msg)
    # Snapshot history before we add the user msg id (we re-fetch below anyway)
    history = list(conv.messages)
    await db.commit()
    await db.refresh(user_msg)

    # Load passages for the bound document
    passages, doc = await load_passages_for_document(db, str(conv.scope_document_id))
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scope document no longer exists.",
        )

    history.append(user_msg)

    def _sse(event: str, data) -> str:
        return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"

    async def stream() -> AsyncIterator[str]:
        accumulated: list[str] = []
        try:
            async for delta in stream_response(body.content, passages, history):
                accumulated.append(delta)
                yield _sse("token", {"delta": delta})

            full_content = "".join(accumulated).strip()
            citations = parse_citations(full_content, passages)

            verdict_hits = detect_verdict_language(full_content)
            if verdict_hits:
                logger.warning(
                    "verdict language detected in assistant reply",
                    extra={
                        "conversation_id": str(conv.id),
                        "hits": verdict_hits,
                    },
                )

            # Persist the assistant message
            from app.db.session import AsyncSessionLocal
            async with AsyncSessionLocal() as session:
                assistant_msg = Message(
                    conversation_id=conv.id,
                    role="assistant",
                    content=full_content,
                    citations=citations or None,
                )
                session.add(assistant_msg)
                # Title the conversation on the first exchange
                if not conv.title:
                    title = body.content[:80].strip()
                    await session.execute(
                        Conversation.__table__.update()
                        .where(Conversation.id == conv.id)
                        .values(title=title)
                    )
                await session.commit()
                await session.refresh(assistant_msg)
                yield _sse("citations", citations)
                yield _sse("done", {"message_id": str(assistant_msg.id)})
        except Exception as exc:
            logger.exception("chat stream failed: %s", exc)
            yield _sse("error", {"detail": str(exc)})

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable proxy buffering
        },
    )
