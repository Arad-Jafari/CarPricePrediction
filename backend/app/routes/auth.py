from __future__ import annotations

import threading
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.dependencies import current_user, issue_auth_session, require_csrf
from app.models import RefreshToken, User
from app.schemas import (
    LoginRequest,
    PasswordChangeRequest,
    ProfileUpdateRequest,
    RefreshResponse,
    RegistrationRequest,
    UserResponse,
    TokenResponse,
)
from app.security import (
    create_access_token,
    create_csrf_token,
    create_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["authentication"])
_attempts: dict[str, deque[float]] = defaultdict(deque)
_attempts_lock = threading.Lock()
_LIMIT = 10
_WINDOW_SECONDS = 60


def _check_login_limit(request: Request) -> None:
    key = request.client.host if request.client else "unknown"
    now = time.monotonic()
    with _attempts_lock:
        attempts = _attempts[key]
        while attempts and now - attempts[0] > _WINDOW_SECONDS:
            attempts.popleft()
        if len(attempts) >= _LIMIT:
            raise HTTPException(
                429,
                "Too many login attempts. Please try again later.",
                headers={"Retry-After": str(_WINDOW_SECONDS)},
            )
        attempts.append(now)


def _set_session_cookies(response: Response, refresh_token: str, csrf_token: str) -> None:
    response.set_cookie(
        "refresh_token",
        refresh_token,
        httponly=True,
        secure=settings.production,
        samesite="lax",
        path="/",
        max_age=settings.refresh_token_days * 86400,
    )
    response.set_cookie(
        "csrf_token",
        csrf_token,
        httponly=False,
        secure=settings.production,
        samesite="lax",
        path="/",
        max_age=settings.refresh_token_days * 86400,
    )


def _clear_session_cookies(response: Response) -> None:
    response.delete_cookie("refresh_token", path="/", httponly=True, secure=settings.production, samesite="lax")
    response.delete_cookie("csrf_token", path="/", secure=settings.production, samesite="lax")


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _new_refresh_record(db: Session, user_id: uuid.UUID, family_id: uuid.UUID) -> tuple[RefreshToken, str]:
    token = create_refresh_token()
    record = RefreshToken(
        user_id=user_id,
        token_hash=hash_refresh_token(token),
        family_id=family_id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_days),
    )
    db.add(record)
    db.flush()
    return record, token


@router.post("/register", response_model=UserResponse, status_code=201)
def register(payload: RegistrationRequest, db: Session = Depends(get_db)):
    email = _normalize_email(str(payload.email))
    full_name = payload.full_name.strip()
    if not full_name:
        raise HTTPException(422, "A full name is required.")
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(409, "An account with this email already exists.")
    user = User(
        full_name=full_name,
        email=email,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    _check_login_limit(request)
    user = db.query(User).filter(User.email == _normalize_email(str(payload.email))).first()
    if user is None or not user.is_active or not verify_password(user.password_hash, payload.password):
        raise HTTPException(401, "Email or password is incorrect.")
    access_token, refresh_token = issue_auth_session(user, db)
    _set_session_cookies(response, refresh_token, create_csrf_token())
    return {"access_token": access_token, "user": user}


@router.post("/refresh", response_model=RefreshResponse, dependencies=[Depends(require_csrf)])
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    raw_token = request.cookies.get("refresh_token")
    if not raw_token:
        raise HTTPException(401, "Refresh session is missing or expired.")
    record = db.query(RefreshToken).filter(RefreshToken.token_hash == hash_refresh_token(raw_token)).first()
    now = datetime.now(timezone.utc)
    if record is None:
        raise HTTPException(401, "Refresh session is missing or expired.")
    expires_at = record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if record.revoked_at is not None:
        db.query(RefreshToken).filter(
            RefreshToken.family_id == record.family_id, RefreshToken.revoked_at.is_(None)
        ).update({RefreshToken.revoked_at: now}, synchronize_session=False)
        db.commit()
        raise HTTPException(401, "Refresh session has been revoked.")
    if expires_at <= now:
        record.revoked_at = now
        db.commit()
        raise HTTPException(401, "Refresh session is missing or expired.")

    user = db.get(User, record.user_id)
    if user is None or not user.is_active:
        record.revoked_at = now
        db.commit()
        raise HTTPException(401, "Refresh session is missing or expired.")
    record.revoked_at = now
    replacement, new_refresh = _new_refresh_record(db, user.id, record.family_id)
    record.replaced_by_id = replacement.id
    db.commit()
    csrf_token = create_csrf_token()
    _set_session_cookies(response, new_refresh, csrf_token)
    return {"access_token": create_access_token(user.id)}


@router.post("/logout", status_code=204, dependencies=[Depends(require_csrf)])
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    raw_token = request.cookies.get("refresh_token")
    if raw_token:
        record = db.query(RefreshToken).filter(RefreshToken.token_hash == hash_refresh_token(raw_token)).first()
        if record and record.revoked_at is None:
            record.revoked_at = datetime.now(timezone.utc)
            db.commit()
    _clear_session_cookies(response)
    response.status_code = 204
    return response


@router.get("/me", response_model=UserResponse)
def profile(user: User = Depends(current_user)):
    return user


@router.patch("/me", response_model=UserResponse)
def update_profile(
    payload: ProfileUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    email = _normalize_email(str(payload.email))
    duplicate = db.query(User).filter(User.email == email, User.id != user.id).first()
    if duplicate:
        raise HTTPException(409, "An account with this email already exists.")
    user.email = email
    db.commit()
    db.refresh(user)
    return user


@router.post("/password", status_code=204)
def change_password(
    payload: PasswordChangeRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    if not verify_password(user.password_hash, payload.current_password):
        raise HTTPException(400, "Current password is incorrect.")
    user.password_hash = hash_password(payload.new_password)
    db.query(RefreshToken).filter(
        RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None)
    ).update({RefreshToken.revoked_at: datetime.now(timezone.utc)}, synchronize_session=False)
    db.commit()


@router.delete("/me", status_code=204)
def delete_account(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    db.delete(user)
    db.commit()
