import json

from backend.db.repo import get_repository
from backend.services.analysis_service import AnalysisService
from backend.services.comps_service import CompsService
from backend.services.forecast_service import ForecastService


def _analysis_service() -> AnalysisService:
    repo = get_repository()
    forecast = ForecastService(repo)
    comps = CompsService(repo)
    return AnalysisService(repo, forecast, comps)


def test_analysis_contains_required_fields():
    service = _analysis_service()
    analysis = service.analyze_property("P20001-01")
    data = json.loads(analysis.json())
    assert data["property_id"] == "P20001-01"
    assert "metrics" in data
    assert data["metrics"]["current_est_value"] > 0
    assert 0 <= data["score"] <= 100
    assert data["decision"] in {"Buy", "Hold", "Sell"}
    assert data["zip_trends"]["price_history"], "price history should not be empty"
    assert data["comps"], "comps should be available"

