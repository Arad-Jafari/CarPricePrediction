from __future__ import annotations

import importlib
import json
import os
from collections.abc import AsyncIterator, Iterator
from typing import Protocol

import httpx


class ChatProviderError(RuntimeError):
    pass


class ProviderUnavailableError(ChatProviderError):
    pass


class ProviderResponseError(ChatProviderError):
    pass


class ChatProvider(Protocol):
    default_model: str

    def generate(self, messages: list[dict[str, str]], model: str | None = None) -> str: ...

    def stream(
        self, messages: list[dict[str, str]], model: str | None = None
    ) -> AsyncIterator[str]: ...

    def list_models(self) -> list[str]: ...

    def health_check(self) -> bool: ...


class OllamaChatProvider:
    def __init__(
        self,
        base_url: str | None = None,
        default_model: str | None = None,
        timeout: float = 10.0,
        client: httpx.Client | None = None,
        async_client: httpx.AsyncClient | None = None,
        context_window: int = 2048,
        temperature: float = 0.3,
    ) -> None:
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL") or "http://127.0.0.1:11434").rstrip("/")
        self.default_model = (
            default_model
            or os.getenv("OLLAMA_CHAT_MODEL")
            or os.getenv("DEFAULT_MODEL")
            or "gemma3:1b"
        )
        self.timeout = timeout
        self.context_window = context_window
        self.temperature = temperature
        self.client = client or httpx.Client(timeout=timeout, trust_env=False)
        self.async_client = async_client

    def is_available(self) -> bool:
        try:
            self.list_models()
        except ChatProviderError:
            return False
        return True

    def health_check(self) -> bool:
        return self.is_available()

    def list_models(self) -> list[str]:
        try:
            response = self.client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError("Ollama is unavailable.") from exc
        try:
            payload = response.json()
        except ValueError as exc:
            raise ProviderResponseError("Ollama returned invalid model metadata.") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("models"), list):
            raise ProviderResponseError("Ollama returned invalid model metadata.")
        return [
            item["name"]
            for item in payload["models"]
            if isinstance(item, dict) and isinstance(item.get("name"), str) and item["name"]
        ]

    def generate(self, messages: list[dict[str, str]], model: str | None = None) -> str:
        if not messages:
            raise RuntimeError("At least one message is required to generate a response.")
        payload = {
            "model": model or self.default_model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": self.temperature, "num_ctx": self.context_window},
        }
        try:
            response = self.client.post(f"{self.base_url}/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError("Ollama could not complete the chat request.") from exc
        except ValueError as exc:
            raise ProviderResponseError("Ollama returned invalid chat data.") from exc
        content = data.get("message", {}).get("content") if isinstance(data, dict) else None
        if not isinstance(content, str) or not content.strip():
            raise ProviderResponseError("Ollama returned no usable completion.")
        return content.strip()

    def generate_reply(self, messages: list[dict[str, str]]) -> str:
        return self.generate(messages)

    async def stream(
        self, messages: list[dict[str, str]], model: str | None = None
    ) -> AsyncIterator[str]:
        if not messages:
            raise RuntimeError("At least one message is required to generate a response.")
        payload = {
            "model": model or self.default_model,
            "messages": messages,
            "stream": True,
            "options": {"temperature": self.temperature, "num_ctx": self.context_window},
        }
        async def receive(client: httpx.AsyncClient) -> AsyncIterator[str]:
            async with client.stream("POST", f"{self.base_url}/api/chat", json=payload) as response:
                response.raise_for_status()
                async for raw in response.aiter_lines():
                    if not raw:
                        continue
                    try:
                        chunk = json.loads(raw)
                    except json.JSONDecodeError as exc:
                        raise ProviderResponseError("Ollama returned a malformed streaming chunk.") from exc
                    if isinstance(chunk, dict) and chunk.get("error"):
                        raise ProviderResponseError("Ollama reported a streaming error.")
                    if not isinstance(chunk, dict):
                        raise ProviderResponseError("Ollama returned an invalid streaming chunk.")
                    content = chunk.get("message", {}).get("content")
                    if isinstance(content, str) and content:
                        yield content
                    if chunk.get("done") is True:
                        return

        try:
            if self.async_client is not None:
                async for content in receive(self.async_client):
                    yield content
            else:
                async with httpx.AsyncClient(timeout=self.timeout, trust_env=False) as client:
                    async for content in receive(client):
                        yield content
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError("Ollama could not stream the chat request.") from exc

    def stream_response(self, messages: list[dict[str, str]]) -> Iterator[str]:
        raise RuntimeError("Use the asynchronous stream() method for Ollama responses.")


def load_chat_provider(provider_path: str | None) -> ChatProvider | None:
    if not provider_path:
        return None
    module_name = provider_path
    attribute = ""
    if ":" in provider_path:
        module_name, attribute = provider_path.split(":", 1)
    else:
        module_name, separator, attribute = provider_path.rpartition(".")
        if not separator:
            raise RuntimeError("CHAT_PROVIDER must be a dotted module.Class path or module:Class path.")
    provider_class = getattr(importlib.import_module(module_name), attribute)
    provider = provider_class()
    if not callable(getattr(provider, "generate", None)) and not callable(
        getattr(provider, "generate_reply", None)
    ):
        raise RuntimeError("Configured chat provider must implement generate(messages).")
    return provider


def generate_with_provider(
    provider: ChatProvider,
    messages: list[dict[str, str]],
    model: str | None = None,
) -> str:
    generate = getattr(provider, "generate", None)
    if callable(generate):
        return generate(messages, model=model)
    generate_reply = getattr(provider, "generate_reply", None)
    if callable(generate_reply):
        return generate_reply(messages)
    raise RuntimeError("Configured chat provider cannot generate responses.")


async def stream_with_provider(
    provider: ChatProvider,
    messages: list[dict[str, str]],
    model: str | None = None,
) -> AsyncIterator[str]:
    stream = getattr(provider, "stream", None)
    if callable(stream):
        result = stream(messages, model=model)
        if hasattr(result, "__aiter__"):
            async for token in result:
                yield token
        else:
            for token in result:
                yield token
        return
    stream_response = getattr(provider, "stream_response", None)
    if callable(stream_response):
        for token in stream_response(messages):
            yield token
        return
    raise RuntimeError("Configured chat provider does not implement streaming.")
