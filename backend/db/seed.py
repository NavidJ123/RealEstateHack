"""Seed Postgres/Supabase tables from CSV demo data."""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

from ..utils.logging import get_logger

LOGGER = get_logger("db.seed")

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def load_dataframe(name: str) -> pd.DataFrame:
    path = DATA_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Missing data file: {path}")
    return pd.read_csv(path)


def seed() -> None:
    load_dotenv()
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        raise RuntimeError("DATABASE_URL not configured")

    try:
        import psycopg  # type: ignore
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("psycopg is required to seed the database") from exc

    LOGGER.info("Connecting to database")
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            LOGGER.info("Clearing existing tables")
            cur.execute("TRUNCATE comps RESTART IDENTITY CASCADE")
            cur.execute("TRUNCATE market_stats RESTART IDENTITY CASCADE")
            cur.execute("TRUNCATE properties RESTART IDENTITY CASCADE")
        conn.commit()

        LOGGER.info("Loading properties")
        properties = load_dataframe("properties.csv").fillna(value=None)
        with conn.cursor() as cur:
            for row in properties.to_dict(orient="records"):
                cur.execute(
                    """
                    INSERT INTO properties (id, address, zipcode, sqft, type, last_sale_price, last_sale_date, current_est_value, est_monthly_rent, image_url)
                    VALUES (%(id)s, %(address)s, %(zipcode)s, %(sqft)s, %(type)s, %(last_sale_price)s, %(last_sale_date)s, %(current_est_value)s, %(est_monthly_rent)s, %(image_url)s)
                    ON CONFLICT (id) DO UPDATE SET
                        address = EXCLUDED.address,
                        zipcode = EXCLUDED.zipcode,
                        sqft = EXCLUDED.sqft,
                        type = EXCLUDED.type,
                        last_sale_price = EXCLUDED.last_sale_price,
                        last_sale_date = EXCLUDED.last_sale_date,
                        current_est_value = EXCLUDED.current_est_value,
                        est_monthly_rent = EXCLUDED.est_monthly_rent,
                        image_url = EXCLUDED.image_url
                    """,
                    row,
                )
        conn.commit()

        LOGGER.info("Loading market stats")
        stats = load_dataframe("market_stats.csv").fillna(value=None)
        with conn.cursor() as cur:
            for row in stats.to_dict(orient="records"):
                cur.execute(
                    """
                    INSERT INTO market_stats (zipcode, date, median_price, median_rent, inventory, dom, income, vacancy_rate)
                    VALUES (%(zipcode)s, %(date)s, %(median_price)s, %(median_rent)s, %(inventory)s, %(dom)s, %(income)s, %(vacancy_rate)s)
                    ON CONFLICT (zipcode, date) DO UPDATE SET
                        median_price = EXCLUDED.median_price,
                        median_rent = EXCLUDED.median_rent,
                        inventory = EXCLUDED.inventory,
                        dom = EXCLUDED.dom,
                        income = EXCLUDED.income,
                        vacancy_rate = EXCLUDED.vacancy_rate
                    """,
                    row,
                )
        conn.commit()

        LOGGER.info("Loading comps")
        comps = load_dataframe("comps.csv").fillna(value=None)
        with conn.cursor() as cur:
            for row in comps.to_dict(orient="records"):
                cur.execute(
                    """
                    INSERT INTO comps (comp_id, property_id, address, sale_price, sale_date, sqft, distance_mi)
                    VALUES (%(comp_id)s, %(property_id)s, %(address)s, %(sale_price)s, %(sale_date)s, %(sqft)s, %(distance_mi)s)
                    ON CONFLICT (comp_id) DO UPDATE SET
                        property_id = EXCLUDED.property_id,
                        address = EXCLUDED.address,
                        sale_price = EXCLUDED.sale_price,
                        sale_date = EXCLUDED.sale_date,
                        sqft = EXCLUDED.sqft,
                        distance_mi = EXCLUDED.distance_mi
                    """,
                    row,
                )
        conn.commit()

    LOGGER.info("Seed complete")


if __name__ == "__main__":
    seed()

