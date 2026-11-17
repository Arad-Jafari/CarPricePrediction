from __future__ import annotations

import csv
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RAGDocument:
    id: str
    content: str
    metadata: dict


def _normalize_digits(value: str) -> str:
    return value.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))


def _integer(value: str | None) -> int | None:
    if value is None:
        return None
    digits = re.sub(r"\D", "", _normalize_digits(value))
    return int(digits) if digits else None


def clean_record(record: dict[str, str]) -> dict | None:
    model = (record.get("model") or "").strip()
    year = _integer(record.get("year"))
    mileage = _integer(record.get("mileage"))
    price = _integer(record.get("price"))
    if not model or year is None or mileage is None or price is None or price <= 0:
        return None
    return {
        "model": model,
        "year": year,
        "mileage": mileage,
        "trim": (record.get("trim") or "").strip(),
        "transmission": (record.get("transmission") or "").strip(),
        "body_status": (record.get("body_status") or "").strip(),
        "color": (record.get("color") or "").strip(),
        "modified_date": (record.get("modified_date") or "").strip(),
        "price": price,
    }


def build_document(record: dict[str, str], row_number: int) -> RAGDocument | None:
    cleaned = clean_record(record)
    if cleaned is None:
        return None
    identifier_source = json.dumps(
        {"row_number": row_number, **cleaned},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    document_id = hashlib.sha256(identifier_source.encode("utf-8")).hexdigest()
    lines = [
        "Historical vehicle record from the repository dataset.",
        f"Vehicle model: {cleaned['model']}",
        f"Year as recorded in source data: {cleaned['year']}",
        f"Mileage: {cleaned['mileage']}",
    ]
    for key, label in (
        ("trim", "Trim"),
        ("transmission", "Transmission"),
        ("body_status", "Body status"),
        ("color", "Color"),
    ):
        if cleaned[key]:
            lines.append(f"{label}: {cleaned[key]}")
    lines.append(f"Source price: {cleaned['price']} (currency denomination not specified)")
    if cleaned["modified_date"]:
        lines.append(f"Source modified date: {cleaned['modified_date']}")

    metadata = {
        "record_type": "historical_source_record",
        "source_row": row_number,
        "model": cleaned["model"],
        "year": cleaned["year"],
        "mileage": cleaned["mileage"],
        "price": cleaned["price"],
    }
    for key in ("trim", "transmission", "body_status", "color", "modified_date"):
        if cleaned[key]:
            metadata[key] = cleaned[key]
    return RAGDocument(id=document_id, content="\n".join(lines), metadata=metadata)


def load_dataset(path: Path) -> list[RAGDocument]:
    documents = []
    with path.open(encoding="utf-8-sig", newline="") as source:
        for row_number, row in enumerate(csv.DictReader(source), start=1):
            document = build_document(row, row_number)
            if document is not None:
                documents.append(document)
    return documents
