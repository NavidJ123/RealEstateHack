from backend.services.scoring import MetricDistributions, decision_from_score, score_from_metrics

DISTRIBUTIONS = MetricDistributions(
    appreciation_5y=[-0.1, 0.0, 0.25, 0.4],
    cap_rate_est=[0.03, 0.05, 0.08],
    rent_growth_3y=[0.0, 0.02, 0.05],
    market_strength=[-1.0, 0.0, 1.5],
)


def test_cap_rate_monotonicity():
    base_metrics = {
        "appreciation_5y": 0.2,
        "cap_rate_est": 0.04,
        "rent_growth_3y": 0.03,
        "market_strength": 0.2,
    }
    low_score = score_from_metrics(base_metrics, DISTRIBUTIONS)
    improved = dict(base_metrics)
    improved["cap_rate_est"] = 0.08
    high_score = score_from_metrics(improved, DISTRIBUTIONS)
    assert high_score > low_score


def test_score_clamped_to_range():
    extreme_metrics = {
        "appreciation_5y": 10.0,
        "cap_rate_est": 2.0,
        "rent_growth_3y": 5.0,
        "market_strength": 4.0,
    }
    score = score_from_metrics(extreme_metrics, DISTRIBUTIONS)
    assert 0 <= score <= 100

    negative_metrics = {
        "appreciation_5y": -5.0,
        "cap_rate_est": -1.0,
        "rent_growth_3y": -2.0,
        "market_strength": -3.0,
    }
    score = score_from_metrics(negative_metrics, DISTRIBUTIONS)
    assert 0 <= score <= 100


def test_decision_thresholds():
    buy_metrics = {
        "appreciation_5y": 0.4,
        "cap_rate_est": 0.08,
        "rent_growth_3y": 0.05,
        "market_strength": 1.0,
    }
    hold_metrics = {
        "appreciation_5y": 0.15,
        "cap_rate_est": 0.05,
        "rent_growth_3y": 0.02,
        "market_strength": 0.1,
    }
    sell_metrics = {
        "appreciation_5y": -0.05,
        "cap_rate_est": 0.03,
        "rent_growth_3y": 0.0,
        "market_strength": -0.5,
    }

    assert decision_from_score(score_from_metrics(buy_metrics, DISTRIBUTIONS)) == "Buy"
    assert decision_from_score(score_from_metrics(hold_metrics, DISTRIBUTIONS)) == "Hold"
    assert decision_from_score(score_from_metrics(sell_metrics, DISTRIBUTIONS)) == "Sell"

