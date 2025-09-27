"""Compute property analytics and assemble structured responses."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

import numpy as np
import pandas as pd

from ..models.analysis import Analysis, AnalysisMetrics, ZipTrendPoint, ZipTrends
from ..models.property import Property
from ..utils.caching import memoize
from ..utils.logging import get_logger
from .comps_service import CompsService
from .forecast_service import ForecastService
from .provenance import dataset_provenance
from .scoring import MetricDistributions, decision_from_score, score_from_metrics

LOGGER = get_logger("services.analysis")


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

    def analyze_property(self, property_id: str) -> Analysis:
        property_obj = self.repository.get_property(property_id)
        if property_obj is None:
            raise ValueError(f"Property not found: {property_id}")
        market_df = self.repository.get_market_stats(property_obj.zipcode)
        metrics = self._compute_metrics(property_obj, market_df)
        all_metrics = self._metric_distributions()
        score = score_from_metrics(metrics.as_dict(), all_metrics)
        decision = decision_from_score(score)

        forecasts = self.forecast_service.get_zip_forecast(property_obj.zipcode)
        price_history = [ZipTrendPoint(**point) for point in forecasts["median_price"].history]
        price_forecast = [ZipTrendPoint(**point) for point in forecasts["median_price"].forecast]
        rent_history = [ZipTrendPoint(**point) for point in forecasts["median_rent"].history]
        rent_forecast = [ZipTrendPoint(**point) for point in forecasts["median_rent"].forecast]

        comps = self.comps_service.get_ranked_comps(property_obj)

        analysis_metrics = AnalysisMetrics(
            current_est_value=float(property_obj.current_est_value or 0.0),
            appreciation_5y=metrics.appreciation_5y,
            cap_rate_est=metrics.cap_rate_est,
            rent_growth_3y=metrics.rent_growth_3y,
            market_strength=metrics.market_strength,
            zip_income=metrics.zip_income,
            zip_vacancy_rate=metrics.zip_vacancy_rate,
        )
        analysis = Analysis(
            property_id=property_obj.id,
            address=property_obj.address,
            zip=property_obj.zipcode,
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
            provenance={"market_stats": dataset_provenance(), "generated_at": pd.Timestamp.utcnow().isoformat()},
        )
        return analysis

    def _compute_metrics(self, property_obj: Property, market_df: pd.DataFrame) -> RawMetrics:
        df = market_df.copy()
        if df.empty:
            return RawMetrics(None, None, None, None, None, None)
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"])
        df = df.sort_values("date")
        latest = df.iloc[-1]
        current_value = property_obj.current_est_value or float(latest["median_price"])
        # Appreciation over 5 years (60 months)
        five_years_ago = latest["date"] - pd.DateOffset(years=5)
        historical = df[df["date"] <= five_years_ago]
        if historical.empty:
            historical = df.head(1)
        value_5y = float(historical.iloc[-1]["median_price"])
        appreciation = (float(latest["median_price"]) - value_5y) / value_5y if value_5y else None

        # Cap rate estimate using rent
        cap_rate = None
        if property_obj.est_monthly_rent and current_value:
            cap_rate = (12 * float(property_obj.est_monthly_rent)) / float(current_value)

        # Rent growth CAGR over 3 years (36 months)
        three_years_ago = latest["date"] - pd.DateOffset(years=3)
        rent_history = df[df["date"] <= three_years_ago]
        if rent_history.empty:
            rent_history = df.head(1)
        rent_history = rent_history.sort_values("date")
        rent_3y = float(rent_history.iloc[-1]["median_rent"])
        rent_growth = None
        if rent_3y > 0:
            period_years = max((latest["date"] - rent_history.iloc[-1]["date"]).days / 365.25, 0.0)
            if period_years >= 1.0:
                ratio = float(latest["median_rent"]) / rent_3y
                rent_growth = ratio ** (1 / period_years) - 1

        # Market strength via income and vacancy
        income_mean = df["income"].astype(float).mean()
        income_std = df["income"].astype(float).std()
        vacancy_mean = df["vacancy_rate"].astype(float).mean()
        vacancy_std = df["vacancy_rate"].astype(float).std()
        income_z = 0.0
        vacancy_z = 0.0
        if income_std and not np.isnan(income_std):
            income_z = (float(latest["income"]) - income_mean) / income_std
        if vacancy_std and not np.isnan(vacancy_std):
            vacancy_z = (float(latest["vacancy_rate"]) - vacancy_mean) / vacancy_std
        market_strength = income_z - vacancy_z

        zip_income = float(latest["income"]) if pd.notna(latest.get("income")) else None
        zip_vacancy = float(latest["vacancy_rate"]) if pd.notna(latest.get("vacancy_rate")) else None
        return RawMetrics(
            appreciation_5y=appreciation,
            cap_rate_est=cap_rate,
            rent_growth_3y=rent_growth,
            market_strength=market_strength,
            zip_income=zip_income,
            zip_vacancy_rate=zip_vacancy,
        )

    @memoize("analysis.distributions")
    def _metric_distributions(self) -> MetricDistributions:
        metrics = {"appreciation_5y": [], "cap_rate_est": [], "rent_growth_3y": [], "market_strength": []}
        for property_obj in self.repository.list_properties(limit=None):
            market_df = self.repository.get_market_stats(property_obj.zipcode)
            raw = self._compute_metrics(property_obj, market_df)
            for key, value in raw.as_dict().items():
                if value is not None and np.isfinite(value):
                    metrics[key].append(float(value))
        # provide fallbacks to avoid empty iterables
        for key in metrics:
            if not metrics[key]:
                metrics[key] = [0.0]
        return MetricDistributions(**metrics)

    def warm_caches(self) -> None:
        """Preload analysis for all properties; useful at startup."""
        for prop in self.repository.list_properties(limit=None):
            try:
                self.analyze_property(prop.id)
            except Exception as exc:
                LOGGER.warning("Failed to warm analysis cache property_id=%s error=%s", prop.id, exc)

