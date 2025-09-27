"""ServiceNow Table API client and repository implementation."""

from __future__ import annotations

import os
from datetime import date
from typing import Dict, List, Optional, Tuple

import requests

from ..utils.logging import get_logger

LOGGER = get_logger("db.servicenow")

DEFAULT_TIMEOUT = 10
PAGE_SIZE = 200


class ServiceNowClient:
    def __init__(self) -> None:
        instance = os.getenv("SERVICENOW_INSTANCE")
        user = os.getenv("SERVICENOW_USER")
        password = os.getenv("SERVICENOW_PASS")
        if not instance or not user or not password:
            raise RuntimeError("ServiceNow credentials are required when DB_MODE=servicenow")
        self.base_url = instance.rstrip("/")
        if not self.base_url.startswith("https://"):
            self.base_url = f"https://{self.base_url}"
        self.base_url = f"{self.base_url}/api/now/table"
        self.session = requests.Session()
        self.session.auth = (user, password)
        self.session.headers.update({"Content-Type": "application/json"})

    def fetch_table(self, table: str, query: Optional[str] = None) -> List[Dict]:
        records: List[Dict] = []
        offset = 0
        while True:
            params = {
                "sysparm_limit": PAGE_SIZE,
                "sysparm_offset": offset,
                "sysparm_display_value": "false",
            }
            if query:
                params["sysparm_query"] = query
            response = self.session.get(
                f"{self.base_url}/{table}", params=params, timeout=DEFAULT_TIMEOUT
            )
            response.raise_for_status()
            data = response.json().get("result", [])
            if not data:
                break
            for item in data:
                records.append(_coerce_record(item))
            if len(data) < PAGE_SIZE:
                break
            offset += PAGE_SIZE
        return records


def _coerce_value(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    value_str = str(value).strip()
    if value_str == "":
        return None
    # Try integer conversion
    try:
        if value_str.isdigit() or (value_str[0] == "-" and value_str[1:].isdigit()):
            return int(value_str)
    except Exception:
        pass
    # Try float conversion
    try:
        return float(value_str.replace(",", ""))
    except Exception:
        pass
    # Minimal ISO date detection
    if len(value_str) >= 10 and value_str[4] == "-" and value_str[7] == "-":
        return value_str[:10]
    return value


def _coerce_record(record: Dict) -> Dict:
    return {key: _coerce_value(value) for key, value in record.items()}


class ServiceNowRepository:
    def __init__(self, client: ServiceNowClient) -> None:
        self.client = client
        self.properties_table = os.getenv("SERVICENOW_PROPERTIES_TABLE", "u_properties")
        self.market_table = os.getenv("SERVICENOW_MARKET_TABLE", "u_market_stats")
        self.comps_table = os.getenv("SERVICENOW_COMPS_TABLE", "u_comps")

    def list_properties(self, zipcode: Optional[str] = None, limit: Optional[int] = 24) -> List[Dict]:
        query = None
        if zipcode:
            query = f"zipcode={zipcode}"
        records = self.client.fetch_table(self.properties_table, query=query)
        records.sort(key=lambda r: (r.get("current_est_value") or 0), reverse=True)
        if limit is not None:
            records = records[:limit]
        trimmed = [self._normalize_property(rec) for rec in records]
        return trimmed

    def get_property(self, property_id: str) -> Optional[Dict]:
        query = f"sys_id={property_id}^ORid={property_id}"
        records = self.client.fetch_table(self.properties_table, query=query)
        if not records:
            return None
        return self._normalize_property(records[0])

    def get_market_stats(
        self, zipcode: str, start: Optional[date] = None, end: Optional[date] = None
    ) -> List[Dict]:
        parts = [f"zipcode={zipcode}"]
        if start:
            parts.append(f"date>={start.isoformat()}")
        if end:
            parts.append(f"date<={end.isoformat()}")
        query = "^".join(parts)
        records = self.client.fetch_table(self.market_table, query=query)
        records.sort(key=lambda r: r.get("date"))
        return records

    def get_comps(self, property_id: str) -> List[Dict]:
        query = f"property_id={property_id}"
        records = self.client.fetch_table(self.comps_table, query=query)
        records.sort(key=lambda r: r.get("sale_date"), reverse=True)
        return records

    def _normalize_property(self, record: Dict) -> Dict:
        output = dict(record)
        sys_id = record.get("sys_id")
        if sys_id and not output.get("id"):
            output["id"] = sys_id
        return output

