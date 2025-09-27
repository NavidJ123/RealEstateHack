from fastapi.testclient import TestClient

from backend.api import app

client = TestClient(app)


def test_properties_endpoint():
    resp = client.get("/api/properties")
    assert resp.status_code == 200
    payload = resp.json()
    assert "items" in payload
    assert payload["items"]


def test_property_analysis_endpoint():
    resp = client.get("/api/properties/P20001-01")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["property_id"] == "P20001-01"
    assert 0 <= payload["score"] <= 100


def test_broker_endpoint_returns_message():
    analysis = client.get("/api/properties/P20001-01").json()
    resp = client.post("/api/broker", json={"analysis_json": analysis, "question": "Should I sell in 2 years?"})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["messages"]
    assert payload["messages"][0]["role"] == "assistant"

