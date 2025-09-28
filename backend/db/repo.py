"""Repository abstraction for CSV or ServiceNow backends."""

from __future__ import annotations

import os
from typing import Dict, List, Optional

from ..utils.logging import get_logger
from .csv_repo import CSVRepository
from .mappers import map_market_row, map_property_row
from .servicenow_client import SNClient, stream_properties
from . import csv_gotham

LOGGER = get_logger("db.repo")

DB_MODE = os.getenv("DB_MODE", "csv").lower()


class Repo:
    def __init__(self) -> None:
        self.mode = DB_MODE
        self._csv_repo: Optional[CSVRepository] = None
        self._sn_client: Optional[SNClient] = None
        if self.mode == "servicenow":
            try:
                self._sn_client = SNClient()
                LOGGER.info("Repository running in ServiceNow mode")
            except Exception as exc:
                LOGGER.warning("Failed to initialise ServiceNow client (%s); falling back to CSV", exc)
                self.mode = "csv"
        if self.mode != "servicenow":
            self._csv_repo = CSVRepository()
            LOGGER.info("Repository running in CSV mode")

    # ------------------------------------------------------------------
    # Listings
    def list_properties(self, submarket: Optional[str] = None, limit: int = 200) -> List[Dict]:
        if self.mode == "servicenow" and self._sn_client:
            items: List[Dict] = []
            for row in stream_properties(self._sn_client, submarket=submarket, limit_per_page=200):
                mapped = map_property_row(row)
                items.append(mapped)
                if len(items) >= limit:
                    break
            return items
        repo = self._ensure_csv()
        return repo.list_properties(submarket=submarket, limit=limit)

    # ------------------------------------------------------------------
    # Property detail helpers
    def get_property(self, property_id: str) -> Optional[Dict]:
        if self.mode == "servicenow" and self._sn_client:
            from .servicenow_client import TBL_PROP
            record = self._sn_client.get_record(TBL_PROP, property_id)
            return map_property_row(record)
        repo = self._ensure_csv()
        return repo.get_property(property_id)

    def get_market_series_for_property(self, property_row: Dict) -> List[Dict]:
        submarket = property_row.get("submarket") or property_row.get("submarket_name")
        zipcode = property_row.get("zipcode") or property_row.get("zip")
        target = str(submarket or zipcode or "").strip()
        if not target:
            return []
        try:
            rows = csv_gotham.get_market_series(target)
        except FileNotFoundError:
            rows = []
        if not rows and self.mode != "servicenow":
            csv_repo = self._ensure_csv()
            return csv_repo.get_market_stats(target)
        return [map_market_row(row) for row in rows]

    def get_distribution_dataset(self) -> List[Dict]:
        try:
            return csv_gotham.get_distribution_dataset()
        except FileNotFoundError:
            return []

    def get_market_series(self, submarket_or_zip: str) -> List[Dict]:
        rows = csv_gotham.get_market_series(submarket_or_zip)
        return [map_market_row(row) for row in rows]

    def get_market_stats(self, key: str) -> List[Dict]:
        return self.get_market_series(key)

    def get_comps(self, property_id: str) -> List[Dict]:
        repo = self._ensure_csv()
        return repo.get_comps(property_id)

    # ------------------------------------------------------------------
    def _ensure_csv(self) -> CSVRepository:
        if self._csv_repo is None:
            self._csv_repo = CSVRepository()
        return self._csv_repo


_repo_singleton: Repo | None = None


def get_repository() -> Repo:
    global _repo_singleton
    if _repo_singleton is None:
        _repo_singleton = Repo()
    return _repo_singleton


def reset_repository() -> None:
    global _repo_singleton
    _repo_singleton = None
