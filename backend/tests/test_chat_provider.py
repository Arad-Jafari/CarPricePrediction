from __future__ import annotations

import asyncio
import json
from unittest.mock import Mock

import httpx

from app.chat import OllamaChatProvider, load_chat_provider


def test_load_chat_provider_accepts_module_class_paths():
    provider = load_chat_provider("app.chat:OllamaChatProvider")
    assert isinstance(provider, OllamaChatProvider)


def test_ollama_chat_provider_uses_chat_api():
    client = Mock()
    response = Mock()
    response.json.return_value = {"message": {"content": "This is a generated answer."}}
    response.raise_for_status.return_value = None
    client.post.return_value = response

    provider = OllamaChatProvider(base_url="http://ollama:11434", default_model="gemma3:1b", client=client)
    assert provider.generate_reply([{"role": "user", "content": "Hello"}]) == "This is a generated answer."
    client.post.assert_called_once_with(
        "http://ollama:11434/api/chat",
        json={
            "model": "gemma3:1b",
            "messages": [{"role": "user", "content": "Hello"}],
            "stream": False,
            "options": {"temperature": 0.3, "num_ctx": 2048},
        },
    )


def test_ollama_chat_provider_disables_proxy_env(monkeypatch):
    captured = {}

    def fake_client(*args, **kwargs):
        captured.update(kwargs)
        return Mock()

    monkeypatch.setattr("app.chat.httpx.Client", fake_client)
    monkeypatch.setenv("HTTP_PROXY", "http://proxy.example:3128")
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.example:3128")

    OllamaChatProvider(base_url="http://localhost:11434", default_model="gemma3:1b")

    assert captured["trust_env"] is False


def test_ollama_stream_parses_ndjson_progressively_and_uses_selected_model():
    async def verify():
        requests = []

        def respond(request):
            requests.append(request)
            return httpx.Response(
                200,
                content=(
                    b'{"message":{"content":"first"},"done":false}\n'
                    b'{"message":{"content":" second"},"done":true}\n'
                ),
            )

        client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
        provider = OllamaChatProvider(
            base_url="http://ollama:11434",
            default_model="configured-model",
            async_client=client,
        )
        try:
            tokens = [
                token async for token in provider.stream(
                    [{"role": "user", "content": "Hello"}], model="selected-model"
                )
            ]
        finally:
            await client.aclose()

        assert tokens == ["first", " second"]
        request_payload = json.loads(requests[0].content)
        assert request_payload["model"] == "selected-model"
        assert request_payload["stream"] is True

    asyncio.run(verify())
