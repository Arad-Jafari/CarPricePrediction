from __future__ import annotations

import importlib
from typing import Protocol


class ChatProvider(Protocol):
    def generate_reply(self, messages: list[dict[str, str]]) -> str: ...


def load_chat_provider(provider_path: str | None) -> ChatProvider | None:
    if not provider_path:
        return None
    module_name, separator, attribute = provider_path.rpartition(".")
    if not separator:
        raise RuntimeError("CHAT_PROVIDER must be a dotted module.Class path.")
    provider_class = getattr(importlib.import_module(module_name), attribute)
    provider = provider_class()
    if not callable(getattr(provider, "generate_reply", None)):
        raise RuntimeError("Configured chat provider must implement generate_reply(messages).")
    return provider
