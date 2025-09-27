"""Repository factory that routes to CSV or ServiceNow backends."""

from __future__ import annotations

import os
from datetime import date
from typing import Dict, List, Optional, Protocol

from ..utils.logging import get_logger
from .csv_repo import CSVRepository
from .servicenow_client import ServiceNowClient, ServiceNowRepository

LOGGER = get_logger("db.repo")


class Repository(Protocol):
    def list_properties(self, zipcode: Optional[str] = None, limit: Optional[int] = 24) -> List[Dict]:
        ...

    def get_property(self, property_id: str) -> Optional[Dict]:
        ...

    def get_market_stats(
        self, zipcode: str, start: Optional[date] = None, end: Optional[date] = None
    ) -> List[Dict]:
        ...

    def get_comps(self, property_id: str) -> List[Dict]:
        ...


_repository: Optional[Repository] = None


def get_repository() -> Repository:
    global _repository
    if _repository is not None:
        return _repository

    mode = os.getenv("DB_MODE", "csv").lower()
    if mode == "servicenow":
        LOGGER.info("Using ServiceNow repository")
        client = ServiceNowClient()
        _repository = ServiceNowRepository(client)
    else:
        LOGGER.info("Using CSV repository")
        _repository = CSVRepository()
    return _repository


def reset_repository() -> None:
    global _repository
    _repository = None

