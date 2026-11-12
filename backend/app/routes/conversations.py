from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import desc, func, or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import current_user
from app.models import Conversation, Message, User
from app.schemas import (
    ConversationCreateRequest,
    ConversationDetailResponse,
    ConversationListResponse,
    ConversationResponse,
    ConversationUpdateRequest,
    ItemsResponse,
    MessageRequest,
    MessageResponse,
    MessageSubmissionResponse,
)

router = APIRouter(prefix="/conversations", tags=["conversations"])


def _owned_conversation(db: Session, user_id: uuid.UUID, conversation_id: uuid.UUID) -> Conversation:
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id, Conversation.user_id == user_id
    ).first()
    if conversation is None:
        raise HTTPException(404, "Conversation not found.")
    return conversation


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
    return {"items": items, "total": total}


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
    return {"items": items}


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
        user_message = Message(
            conversation_id=conversation.id,
            role="user",
            content=payload.content,
            created_at=datetime.now(timezone.utc),
        )
        db.add(user_message)
        conversation.updated_at = func.now()
        db.commit()
        db.refresh(user_message)
        return {"items": [user_message], "assistant_response_available": False}
    previous = (
        db.query(Message)
        .filter(Message.conversation_id == conversation.id)
        .order_by(Message.created_at, Message.id)
        .all()
    )
    provider_messages = [{"role": message.role, "content": message.content} for message in previous]
    provider_messages.append({"role": "user", "content": payload.content})
    try:
        answer = provider.generate_reply(provider_messages)
    except Exception as exc:
        from app.errors import logger

        logger.warning(
            "Configured chat provider failed conversation_id=%s error_type=%s",
            conversation.id,
            type(exc).__name__,
        )
        raise HTTPException(502, "The configured chat provider could not complete this request.") from None
    if not isinstance(answer, str) or not answer.strip():
        raise HTTPException(502, "The configured chat provider returned no usable response.")

    message_time = datetime.now(timezone.utc)
    user_message = Message(
        conversation_id=conversation.id,
        role="user",
        content=payload.content,
        created_at=message_time,
    )
    assistant_message = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=answer.strip(),
        created_at=message_time + timedelta(microseconds=1),
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
