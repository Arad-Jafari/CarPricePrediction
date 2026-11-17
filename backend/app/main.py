from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from app.chat import ChatProviderError, OllamaChatProvider, load_chat_provider
from app.config import settings
from app.database import engine, get_db, init_db
from app.errors import install_error_handlers
from app.routes import auth, conversations, predictions, users
from app.schemas import get_public_feature_contract
from ml.inference import CarPricePredictor, FEATURE_CONTRACT

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


def create_app(predictor=None, chat_provider=None, database_engine=None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI):
        if application.state.database_engine is not None:
            init_db(application.state.database_engine)
        else:
            init_db()
        if application.state.predictor is None:
            application.state.predictor = CarPricePredictor(
                model_path=settings.model_path,
                preprocessor_path=settings.preprocessor_path,
            )
        if application.state.chat_provider is None and settings.chat_provider:
            application.state.chat_provider = load_chat_provider(settings.chat_provider)
        elif application.state.chat_provider is None and (
            settings.ai_enabled or os.getenv("AUTO_LOAD_OLLAMA", "false").lower() == "true"
        ):
            application.state.chat_provider = OllamaChatProvider(
                base_url=settings.ollama_base_url,
                default_model=settings.default_model,
                context_window=settings.ai_context_window,
                temperature=settings.ai_temperature,
            )
        yield

    application = FastAPI(title="Peugeot 206 Prediction API", version="1.0.0", lifespan=lifespan)
    application.state.predictor = predictor
    application.state.chat_provider = chat_provider
    application.state.database_engine = database_engine or engine
    application.state.session_factory = sessionmaker(
        bind=application.state.database_engine,
        autoflush=False,
        expire_on_commit=False,
    )
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
        provider = application.state.chat_provider
        model_name = getattr(provider, "default_model", None) if provider is not None else settings.default_model
        available = provider is not None
        models: list[str] = []
        if provider is not None:
            health_check = getattr(provider, "health_check", None)
            list_models = getattr(provider, "list_models", None)
            try:
                if callable(health_check):
                    available = bool(health_check())
                if callable(list_models):
                    models = list_models()
                    available = available and bool(models)
            except ChatProviderError as exc:
                available = False
                logging.getLogger("car_estimation.api").warning(
                    "Chat provider health check failed error_type=%s",
                    type(exc).__name__,
                )
        return {
            "vehicle_model": FEATURE_CONTRACT["vehicle_model"],
            "model_version": application.state.predictor.model_version,
            "chat_assistant_available": available,
            "chat_model": model_name,
            "chat_models": models,
            "chat_provider_configured": provider is not None,
            "ollama_base_url": settings.ollama_base_url,
            "target": get_public_feature_contract()["target"],
        }

    @application.get("/api/chat/models", tags=["chat"])
    @application.get("/api/v1/chat/models", tags=["chat"])
    def chat_models():
        provider = application.state.chat_provider
        if provider is None:
            return {
                "available": False,
                "selected_model": settings.default_model,
                "models": [],
            }
        list_models = getattr(provider, "list_models", None)
        if not callable(list_models):
            return {
                "available": True,
                "selected_model": getattr(provider, "default_model", settings.default_model),
                "models": [],
            }
        try:
            models = list_models()
        except ChatProviderError as exc:
            raise HTTPException(503, "The local AI provider is unavailable.") from exc
        return {
            "available": bool(models),
            "selected_model": getattr(provider, "default_model", settings.default_model),
            "models": models,
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
