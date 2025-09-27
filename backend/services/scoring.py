"""Scoring helpers for Buy/Hold/Sell decisions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Optional

from ..utils.normalize import bounded_min_max, sigmoid_z

SCORING_WEIGHTS = {
    "appreciation_5y": 0.40,
    "cap_rate_est": 0.30,
    "rent_growth_3y": 0.20,
    "market_strength": 0.10,
}


@dataclass
class MetricDistributions:
    appreciation_5y: Iterable[float]
    cap_rate_est: Iterable[float]
    rent_growth_3y: Iterable[float]
    market_strength: Iterable[float]


def normalize_metric(name: str, value: Optional[float], distributions: MetricDistributions) -> float:
    """Normalize a metric to 0-1 range; default to 0.5 when value is missing."""

    if value is None:
        return 0.5
    values = getattr(distributions, name)
    return bounded_min_max(value, values)


def score_from_metrics(metrics: Dict[str, Optional[float]], distributions: MetricDistributions) -> int:
    """Compute the 0-100 score and clamp via sigmoid."""

    total = 0.0
    for name, weight in SCORING_WEIGHTS.items():
        normalized = normalize_metric(name, metrics.get(name), distributions)
        total += weight * normalized
    # Convert from [0,1] to (-inf,+inf) like z via simple centering and scaling
    score_raw_like_z = (total - 0.5) * 5
    score = sigmoid_z(score_raw_like_z) * 100
    score = max(0, min(100, round(score)))
    return int(score)


def decision_from_score(score: int) -> str:
    if score >= 75:
        return "Buy"
    if score >= 55:
        return "Hold"
    return "Sell"

