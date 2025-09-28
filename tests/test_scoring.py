from backend.services.scoring import (
    MetricDistributions,
    build_factor_attributions,
    decision_from_score,
)


def _distributions() -> MetricDistributions:
    return MetricDistributions(
        {
            "cap_rate_market_now": [0.03, 0.045, 0.06, 0.07],
            "rent_growth_proj_12m": [0.0, 0.015, 0.03, 0.05],
            "market_strength_index": [-1.5, -0.2, 0.4, 1.3],
        }
    )


def test_cap_rate_monotonicity():
    distributions = _distributions()
    metrics_low = {
        "cap_rate_market_now": 0.04,
        "rent_growth_proj_12m": 0.02,
        "market_strength_index": 0.1,
    }
    low = build_factor_attributions(metrics_low, distributions).fallback_total_score
    metrics_high = dict(metrics_low)
    metrics_high["cap_rate_market_now"] = 0.065
    high = build_factor_attributions(metrics_high, distributions).fallback_total_score
    assert high > low


def test_rent_growth_monotonicity():
    distributions = _distributions()
    base_metrics = {
        "cap_rate_market_now": 0.05,
        "rent_growth_proj_12m": 0.01,
        "market_strength_index": 0.0,
    }
    slow = build_factor_attributions(base_metrics, distributions).fallback_total_score
    base_metrics["rent_growth_proj_12m"] = 0.045
    fast = build_factor_attributions(base_metrics, distributions).fallback_total_score
    assert fast > slow


def test_market_strength_declines_with_negative_signal():
    distributions = _distributions()
    strong = {
        "cap_rate_market_now": 0.05,
        "rent_growth_proj_12m": 0.03,
        "market_strength_index": 1.0,
    }
    strong_score = build_factor_attributions(strong, distributions).fallback_total_score
    weak = dict(strong)
    weak["market_strength_index"] = -1.0
    weak_score = build_factor_attributions(weak, distributions).fallback_total_score
    assert weak_score < strong_score


def test_decision_thresholds():
    assert decision_from_score(80) == "Buy"
    assert decision_from_score(60) == "Hold"
    assert decision_from_score(40) == "Sell"
