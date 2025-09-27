"""Scoring helpers for Buy/Hold/Sell decisions.

This module turns raw numeric metrics about a property into a single
score from 0 to 100 and then a simple decision label.

High-level steps:
1. Normalize each metric into a 0-1 range using historical distributions.
2. Combine the normalized metrics with domain weights to form a weighted
   average in [0,1].
3. Stretch and pass the result through a sigmoid to compress extremes and
   produce a final 0-100 score.
4. Map the numeric score to Buy/Hold/Sell labels with simple thresholds.

The helper functions `bounded_min_max` and `sigmoid_z` are imported from
`..utils.normalize` and handle the normalization math and sigmoid mapping.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Optional

from ..utils.normalize import bounded_min_max, sigmoid_z


# These weights control how important each metric is to the final score.
# They should sum to 1.0 (or close) so the weighted average stays in [0,1].
SCORING_WEIGHTS = {
    "appreciation_5y": 0.40,  # how much the area appreciated over 5 years
    "cap_rate_est": 0.30,     # estimated capitalization rate (income-based)
    "rent_growth_3y": 0.20,   # recent rent growth
    "market_strength": 0.10,  # qualitative/aggregate market signal
}


@dataclass
class MetricDistributions:
    """Container for historical distributions used to normalize metrics.

    Each attribute should be an iterable (e.g., list) of past values for that
    metric. We use these to map a current value into a 0-1 range relative to
    historical min/max (via `bounded_min_max`).
    """

    appreciation_5y: Iterable[float]
    cap_rate_est: Iterable[float]
    rent_growth_3y: Iterable[float]
    market_strength: Iterable[float]


def normalize_metric(name: str, value: Optional[float], distributions: MetricDistributions) -> float:
    """Turn a raw metric value into a normalized score in [0,1].

    - name: the key matching an attribute on `distributions` (e.g. 'cap_rate_est').
    - value: the current metric value to normalize. If value is missing (None)
      we return 0.5 which represents a neutral/default score.
    - distributions: historical values used to compute a relative position.

    The actual mapping is performed by `bounded_min_max(value, values)` which
    returns where `value` falls between the observed min and max in `values`.
    If the value is lower than the historical min it will be clamped to 0.0,
    and if higher than the max it is clamped to 1.0.
    """

    # If there's no data for this property, return the neutral midpoint.
    if value is None:
        return 0.5

    # Get the historical values for this metric (using the attribute name).
    values = getattr(distributions, name)

    # Map to [0,1] relative to historical min/max and return.
    return bounded_min_max(value, values)


def score_from_metrics(metrics: Dict[str, Optional[float]], distributions: MetricDistributions) -> int:
    """Compute a 0-100 integer score from raw metrics.

    Steps:
    1. For each metric, normalize it to [0,1]. Missing metrics become 0.5.
    2. Multiply each normalized value by its weight and sum to get a weighted
       average `total` in [0,1].
    3. Convert the weighted average into a z-like value (center at 0 -> good/bad
       around 0) by subtracting 0.5 and scaling. This gives more room to the
       sigmoid to compress extreme values.
    4. Apply `sigmoid_z` to squash the value into (0,1), multiply by 100, round,
       and clamp to [0,100].

    Returns an integer score between 0 and 100.
    """

    # Weighted sum of normalized metrics (starts at 0.0)
    total = 0.0

    # Normalize each metric and accumulate weighted contribution
    for name, weight in SCORING_WEIGHTS.items():
        normalized = normalize_metric(name, metrics.get(name), distributions)
        total += weight * normalized

    # `total` is a weighted average in [0,1]. We re-center around 0 and scale
    # so the subsequent sigmoid has a meaningful slope. The factor 5 is an
    # empirical choice that controls how steep the transition is.
    score_raw_like_z = (total - 0.5) * 5

    # `sigmoid_z` maps real numbers to a (0,1) range and compresses extremes.
    score = sigmoid_z(score_raw_like_z) * 100

    # Ensure the final value is a rounded integer and clamped to [0,100].
    score = max(0, min(100, round(score)))
    return int(score)


def decision_from_score(score: int) -> str:
    """Turn a numeric score into a simple decision label.

    Thresholds:
    - 75 and above: "Buy"  (strong positive signal)
    - 55 to 74:     "Hold" (neutral/moderate)
    - below 55:     "Sell" (negative signal)

    These thresholds are simple heuristics and can be tuned later.
    """

    if score >= 75:
        return "Buy"
    if score >= 55:
        return "Hold"
    return "Sell"


