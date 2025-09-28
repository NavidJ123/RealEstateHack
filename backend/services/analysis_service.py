"""Compute property analytics and assemble structured responses."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from ..models.analysis import AnalysisMetrics, AnalysisResponse, Comp, Explanations, FactorPayload, TrendPoint, ZipTrends
from ..utils.caching import memoize
from ..utils.logging import get_logger
from .comps_service import CompsService
from .forecast_service import ForecastService
from .scoring import ScoringResult, MetricDistributions, build_factor_attributions, prepare_distributions
from ..db.repo import Repo

LOGGER = get_logger("services.analysis")

DEFAULT_LTV = float(os.getenv("ASSUME_LTV", "0.65"))
DEFAULT_RATE = float(os.getenv("ASSUME_DEBT_RATE", "0.062"))
DEFAULT_AMORT_YEARS = int(os.getenv("ASSUME_AMORT_YEARS", "30"))


@dataclass
class ComputedBundle:
    metrics: Dict[str, Optional[float]]
    components: Dict[str, Optional[float]]
    median_rent_series: List[Dict[str, Optional[float]]]
    median_price_series: List[Dict[str, Optional[float]]]


class AnalysisService:
    def __init__(self, repository: Repo, forecast_service: ForecastService, comps_service: CompsService) -> None:
        self.repository = repository
        self.forecast_service = forecast_service
        self.comps_service = comps_service

    def analyze_property(self, property_id: str) -> AnalysisResponse:
        property_row = self.repository.get_property(property_id)
        if not property_row:
            raise ValueError(f"Property not found: {property_id}")

        bundle = self._compute_metrics(property_row, include_forecast=True)
        distributions = self._metric_distributions()
        scoring: ScoringResult = build_factor_attributions(bundle.metrics, distributions)

        zip_trends = ZipTrends(
            price_history=[TrendPoint(**pt) for pt in bundle.median_price_series],
            rent_history=[TrendPoint(**pt) for pt in bundle.median_rent_series],
            price_forecast=self._forecast_series(property_row, metric="median_price"),
            rent_forecast=self._forecast_series(property_row, metric="median_rent"),
        )

        comps = self.comps_service.get_ranked_comps(property_row)

        explanations = Explanations(
            factors=[
                FactorPayload(
                    name=factor.name,
                    key=factor.key,
                    weight=factor.weight,
                    value=factor.value,
                    norm=factor.normalized,
                    contrib=factor.contribution,
                )
                for factor in scoring.factors
            ],
            fallback_total_score=scoring.fallback_total_score,
        )

        analysis_metrics = AnalysisMetrics(**bundle.metrics)
        sources = property_row.get("provenance", [])
        if isinstance(sources, str):
            sources = [sources]
        elif sources is None:
            sources = []
        if "Gotham Market CSV" not in sources:
            sources.append("Gotham Market CSV")

        analysis = AnalysisResponse(
            property_id=str(property_row.get("id") or property_id),
            address=property_row.get("address", ""),
            zip=str(property_row.get("zipcode") or property_row.get("zip") or ""),
            metrics=analysis_metrics,
            score=scoring.fallback_total_score,
            decision=scoring.decision,
            explanations=explanations,
            zip_trends=zip_trends,
            comps=comps,
            provenance={
                "sources": sources,
                "generated_at": pd.Timestamp.utcnow().isoformat(),
            },
        )
        return analysis

    @memoize("analysis.metric_distributions")
    def _metric_distributions(self) -> MetricDistributions:
        dataset = self.repository.get_distribution_dataset()
        if not dataset:
            dataset = [{}]
        return prepare_distributions(dataset)

    def _compute_metrics(self, property_row: Dict[str, Optional[float]], include_forecast: bool) -> ComputedBundle:
        market_records = self.repository.get_market_series_for_property(property_row)
        if not market_records:
            raise ValueError("No market records for property submarket")
        market_df = self._market_frame(market_records)
        latest = market_df.iloc[-1]

        cap_rate_market_now = _coalesce(
            property_row.get("cap_rate_market_now"),
            latest.get("cap_rate_market_now"),
        )

        target_key = str(property_row.get("submarket") or property_row.get("zipcode") or property_row.get("zip") or "")
        rent_growth_proj_12m: Optional[float] = None
        if include_forecast and target_key:
            rent_growth_proj_12m = self.forecast_service.projected_rent_growth(target_key, months=12)
        if rent_growth_proj_12m is None:
            rent_growth_proj_12m = _safe_float(latest.get("rent_yoy"))

        vacancy_now = _safe_float(latest.get("vacancy_rate"))
        dom_now = _safe_float(latest.get("dom"))
        availability_now = _safe_float(latest.get("availability_rate"))

        msi = self._market_strength_index(rent_growth_proj_12m, vacancy_now, availability_now)
        affordability_index, rent_to_income_ratio = self._affordability(property_row, latest)
        appreciation_5y = self._appreciation(market_df, years=5)
        dscr_proj = self._projected_dscr(property_row, cap_rate_market_now)

        income_now = _safe_float(property_row.get("median_income_now")) or _safe_float(latest.get("median_income"))
        income_growth_3y = self._compound_growth(market_df, "median_income", years=3)

        metrics = {
            "current_est_value": _safe_float(property_row.get("current_est_value")),
            "cap_rate_market_now": cap_rate_market_now,
            "rent_growth_proj_12m": rent_growth_proj_12m,
            "income_median_now": income_now,
            "income_growth_3y": income_growth_3y,
            "vacancy_rate_now": vacancy_now,
            "dom_now": dom_now,
            "affordability_index": affordability_index,
            "rent_to_income_ratio": rent_to_income_ratio,
            "market_strength_index": msi,
            "dscr_proj": dscr_proj,
            "appreciation_5y": appreciation_5y,
        }

        components = {
            "rent_growth_12m": rent_growth_proj_12m,
            "vacancy_rate_now": vacancy_now,
            "dom_now": dom_now,
        }

        rent_series = [
            {"date": row["date"].date().isoformat(), "value": float(row["median_rent"])}
            for _, row in market_df.iterrows()
            if pd.notna(row.get("median_rent"))
        ]
        price_series = [
            {"date": row["date"].date().isoformat(), "value": float(row["median_price"])}
            for _, row in market_df.iterrows()
            if pd.notna(row.get("median_price"))
        ]

        return ComputedBundle(metrics=metrics, components=components, median_rent_series=rent_series, median_price_series=price_series)

    def _forecast_series(self, property_row: Dict[str, Optional[float]], metric: str) -> List[TrendPoint]:
        target_key = str(property_row.get("submarket") or property_row.get("zipcode") or property_row.get("zip") or "")
        if not target_key:
            return []
        forecasts = self.forecast_service.get_zip_forecast(target_key)
        series = forecasts.get("median_rent" if metric == "median_rent" else "median_price")
        if series is None:
            return []
        return [TrendPoint(**point) for point in series.forecast]

    def _market_frame(self, records: List[Dict[str, Optional[float]]]) -> pd.DataFrame:
        frame = pd.DataFrame(records)
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
        frame = frame.dropna(subset=["date"]).sort_values("date")
        for col in ["median_price", "median_rent", "cap_rate_market_now", "median_income", "vacancy_rate", "dom", "rent_yoy", "availability_rate"]:
            if col in frame.columns:
                frame[col] = pd.to_numeric(frame[col], errors="coerce")
        return frame.dropna(subset=["median_rent"]) if "median_rent" in frame.columns else frame

    def _trailing_rent_growth(self, df: pd.DataFrame, months: int = 12) -> Optional[float]:
        if df.empty or "median_rent" not in df:
            return None
        rents = df.dropna(subset=["median_rent"])
        if rents.empty:
            return None
        latest = rents.iloc[-1]
        idx = max(0, len(rents) - months - 1)
        base = rents.iloc[idx]
        if base["median_rent"] and base["median_rent"] > 0:
            return float(latest["median_rent"] / base["median_rent"] - 1)
        return None

    def _compound_growth(self, df: pd.DataFrame, column: str, years: int = 3) -> Optional[float]:
        if column not in df:
            return None
        series = df.dropna(subset=[column])
        if series.empty:
            return None
        latest = series.iloc[-1]
        cutoff = latest["date"] - pd.DateOffset(years=years)
        history = series[series["date"] <= cutoff]
        if history.empty:
            history = series.head(1)
        start_val = history.iloc[-1][column]
        end_val = latest[column]
        if start_val is None or end_val is None or start_val <= 0 or end_val <= 0:
            return None
        years_elapsed = max((latest["date"] - history.iloc[-1]["date"]).days / 365.25, 0.0)
        if years_elapsed <= 0:
            return None
        return float((end_val / start_val) ** (1 / years_elapsed) - 1)

    def _market_strength_index(
        self,
        rent_growth: Optional[float],
        vacancy: Optional[float],
        availability: Optional[float],
    ) -> Optional[float]:
        factors = []
        if rent_growth is not None:
            factors.append((rent_growth - 0.02) / 0.02)
        if vacancy is not None:
            factors.append(-(vacancy - 0.06) / 0.03)
        if availability is not None:
            factors.append(-(availability - 0.08) / 0.04)
        if not factors:
            return None
        return float(np.mean(factors))

    def _affordability(self, property_row: Dict[str, Optional[float]], latest: pd.Series) -> Tuple[Optional[float], Optional[float]]:
        rent = _safe_float(property_row.get("est_monthly_rent")) or _safe_float(latest.get("median_rent"))
        income = _safe_float(latest.get("median_income")) or _safe_float(property_row.get("median_income_now"))
        if not rent or not income or income <= 0:
            return None, None
        ratio = (rent * 12) / income
        return max(0.0, min(1.0, 1 - ratio)), ratio

    def _appreciation(self, df: pd.DataFrame, years: int = 5) -> Optional[float]:
        if "median_price" not in df or df.empty:
            return None
        latest = df.iloc[-1]
        cutoff = latest["date"] - pd.DateOffset(years=years)
        history = df[df["date"] <= cutoff]
        if history.empty:
            history = df.head(1)
        base = history.iloc[-1]["median_price"]
        if base and base > 0 and latest["median_price"]:
            return float(latest["median_price"] / base - 1)
        return None

    def _projected_dscr(self, property_row: Dict[str, Optional[float]], cap_rate_market_now: Optional[float]) -> Optional[float]:
        noi = _safe_float(property_row.get("noi_t12"))
        value = _safe_float(property_row.get("current_est_value"))
        if not value and noi and cap_rate_market_now and cap_rate_market_now > 0:
            value = noi / cap_rate_market_now
        if not noi or not value:
            return None
        loan_amount = value * DEFAULT_LTV
        monthly_rate = DEFAULT_RATE / 12
        periods = DEFAULT_AMORT_YEARS * 12
        if monthly_rate <= 0 or periods <= 0:
            return None
        payment = (loan_amount * monthly_rate) / (1 - (1 + monthly_rate) ** (-periods))
        annual_debt_service = payment * 12
        if annual_debt_service <= 0:
            return None
        return float(noi / annual_debt_service)


_SERVICE_SINGLETON: AnalysisService | None = None


def _get_default_service() -> AnalysisService:
    global _SERVICE_SINGLETON
    if _SERVICE_SINGLETON is None:
        repository = Repo()
        forecast = ForecastService(repository)
        comps = CompsService(repository)
        _SERVICE_SINGLETON = AnalysisService(repository, forecast, comps)
    return _SERVICE_SINGLETON


def analyze_property(property_id: str) -> AnalysisResponse:
    """Module-level helper used by the FastAPI layer."""

    service = _get_default_service()
    return service.analyze_property(property_id)


def _safe_float(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coalesce(*values):
    for val in values:
        if val is not None:
            try:
                return float(val)
            except (TypeError, ValueError):
                continue
    return None
