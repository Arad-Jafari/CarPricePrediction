from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import desc, asc
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import current_user
from app.models import Prediction, User
from app.schemas import InputModel, PredictionPage, PredictionResponse
from ml.inference import InferenceError

router = APIRouter(prefix="/predictions", tags=["predictions"])
predict_router = APIRouter(tags=["predictions"])


def _owned_prediction(db: Session, user_id: uuid.UUID, prediction_id: uuid.UUID) -> Prediction:
    prediction = db.query(Prediction).filter(
        Prediction.id == prediction_id, Prediction.user_id == user_id
    ).first()
    if prediction is None:
        raise HTTPException(404, "Prediction not found.")
    return prediction


def _create_prediction(
    payload: InputModel,
    request: Request,
    db: Session,
    user: User,
) -> Prediction:
    try:
        result = request.app.state.predictor.predict(payload.model_dump())
    except InferenceError as exc:
        raise HTTPException(422, str(exc)) from None
    prediction = Prediction(
        user_id=user.id,
        input_data=result["input_data"],
        predicted_price=result["predicted_price"],
        prediction_unit=result["prediction_unit"],
        model_version=result["model_version"],
    )
    db.add(prediction)
    db.commit()
    db.refresh(prediction)
    return prediction


@router.post("", response_model=PredictionResponse, status_code=201)
def create_prediction(
    payload: InputModel,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    return _create_prediction(payload, request, db, user)


@predict_router.post("/predict", response_model=PredictionResponse, status_code=201)
def predict(
    payload: InputModel,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    return _create_prediction(payload, request, db, user)


@router.get("", response_model=PredictionPage)
def prediction_history(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort: str = Query("desc", pattern="^(asc|desc)$"),
    from_date: datetime | None = Query(None),
    to_date: datetime | None = Query(None),
):
    query = db.query(Prediction).filter(Prediction.user_id == user.id)
    if from_date:
        query = query.filter(Prediction.created_at >= from_date)
    if to_date:
        query = query.filter(Prediction.created_at <= to_date)
    total = query.count()
    order = desc(Prediction.created_at) if sort == "desc" else asc(Prediction.created_at)
    items = (
        query.order_by(order, Prediction.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.delete("", status_code=204)
def clear_prediction_history(
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    db.query(Prediction).filter(Prediction.user_id == user.id).delete(synchronize_session=False)
    db.commit()
    response.status_code = 204
    return response


@router.get("/{prediction_id}", response_model=PredictionResponse)
def get_prediction(
    prediction_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    return _owned_prediction(db, user.id, prediction_id)


@router.delete("/{prediction_id}", status_code=204)
def delete_prediction(
    prediction_id: uuid.UUID,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    prediction = _owned_prediction(db, user.id, prediction_id)
    db.delete(prediction)
    db.commit()
    response.status_code = 204
    return response
