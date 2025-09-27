"""Seed ServiceNow tables using CSV demo data."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Iterable, Tuple

import pandas as pd
import requests
from dotenv import load_dotenv

from ..utils.logging import get_logger

LOGGER = get_logger("db.seed_servicenow")

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

def load_csv(name: str) -> Iterable[Dict]:
    path = DATA_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Missing data file: {path}")
    df = pd.read_csv(path)
    df = df.where(pd.notnull(df), None)
    return df.to_dict("records")


def main() -> None:
    load_dotenv()
    instance = os.getenv("SERVICENOW_INSTANCE")
    user = os.getenv("SERVICENOW_USER")
    password = os.getenv("SERVICENOW_PASS")
    if not instance or not user or not password:
        raise RuntimeError("ServiceNow credentials (INSTANCE/USER/PASS) are required")
    base_url = instance.rstrip("/")
    if not base_url.startswith("https://"):
        base_url = f"https://{base_url}"
    base_url = f"{base_url}/api/now/table"

    session = requests.Session()
    session.auth = (user, password)
    session.headers.update({"Content-Type": "application/json"})

    table_map: Dict[str, Tuple[str, str]] = {
        "properties.csv": (os.getenv("SERVICENOW_PROPERTIES_TABLE", "u_properties"), "id"),
        "market_stats.csv": (os.getenv("SERVICENOW_MARKET_TABLE", "u_market_stats"), "id"),
        "comps.csv": (os.getenv("SERVICENOW_COMPS_TABLE", "u_comps"), "comp_id"),
    }

    for csv_name, (table, pk_field) in table_map.items():
        LOGGER.info("Seeding %s into table %s", csv_name, table)
        for row in load_csv(csv_name):
            payload = dict(row)
            if pk_field not in payload:
                # For properties.csv we treat the `id` column as external key
                if csv_name == "properties.csv" and "id" in payload:
                    payload[pk_field] = payload["id"]
            response = session.post(f"{base_url}/{table}", json=payload, timeout=10)
            try:
                response.raise_for_status()
            except Exception as exc:  # pragma: no cover - best effort logging
                LOGGER.error("Failed to seed %s row %s: %s", table, payload, exc)
                continue

    LOGGER.info("ServiceNow seed complete")


if __name__ == "__main__":
    main()

