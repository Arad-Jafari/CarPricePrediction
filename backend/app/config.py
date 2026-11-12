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
    return Settings(
        database_url=database_url,
        jwt_secret_key=secret,
        access_token_minutes=int(os.getenv("ACCESS_TOKEN_MINUTES", "15")),
        refresh_token_days=int(os.getenv("REFRESH_TOKEN_DAYS", "30")),
        environment=environment,
        cors_origins=origins,
        chat_provider=os.getenv("CHAT_PROVIDER") or None,
        model_path=Path(os.getenv("MODEL_PATH", str(DEFAULT_MODEL_PATH))),
        preprocessor_path=Path(os.getenv("PREPROCESSOR_PATH", str(DEFAULT_PREPROCESSOR_PATH))),
        jwt_algorithm=jwt_algorithm,
    )


settings = load_settings()
