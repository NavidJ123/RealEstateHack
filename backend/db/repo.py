"""Repository layer providing CSV-first access with optional Postgres fallback."""

from __future__ import annotations

import os
from typing import Iterable, List, Optional

import pandas as pd

from ..models.property import Property
from ..utils.io import load_csv
from ..utils.logging import get_logger

LOGGER = get_logger("db.repo")


class BaseRepository:
    def list_properties(self, zipcode: Optional[str] = None, limit: Optional[int] = 20) -> List[Property]:
        raise NotImplementedError

    def get_property(self, property_id: str) -> Optional[Property]:
        raise NotImplementedError

    def get_market_stats(self, zipcode: str) -> pd.DataFrame:
        raise NotImplementedError

    def get_comps(self, property_id: str) -> pd.DataFrame:
        raise NotImplementedError


class CSVRepository(BaseRepository):
    def __init__(self) -> None:
        self._properties = load_csv("properties.csv")
        self._market_stats = load_csv("market_stats.csv")
        self._comps = load_csv("comps.csv")

    def list_properties(self, zipcode: Optional[str] = None, limit: Optional[int] = 20) -> List[Property]:
        df = self._properties
        if zipcode:
            df = df[df["zipcode"].astype(str) == str(zipcode)]
        df = df.sort_values("current_est_value", ascending=False)
        if limit:
            df = df.head(limit)
        df = df.where(pd.notnull(df), None)
        return [Property(**row) for row in df.to_dict("records")]

    def get_property(self, property_id: str) -> Optional[Property]:
        df = self._properties
        row = df[df["id"] == property_id]
        if row.empty:
            return None
        record = row.iloc[0].to_dict()
        record = {key: (None if pd.isna(value) else value) for key, value in record.items()}
        return Property(**record)

    def get_market_stats(self, zipcode: str) -> pd.DataFrame:
        df = self._market_stats
        subset = df[df["zipcode"].astype(str) == str(zipcode)].copy()
        return subset

    def get_comps(self, property_id: str) -> pd.DataFrame:
        df = self._comps
        subset = df[df["property_id"] == property_id].copy()
        return subset


class DatabaseRepository(BaseRepository):
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn
        try:
            import psycopg  # type: ignore

            self._psycopg = psycopg
        except Exception as exc:  # pragma: no cover - optional dependency
            LOGGER.error("psycopg is required for database mode: %s", exc)
            raise

    def _query(self, sql: str, params: Iterable) -> pd.DataFrame:
        with self._psycopg.connect(self.dsn) as conn:
            return pd.read_sql(sql, conn, params=params)

    def list_properties(self, zipcode: Optional[str] = None, limit: Optional[int] = 20) -> List[Property]:
        sql = "SELECT * FROM properties"
        params: List = []
        if zipcode:
            sql += " WHERE zipcode = %s"
            params.append(zipcode)
        sql += " ORDER BY current_est_value DESC"
        if limit:
            sql += " LIMIT %s"
            params.append(limit)
        df = self._query(sql, params)
        df = df.where(pd.notnull(df), None)
        return [Property(**row) for row in df.to_dict("records")]

    def get_property(self, property_id: str) -> Optional[Property]:
        df = self._query("SELECT * FROM properties WHERE id = %s", [property_id])
        if df.empty:
            return None
        record = df.iloc[0].to_dict()
        record = {key: (None if pd.isna(value) else value) for key, value in record.items()}
        return Property(**record)

    def get_market_stats(self, zipcode: str) -> pd.DataFrame:
        return self._query("SELECT * FROM market_stats WHERE zipcode = %s ORDER BY date", [zipcode])

    def get_comps(self, property_id: str) -> pd.DataFrame:
        return self._query("SELECT * FROM comps WHERE property_id = %s", [property_id])


def get_repository() -> BaseRepository:
    use_db = os.getenv("USE_DB", "false").lower() == "true"
    dsn = os.getenv("DATABASE_URL")
    if use_db and dsn:
        LOGGER.info("Using Postgres repository")
        return DatabaseRepository(dsn)
    LOGGER.info("Using CSV-backed repository")
    return CSVRepository()

