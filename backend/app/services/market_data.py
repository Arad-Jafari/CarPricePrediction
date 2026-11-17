from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Protocol


class MarketDataProvider(Protocol):
    def search_listings(self, filters: dict, limit: int = 20) -> list[dict]: ...

    def get_listing(self, listing_id: str) -> dict | None: ...


class CsvMarketDataProvider:
    """Read-only access to the repository's historical source-price dataset."""

    def __init__(self, dataset_path: Path):
        self.dataset_path = dataset_path

    def _records(self) -> list[dict]:
        with self.dataset_path.open(encoding="utf-8-sig", newline="") as source:
            return list(csv.DictReader(source))

    @staticmethod
    def _numeric(value: str | None) -> int | None:
        if value is None:
            return None
        normalized = value.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
        digits = re.sub(r"\D", "", normalized)
        return int(digits) if digits else None

    def search_listings(self, filters: dict, limit: int = 20) -> list[dict]:
        if not 1 <= limit <= 100:
            raise ValueError("Listing limit must be between 1 and 100.")
        numeric_filters = {"year", "min_year", "max_year", "min_mileage", "max_mileage"}
        text_filters = {"model", "transmission", "body_status", "trim"}
        if set(filters) - numeric_filters - text_filters:
            raise ValueError("Unsupported historical listing filter.")
        if any(
            not isinstance(filters[key], int) or isinstance(filters[key], bool)
            for key in numeric_filters.intersection(filters)
        ):
            raise ValueError("Year and mileage filters must be integers.")
        if any(
            not isinstance(filters[key], str) or not filters[key].strip()
            for key in text_filters.intersection(filters)
        ):
            raise ValueError("Text filters must be non-empty strings.")
        results = []
        for index, row in enumerate(self._records(), 1):
            year = self._numeric(row.get("year"))
            mileage = self._numeric(row.get("mileage"))
            if "model" in filters and row.get("model") != filters["model"]:
                continue
            if "year" in filters and year != filters["year"]:
                continue
            if "min_year" in filters and (year is None or year < filters["min_year"]):
                continue
            if "max_year" in filters and (year is None or year > filters["max_year"]):
                continue
            if "min_mileage" in filters and (mileage is None or mileage < filters["min_mileage"]):
                continue
            if "max_mileage" in filters and (mileage is None or mileage > filters["max_mileage"]):
                continue
            if any(row.get(key) != filters[key] for key in ("transmission", "body_status", "trim") if key in filters):
                continue
            result = dict(row)
            result["source_id"] = str(index)
            results.append(result)
            if len(results) >= limit:
                break
        return results

    def get_listing(self, listing_id: str) -> dict | None:
        if not listing_id.isdigit() or int(listing_id) < 1:
            return None
        for index, row in enumerate(self._records(), 1):
            if index == int(listing_id):
                result = dict(row)
                result["source_id"] = str(index)
                return result
        return None
