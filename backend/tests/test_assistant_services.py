from __future__ import annotations

import uuid

import pytest

from app.config import REPOSITORY_ROOT
from app.models import User
from app.services.assistant import (
    OUT_OF_SCOPE_RESPONSE,
    build_assistant_messages,
    is_in_scope_request,
    load_system_prompt,
)
from app.services.market_data import CsvMarketDataProvider
from app.services.prediction_tools import (
    get_latest_user_prediction,
    get_user_prediction,
    get_user_prediction_history,
)
from tests.conftest import auth_headers


def valid_car():
    return {
        "year": 1399,
        "mileage": 50000,
        "trim": "تیپ 2",
        "transmission": "دنده ای",
        "body_status": "بدون رنگ",
        "color": "سفید",
    }


def test_prompt_scope_and_bounded_conversation_context():
    prompt = load_system_prompt()
    assert "Never invent prices" in prompt
    assert "Never claim access to live Bama data" in prompt
    assert is_in_scope_request("Explain my Peugeot 206 estimate.")
    assert not is_in_scope_request("Write a sorting algorithm.")
    assert "car price predictions" in OUT_OF_SCOPE_RESPONSE

    messages = build_assistant_messages(
        [
            {"role": "user", "content": "old question"},
            {"role": "assistant", "content": "old answer"},
            {"role": "user", "content": "recent question"},
            {"role": "assistant", "content": "recent answer"},
        ],
        "What affects car prices?",
        max_history_messages=2,
        authorized_context='{"prediction": "private to current user"}',
        system_prompt="test system prompt",
    )
    assert [message["role"] for message in messages] == [
        "system",
        "system",
        "user",
        "assistant",
        "user",
    ]
    assert messages[0]["content"] == "test system prompt"
    assert "private to current user" in messages[1]["content"]
    assert messages[-3]["content"] == "recent question"
    assert messages[-1]["content"] == "What affects car prices?"


def test_market_data_provider_uses_existing_csv_fields_and_structured_filters():
    path = REPOSITORY_ROOT / "ml" / "data" / "cleaned_data" / "cleaned_dataset.csv"
    provider = CsvMarketDataProvider(path)
    sample = provider.get_listing("1")
    assert sample is not None
    assert set(sample) == {
        "model",
        "year",
        "mileage",
        "trim",
        "transmission",
        "body_status",
        "color",
        "modified_date",
        "price",
        "source_id",
    }
    matches = provider.search_listings(
        {"model": sample["model"], "year": int(sample["year"])},
        limit=10,
    )
    assert matches
    assert all(item["model"] == sample["model"] for item in matches)
    assert all(int(item["year"]) == int(sample["year"]) for item in matches)
    with pytest.raises(ValueError, match="Unsupported"):
        provider.search_listings({"owner_id": "another-user"})
    with pytest.raises(ValueError, match="integers"):
        provider.search_listings({"min_mileage": "high"})


def test_prediction_tools_are_scoped_to_the_authenticated_user(client):
    _, owner_headers = auth_headers(client, "tools-owner@example.com")
    auth_headers(client, "tools-other@example.com")
    saved = client.post(
        "/api/predictions",
        json=valid_car(),
        headers=owner_headers,
    ).json()
    prediction_id = uuid.UUID(saved["id"])

    with client.app.state.session_factory() as db:
        owner_id = db.query(User).filter_by(email="tools-owner@example.com").first().id
        other_id = db.query(User).filter_by(email="tools-other@example.com").first().id

    with client.app.state.session_factory() as db:
        latest = get_latest_user_prediction(db, owner_id)
        assert latest is not None
        assert latest["id"] == saved["id"]
        assert get_user_prediction(db, owner_id, prediction_id)["id"] == saved["id"]
        assert get_user_prediction(db, other_id, prediction_id) is None
        assert get_user_prediction_history(db, owner_id, limit=1)["total"] == 1
        with pytest.raises(ValueError, match="limit"):
            get_user_prediction_history(db, owner_id, limit=101)


def test_chat_receives_only_the_authenticated_users_latest_prediction(client):
    _, owner_headers = auth_headers(client, "prompt-context-owner@example.com")
    _, other_headers = auth_headers(client, "prompt-context-other@example.com")
    owner_prediction = client.post(
        "/api/predictions", json=valid_car(), headers=owner_headers
    ).json()
    client.post("/api/predictions", json={**valid_car(), "mileage": 70000}, headers=other_headers)
    conversation_id = client.post(
        "/api/conversations", json={}, headers=owner_headers
    ).json()["items"][0]["id"]

    class ContextProvider:
        def generate_reply(self, messages):
            self.messages = messages
            return "Your saved estimate is available in your history."

    provider = ContextProvider()
    client.app.state.chat_provider = provider
    response = client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={"content": "What is my latest price prediction?"},
        headers=owner_headers,
    )
    assert response.status_code == 201
    context = provider.messages[1]["content"]
    assert owner_prediction["id"] in context
    assert str(owner_prediction["predicted_price"]) in context
    assert "another user's" not in context
