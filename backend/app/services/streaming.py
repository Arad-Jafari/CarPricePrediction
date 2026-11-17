from __future__ import annotations

import json
import logging
import uuid
from collections.abc import AsyncIterator, Callable
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.chat import ChatProvider, stream_with_provider
from app.models import Conversation, Message

logger = logging.getLogger("car_estimation.chat")


def _event(name: str, data: dict) -> str:
    return f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _persist_assistant_message(
    session_factory: Callable[[], Session],
    conversation_id: uuid.UUID,
    content: str,
    model: str,
    status: str,
    supersede_message_id: uuid.UUID | None = None,
) -> dict:
    with session_factory() as db:
        conversation = db.get(Conversation, conversation_id)
        if conversation is None:
            raise RuntimeError("Conversation no longer exists.")
        if supersede_message_id is not None:
            previous = db.get(Message, supersede_message_id)
            if previous is not None and previous.conversation_id == conversation_id:
                previous.message_metadata = {"status": "superseded"}
        message = Message(
            conversation_id=conversation_id,
            role="assistant",
            content=content,
            message_metadata={"status": status, "model": model},
            created_at=datetime.now(timezone.utc),
        )
        db.add(message)
        conversation.updated_at = func.now()
        db.commit()
        db.refresh(message)
        return {
            "id": str(message.id),
            "role": message.role,
            "content": message.content,
            "created_at": message.created_at.isoformat(),
            "message_metadata": message.message_metadata,
        }


async def stream_assistant_events(
    provider: ChatProvider,
    provider_messages: list[dict[str, str]],
    session_factory: Callable[[], Session],
    conversation_id: uuid.UUID,
    user_message_id: uuid.UUID,
    model: str,
    supersede_message_id: uuid.UUID | None = None,
) -> AsyncIterator[str]:
    chunks: list[str] = []
    saved = False
    stream = stream_with_provider(provider, provider_messages, model=model)
    try:
        yield _event("start", {"user_message_id": str(user_message_id), "model": model})
        async for token in stream:
            if not token:
                continue
            chunks.append(token)
            yield _event("token", {"token": token})
        content = "".join(chunks).strip()
        if not content:
            raise RuntimeError("The provider returned an empty completion.")
        message = _persist_assistant_message(
            session_factory,
            conversation_id,
            content,
            model,
            "complete",
            supersede_message_id,
        )
        saved = True
        yield _event("done", {"message": message})
    except GeneratorExit:
        raise
    except Exception as exc:
        logger.warning(
            "Chat stream failed conversation_id=%s error_type=%s",
            conversation_id,
            type(exc).__name__,
        )
        if chunks and not saved:
            try:
                _persist_assistant_message(
                    session_factory,
                    conversation_id,
                    "".join(chunks),
                    model,
                    "interrupted",
                )
                saved = True
            except Exception as persist_error:
                logger.error(
                    "Could not persist interrupted chat response conversation_id=%s error_type=%s",
                    conversation_id,
                    type(persist_error).__name__,
                )
        yield _event("error", {"message": "The assistant could not complete this response."})
    finally:
        close = getattr(stream, "aclose", None)
        if callable(close):
            await close()
        if chunks and not saved:
            try:
                _persist_assistant_message(
                    session_factory,
                    conversation_id,
                    "".join(chunks),
                    model,
                    "interrupted",
                )
            except Exception as exc:
                logger.error(
                    "Could not persist cancelled chat response conversation_id=%s error_type=%s",
                    conversation_id,
                    type(exc).__name__,
                )


async def stream_static_response_events(
    content: str,
    session_factory: Callable[[], Session],
    conversation_id: uuid.UUID,
    user_message_id: uuid.UUID,
) -> AsyncIterator[str]:
    saved = False
    try:
        yield _event("start", {"user_message_id": str(user_message_id), "model": "scope-policy"})
        yield _event("token", {"token": content})
        message = _persist_assistant_message(
            session_factory, conversation_id, content, "scope-policy", "complete"
        )
        saved = True
        yield _event("done", {"message": message})
    finally:
        if not saved:
            _persist_assistant_message(
                session_factory, conversation_id, content, "scope-policy", "complete"
            )
