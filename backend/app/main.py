from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from app.chat import load_chat_provider
from app.config import settings
from app.database import engine, get_db
from app.errors import install_error_handlers
from app.routes import auth, conversations, predictions, users
from app.schemas import get_public_feature_contract
from ml.inference import CarPricePredictor, FEATURE_CONTRACT

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


def create_app(predictor=None, chat_provider=None, database_engine=None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI):
        if application.state.predictor is None:
            application.state.predictor = CarPricePredictor(
                model_path=settings.model_path,
                preprocessor_path=settings.preprocessor_path,
            )
        if application.state.chat_provider is None and settings.chat_provider:
            application.state.chat_provider = load_chat_provider(settings.chat_provider)
        yield

    application = FastAPI(title="Peugeot 206 Prediction API", version="1.0.0", lifespan=lifespan)
    application.state.predictor = predictor
    application.state.chat_provider = chat_provider
    application.state.database_engine = database_engine or engine
    if database_engine is not None and database_engine is not engine:
        application_sessions = sessionmaker(
            bind=database_engine, autoflush=False, expire_on_commit=False
        )

        def application_db():
            db = application_sessions()
            try:
                yield db
            finally:
                db.close()

        application.dependency_overrides[get_db] = application_db
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-CSRF-Token"],
    )
    install_error_handlers(application)
    for route in (auth.router, predictions.router, conversations.router, users.router):
        application.include_router(route)
        application.include_router(route, prefix="/api")
        application.include_router(route, prefix="/api/v1")
    application.include_router(predictions.predict_router, prefix="/api/v1")

    @application.get("/api/health", tags=["service"])
    @application.get("/api/v1/health", tags=["service"])
    def health():
        from sqlalchemy.orm import Session

        with Session(application.state.database_engine) as db:
            db.execute(text("SELECT 1"))
        return {"status": "ok"}

    @application.get("/api/model", tags=["model"])
    @application.get("/api/v1/model/info", tags=["model"])
    def model_info():
        return {
            "vehicle_model": FEATURE_CONTRACT["vehicle_model"],
            "model_version": application.state.predictor.model_version,
            "chat_assistant_available": application.state.chat_provider is not None,
            "target": get_public_feature_contract()["target"],
        }

    @application.get("/api/features", tags=["model"])
    @application.get("/api/v1/model/features", tags=["model"])
    def features():
        return get_public_feature_contract()

    @application.get("/api/v1/features", tags=["model"])
    def versioned_features():
        return get_public_feature_contract()

    return application


app = create_app()
