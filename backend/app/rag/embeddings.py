from __future__ import annotations

from typing import Protocol

import httpx


class EmbeddingProvider(Protocol):
    @property
    def model_name(self) -> str: ...

    def get_embedding_dimension(self) -> int: ...

    def embed_query(self, text: str) -> list[float]: ...

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...


class OllamaEmbeddingProvider:
    def __init__(
        self,
        base_url: str,
        model_name: str,
        dimension: int,
        timeout: float = 60.0,
        client: httpx.Client | None = None,
    ) -> None:
        if not model_name.strip():
            raise ValueError("An embedding model name is required.")
        if dimension < 1:
            raise ValueError("Embedding dimension must be positive.")
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self.dimension = dimension
        self.client = client or httpx.Client(timeout=timeout, trust_env=False)

    def get_embedding_dimension(self) -> int:
        return self.dimension

    def embed_query(self, text: str) -> list[float]:
        vectors = self.embed_documents([text])
        return vectors[0]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        response = self.client.post(
            f"{self.base_url}/api/embed",
            json={"model": self.model_name, "input": texts},
        )
        response.raise_for_status()
        payload = response.json()
        embeddings = payload.get("embeddings") if isinstance(payload, dict) else None
        if not isinstance(embeddings, list) or len(embeddings) != len(texts):
            raise RuntimeError("The embedding provider returned an invalid response.")
        if any(
            not isinstance(vector, list)
            or len(vector) != self.dimension
            or any(not isinstance(value, (int, float)) for value in vector)
            for vector in embeddings
        ):
            raise RuntimeError("The embedding provider returned vectors with an unexpected dimension.")
        return [[float(value) for value in vector] for vector in embeddings]
