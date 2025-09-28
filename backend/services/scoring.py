"""Deterministic scoring utilities for fallback analytics and tests."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Tuple

import numpy as np

MetricKey = str


@dataclass(frozen=True)
class FactorAttribution:
    """Represents the contribution of an individual metric to the fallback score."""

    name: str
    key: MetricKey
    weight: float
    value: Optional[float]
    normalized: float
    contribution: float


@dataclass(frozen=True)
class ScoringResult:
    """Composite scoring output used by the analysis service and tests."""

    fallback_total_score: int
    decision: str
    factors: List[FactorAttribution]


class MetricDistributions:
    """Holds percentile bands for each scoring metric used in fallback scoring."""

    def __init__(self, percentiles: Mapping[MetricKey, Sequence[float]]) -> None:
        cleaned: Dict[MetricKey, Tuple[float, float, float, float]] = {}
        for key, values in percentiles.items():
            if len(values) < 4:
                raise ValueError(f"Expected four percentile values for '{key}', got {values}")
            cleaned[key] = tuple(float(v) for v in values[:4])  # type: ignore[assignment]
        self._percentiles = cleaned

    def get(self, key: MetricKey) -> Tuple[float, float, float, float]:
        return self._percentiles.get(key, DEFAULT_DISTRIBUTIONS[key])

    def to_dict(self) -> Dict[MetricKey, Tuple[float, float, float, float]]:
        return dict(self._percentiles)


# ---------------------------------------------------------------------------
# Scoring configuration and helpers
# ---------------------------------------------------------------------------

METRIC_WEIGHTS: Dict[MetricKey, Tuple[str, float]] = {
    "cap_rate_market_now": ("Market Cap Rate", 0.35),
    "rent_growth_proj_12m": ("Projected Rent Growth (12m)", 0.35),
    "market_strength_index": ("Market Strength Index", 0.30),
}

DEFAULT_DISTRIBUTIONS: Dict[MetricKey, Tuple[float, float, float, float]] = {
    "cap_rate_market_now": (0.03, 0.05, 0.07, 0.08),
    "rent_growth_proj_12m": (0.0, 0.02, 0.04, 0.06),
    "market_strength_index": (-1.5, 0.0, 0.8, 1.5),
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def decision_from_score(score: Optional[int]) -> str:
    if score is None:
        return "Hold"
    if score >= 75:
        return "Buy"
    if score >= 55:
        return "Hold"
    return "Sell"


def build_factor_attributions(
    metrics: Mapping[MetricKey, Optional[float]],
    distributions: MetricDistributions,
) -> ScoringResult:
    total = 0.0
    factors: List[FactorAttribution] = []
    for key, (label, weight) in METRIC_WEIGHTS.items():
        value = _safe_float(metrics.get(key))
        percentiles = distributions.get(key)
        norm = _normalise(value, percentiles)
        total += weight * norm
        factors.append(
            FactorAttribution(
                name=label,
                key=key,
                weight=weight,
                value=value,
                normalized=norm,
                contribution=weight * norm * 100,
            )
        )

    fallback_score = int(round(100 * total))
    fallback_score = max(0, min(100, fallback_score))
    return ScoringResult(
        fallback_total_score=fallback_score,
        decision=decision_from_score(fallback_score),
        factors=factors,
    )


def prepare_distributions(dataset: Iterable[Mapping[str, Optional[float]]]) -> MetricDistributions:
    buckets: MutableMapping[MetricKey, List[float]] = {key: [] for key in METRIC_WEIGHTS}
    for row in dataset:
        for key in METRIC_WEIGHTS:
            value = _safe_float(row.get(key))
            if value is not None and not math.isnan(value):
                buckets[key].append(value)

    percentiles: Dict[MetricKey, Tuple[float, float, float, float]] = {}
    for key, values in buckets.items():
        if values:
            arr = np.array(values, dtype=float)
            percentiles[key] = (
                float(np.nanpercentile(arr, 10)),
                float(np.nanpercentile(arr, 50)),
                float(np.nanpercentile(arr, 90)),
                float(np.nanpercentile(arr, 98)),
            )
        else:
            percentiles[key] = DEFAULT_DISTRIBUTIONS[key]

    return MetricDistributions(percentiles)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _normalise(value: Optional[float], bounds: Tuple[float, float, float, float]) -> float:
    if value is None or math.isnan(value):
        return 0.0
    lo, _, _, hi = bounds
    if math.isclose(hi, lo):
        return 0.5
    if value <= lo:
        return 0.0
    if value >= hi:
        return 1.0
    return float((value - lo) / (hi - lo))


def _safe_float(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(result):
        return None
    return result
