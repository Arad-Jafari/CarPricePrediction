from __future__ import annotations

from pathlib import Path

from app.rag.dataset import RAGDocument, load_dataset
from app.rag.embeddings import EmbeddingProvider
from app.rag.vector_store import VectorStore


def index_documents(
    documents: list[RAGDocument],
    store: VectorStore,
    embedding_provider: EmbeddingProvider,
    batch_size: int = 32,
    reindex: bool = False,
) -> int:
    if batch_size < 1:
        raise ValueError("batch_size must be positive.")
    vectors_by_batch = []
    expected_dimension = embedding_provider.get_embedding_dimension()
    for start in range(0, len(documents), batch_size):
        batch = documents[start:start + batch_size]
        vectors = embedding_provider.embed_documents([document.content for document in batch])
        if len(vectors) != len(batch) or any(
            len(vector) != expected_dimension for vector in vectors
        ):
            raise RuntimeError("Embedding provider returned vectors with an invalid shape.")
        vectors_by_batch.append((batch, vectors))

    if reindex:
        clear = getattr(store, "clear", None)
        if callable(clear):
            clear()
        else:
            store.delete(store.list_ids())

    document_ids = {document.id for document in documents}
    stale_ids = set(store.list_ids()) - document_ids
    store.delete(sorted(stale_ids))

    for batch, vectors in vectors_by_batch:
        store.upsert(
            [document.id for document in batch],
            [document.content for document in batch],
            [document.metadata for document in batch],
            vectors,
        )
    return len(documents)


def index_dataset(
    path: Path,
    store: VectorStore,
    embedding_provider: EmbeddingProvider,
    batch_size: int = 32,
    reindex: bool = False,
) -> int:
    return index_documents(
        load_dataset(path),
        store,
        embedding_provider,
        batch_size=batch_size,
        reindex=reindex,
    )
