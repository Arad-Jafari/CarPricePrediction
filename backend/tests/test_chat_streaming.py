from __future__ import annotations

import asyncio
import uuid

from app.models import Message
from app.services.streaming import stream_assistant_events
from tests.conftest import auth_headers


class MockStreamingProvider:
    default_model = "mock-model"

    def __init__(self, chunks=("A", " real response."), fail_after_first=False):
        self.chunks = chunks
        self.fail_after_first = fail_after_first
        self.closed = False

    def list_models(self):
        return ["mock-model", "alternate-model"]

    def health_check(self):
        return True

    def generate_reply(self, messages):
        return "A mocked response."

    async def stream(self, messages, model=None):
        try:
            assert model in {"mock-model", "alternate-model"}
            assert messages[0]["role"] == "system"
            for index, chunk in enumerate(self.chunks):
                yield chunk
                if self.fail_after_first and index == 0:
                    raise RuntimeError("mock stream failure")
        finally:
            self.closed = True


def _create_conversation(client, headers):
    response = client.post("/api/conversations", json={}, headers=headers)
    assert response.status_code == 201
    return response.json()["items"][0]["id"]


def test_stream_endpoint_persists_completed_provider_output(client):
    _, headers = auth_headers(client, "stream-complete@example.com")
    conversation_id = _create_conversation(client, headers)
    provider = MockStreamingProvider()
    client.app.state.chat_provider = provider

    with client.stream(
        "POST",
        f"/api/conversations/{conversation_id}/messages/stream",
        json={"content": "What affects Peugeot 206 prices?"},
        headers=headers,
    ) as response:
        body = response.read().decode()

    assert response.status_code == 200
    assert "event: token" in body
    assert '"token": "A"' in body
    assert "event: done" in body
    history = client.get(
        f"/api/conversations/{conversation_id}/messages", headers=headers
    ).json()["items"]
    assert [item["role"] for item in history] == ["user", "assistant"]
    assert history[1]["content"] == "A real response."
    assert history[1]["message_metadata"]["status"] == "complete"
    assert provider.closed


def test_stream_failure_emits_error_and_persists_interrupted_partial(client):
    _, headers = auth_headers(client, "stream-error@example.com")
    conversation_id = _create_conversation(client, headers)
    client.app.state.chat_provider = MockStreamingProvider(fail_after_first=True)

    with client.stream(
        "POST",
        f"/api/conversations/{conversation_id}/messages/stream",
        json={"content": "Explain Peugeot 206 mileage."},
        headers=headers,
    ) as response:
        body = response.read().decode()

    assert response.status_code == 200
    assert "event: error" in body
    history = client.get(
        f"/api/conversations/{conversation_id}/messages", headers=headers
    ).json()["items"]
    assert [item["role"] for item in history] == ["user", "assistant"]
    assert history[1]["content"] == "A"
    assert history[1]["message_metadata"]["status"] == "interrupted"


def test_closing_stream_propagates_cancellation_and_persists_partial(client):
    _, headers = auth_headers(client, "stream-cancel@example.com")
    conversation_id = _create_conversation(client, headers)
    saved_user = client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={"content": "How does a Peugeot 206 estimate work?"},
        headers=headers,
    ).json()["items"][0]
    provider = MockStreamingProvider(chunks=("partial", " not consumed"))

    async def cancel_after_first_token():
        events = stream_assistant_events(
            provider,
            [
                {"role": "system", "content": "Test assistant system prompt."},
                {"role": "user", "content": "How does a Peugeot 206 estimate work?"},
            ],
            client.app.state.session_factory,
            uuid.UUID(conversation_id),
            uuid.UUID(saved_user["id"]),
            "mock-model",
        )
        assert "event: start" in await anext(events)
        assert "event: token" in await anext(events)
        await events.aclose()

    asyncio.run(cancel_after_first_token())
    with client.app.state.session_factory() as db:
        history = (
            db.query(Message)
            .filter(Message.conversation_id == uuid.UUID(conversation_id))
            .order_by(Message.created_at, Message.id)
            .all()
        )
    assert [item.role for item in history] == ["user", "assistant"]
    assert history[1].content == "partial"
    assert history[1].message_metadata["status"] == "interrupted"
    assert provider.closed


def test_model_list_selection_scope_policy_and_regeneration(client):
    _, headers = auth_headers(client, "stream-controls@example.com")
    conversation_id = _create_conversation(client, headers)
    provider = MockStreamingProvider()
    client.app.state.chat_provider = provider

    model_info = client.get("/api/v1/model/info")
    assert model_info.json()["chat_assistant_available"] is True
    assert model_info.json()["chat_models"] == ["mock-model", "alternate-model"]
    assert client.get("/api/v1/chat/models").json()["selected_model"] == "mock-model"

    invalid_model = client.post(
        f"/api/conversations/{conversation_id}/messages/stream",
        json={"content": "What affects Peugeot prices?", "model": "not-installed"},
        headers=headers,
    )
    assert invalid_model.status_code == 422
    assert client.get(
        f"/api/conversations/{conversation_id}/messages", headers=headers
    ).json()["items"] == []

    out_of_scope = client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={"content": "Write me a poem about astronomy."},
        headers=headers,
    )
    assert out_of_scope.status_code == 201
    assert out_of_scope.json()["items"][1]["content"].startswith(
        "I'm designed to help with car price predictions"
    )

    with client.stream(
        "POST",
        f"/api/conversations/{conversation_id}/messages/stream",
        json={"content": "Explain Peugeot 206 price factors."},
        headers=headers,
    ) as response:
        response.read()
    messages = client.get(
        f"/api/conversations/{conversation_id}/messages", headers=headers
    ).json()["items"]
    assistant_id = messages[-1]["id"]

    with client.stream(
        "POST",
        f"/api/conversations/{conversation_id}/messages/{assistant_id}/regenerate/stream",
        json={"model": "alternate-model"},
        headers=headers,
    ) as response:
        regenerated_body = response.read().decode()
    assert response.status_code == 200
    assert '"model": "alternate-model"' in regenerated_body

    visible_messages = client.get(
        f"/api/conversations/{conversation_id}/messages", headers=headers
    ).json()["items"]
    assert sum(item["role"] == "user" for item in visible_messages) == 2
    assert visible_messages[-1]["content"] == "A real response."
    assert visible_messages[-1]["message_metadata"]["status"] == "complete"
