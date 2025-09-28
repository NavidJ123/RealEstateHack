import json

from backend.db.repo import get_repository, reset_repository
from backend.services.analysis_service import AnalysisService
from backend.services.comps_service import CompsService
from backend.services.forecast_service import ForecastService


def _analysis_service() -> AnalysisService:
    reset_repository()
    repo = get_repository()
    forecast = ForecastService(repo)
    comps = CompsService(repo)
    return AnalysisService(repo, forecast, comps)


def test_analysis_contains_required_fields():
    service = _analysis_service()
    analysis = service.analyze_property("P20001-01")
    data = json.loads(analysis.json())
    assert data["property_id"] == "P20001-01"
    assert "score" in data
    assert "decision" in data
    metrics = data["metrics"]
    assert "cap_rate_market_now" in metrics
    assert "rent_growth_proj_12m" in metrics
    assert "market_strength_index" in metrics
    explanations = data["explanations"]
    assert explanations["factors"]
    assert "fallback_total_score" in explanations
    assert data["zip_trends"]["rent_history"], "rent history should not be empty"
    assert data["comps"], "comps should be available"

