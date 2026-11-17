from __future__ import annotations

from typing import Protocol


class VectorStore(Protocol):
    def list_ids(self) -> list[str]: ...

    def upsert(
        self,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict],
        embeddings: list[list[float]],
    ) -> None: ...

    def delete(self, ids: list[str]) -> None: ...

    def query(
        self,
        embedding: list[float],
        limit: int = 5,
        metadata_filter: dict | None = None,
    ) -> dict: ...


class ChromaVectorStore:
    def __init__(
        self,
        path: str,
        collection_name: str,
        embedding_model: str,
        embedding_dimension: int,
    ) -> None:
        try:
            import chromadb
        except ImportError as exc:
            raise RuntimeError(
                "Chroma is optional; install backend/requirements-rag.txt to use vector storage."
            ) from exc

        self._client = chromadb.PersistentClient(path=path)
        metadata = {
            "embedding_model": embedding_model,
            "embedding_dimension": embedding_dimension,
            "hnsw:space": "cosine",
        }
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata=metadata,
        )
        collection_metadata = self._collection.metadata or {}
        if (
            collection_metadata.get("embedding_model") != embedding_model
            or collection_metadata.get("embedding_dimension") != embedding_dimension
        ):
            raise RuntimeError(
                "The Chroma collection uses a different embedding model or dimension. "
                "Create a new collection or reindex it deliberately."
            )

    def list_ids(self) -> list[str]:
        return list(self._collection.get(include=[])["ids"])

    def upsert(
        self,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict],
        embeddings: list[list[float]],
    ) -> None:
        self._collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=embeddings,
        )

    def delete(self, ids: list[str]) -> None:
        if ids:
            self._collection.delete(ids=ids)

    def clear(self) -> None:
        self.delete(self.list_ids())

    def query(
        self,
        embedding: list[float],
        limit: int = 5,
        metadata_filter: dict | None = None,
    ) -> dict:
        return self._collection.query(
            query_embeddings=[embedding],
            n_results=limit,
            where=metadata_filter,
            include=["documents", "metadatas", "distances"],
        )
