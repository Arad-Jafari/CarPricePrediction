from __future__ import annotations

import csv
import hashlib

import pytest

from app.config import REPOSITORY_ROOT
from app.rag.dataset import build_document, load_dataset
from app.rag.embeddings import OllamaEmbeddingProvider
from app.rag.ingestion import index_dataset, index_documents


class FakeEmbeddingProvider:
    model_name = "fake-test-only"

    def __init__(self, invalid_shape=False):
        self.invalid_shape = invalid_shape

    def get_embedding_dimension(self):
        return 4

    def embed_query(self, text):
        return self.embed_documents([text])[0]

    def embed_documents(self, texts):
        if self.invalid_shape:
            return [[0.1, 0.2] for _ in texts]
        vectors = []
        for text in texts:
            digest = hashlib.sha256(text.encode("utf-8")).digest()
            vectors.append([byte / 255 for byte in digest[:4]])
        return vectors


class FakeVectorStore:
    def __init__(self):
        self.records = {}

    def list_ids(self):
        return list(self.records)

    def upsert(self, ids, documents, metadatas, embeddings):
        for identifier, document, metadata, vector in zip(
            ids, documents, metadatas, embeddings, strict=True
        ):
            self.records[identifier] = {
                "document": document,
                "metadata": metadata,
                "embedding": vector,
            }

    def delete(self, ids):
        for identifier in ids:
            self.records.pop(identifier, None)

    def clear(self):
        self.records.clear()

    def query(self, embedding, limit=5, metadata_filter=None):
        items = [
            {"id": identifier, **record}
            for identifier, record in self.records.items()
            if not metadata_filter
            or all(record["metadata"].get(key) == value for key, value in metadata_filter.items())
        ]
        return {"items": items[:limit]}


def _write_dataset(path, rows):
    fields = [
        "model",
        "year",
        "mileage",
        "trim",
        "transmission",
        "body_status",
        "color",
        "modified_date",
        "price",
    ]
    with path.open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_dataset_documents_use_real_fields_and_stable_ids():
    record = {
        "model": "206",
        "year": "۱۳۸۸",
        "mileage": "۱۳۹,۰۰۰ km",
        "trim": "تیپ 6",
        "transmission": "اتوماتیک",
        "body_status": "چند لکه رنگ",
        "color": "گیلاسی",
        "modified_date": "2026-11-10T15:00:00.6",
        "price": "1,550,000,000",
    }
    document = build_document(record, 1)
    assert document is not None
    assert document.id == build_document(record, 1).id
    assert document.metadata["model"] == "206"
    assert document.metadata["year"] == 1388
    assert document.metadata["mileage"] == 139000
    assert document.metadata["price"] == 1550000000
    assert "currency denomination not specified" in document.content
    assert "description" not in document.metadata
    assert build_document({**record, "price": ""}, 2) is None


def test_actual_cleaned_dataset_is_loadable_without_invented_fields():
    dataset_path = REPOSITORY_ROOT / "ml" / "data" / "cleaned_data" / "cleaned_dataset.csv"
    documents = load_dataset(dataset_path)
    assert documents
    assert all(document.metadata["record_type"] == "historical_source_record" for document in documents)
    assert all("Source price:" in document.content for document in documents)
    assert all("description" not in document.metadata for document in documents)


def test_ingestion_is_idempotent_updates_changed_rows_and_deletes_removed_rows(tmp_path):
    path = tmp_path / "cars.csv"
    original_rows = [
        {
            "model": "206",
            "year": "1388",
            "mileage": "139,000 km",
            "trim": "تیپ 6",
            "transmission": "اتوماتیک",
            "body_status": "چند لکه رنگ",
            "color": "گیلاسی",
            "modified_date": "2026-11-10",
            "price": "1,550,000,000",
        },
        {
            "model": "206",
            "year": "1390",
            "mileage": "95000",
            "trim": "تیپ 2",
            "transmission": "دنده ای",
            "body_status": "بدون رنگ",
            "color": "سفید",
            "modified_date": "2026-11-11",
            "price": "1,200,000,000",
        },
    ]
    _write_dataset(path, original_rows)
    store = FakeVectorStore()
    embeddings = FakeEmbeddingProvider()

    assert index_dataset(path, store, embeddings, batch_size=1) == 2
    initial_ids = set(store.list_ids())
    assert len(initial_ids) == 2
    assert index_dataset(path, store, embeddings, batch_size=1) == 2
    assert set(store.list_ids()) == initial_ids

    _write_dataset(path, [original_rows[0]])
    assert index_dataset(path, store, embeddings) == 1
    assert len(store.list_ids()) == 1
    matches = store.query([0, 0, 0, 0], metadata_filter={"model": "206"})
    assert len(matches["items"]) == 1


def test_embedding_failure_does_not_clear_or_delete_existing_index():
    store = FakeVectorStore()
    store.records["existing"] = {"document": "keep", "metadata": {}, "embedding": []}
    document = build_document(
        {
            "model": "206",
            "year": "1388",
            "mileage": "1000",
            "price": "1000",
        },
        1,
    )
    with pytest.raises(RuntimeError, match="invalid shape"):
        index_documents(
            [document],
            store,
            FakeEmbeddingProvider(invalid_shape=True),
            reindex=True,
        )
    assert store.list_ids() == ["existing"]


def test_ollama_embedding_adapter_contract_without_real_model_execution():
    class MockResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"embeddings": [[0.1, 0.2, 0.3]]}

    class MockClient:
        def post(self, url, json):
            assert url == "http://ollama:11434/api/embed"
            assert json == {"model": "embeddinggemma", "input": ["a car"]}
            return MockResponse()

    provider = OllamaEmbeddingProvider(
        "http://ollama:11434",
        "embeddinggemma",
        dimension=3,
        client=MockClient(),
    )
    assert provider.embed_query("a car") == [0.1, 0.2, 0.3]
    assert provider.get_embedding_dimension() == 3
