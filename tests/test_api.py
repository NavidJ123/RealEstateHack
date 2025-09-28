from fastapi.testclient import TestClient

from backend.api import app

client = TestClient(app)


def test_properties_endpoint():
    resp = client.get("/api/properties")
    assert resp.status_code == 200
    payload = resp.json()
    assert "items" in payload and "total" in payload
    assert payload["total"] >= len(payload["items"])


def test_property_analysis_endpoint():
    resp = client.get("/api/properties/P20001-01")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["property_id"] == "P20001-01"
    assert "metrics" in payload
    assert payload["metrics"]["cap_rate_market_now"] is not None
    assert payload["explanations"]["factors"]


def test_score_endpoint_fallback():
    analysis = client.get("/api/properties/P20001-01").json()
    resp = client.post("/api/score", json={"analysis_json": analysis})
    assert resp.status_code == 200
    score_payload = resp.json()
    assert "score" in score_payload
    assert "decision" in score_payload
    assert "rationale" in score_payload
    assert isinstance(score_payload["top_contributors"], list)


def test_broker_modes():
    analysis = client.get("/api/properties/P20001-01").json()
    thesis_resp = client.post("/api/broker", json={"mode": "thesis", "analysis_json": analysis})
    assert thesis_resp.status_code == 200
    thesis = thesis_resp.json()
    assert thesis["score"] >= 0
    assert thesis["decision"] in {"Buy", "Hold", "Sell"}
    qa_resp = client.post("/api/broker", json={"mode": "qa", "analysis_json": analysis, "question": "What if vacancy rises?"})
    assert qa_resp.status_code == 200
    assert "text" in qa_resp.json()
