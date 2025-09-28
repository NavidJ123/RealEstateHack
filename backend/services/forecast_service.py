"""Forecast generation for median price and rent using Prophet with ARIMA fallback."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import pandas as pd

from ..utils.caching import memoize
from ..utils.logging import get_logger

LOGGER = get_logger("services.forecast")


@dataclass
class ForecastResult:
    history: List[Dict[str, float]]
    forecast: List[Dict[str, float]]


class ForecastService:
    def __init__(self, repository):
        self.repository = repository
        try:
            from prophet import Prophet  # type: ignore

            self._Prophet = Prophet
        except Exception:  # pragma: no cover - optional dependency
            LOGGER.warning("Prophet not available; will fall back to ARIMA")
            self._Prophet = None

        try:
            from pmdarima import auto_arima  # type: ignore

            self._auto_arima = auto_arima
        except Exception:  # pragma: no cover - optional dependency
            self._auto_arima = None
            LOGGER.warning("pmdarima not available; forecasts will be naive")

    @memoize("forecast")
    def get_zip_forecast(self, zipcode: str) -> Dict[str, ForecastResult]:
        records = self.repository.get_market_stats(zipcode)
        df = pd.DataFrame(records)
        if df.empty:
            return {
                "median_price": ForecastResult(history=[], forecast=[]),
                "median_rent": ForecastResult(history=[], forecast=[]),
            }
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"])
        df = df.sort_values("date")
        forecasts = {}
        for metric in ["median_price", "median_rent"]:
            history_points = [
                {"date": row["date"].date().isoformat(), "value": float(row[metric])}
                for _, row in df.iterrows()
            ]
            forecast_points = self._build_forecast(df[["date", metric]].rename(columns={metric: "y"}), metric)
            forecasts[metric] = ForecastResult(history=history_points, forecast=forecast_points)
        return forecasts

    def projected_rent_growth(self, zipcode: str, months: int = 12) -> Optional[float]:
        forecasts = self.get_zip_forecast(zipcode)
        rent_history = forecasts["median_rent"].history
        rent_forecast = forecasts["median_rent"].forecast
        if not rent_history or not rent_forecast:
            return None
        latest_value = rent_history[-1]["value"]
        if latest_value in (None, 0):
            return None
        idx = min(months, len(rent_forecast)) - 1
        target_value = rent_forecast[idx]["value"]
        if target_value is None:
            return None
        try:
            return float(target_value / latest_value - 1)
        except ZeroDivisionError:
            return None

    def _build_forecast(self, df: pd.DataFrame, metric: str) -> List[Dict[str, float]]:
        df = df.rename(columns={"date": "ds"})
        df = df.reset_index(drop=True)
        future_periods = 36
        if self._Prophet:
            try:
                model = self._Prophet()
                model.fit(df)
                future = model.make_future_dataframe(periods=future_periods, freq="MS")
                forecast = model.predict(future).tail(future_periods)
                return [
                    {
                        "date": row["ds"].date().isoformat(),
                        "value": float(row["yhat"]),
                        "lower": float(row["yhat_lower"]),
                        "upper": float(row["yhat_upper"]),
                    }
                    for _, row in forecast.iterrows()
                ]
            except Exception as exc:  # pragma: no cover - we fallback below
                LOGGER.warning("Prophet forecast failed metric=%s error=%s", metric, exc)
        if self._auto_arima:
            try:
                series = df["y"].astype(float).values
                model = self._auto_arima(series, seasonal=False, suppress_warnings=True)
                forecast, conf_int = model.predict(n_periods=future_periods, return_conf_int=True, alpha=0.20)
                last_date = df["ds"].iloc[-1]
                points = []
                for idx in range(future_periods):
                    date = (last_date + pd.DateOffset(months=idx + 1)).date().isoformat()
                    points.append(
                        {
                            "date": date,
                            "value": float(forecast[idx]),
                            "lower": float(conf_int[idx, 0]),
                            "upper": float(conf_int[idx, 1]),
                        }
                    )
                return points
            except Exception as exc:  # pragma: no cover - fallback further below
                LOGGER.warning("ARIMA forecast failed metric=%s error=%s", metric, exc)
        # naive fallback: extend last known value with slight trend based on slope
        series = df["y"].astype(float).values
        if len(series) < 2:
            baseline = series[0] if len(series) else 0.0
            return [
                {"date": (df["ds"].iloc[-1] + pd.DateOffset(months=i + 1)).date().isoformat(), "value": float(baseline), "lower": float(baseline), "upper": float(baseline)}
                for i in range(future_periods)
            ]
        slope = (series[-1] - series[0]) / max(len(series) - 1, 1)
        last_date = df["ds"].iloc[-1]
        baseline = series[-1]
        points = []
        for idx in range(future_periods):
            date = (last_date + pd.DateOffset(months=idx + 1)).date().isoformat()
            value = baseline + slope * (idx + 1)
            points.append({"date": date, "value": float(value), "lower": float(value * 0.96), "upper": float(value * 1.04)})
        return points

