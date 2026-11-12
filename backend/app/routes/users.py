from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi import Response
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.dependencies import current_user
from app.models import RefreshToken, User
from app.schemas import UserPasswordChangeRequest, UserProfileUpdateRequest, UserResponse
from app.security import hash_password, verify_password

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
def get_current_user(user: User = Depends(current_user)):
    return user


@router.patch("/me", response_model=UserResponse)
def update_current_user(
    payload: UserProfileUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    if payload.full_name is not None:
        full_name = payload.full_name.strip()
        if not full_name:
            raise HTTPException(422, "A full name is required.")
        user.full_name = full_name
    if payload.email is not None:
        email = str(payload.email).strip().lower()
        duplicate = db.query(User).filter(User.email == email, User.id != user.id).first()
        if duplicate:
            raise HTTPException(409, "An account with this email already exists.")
        user.email = email
    db.commit()
    db.refresh(user)
    return user


@router.post("/me/password", status_code=204)
def change_current_user_password(
    payload: UserPasswordChangeRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    if not verify_password(user.password_hash, payload.current_password):
        raise HTTPException(400, "Current password is incorrect.")
    user.password_hash = hash_password(payload.new_password)
    db.query(RefreshToken).filter(
        RefreshToken.user_id == user.id,
        RefreshToken.revoked_at.is_(None),
    ).update(
        {RefreshToken.revoked_at: datetime.now(timezone.utc)},
        synchronize_session=False,
    )
    db.commit()


@router.delete("/me", status_code=204)
def delete_current_user(
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    db.delete(user)
    db.commit()
    response.delete_cookie(
        "refresh_token",
        path="/",
        httponly=True,
        secure=settings.production,
        samesite="lax",
    )
    response.delete_cookie(
        "csrf_token",
        path="/",
        secure=settings.production,
        samesite="lax",
    )
    response.status_code = 204
    return response
