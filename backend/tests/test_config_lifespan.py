from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine

import app.main as main_module
import app.dependencies as dependencies_module
import app.security as security_module
from app.config import DEFAULT_MODEL_PATH, DEFAULT_PREPROCESSOR_PATH, load_settings
from app.main import create_app
import jwt


def _clear_settings(monkeypatch):
    for key in (
        "ENVIRONMENT",
        "JWT_SECRET_KEY",
        "DATABASE_URL",
        "POSTGRES_HOST",
        "POSTGRES_PORT",
        "POSTGRES_DB",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "ACCESS_TOKEN_MINUTES",
        "REFRESH_TOKEN_DAYS",
        "CORS_ORIGINS",
        "CHAT_PROVIDER",
        "MODEL_PATH",
        "PREPROCESSOR_PATH",
        "JWT_ALGORITHM",
    ):
        monkeypatch.delenv(key, raising=False)


def test_production_requires_strong_secret_and_postgresql(monkeypatch):
    _clear_settings(monkeypatch)
    monkeypatch.setenv("ENVIRONMENT", "production")
    with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
        load_settings()

    monkeypatch.setenv("JWT_SECRET_KEY", "short")
    with pytest.raises(RuntimeError, match="32 bytes"):
        load_settings()

    monkeypatch.setenv("JWT_SECRET_KEY", "a" * 40)
    with pytest.raises(RuntimeError, match="32 bytes"):
        load_settings()

    monkeypatch.setenv("JWT_SECRET_KEY", "a-random-production-signing-secret-with-adequate-length")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./prod.db")
    with pytest.raises(RuntimeError, match="PostgreSQL"):
        load_settings()

    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@db:5432/cars")
    assert load_settings().database_url == "postgresql+psycopg://user:pass@db:5432/cars"


def test_production_compose_postgres_environment_variables(monkeypatch):
    _clear_settings(monkeypatch)
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("JWT_SECRET_KEY", "a-random-production-signing-secret-with-adequate-length")
    monkeypatch.setenv("POSTGRES_HOST", "db")
    monkeypatch.setenv("POSTGRES_PORT", "5433")
    monkeypatch.setenv("POSTGRES_DB", "vehicle-data")
    monkeypatch.setenv("POSTGRES_USER", "service user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "p@ss/word")

    settings = load_settings()
    assert settings.database_url == (
        "postgresql+psycopg://service+user:p%40ss%2Fword@db:5433/vehicle-data"
    )
    assert settings.production


def test_model_path_and_jwt_algorithm_settings(monkeypatch):
    _clear_settings(monkeypatch)
    defaults = load_settings()
    assert defaults.model_path == DEFAULT_MODEL_PATH
    assert defaults.preprocessor_path == DEFAULT_PREPROCESSOR_PATH
    assert defaults.jwt_algorithm == "HS256"

    monkeypatch.setenv("MODEL_PATH", "weights/model.pkl")
    monkeypatch.setenv("PREPROCESSOR_PATH", "weights/preprocessor.pkl")
    settings = load_settings()
    assert str(settings.model_path) == "weights\\model.pkl"
    assert str(settings.preprocessor_path) == "weights\\preprocessor.pkl"
    assert settings.jwt_algorithm == "HS256"

    monkeypatch.setenv("JWT_ALGORITHM", "HS512")
    assert load_settings().jwt_algorithm == "HS512"
    monkeypatch.setenv("JWT_ALGORITHM", "none")
    with pytest.raises(RuntimeError, match="JWT_ALGORITHM"):
        load_settings()

    monkeypatch.setenv("JWT_ALGORITHM", "HS512")
    monkeypatch.setenv("JWT_SECRET_KEY", "a-valid-test-signing-secret-for-hs512-algorithm")
    configured = load_settings()
    monkeypatch.setattr(security_module, "settings", configured)
    monkeypatch.setattr(dependencies_module, "settings", configured)
    token = security_module.create_access_token(__import__("uuid").uuid4())
    assert jwt.decode(
        token,
        configured.jwt_secret_key,
        algorithms=[configured.jwt_algorithm],
    )["type"] == "access"


def test_predictor_is_initialized_during_lifespan_and_can_be_injected(monkeypatch):
    constructions = []
    assert main_module.app.state.predictor is None

    class FakePredictor:
        model_version = "test-version"

        def __init__(self, model_path, preprocessor_path):
            constructions.append((model_path, preprocessor_path))

    monkeypatch.setattr(main_module, "CarPricePredictor", FakePredictor)
    monkeypatch.setattr(
        main_module,
        "settings",
        replace(
            main_module.settings,
            model_path=Path("custom/model.pkl"),
            preprocessor_path=Path("custom/preprocessor.pkl"),
        ),
    )
    test_engine = create_engine("sqlite://")
    application = create_app(database_engine=test_engine)
    assert application.state.predictor is None
    assert constructions == []

    with TestClient(application) as client:
        assert constructions == [
            (
                Path("custom/model.pkl"),
                Path("custom/preprocessor.pkl"),
            )
        ]
        model_info = client.get("/api/v1/model/info").json()
        assert model_info["model_version"] == "test-version"
        assert model_info["chat_assistant_available"] is False

    injected = FakePredictor(
        Path("injected/model.pkl"),
        Path("injected/preprocessor.pkl"),
    )
    second_app = create_app(predictor=injected, database_engine=test_engine)
    assert second_app.state.predictor is injected
    assert len(constructions) == 2
    test_engine.dispose()
