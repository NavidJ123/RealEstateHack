"""Compute property analytics and assemble structured responses."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from ..models.analysis import AnalysisMetrics, AnalysisResponse, Comp, TrendPoint, ZipTrends
from ..utils.caching import memoize
from ..utils.logging import get_logger
from .comps_service import CompsService
from .forecast_service import ForecastService
from .provenance import dataset_provenance
from .scoring import MetricDistributions, decision_from_score, score_from_metrics

LOGGER = get_logger("services.analysis")


def _to_float(value) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@dataclass
class RawMetrics:
    appreciation_5y: Optional[float]
    cap_rate_est: Optional[float]
    rent_growth_3y: Optional[float]
    market_strength: Optional[float]
    zip_income: Optional[float]
    zip_vacancy_rate: Optional[float]

    def as_dict(self) -> Dict[str, Optional[float]]:
        return {
            "appreciation_5y": self.appreciation_5y,
            "cap_rate_est": self.cap_rate_est,
            "rent_growth_3y": self.rent_growth_3y,
            "market_strength": self.market_strength,
        }


class AnalysisService:
    def __init__(self, repository, forecast_service: ForecastService, comps_service: CompsService) -> None:
        self.repository = repository
        self.forecast_service = forecast_service
        self.comps_service = comps_service

    def analyze_property(self, property_id: str) -> AnalysisResponse:
        property_obj = self.repository.get_property(property_id)
        if property_obj is None:
            raise ValueError(f"Property not found: {property_id}")

        market_rows = self.repository.get_market_stats(property_obj["zipcode"])
        market_df = pd.DataFrame(market_rows)
        raw_metrics = self._compute_metrics(property_obj, market_df)
        distributions = self._metric_distributions()
        score = score_from_metrics(raw_metrics.as_dict(), distributions)
        decision = decision_from_score(score)

        forecasts = self.forecast_service.get_zip_forecast(property_obj["zipcode"])
        price_history = [TrendPoint(**point) for point in forecasts["median_price"].history]
        price_forecast = [TrendPoint(**point) for point in forecasts["median_price"].forecast]
        rent_history = [TrendPoint(**point) for point in forecasts["median_rent"].history]
        rent_forecast = [TrendPoint(**point) for point in forecasts["median_rent"].forecast]

        comps: List[Comp] = self.comps_service.get_ranked_comps(property_obj)

        current_value = _to_float(property_obj.get("current_est_value")) or 0.0
        analysis_metrics = AnalysisMetrics(
            current_est_value=current_value,
            appreciation_5y=raw_metrics.appreciation_5y,
            cap_rate_est=raw_metrics.cap_rate_est,
            rent_growth_3y=raw_metrics.rent_growth_3y,
            market_strength=raw_metrics.market_strength,
            zip_income=raw_metrics.zip_income,
            zip_vacancy_rate=raw_metrics.zip_vacancy_rate,
        )

        sources = [src for src in [dataset_provenance()] if src]
        analysis = AnalysisResponse(
            property_id=property_obj.get("id") or property_obj.get("sys_id"),
            address=property_obj.get("address"),
            zip=str(property_obj.get("zipcode")),
            metrics=analysis_metrics,
            score=score,
            decision=decision,
            zip_trends=ZipTrends(
                price_history=price_history,
                rent_history=rent_history,
                price_forecast=price_forecast,
                rent_forecast=rent_forecast,
            ),
            comps=comps,
            provenance={
                "sources": sources,
                "generated_at": pd.Timestamp.utcnow().isoformat(),
            },
        )
        return analysis

    def _compute_metrics(self, property_obj: dict, market_df: pd.DataFrame) -> RawMetrics:
        df = market_df.copy()
        if df.empty:
            return RawMetrics(None, None, None, None, None, None)
        df["date"] = pd.to_datetime(df.get("date"), errors="coerce")
        df = df.dropna(subset=["date"])
        df = df.sort_values("date")
        latest = df.iloc[-1]

        current_value = _to_float(property_obj.get("current_est_value")) or float(latest.get("median_price", 0.0))

        five_years_ago = latest["date"] - pd.DateOffset(years=5)
        historical = df[df["date"] <= five_years_ago]
        if historical.empty:
            historical = df.head(1)
        value_5y = float(historical.iloc[-1].get("median_price", 0.0))
        appreciation = None
        if value_5y > 0:
            appreciation = (float(latest.get("median_price", 0.0)) - value_5y) / value_5y

        cap_rate = None
        rent_est = _to_float(property_obj.get("est_monthly_rent"))
        if rent_est and current_value:
            cap_rate = (12 * rent_est) / current_value

        three_years_ago = latest["date"] - pd.DateOffset(years=3)
        rent_history = df[df["date"] <= three_years_ago]
        if rent_history.empty:
            rent_history = df.head(1)
        rent_history = rent_history.sort_values("date")
        rent_3y = float(rent_history.iloc[-1].get("median_rent", 0.0))
        rent_growth = None
        if rent_3y > 0:
            period_years = max((latest["date"] - rent_history.iloc[-1]["date"]).days / 365.25, 0.0)
            if period_years >= 1.0:
                ratio = float(latest.get("median_rent", 0.0)) / rent_3y
                rent_growth = ratio ** (1 / period_years) - 1

        income_series = pd.to_numeric(df.get("income"), errors="coerce")
        vacancy_series = pd.to_numeric(df.get("vacancy_rate"), errors="coerce")
        income_mean = income_series.mean()
        income_std = income_series.std()
        vacancy_mean = vacancy_series.mean()
        vacancy_std = vacancy_series.std()
        income_z = 0.0
        vacancy_z = 0.0
        latest_income = float(pd.to_numeric(pd.Series([latest.get("income")]), errors="coerce").iloc[0]) if pd.notna(latest.get("income")) else None
        latest_vacancy = float(pd.to_numeric(pd.Series([latest.get("vacancy_rate")]), errors="coerce").iloc[0]) if pd.notna(latest.get("vacancy_rate")) else None
        if income_std and not np.isnan(income_std) and latest_income is not None:
            income_z = (latest_income - income_mean) / income_std
        if vacancy_std and not np.isnan(vacancy_std) and latest_vacancy is not None:
            vacancy_z = (latest_vacancy - vacancy_mean) / vacancy_std
        market_strength = income_z - vacancy_z

        return RawMetrics(
            appreciation_5y=appreciation,
            cap_rate_est=cap_rate,
            rent_growth_3y=rent_growth,
            market_strength=market_strength,
            zip_income=latest_income,
            zip_vacancy_rate=latest_vacancy,
        )

    @memoize("analysis.distributions")
    def _metric_distributions(self) -> MetricDistributions:
        metrics = {"appreciation_5y": [], "cap_rate_est": [], "rent_growth_3y": [], "market_strength": []}
        properties = self.repository.list_properties(limit=None)
        for prop in properties:
            market_rows = self.repository.get_market_stats(prop["zipcode"])
            market_df = pd.DataFrame(market_rows)
            raw = self._compute_metrics(prop, market_df)
            for key, value in raw.as_dict().items():
                if value is not None and np.isfinite(value):
                    metrics[key].append(float(value))
        for key in metrics:
            if not metrics[key]:
                metrics[key] = [0.0]
        return MetricDistributions(**metrics)

    def warm_caches(self) -> None:
        for prop in self.repository.list_properties(limit=None):
            try:
                self.analyze_property(prop["id"])
            except Exception as exc:  # pragma: no cover - warm best effort
                LOGGER.warning("Failed to warm analysis cache property_id=%s error=%s", prop.get("id"), exc)

