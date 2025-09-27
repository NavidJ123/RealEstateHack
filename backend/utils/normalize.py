"""Normalization utilities used for property scoring."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Tuple

import numpy as np


@dataclass(frozen=True)
class Bounds:
    minimum: float
    maximum: float

    def clamp(self, value: float) -> float:
        return max(self.minimum, min(self.maximum, value))


def bounded_min_max(value: float, values: Iterable[float], percentile_clip: Tuple[float, float] = (0.05, 0.95)) -> float:
    """Min-max normalize and optionally clip extremes via percentiles."""

    arr = np.array([v for v in values if np.isfinite(v)])
    if arr.size == 0:
        return 0.5
    lo_pct, hi_pct = percentile_clip
    lower = np.percentile(arr, lo_pct * 100)
    upper = np.percentile(arr, hi_pct * 100)
    lower, upper = float(lower), float(upper)
    if upper == lower:
        return 0.5
    value = max(lower, min(upper, value))
    normalized = (value - lower) / (upper - lower)
    return float(max(0.0, min(1.0, normalized)))


def sigmoid_z(value: float) -> float:
    """Convert a z-like value to 0-1 range via sigmoid."""

    return float(1 / (1 + np.exp(-value)))


def combine_z_scores(positive: float, negative: float) -> float:
    """Combine positive and negative indicators into a composite market strength.

    Positive inputs (e.g. income growth) lift the score while negative inputs
    (e.g. vacancy) reduce it. We convert to a pseudo z-score by subtraction.
    """

    return positive - negative


__all__ = ["Bounds", "bounded_min_max", "sigmoid_z", "combine_z_scores"]

