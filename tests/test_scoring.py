from backend.services.scoring import MetricDistributions, decision_from_score, score_from_metrics


def test_score_ranges_and_decision():
    distributions = MetricDistributions(
        appreciation_5y=[-0.1, 0.0, 0.25, 0.4],
        cap_rate_est=[0.03, 0.05, 0.08],
        rent_growth_3y=[0.0, 0.02, 0.05],
        market_strength=[-1.0, 0.0, 1.5],
    )
    metrics = {
        "appreciation_5y": 0.3,
        "cap_rate_est": 0.07,
        "rent_growth_3y": 0.04,
        "market_strength": 0.8,
    }
    score = score_from_metrics(metrics, distributions)
    assert 0 <= score <= 100
    assert decision_from_score(score) in {"Buy", "Hold", "Sell"}


def test_low_metrics_result_in_sell():
    distributions = MetricDistributions(
        appreciation_5y=[-0.2, 0.3],
        cap_rate_est=[0.03, 0.07],
        rent_growth_3y=[0.0, 0.04],
        market_strength=[-1.5, 1.2],
    )
    metrics = {
        "appreciation_5y": -0.1,
        "cap_rate_est": 0.03,
        "rent_growth_3y": 0.0,
        "market_strength": -0.8,
    }
    score = score_from_metrics(metrics, distributions)
    assert score < 55
    assert decision_from_score(score) == "Sell"

