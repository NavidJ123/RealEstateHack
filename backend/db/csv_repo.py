"""CSV-backed repository implementation."""

from __future__ import annotations

import math
from datetime import date
from typing import Dict, List, Optional

import pandas as pd

from ..utils.coerce import to_float
from ..utils.io import load_csv

P_FALLBACK = "properties.csv"
P_GOTHAM = "x_ai_prop_property_gotham.csv"
M_FALLBACK = "market_stats.csv"
M_GOTHAM = "x_ai_prop_market_stats_gotham.csv"
C_GOTHAM = "x_ai_prop_sales_history_gotham.csv"
C_FALLBACK = "comps.csv"

DEFAULT_DOM = 30


class CSVRepository:
    def __init__(self) -> None:
        self._properties = self._load_first([P_GOTHAM, P_FALLBACK])
        self._market_stats = self._load_first([M_GOTHAM, M_FALLBACK])
        self._sales_history = self._load_first([C_GOTHAM, C_FALLBACK])
        self._prepare_market_stats()
        self._prepare_properties()
        self._property_lookup = self._build_property_lookup()

    def list_properties(
        self, zipcode: Optional[str] = None, limit: Optional[int] = 24, submarket: Optional[str] = None
    ) -> List[Dict]:
        df = self._properties.copy()
        if submarket:
            key = str(submarket).lower()
            if 'submarket' in df.columns:
                df = df[df['submarket'].astype(str).str.lower() == key]
            elif 'submarket_name' in df.columns:
                df = df[df['submarket_name'].astype(str).str.lower() == key]
        elif zipcode:
            key = str(zipcode)
            if 'zipcode' in df.columns:
                df = df[df['zipcode'].astype(str) == key]
            elif 'zip' in df.columns:
                df = df[df['zip'].astype(str) == key]

        sort_series = pd.to_numeric(df.get('current_est_value'), errors='coerce').fillna(0)
        df = df.assign(_sort_value=sort_series).sort_values('_sort_value', ascending=False).drop(columns=['_sort_value'])
        if limit is not None:
            df = df.head(limit)
        df = df.where(pd.notnull(df), None)
        records = df.to_dict("records")
        # Convert zipcode to string
        for record in records:
            if record.get("zipcode") is not None:
                record["zipcode"] = str(record["zipcode"]).strip()
        return records

    def get_property(self, property_id: str) -> Optional[Dict]:
        df = self._properties
        row = df[df["id"] == property_id]
        if row.empty:
            return None
        record = row.iloc[0].to_dict()
        record = {k: (None if pd.isna(v) else v) for k, v in record.items()}
        # Convert zipcode to string
        if record.get("zipcode") is not None:
            record["zipcode"] = str(record["zipcode"]).strip()
        return record

    def get_market_stats(
        self, zipcode_or_submarket: str, start: Optional[date] = None, end: Optional[date] = None
    ) -> List[Dict]:
        df = self._market_stats
        subset = df[df['zipcode'].astype(str) == str(zipcode_or_submarket)].copy()
        if subset.empty and 'submarket_name' in df.columns:
            subset = df[df['submarket_name'].astype(str).str.lower() == str(zipcode_or_submarket).lower()].copy()
        subset["date"] = pd.to_datetime(subset["date"])
        if start:
            subset = subset[subset["date"] >= pd.Timestamp(start)]
        if end:
            subset = subset[subset["date"] <= pd.Timestamp(end)]
        subset = subset.sort_values("date")
        subset["date"] = subset["date"].dt.date.astype(str)
        subset = subset.where(pd.notnull(subset), None)
        return subset.to_dict("records")


    def _load_first(self, filenames):
        for name in filenames:
            try:
                return load_csv(name)
            except FileNotFoundError:
                continue
        raise FileNotFoundError(f"CSV not found for any of {filenames}")

    def _prepare_market_stats(self) -> None:
        df = self._market_stats
        if 'median_income' not in df.columns and 'income' in df.columns:
            df['median_income'] = df['income']

        def _numeric(values, fill: Optional[float] = None) -> pd.Series:
            if isinstance(values, pd.Series):
                return pd.to_numeric(values, errors='coerce')
            if values is None:
                fill_value = float(fill) if fill is not None else float('nan')
                return pd.Series([fill_value] * len(df.index), index=df.index, dtype='float64')
            return pd.to_numeric(pd.Series(values, index=df.index), errors='coerce')

        rent = _numeric(df.get('median_rent'))
        price = _numeric(df.get('median_price'))

        if 'cap_rate_market_now' in df.columns:
            df['cap_rate_market_now'] = _numeric(df['cap_rate_market_now'])
        else:
            df['cap_rate_market_now'] = (rent * 12) / price

        df['median_rent'] = rent
        df['median_price'] = price
        df['median_income'] = _numeric(df.get('median_income'))
        df['income'] = _numeric(df.get('income'))
        df['vacancy_rate'] = _numeric(df.get('vacancy_rate'))
        df['inventory'] = _numeric(df.get('inventory'))
        df['dom'] = _numeric(df.get('dom'), DEFAULT_DOM).fillna(DEFAULT_DOM).round().astype(int)

    def get_comps(self, property_id: str) -> List[Dict]:
        if "sys_id" not in self._properties.columns:
            return []
        subject_mask = self._properties["sys_id"].astype(str) == str(property_id)
        subject = self._properties[subject_mask]
        if subject.empty:
            return []

        subject_row = subject.iloc[0]
        subject_lat = to_float(subject_row.get("latitude"))
        subject_lon = to_float(subject_row.get("longitude"))
        subject_submarket = str(subject_row.get("submarket_name") or "").strip().lower()

        comps = self._sales_history.copy()
        if comps.empty or "property_sys_id" not in comps.columns:
            return []

        if "comp_id" not in comps.columns and "sys_id" in comps.columns:
            comps["comp_id"] = comps["sys_id"].astype(str)
        else:
            comps["comp_id"] = comps.get("comp_id", pd.Series(dtype=str)).astype(str)

        if "sale_price" not in comps.columns:
            price_col = "sale_price_usd" if "sale_price_usd" in comps.columns else None
            if price_col:
                comps["sale_price"] = pd.to_numeric(comps[price_col], errors="coerce")
        else:
            comps["sale_price"] = pd.to_numeric(comps["sale_price"], errors="coerce")

        comps["sale_date"] = pd.to_datetime(comps.get("sale_date"), errors="coerce")

        comps = comps.merge(
            self._property_lookup,
            left_on="property_sys_id",
            right_on="comp_property_id",
            how="left",
        )

        comps["comp_id"] = comps["comp_id"].where(comps["comp_id"].notnull(), comps["property_sys_id"].astype(str))

        if subject_submarket and "submarket_name" in comps.columns:
            filtered = comps[
                comps["submarket_name"].astype(str).str.lower() == subject_submarket
            ]
            if not filtered.empty:
                comps = filtered.copy()

        without_self = comps[comps["property_sys_id"].astype(str) != str(property_id)]
        if not without_self.empty:
            comps = without_self.copy()

        if subject_lat is not None and subject_lon is not None:
            comps["distance_mi"] = comps.apply(
                lambda row: self._distance_miles(
                    subject_lat,
                    subject_lon,
                    to_float(row.get("latitude")),
                    to_float(row.get("longitude")),
                ),
                axis=1,
            )
        else:
            comps["distance_mi"] = None

        comps["sqft"] = pd.to_numeric(comps.get("net_rentable_area_sqft"), errors="coerce")
        comps["address"] = comps.apply(self._format_address, axis=1)
        comps["property_id"] = str(property_id)

        comps = comps.dropna(subset=["sale_date", "sale_price"])
        if comps.empty:
            return []

        comps = comps.sort_values("sale_date", ascending=False).head(100)
        comps["comp_id"] = comps["comp_id"].astype(str)
        comps["sale_date"] = comps["sale_date"].dt.date.astype(str)
        comps = comps.where(pd.notnull(comps), None)
        return comps[["comp_id", "property_id", "address", "sale_price", "sale_date", "sqft", "distance_mi"]].to_dict("records")

    def _prepare_properties(self) -> None:
        df = self._properties

        if 'id' not in df.columns and 'sys_id' in df.columns:
            df['id'] = df['sys_id'].astype(str)
        elif 'id' in df.columns:
            df['id'] = df['id'].astype(str)

        if 'zipcode' not in df.columns and 'zip' in df.columns:
            df['zipcode'] = df['zip']

        if 'submarket' not in df.columns and 'submarket_name' in df.columns:
            df['submarket'] = df['submarket_name']

        if 'type' not in df.columns:
            if 'property_type' in df.columns:
                df['type'] = df['property_type']
            elif 'mf_product_type' in df.columns:
                df['type'] = df['mf_product_type']

        if 'sqft' not in df.columns:
            if 'net_rentable_area_sqft' in df.columns:
                df['sqft'] = pd.to_numeric(df['net_rentable_area_sqft'], errors='coerce')
            elif 'net_rentable_area' in df.columns:
                df['sqft'] = pd.to_numeric(df['net_rentable_area'], errors='coerce')

        if 'current_est_value' not in df.columns:
            value_series = None
            for candidate in [
                'last_appraised_value_usd',
                'current_value_estimate',
                'appraised_value',
                'assessed_value_improvement_usd',
            ]:
                if candidate in df.columns:
                    series = pd.to_numeric(df[candidate], errors='coerce')
                    value_series = series if value_series is None else value_series.combine_first(series)
            if value_series is None:
                value_series = pd.Series([None] * len(df.index), index=df.index, dtype='float64')
            df['current_est_value'] = value_series
        else:
            df['current_est_value'] = pd.to_numeric(df['current_est_value'], errors='coerce')

        if 'address' not in df.columns:
            df['address'] = df.apply(self._format_address, axis=1)

        if 'zipcode' in df.columns:
            df['zipcode'] = df['zipcode'].apply(self._normalise_zipcode)

        if 'sqft' in df.columns:
            df['sqft'] = pd.to_numeric(df['sqft'], errors='coerce')

    def _build_property_lookup(self) -> pd.DataFrame:
        cols = [
            "sys_id",
            "property_name",
            "address_line1",
            "address_line2",
            "city",
            "state",
            "zip",
            "submarket_name",
            "net_rentable_area_sqft",
            "latitude",
            "longitude",
        ]
        existing_cols = [col for col in cols if col in self._properties.columns]
        lookup = self._properties[existing_cols].copy()
        lookup = lookup.rename(columns={"sys_id": "comp_property_id"})
        return lookup

    @staticmethod
    def _distance_miles(lat1: Optional[float], lon1: Optional[float], lat2: Optional[float], lon2: Optional[float]) -> Optional[float]:
        if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
            return None
        try:
            lat1_rad = math.radians(float(lat1))
            lon1_rad = math.radians(float(lon1))
            lat2_rad = math.radians(float(lat2))
            lon2_rad = math.radians(float(lon2))
        except (TypeError, ValueError):
            return None
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        earth_radius_miles = 3958.8
        return earth_radius_miles * c

    @staticmethod
    def _format_address(row: pd.Series) -> str:
        line1 = str(row.get("address_line1") or "").strip()
        city = str(row.get("city") or "").strip()
        state = str(row.get("state") or "").strip()
        zipcode = str(row.get("zip") or row.get("zipcode") or "").strip()

        locality_parts = [part for part in [city, state] if part]
        locality = ", ".join(locality_parts)
        if zipcode:
            locality = f"{locality} {zipcode}".strip() if locality else zipcode

        parts = [part for part in [line1, locality] if part]
        if not parts:
            fallback = str(row.get("property_name") or "").strip()
            return fallback
        return ", ".join(parts)

    @staticmethod
    def _normalise_zipcode(value) -> Optional[str]:
        if value is None or (isinstance(value, float) and math.isnan(value)):
            return None
        try:
            if pd.isna(value):
                return None
        except TypeError:
            pass
        text = str(value).strip()
        if not text or text.lower() == "nan":
            return None
        digits = ''.join(ch for ch in text if ch.isdigit())
        if digits:
            if len(digits) >= 5:
                return digits[:5]
            return digits
        return text
