from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import create_app
from app.routes.auth import _attempts, _attempts_lock
from ml.inference import CarPricePredictor


@pytest.fixture(scope="session")
def predictor():
    return CarPricePredictor()


@pytest.fixture()
def client(predictor):
    with _attempts_lock:
        _attempts.clear()
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(test_engine, "connect")
    def enable_foreign_keys(connection, _):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(test_engine)
    testing_sessions = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)

    def override_get_db():
        db = testing_sessions()
        try:
            yield db
        finally:
            db.close()

    application = create_app(predictor=predictor, database_engine=test_engine)
    application.dependency_overrides[get_db] = override_get_db
    with TestClient(application) as test_client:
        yield test_client
    application.dependency_overrides.clear()
    Base.metadata.drop_all(test_engine)
    test_engine.dispose()


def register(client: TestClient, email="person@example.com"):
    response = client.post(
        "/auth/register",
        json={
            "full_name": "Test Person",
            "email": email,
            "password": "a-very-long-password-123",
            "password_confirmation": "a-very-long-password-123",
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["full_name"] == "Test Person"
    login_response = client.post(
        "/auth/login",
        json={"email": email.strip().lower(), "password": "a-very-long-password-123"},
    )
    assert login_response.status_code == 200, login_response.text
    assert set(login_response.json()) == {"access_token", "token_type", "user"}
    return login_response.json()


def auth_headers(client: TestClient, email="person@example.com"):
    data = register(client, email)
    return data, {"Authorization": f"Bearer {data['access_token']}"}
