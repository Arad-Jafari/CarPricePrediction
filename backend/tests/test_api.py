from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from tests.conftest import auth_headers, register
from app.models import User
from sqlalchemy import Numeric


def valid_car():
    return {
        "year": 1399,
        "mileage": 50000,
        "trim": "تیپ 2",
        "transmission": "دنده ای",
        "body_status": "بدون رنگ",
        "color": "سفید",
    }


def test_model_features_and_prediction_integration(client):
    feature_contract = client.get("/api/features")
    assert feature_contract.status_code == 200
    metadata = feature_contract.json()
    assert set(metadata) == {"features", "target"}
    assert metadata["target"]["unit"] is None
    assert metadata["target"]["unit_note"].startswith("Source price units;")
    assert [feature["name"] for feature in metadata["features"]] == [
        "year",
        "mileage",
        "trim",
        "transmission",
        "body_status",
        "color",
    ]
    expected_feature_fields = {
        "name",
        "display_label",
        "type",
        "required",
        "minimum",
        "maximum",
        "unit",
        "supported_values",
        "constraint_note",
    }
    assert all(set(feature) == expected_feature_fields for feature in metadata["features"])
    assert client.get("/api/v1/features").json() == metadata
    assert client.get("/api/v1/model/info").json()["chat_assistant_available"] is False
    assert client.get("/api/v1/model/features").json() == metadata
    assert client.get("/api/v1/model/info").status_code == 200
    assert client.get("/api/v1/health").json() == {"status": "ok"}

    _, headers = auth_headers(client)
    response = client.post("/api/v1/predictions", json=valid_car(), headers=headers)
    assert response.status_code == 201, response.text
    prediction = response.json()
    assert prediction["id"]
    assert prediction["predicted_price"] > 0
    assert prediction["prediction_unit"].startswith("Source price units")
    assert prediction["model_version"]
    assert prediction["input_data"] == valid_car()
    history = client.get("/api/v1/predictions?page=1&page_size=1", headers=headers).json()
    assert history["items"][0]["id"] == prediction["id"]
    assert (history["total"], history["page"], history["page_size"]) == (1, 1, 1)


def test_versioned_predict_endpoint_uses_the_real_model(client):
    _, headers = auth_headers(client)
    response = client.post("/api/v1/predict", json=valid_car(), headers=headers)
    assert response.status_code == 201, response.text
    prediction = response.json()
    assert prediction["predicted_price"] > 0
    assert prediction["prediction_unit"].startswith("Source price units")
    assert prediction["input_data"] == valid_car()


def test_auth_refresh_rotation_profile_and_password(client):
    user = register(client, "  PERSON@Example.com ")
    assert user["user"]["email"] == "person@example.com"
    assert set(user["user"]) == {"id", "full_name", "email"}
    assert user["token_type"] == "bearer"
    old_refresh = client.cookies.get("refresh_token")
    csrf = client.cookies.get("csrf_token")
    response = client.post("/auth/refresh", headers={"X-CSRF-Token": csrf})
    assert response.status_code == 200
    assert set(response.json()) == {"access_token", "token_type"}
    assert client.cookies.get("refresh_token") != old_refresh

    replay = client.post(
        "/auth/refresh",
        cookies={"refresh_token": old_refresh, "csrf_token": csrf},
        headers={"X-CSRF-Token": csrf},
    )
    assert replay.status_code == 401
    assert client.post("/auth/refresh").status_code == 403

    headers = {"Authorization": f"Bearer {user['access_token']}"}
    profile = client.get("/auth/me", headers=headers)
    assert profile.status_code == 200
    assert profile.json()["email"] == "person@example.com"
    assert client.get("/users/me", headers=headers).json() == profile.json()
    changed = client.post(
        "/api/auth/password",
        json={
            "current_password": "a-very-long-password-123",
            "new_password": "another-very-long-password-123",
        },
        headers=headers,
    )
    assert changed.status_code == 204
    assert client.post(
        "/auth/login",
        json={"email": "person@example.com", "password": "a-very-long-password-123"},
    ).status_code == 401
    login = client.post(
        "/auth/login",
        json={"email": "person@example.com", "password": "another-very-long-password-123"},
    )
    assert login.status_code == 200
    access_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    profile_update = client.patch(
        "/api/auth/me", json={"email": "updated@example.com"}, headers=access_headers
    )
    assert profile_update.status_code == 200
    assert profile_update.json()["email"] == "updated@example.com"

    mismatch = client.post(
        "/api/v1/users/me/password",
        json={
            "current_password": "another-very-long-password-123",
            "new_password": "a-new-valid-password-123",
            "password_confirmation": "a-different-valid-password-123",
        },
        headers=access_headers,
    )
    assert mismatch.status_code == 422
    weak = client.post(
        "/api/v1/users/me/password",
        json={
            "current_password": "another-very-long-password-123",
            "new_password": "short",
            "password_confirmation": "short",
        },
        headers=access_headers,
    )
    assert weak.status_code == 422
    wrong_current = client.post(
        "/api/v1/users/me/password",
        json={
            "current_password": "not-the-current-password",
            "new_password": "a-new-valid-password-123",
            "password_confirmation": "a-new-valid-password-123",
        },
        headers=access_headers,
    )
    assert wrong_current.status_code == 400
    updated_password = client.post(
        "/api/v1/users/me/password",
        json={
            "current_password": "another-very-long-password-123",
            "new_password": "a-new-valid-password-123",
            "password_confirmation": "a-new-valid-password-123",
        },
        headers=access_headers,
    )
    assert updated_password.status_code == 204
    assert client.post(
        "/auth/login",
        json={"email": "updated@example.com", "password": "another-very-long-password-123"},
    ).status_code == 401
    assert client.post(
        "/auth/login",
        json={"email": "updated@example.com", "password": "a-new-valid-password-123"},
    ).status_code == 200


def test_logout_requires_csrf_and_clears_refresh_session(client):
    register(client)
    csrf = client.cookies.get("csrf_token")
    assert client.post("/api/auth/logout").status_code == 403
    response = client.post("/api/auth/logout", headers={"X-CSRF-Token": csrf})
    assert response.status_code == 204
    assert client.cookies.get("refresh_token") is None


def test_prediction_and_conversation_ownership(client):
    _, owner_headers = auth_headers(client, "owner@example.com")
    _, other_headers = auth_headers(client, "other@example.com")
    prediction = client.post("/api/predictions", json=valid_car(), headers=owner_headers).json()
    conversation = client.post(
        "/api/conversations", json={"title": "My car"}, headers=owner_headers
    ).json()["items"][0]

    assert client.get(f"/api/predictions/{prediction['id']}", headers=other_headers).status_code == 404
    assert client.delete(f"/api/predictions/{prediction['id']}", headers=other_headers).status_code == 404
    assert client.get(f"/api/conversations/{conversation['id']}", headers=other_headers).status_code == 404
    assert client.get(
        f"/api/conversations/{conversation['id']}/messages", headers=other_headers
    ).status_code == 404


def test_strict_input_and_chat_without_provider_persists_user_message(client):
    _, headers = auth_headers(client)
    malformed = valid_car()
    malformed["year"] = True
    assert client.post("/api/predictions", json=malformed, headers=headers).status_code == 422
    extra = valid_car()
    extra["model"] = "user-controlled"
    assert client.post("/api/predictions", json=extra, headers=headers).status_code == 422

    conversation = client.post("/api/conversations", json={}, headers=headers).json()["items"][0]
    unavailable = client.post(
        f"/api/conversations/{conversation['id']}/messages",
        json={"content": "What is my car worth?"},
        headers=headers,
    )
    assert unavailable.status_code == 201
    assert unavailable.json()["assistant_response_available"] is False
    assert [message["role"] for message in unavailable.json()["items"]] == ["user"]
    history = client.get(
        f"/api/conversations/{conversation['id']}/messages", headers=headers
    ).json()["items"]
    assert [message["role"] for message in history] == ["user"]
    assert history[0]["content"] == "What is my car worth?"


def test_configured_chat_provider_stores_and_searches_messages(client):
    _, headers = auth_headers(client)
    conversation = client.post(
        "/api/conversations", json={"title": "Price discussion"}, headers=headers
    ).json()["items"][0]

    class TestProvider:
        def generate_reply(self, messages):
            assert messages[-1] == {"role": "user", "content": "Tell me about this estimate"}
            return "The prediction is based on the submitted vehicle features."

    client.app.state.chat_provider = TestProvider()
    model_info = client.get("/api/v1/model/info")
    assert model_info.status_code == 200
    assert model_info.json()["chat_assistant_available"] is True
    sent = client.post(
        f"/api/conversations/{conversation['id']}/messages",
        json={"content": "Tell me about this estimate"},
        headers=headers,
    )
    assert sent.status_code == 201
    assert sent.json()["assistant_response_available"] is True
    assert [message["role"] for message in sent.json()["items"]] == ["user", "assistant"]
    history = client.get(
        f"/api/conversations/{conversation['id']}/messages", headers=headers
    ).json()
    assert [message["role"] for message in history["items"]] == ["user", "assistant"]
    search = client.get("/api/conversations?search=estimate", headers=headers)
    assert search.status_code == 200
    assert [item["id"] for item in search.json()["items"]] == [conversation["id"]]
    assert search.json()["total"] == 1


def test_conversation_list_total_counts_filtered_owned_results_not_loaded_page(client):
    _, owner_headers = auth_headers(client, "conversation-total-owner@example.com")
    _, other_headers = auth_headers(client, "conversation-total-other@example.com")
    created = [
        client.post(
            "/api/v1/conversations",
            json={"title": f"Owner discussion {index}"},
            headers=owner_headers,
        ).json()["items"][0]
        for index in range(3)
    ]
    client.post(
        "/api/v1/conversations",
        json={"title": "Owner unrelated"},
        headers=owner_headers,
    )
    client.post(
        "/api/v1/conversations",
        json={"title": "Owner discussion outsider"},
        headers=other_headers,
    )

    page = client.get(
        "/api/v1/conversations?search=Owner%20discussion&limit=1&offset=1",
        headers=owner_headers,
    )
    assert page.status_code == 200
    assert len(page.json()["items"]) == 1
    assert page.json()["total"] == 3
    assert page.json()["items"][0]["id"] in {item["id"] for item in created}


def test_clear_prediction_history_deletes_only_current_users_records(client):
    _, owner_headers = auth_headers(client, "history-owner@example.com")
    _, other_headers = auth_headers(client, "history-other@example.com")
    owner_prediction = client.post(
        "/api/v1/predictions", json=valid_car(), headers=owner_headers
    ).json()
    other_prediction = client.post(
        "/api/v1/predictions", json=valid_car(), headers=other_headers
    ).json()

    assert client.delete("/api/v1/predictions").status_code == 401
    cleared = client.delete("/api/v1/predictions", headers=owner_headers)
    assert cleared.status_code == 204
    assert client.get("/api/v1/predictions", headers=owner_headers).json()["total"] == 0
    assert client.get(
        f"/api/v1/predictions/{other_prediction['id']}", headers=other_headers
    ).status_code == 200
    assert client.get(
        f"/api/v1/predictions/{owner_prediction['id']}", headers=owner_headers
    ).status_code == 404


def test_account_delete_cascades_and_duplicate_email(client):
    _, headers = auth_headers(client, "delete@example.com")
    prediction = client.post("/api/predictions", json=valid_car(), headers=headers).json()
    assert client.post(
        "/api/auth/register",
        json={
            "full_name": "Delete Person",
            "email": "DELETE@example.com",
            "password": "a-very-long-password-123",
            "password_confirmation": "a-very-long-password-123",
        },
    ).status_code == 409
    assert client.delete("/api/auth/me", headers=headers).status_code == 204
    assert client.get("/api/predictions", headers=headers).status_code == 401
    assert client.post(
        "/api/auth/register",
        json={
            "full_name": "Delete Person",
            "email": "delete@example.com",
            "password": "a-very-long-password-123",
            "password_confirmation": "a-very-long-password-123",
        },
    ).status_code == 201


def test_full_name_update_and_account_deletion_clear_cookies_and_owned_data(client):
    registration, headers = auth_headers(client, "profile-delete@example.com")
    prediction = client.post(
        "/api/v1/predictions", json=valid_car(), headers=headers
    ).json()
    conversation = client.post(
        "/api/v1/conversations", json={"title": "Keep no data"}, headers=headers
    ).json()["items"][0]
    client.post(
        f"/api/v1/conversations/{conversation['id']}/messages",
        json={"content": "My note"},
        headers=headers,
    )

    updated = client.patch(
        "/api/v1/users/me",
        json={"full_name": "Updated Name"},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json() == {
        "id": registration["user"]["id"],
        "full_name": "Updated Name",
        "email": "profile-delete@example.com",
    }

    deleted = client.delete("/api/v1/users/me", headers=headers)
    assert deleted.status_code == 204
    assert "refresh_token" not in client.cookies
    assert "csrf_token" not in client.cookies
    assert client.get("/api/v1/users/me", headers=headers).status_code == 401
    with Session(client.app.state.database_engine) as db:
        from app.models import Conversation, Message, Prediction, RefreshToken

        assert db.get(User, uuid.UUID(registration["user"]["id"])) is None
        assert db.query(User).count() == 0
        assert db.query(Prediction).count() == 0
        assert db.query(Conversation).count() == 0
        assert db.query(Message).count() == 0
        assert db.query(RefreshToken).count() == 0
    assert client.get(f"/api/v1/predictions/{prediction['id']}", headers=headers).status_code == 401


def test_inactive_accounts_cannot_login_or_use_existing_access_token(client):
    registration, headers = auth_headers(client, "inactive@example.com")
    user_id = registration["user"]["id"]
    with Session(client.app.state.database_engine) as db:
        user = db.get(User, uuid.UUID(user_id))
        user.is_active = False
        db.commit()

    assert client.post(
        "/api/v1/auth/login",
        json={"email": "inactive@example.com", "password": "a-very-long-password-123"},
    ).status_code == 401
    assert client.get("/api/v1/users/me", headers=headers).status_code == 401
    assert client.post(
        "/api/v1/auth/refresh",
        headers={"X-CSRF-Token": client.cookies.get("csrf_token")},
    ).status_code == 401


def test_registration_rejects_invalid_email(client):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Invalid Email",
            "email": "not-an-email",
            "password": "a-very-long-password-123",
            "password_confirmation": "a-very-long-password-123",
        },
    )
    assert response.status_code == 422


def test_message_metadata_and_system_role_are_supported(client):
    _, headers = auth_headers(client)
    conversation = client.post(
        "/api/v1/conversations", json={"title": "Metadata"}, headers=headers
    ).json()["items"][0]
    message = client.post(
        f"/api/v1/conversations/{conversation['id']}/messages",
        json={"content": "A note"},
        headers=headers,
    ).json()["items"][0]
    assert message["role"] == "user"

    with Session(client.app.state.database_engine) as db:
        from app.models import Message

        record = Message(
            conversation_id=uuid.UUID(conversation["id"]),
            role="system",
            content="System context",
            message_metadata={"source": "test"},
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        assert record.message_metadata == {"source": "test"}

    messages = client.get(
        f"/api/v1/conversations/{conversation['id']}/messages", headers=headers
    ).json()["items"]
    assert any(item["role"] == "system" and item["message_metadata"] == {"source": "test"} for item in messages)


def test_prediction_price_uses_decimal_database_type():
    from app.models import Prediction

    assert isinstance(Prediction.__table__.c.predicted_price.type, Numeric)
    assert Prediction.__table__.c.predicted_price.type.precision == 16
