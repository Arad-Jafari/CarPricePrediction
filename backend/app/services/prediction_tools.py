from __future__ import annotations

import uuid

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models import Prediction
from ml.inference import FEATURE_CONTRACT


def _prediction_payload(prediction: Prediction) -> dict:
    return {
        "id": str(prediction.id),
        "input_data": prediction.input_data,
        "predicted_price": float(prediction.predicted_price),
        "prediction_unit": prediction.prediction_unit,
        "model_version": prediction.model_version,
        "created_at": prediction.created_at.isoformat() if prediction.created_at else None,
    }


def get_latest_user_prediction(db: Session, user_id: uuid.UUID) -> dict | None:
    prediction = (
        db.query(Prediction)
        .filter(Prediction.user_id == user_id)
        .order_by(desc(Prediction.created_at), desc(Prediction.id))
        .first()
    )
    return _prediction_payload(prediction) if prediction else None


def get_user_prediction(
    db: Session,
    user_id: uuid.UUID,
    prediction_id: uuid.UUID,
) -> dict | None:
    prediction = (
        db.query(Prediction)
        .filter(Prediction.id == prediction_id, Prediction.user_id == user_id)
        .first()
    )
    return _prediction_payload(prediction) if prediction else None


def get_user_prediction_history(
    db: Session,
    user_id: uuid.UUID,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    if not 1 <= limit <= 100 or offset < 0:
        raise ValueError("Prediction history limit must be 1..100 and offset must be non-negative.")
    query = db.query(Prediction).filter(Prediction.user_id == user_id)
    return {
        "items": [
            _prediction_payload(item)
            for item in query.order_by(desc(Prediction.created_at), desc(Prediction.id))
            .offset(offset)
            .limit(limit)
            .all()
        ],
        "total": query.count(),
        "limit": limit,
        "offset": offset,
    }


def get_prediction_model_info(predictor) -> dict:
    return {
        "vehicle_model": FEATURE_CONTRACT["vehicle_model"],
        "model_version": getattr(predictor, "model_version", None),
        "target": FEATURE_CONTRACT["target"],
    }
