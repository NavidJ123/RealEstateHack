from fastapi.testclient import TestClient

from backend.api import app

client = TestClient(app)


def test_properties_endpoint():
    resp = client.get("/api/properties")
    assert resp.status_code == 200
    payload = resp.json()
    assert "items" in payload and "total" in payload
    assert payload["total"] >= len(payload["items"])
    first = payload["items"][0]
    for field in ["id", "address", "zipcode", "current_est_value"]:
        assert field in first


def test_property_analysis_endpoint():
    resp = client.get("/api/properties/P20001-01")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["property_id"] == "P20001-01"
    assert payload["decision"] in {"Buy", "Hold", "Sell"}
    assert 0 <= payload["score"] <= 100

    metrics = payload["metrics"]
    assert "current_est_value" in metrics
    assert metrics["current_est_value"] > 0

    trends = payload["zip_trends"]
    assert trends["price_history"]
    assert trends["rent_history"]
    assert isinstance(trends["price_forecast"], list)

    comps = payload["comps"]
    assert isinstance(comps, list)
    assert comps and "sale_price" in comps[0]

    provenance = payload["provenance"]
    assert "generated_at" in provenance
    assert "sources" in provenance


def test_broker_endpoint_returns_message():
    analysis = client.get("/api/properties/P20001-01").json()
    resp = client.post(
        "/api/broker",
        json={"analysis_json": analysis, "question": "Should I sell in 2 years?"},
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["messages"]
    assert payload["messages"][0]["role"] == "assistant"
    assert payload["messages"][0]["content"]

