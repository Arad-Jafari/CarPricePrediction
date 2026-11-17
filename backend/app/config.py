from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote_plus

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL_PATH = REPOSITORY_ROOT / "ml" / "artifacts" / "CarPredictionModel.pkl"
DEFAULT_PREPROCESSOR_PATH = REPOSITORY_ROOT / "ml" / "artifacts" / "CarPreprocessor.pkl"


SUPPORTED_JWT_ALGORITHMS = {"HS256": 32, "HS384": 48, "HS512": 64}


@dataclass(frozen=True)
class Settings:
    database_url: str
    jwt_secret_key: str
    access_token_minutes: int
    refresh_token_days: int
    environment: str
    cors_origins: tuple[str, ...]
    chat_provider: str | None
    ollama_base_url: str
    default_model: str
    ai_enabled: bool
    ai_context_window: int
    ai_max_history_messages: int
    ai_temperature: float
    ai_enable_rag: bool
    ai_enable_tools: bool
    ai_storage_path: Path
    ai_vector_db_path: Path
    embedding_model: str
    embedding_dimension: int
    model_path: Path
    preprocessor_path: Path
    jwt_algorithm: str

    @property
    def production(self) -> bool:
        return self.environment.lower() == "production"


def load_settings() -> Settings:
    environment = os.getenv("ENVIRONMENT", "development")
    production = environment.lower() == "production"
    jwt_algorithm = os.getenv("JWT_ALGORITHM", "HS256").upper()
    if jwt_algorithm not in SUPPORTED_JWT_ALGORITHMS:
        raise RuntimeError("JWT_ALGORITHM must be one of HS256, HS384, or HS512.")
    secret = os.getenv("JWT_SECRET_KEY")
    if not secret:
        if production:
            raise RuntimeError("JWT_SECRET_KEY must be configured in production.")
        secret = secrets.token_urlsafe(48)
    insecure_secret = (
        secret.lower() in {"changeme", "change-me", "secret"}
        or "replace-with" in secret.lower()
        or len(set(secret)) < 8
    )
    minimum_secret_bytes = SUPPORTED_JWT_ALGORITHMS[jwt_algorithm]
    if production and (len(secret.encode("utf-8")) < minimum_secret_bytes or insecure_secret):
        raise RuntimeError(
            f"JWT_SECRET_KEY must contain at least {minimum_secret_bytes} bytes for "
            f"{jwt_algorithm} in production."
        )
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        postgres_host = os.getenv("POSTGRES_HOST")
        postgres_user = os.getenv("POSTGRES_USER")
        postgres_password = os.getenv("POSTGRES_PASSWORD")
        postgres_db = os.getenv("POSTGRES_DB")
        if all((postgres_host, postgres_user, postgres_password, postgres_db)):
            postgres_port = os.getenv("POSTGRES_PORT", "5432")
            database_url = (
                "postgresql+psycopg://"
                f"{quote_plus(postgres_user)}:{quote_plus(postgres_password)}"
                f"@{postgres_host}:{postgres_port}/{quote_plus(postgres_db)}"
            )
        else:
            database_url = "sqlite:///./backend.db"
    if production and not database_url.startswith(("postgresql://", "postgresql+psycopg://")):
        raise RuntimeError("Production DATABASE_URL must use PostgreSQL.")
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    origins = tuple(
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
        if origin.strip()
    )
    ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").strip() or "http://127.0.0.1:11434"

    def boolean_setting(name: str, default: bool) -> bool:
        value = os.getenv(name)
        if value is None:
            return default
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
        raise RuntimeError(f"{name} must be a boolean value.")

    def storage_path(name: str, default: str) -> Path:
        path = Path(os.getenv(name, default))
        return path if path.is_absolute() else REPOSITORY_ROOT / path

    context_window = int(os.getenv("AI_CONTEXT_WINDOW", "2048"))
    max_history_messages = int(os.getenv("AI_MAX_HISTORY_MESSAGES", "8"))
    temperature = float(os.getenv("AI_TEMPERATURE", "0.3"))
    embedding_dimension = int(os.getenv("EMBEDDING_DIMENSION", "768"))
    if context_window < 256:
        raise RuntimeError("AI_CONTEXT_WINDOW must be at least 256.")
    if max_history_messages < 1:
        raise RuntimeError("AI_MAX_HISTORY_MESSAGES must be at least 1.")
    if not 0 <= temperature <= 2:
        raise RuntimeError("AI_TEMPERATURE must be between 0 and 2.")
    if embedding_dimension < 1:
        raise RuntimeError("EMBEDDING_DIMENSION must be a positive integer.")

    return Settings(
        database_url=database_url,
        jwt_secret_key=secret,
        access_token_minutes=int(os.getenv("ACCESS_TOKEN_MINUTES", "15")),
        refresh_token_days=int(os.getenv("REFRESH_TOKEN_DAYS", "30")),
        environment=environment,
        cors_origins=origins,
        chat_provider=os.getenv("CHAT_PROVIDER") or None,
        ollama_base_url=ollama_base_url,
        default_model=(
            os.getenv("OLLAMA_CHAT_MODEL")
            or os.getenv("DEFAULT_MODEL")
            or "gemma3:1b"
        ).strip(),
        ai_enabled=boolean_setting("AI_ENABLED", False),
        ai_context_window=context_window,
        ai_max_history_messages=max_history_messages,
        ai_temperature=temperature,
        ai_enable_rag=boolean_setting("AI_ENABLE_RAG", False),
        ai_enable_tools=boolean_setting("AI_ENABLE_TOOLS", True),
        ai_storage_path=storage_path("AI_STORAGE_PATH", "local_data"),
        ai_vector_db_path=storage_path("AI_VECTOR_DB_PATH", "local_data/chroma"),
        embedding_model=os.getenv("EMBEDDING_MODEL", "embeddinggemma").strip() or "embeddinggemma",
        embedding_dimension=embedding_dimension,
        model_path=Path(os.getenv("MODEL_PATH", str(DEFAULT_MODEL_PATH))),
        preprocessor_path=Path(os.getenv("PREPROCESSOR_PATH", str(DEFAULT_PREPROCESSOR_PATH))),
        jwt_algorithm=jwt_algorithm,
    )


settings = load_settings()
