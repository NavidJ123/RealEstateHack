# backend/services/scoring.py
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple
import numpy as np


@dataclass
class Factor:
    name: str
    weight: float
    value: float
    contrib: float  # contribution to final 0..100 score (approx)

def score_property(metrics: Dict[str, float], norms: Dict) -> Dict:
    """
    Compute 0..100 score + decision + factor attributions.

    inputs (metrics):
      cap_rate_market_now       : float (e.g., 0.059 for 5.9%)
      rent_growth_proj_12m      : float (e.g., 0.041 for 4.1%)
      income_median_now         : float (e.g., 95000)
      income_growth_3y          : float (e.g., 0.028 for 2.8%)
      vacancy_rate_now          : float (e.g., 0.045 for 4.5%)
      dom_now                   : float or None (# days; optional)
      rent_to_income            : float or None (annual rent / income; optional, lower is better)

    inputs (norms): precomputed distribution params, e.g.:
      {
        "cap_minmax":   (cap_lo, cap_hi, clip_lo, clip_hi),
        "rentg_minmax": (rg_lo, rg_hi, clip_lo, clip_hi),
        "msi_minmax":   (msi_lo, msi_hi, None, None),
        "aff_minmax":   (aff_lo, aff_hi, None, None),

        "income_median_z": (mean, std),
        "income_growth_z": (mean, std),
        "vacancy_z":       (mean, std),
        "dom_z":           (mean, std),

        "raw_z": (mean, std)
      }

    returns:
      {
        "score": int 0..100,
        "decision": "Buy"|"Hold"|"Sell",
        "msi": float,
        "factors": [ {name, weight, value, contrib}, ... ]
      }
    """
    # --- Build MSI (income↑ + income_growth↑ − vacancy↓ − dom↓)
    dom = metrics.get("dom_now", None)
    dom_z = _z(dom, *norms["dom_z"]) if isinstance(dom, (float, int)) else 0.0

    msi = (
        _z(metrics["income_median_now"], *norms["income_median_z"])
        + _z(metrics["income_growth_3y"], *norms["income_growth_z"])
        - _z(metrics["vacancy_rate_now"], *norms["vacancy_z"])
        - dom_z
    )

    # --- Normalize contributors (robust min–max to 0..1)
    cap_norm   = _robust_minmax(metrics["cap_rate_market_now"], *norms["cap_minmax"])
    rentg_norm = _robust_minmax(metrics["rent_growth_proj_12m"], *norms["rentg_minmax"])
    msi_norm   = _robust_minmax(msi, *norms["msi_minmax"])

    # Affordability: higher is better when defined as (1 - rent_to_income)
    aff_value = 1.0 - float(metrics.get("rent_to_income", 0.30))
    aff_norm  = _robust_minmax(aff_value, *norms["aff_minmax"])

    # --- Weights (business-driven)
    W_CAP, W_RENTG, W_MSI, W_AFF = 0.35, 0.35, 0.20, 0.10

    raw = (W_CAP*cap_norm + W_RENTG*rentg_norm + W_MSI*msi_norm + W_AFF*aff_norm)

    # Map to 0..100 via sigmoid of z-scored raw (makes distribution nice)
    score = int(round(100 * _sigmoid(_z(raw, *norms["raw_z"]))))

    decision = "Buy" if score >= 75 else "Hold" if score >= 55 else "Sell"

    factors: List[Factor] = [
        Factor("Market Cap Rate",              W_CAP,  metrics["cap_rate_market_now"],     W_CAP*cap_norm*100),
        Factor("Projected Rent Growth (12m)",  W_RENTG,metrics["rent_growth_proj_12m"],    W_RENTG*rentg_norm*100),
        Factor("Market Strength Index (MSI)",  W_MSI,  msi,                                 W_MSI*msi_norm*100),
        Factor("Affordability (1 - Rent/Inc)", W_AFF,  aff_value,                           W_AFF*aff_norm*100),
    ]

    return {
        "score": _clamp_int(score, 0, 100),
        "decision": decision,
        "msi": float(msi),
        "factors": [asdict(f) for f in factors],
    }


# -----------------------
# Norms helpers (optional)
# -----------------------

def build_norms_from_dataset(
    series_dict: Dict[str, np.ndarray],
    robust_percentiles: Tuple[float, float] = (5.0, 95.0)
) -> Dict:
    """
    Build normalization params once from arrays across your dataset.

    series_dict expects arrays (across zip/months), e.g.:
      {
        "cap": np.array([...]),
        "rentg_12m": np.array([...]),
        "income_median": np.array([...]),
        "income_growth_3y": np.array([...]),
        "vacancy": np.array([...]),
        "dom": np.array([...]),
        "aff": np.array([...])  # 1 - rent_to_income
      }
    """
    p_lo, p_hi = robust_percentiles

    cap_lo, cap_hi = _pct_clip(series_dict["cap"], p_lo, p_hi)
    rg_lo,  rg_hi  = _pct_clip(series_dict["rentg_12m"], p_lo, p_hi)

    # MSI min/max over a reasonable z-span (or compute from a first pass)
    msi_lo, msi_hi = -3.0, 3.0

    aff_lo, aff_hi = _pct_clip(series_dict["aff"], p_lo, p_hi)

    # z-score params
    income_mean, income_std = _mean_std(series_dict["income_median"])
    incg_mean,   incg_std   = _mean_std(series_dict["income_growth_3y"])
    vac_mean,    vac_std    = _mean_std(series_dict["vacancy"])
    dom_mean,    dom_std    = _mean_std(series_dict["dom"])

    # final raw composite z baseline (center around ~0.5 with modest spread)
    raw_mean, raw_std = 0.5, 0.12

    return {
        "cap_minmax":   (cap_lo, cap_hi, cap_lo, cap_hi),
        "rentg_minmax": (rg_lo,  rg_hi,  rg_lo,  rg_hi),
        "msi_minmax":   (msi_lo, msi_hi, None,   None),
        "aff_minmax":   (aff_lo, aff_hi, None,   None),

        "income_median_z": (income_mean, max(income_std, 1e-9)),
        "income_growth_z": (incg_mean,   max(incg_std,   1e-9)),
        "vacancy_z":       (vac_mean,    max(vac_std,    1e-9)),
        "dom_z":           (dom_mean,    max(dom_std,    1e-9)),

        "raw_z": (raw_mean, raw_std),
    }


# -----------------------
# Internal math helpers
# -----------------------

def _robust_minmax(x: float, lo: float, hi: float,
                   clip_lo: Optional[float]=None,
                   clip_hi: Optional[float]=None) -> float:
    """Min–max normalize with optional clipping; returns 0..1 even if lo==hi."""
    if clip_lo is not None and x < clip_lo:
        x = clip_lo
    if clip_hi is not None and x > clip_hi:
        x = clip_hi
    if hi == lo:
        return 0.5
    return (x - lo) / (hi - lo)

def _z(x: Optional[float], mean: float, std: float) -> float:
    if x is None:
        return 0.0
    if std == 0:
        return 0.0
    return (x - mean) / std

def _sigmoid(z: float) -> float:
    return 1.0 / (1.0 + np.exp(-z))

def _pct_clip(arr: np.ndarray, lo_pct: float, hi_pct: float) -> Tuple[float, float]:
    arr = np.asarray(arr, dtype=float)
    return (float(np.nanpercentile(arr, lo_pct)),
            float(np.nanpercentile(arr, hi_pct)))

def _mean_std(arr: np.ndarray) -> Tuple[float, float]:
    arr = np.asarray(arr, dtype=float)
    return float(np.nanmean(arr)), float(np.nanstd(arr))

def _clamp_int(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))
