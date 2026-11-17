from __future__ import annotations

import uuid
import json
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import desc, func, or_
from sqlalchemy.orm import Session

from app.chat import ChatProviderError, generate_with_provider
from app.config import settings
from app.database import get_db
from app.dependencies import current_user
from app.models import Conversation, Message, User
from app.schemas import (
    ConversationCreateRequest,
    ConversationDetailResponse,
    ConversationListItemResponse,
    ConversationListResponse,
    ConversationResponse,
    ConversationUpdateRequest,
    ItemsResponse,
    MessageRequest,
    MessageResponse,
    MessageSubmissionResponse,
    RegenerateRequest,
)
from app.services.assistant import (
    OUT_OF_SCOPE_RESPONSE,
    build_assistant_messages,
    is_in_scope_request,
    requests_latest_prediction,
)
from app.services.prediction_tools import get_latest_user_prediction
from app.services.streaming import stream_assistant_events, stream_static_response_events

router = APIRouter(prefix="/conversations", tags=["conversations"])
logger = logging.getLogger("car_estimation.chat")


def _owned_conversation(db: Session, user_id: uuid.UUID, conversation_id: uuid.UUID) -> Conversation:
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id, Conversation.user_id == user_id
    ).first()
    if conversation is None:
        raise HTTPException(404, "Conversation not found.")
    return conversation


def _selected_model(provider, requested_model: str | None) -> str:
    default_model = getattr(provider, "default_model", settings.default_model)
    selected = requested_model or default_model
    list_models = getattr(provider, "list_models", None)
    if callable(list_models):
        try:
            installed_models = list_models()
        except ChatProviderError as exc:
            raise HTTPException(503, "The local AI provider is unavailable.") from exc
        if not installed_models:
            raise HTTPException(503, "No local AI models are currently available.")
        if selected not in installed_models:
            if requested_model:
                raise HTTPException(422, "The selected model is not installed in Ollama.")
            raise HTTPException(503, "The configured default model is not installed in Ollama.")
    return selected


def _provider_messages(
    db: Session,
    conversation_id: uuid.UUID,
    user_id: uuid.UUID,
    content: str,
    current_message: Message | None = None,
) -> list[dict[str, str]]:
    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at, Message.id)
        .all()
    )
    if current_message is not None:
        messages = [
            message for message in messages
            if message.id != current_message.id
            and (message.created_at, str(message.id))
            < (current_message.created_at, str(current_message.id))
        ]
    messages = [
        message for message in messages
        if not (message.message_metadata or {}).get("status") == "superseded"
    ][-settings.ai_max_history_messages:]
    authorized_context = None
    if settings.ai_enable_tools and requests_latest_prediction(content):
        prediction = get_latest_user_prediction(db, user_id)
        authorized_context = (
            json.dumps(prediction, ensure_ascii=False)
            if prediction is not None
            else "No saved prediction exists for this authenticated user."
        )
    return build_assistant_messages(
        [{"role": message.role, "content": message.content} for message in messages],
        content,
        settings.ai_max_history_messages,
        authorized_context=authorized_context,
    )


def _save_user_message(db: Session, conversation: Conversation, content: str) -> Message:
    message = Message(
        conversation_id=conversation.id,
        role="user",
        content=content,
        created_at=datetime.now(timezone.utc),
    )
    db.add(message)
    conversation.updated_at = func.now()
    db.commit()
    db.refresh(message)
    return message


@router.post("", response_model=ItemsResponse[ConversationResponse], status_code=201)
def create_conversation(
    payload: ConversationCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    conversation = Conversation(user_id=user.id, title=payload.title.strip() or "New conversation")
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return {"items": [conversation]}


@router.get("", response_model=ConversationListResponse)
def list_conversations(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
    search: str | None = Query(None, max_length=200),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    query = db.query(Conversation).filter(Conversation.user_id == user.id)
    if search:
        term = f"%{search.strip()}%"
        has_matching_message = (
            db.query(Message.id)
            .filter(
                Message.conversation_id == Conversation.id,
                Message.content.ilike(term),
            )
            .exists()
        )
        query = query.filter(or_(Conversation.title.ilike(term), has_matching_message))
    total = query.count()
    items = query.order_by(desc(Conversation.updated_at), Conversation.id).offset(offset).limit(limit).all()
    result = []
    for conversation in items:
        recent_messages = (
            db.query(Message)
            .filter(Message.conversation_id == conversation.id)
            .order_by(desc(Message.created_at), desc(Message.id))
            .limit(10)
            .all()
        )
        last_message = next(
            (
                message for message in recent_messages
                if (message.message_metadata or {}).get("status") != "superseded"
            ),
            None,
        )
        result.append(
            ConversationListItemResponse(
                id=conversation.id,
                title=conversation.title,
                created_at=conversation.created_at,
                updated_at=conversation.updated_at,
                last_message_preview=(
                    last_message.content[:160] if last_message is not None else None
                ),
                last_message_at=last_message.created_at if last_message is not None else None,
            )
        )
    return {"items": result, "total": total}


@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
def get_conversation(
    conversation_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    return {"items": [_owned_conversation(db, user.id, conversation_id)]}


@router.patch("/{conversation_id}", response_model=ConversationDetailResponse)
def update_conversation(
    conversation_id: uuid.UUID,
    payload: ConversationUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    conversation = _owned_conversation(db, user.id, conversation_id)
    conversation.title = payload.title.strip()
    db.commit()
    db.refresh(conversation)
    return {"items": [conversation]}


@router.delete("/{conversation_id}", status_code=204)
def delete_conversation(
    conversation_id: uuid.UUID,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    conversation = _owned_conversation(db, user.id, conversation_id)
    db.delete(conversation)
    db.commit()
    response.status_code = 204
    return response


@router.get("/{conversation_id}/messages", response_model=ItemsResponse[MessageResponse])
def list_messages(
    conversation_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    conversation = _owned_conversation(db, user.id, conversation_id)
    items = (
        db.query(Message)
        .filter(Message.conversation_id == conversation.id)
        .order_by(Message.created_at, Message.id)
        .offset(offset)
        .limit(limit)
        .all()
    )
    return {
        "items": [
            item for item in items
            if (item.message_metadata or {}).get("status") != "superseded"
        ]
    }


@router.post(
    "/{conversation_id}/messages",
    response_model=MessageSubmissionResponse,
    status_code=201,
    description=(
        "Persists the user's message. When no AI response provider is configured, "
        "returns only that user message and assistant_response_available=false."
    ),
)
def send_message(
    conversation_id: uuid.UUID,
    payload: MessageRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    conversation = _owned_conversation(db, user.id, conversation_id)
    provider = request.app.state.chat_provider
    if provider is None:
        user_message = _save_user_message(db, conversation, payload.content)
        return {"items": [user_message], "assistant_response_available": False}
    if not is_in_scope_request(payload.content):
        user_message = Message(
            conversation_id=conversation.id,
            role="user",
            content=payload.content,
            created_at=datetime.now(timezone.utc),
        )
        assistant_message = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=OUT_OF_SCOPE_RESPONSE,
            message_metadata={"status": "complete", "source": "scope-policy"},
            created_at=datetime.now(timezone.utc) + timedelta(microseconds=1),
        )
        db.add_all([user_message, assistant_message])
        conversation.updated_at = func.now()
        db.commit()
        db.refresh(user_message)
        db.refresh(assistant_message)
        return {
            "items": [user_message, assistant_message],
            "assistant_response_available": True,
        }
    selected_model = _selected_model(provider, payload.model)
    provider_messages = _provider_messages(db, conversation.id, user.id, payload.content)
    try:
        answer = generate_with_provider(provider, provider_messages, model=selected_model)
    except Exception as exc:
        logger.warning(
            "Configured chat provider failed conversation_id=%s error_type=%s",
            conversation.id,
            type(exc).__name__,
        )
        raise HTTPException(502, "The configured chat provider could not complete this request.") from None
    if not isinstance(answer, str) or not answer.strip():
        raise HTTPException(502, "The configured chat provider returned no usable response.")

    message_time = datetime.now(timezone.utc)
    assistant_message = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=answer.strip(),
        message_metadata={"status": "complete", "model": selected_model},
        created_at=message_time + timedelta(microseconds=1),
    )
    user_message = Message(
        conversation_id=conversation.id,
        role="user",
        content=payload.content,
        created_at=message_time,
    )
    db.add_all([user_message, assistant_message])
    conversation.updated_at = func.now()
    db.commit()
    db.refresh(user_message)
    db.refresh(assistant_message)
    return {
        "items": [user_message, assistant_message],
        "assistant_response_available": True,
    }


@router.post(
    "/{conversation_id}/messages/stream",
    status_code=200,
    description="Streams genuine provider tokens as Server-Sent Events and persists completed output.",
)
def stream_message(
    conversation_id: uuid.UUID,
    payload: MessageRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    conversation = _owned_conversation(db, user.id, conversation_id)
    provider = request.app.state.chat_provider
    if provider is None:
        raise HTTPException(503, "The local AI provider is not configured.")
    if not is_in_scope_request(payload.content):
        user_message = _save_user_message(db, conversation, payload.content)
        return StreamingResponse(
            stream_static_response_events(
                OUT_OF_SCOPE_RESPONSE,
                request.app.state.session_factory,
                conversation.id,
                user_message.id,
            ),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    selected_model = _selected_model(provider, payload.model)
    provider_messages = _provider_messages(db, conversation.id, user.id, payload.content)
    user_message = _save_user_message(db, conversation, payload.content)
    return StreamingResponse(
        stream_assistant_events(
            provider,
            provider_messages,
            request.app.state.session_factory,
            conversation.id,
            user_message.id,
            selected_model,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post(
    "/{conversation_id}/messages/{assistant_message_id}/regenerate/stream",
    status_code=200,
    description="Regenerates the latest assistant response without duplicating its user message.",
)
def regenerate_message(
    conversation_id: uuid.UUID,
    assistant_message_id: uuid.UUID,
    payload: RegenerateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    conversation = _owned_conversation(db, user.id, conversation_id)
    provider = request.app.state.chat_provider
    if provider is None:
        raise HTTPException(503, "The local AI provider is not configured.")
    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversation.id)
        .order_by(Message.created_at, Message.id)
        .all()
    )
    visible_messages = [
        message for message in messages
        if (message.message_metadata or {}).get("status") != "superseded"
    ]
    if (
        len(visible_messages) < 2
        or visible_messages[-1].id != assistant_message_id
        or visible_messages[-1].role != "assistant"
        or visible_messages[-2].role != "user"
    ):
        raise HTTPException(409, "Only the latest assistant response can be regenerated.")
    old_assistant = visible_messages[-1]
    user_message = visible_messages[-2]
    if not is_in_scope_request(user_message.content):
        raise HTTPException(422, "This message is outside the assistant's supported scope.")
    selected_model = _selected_model(provider, payload.model)
    provider_messages = _provider_messages(
        db, conversation.id, user.id, user_message.content, user_message
    )
    return StreamingResponse(
        stream_assistant_events(
            provider,
            provider_messages,
            request.app.state.session_factory,
            conversation.id,
            user_message.id,
            selected_model,
            supersede_message_id=old_assistant.id,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
