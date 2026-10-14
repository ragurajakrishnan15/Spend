import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.main import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_health_and_meta(client):
    assert client.get("/api/health").json()["status"] == "ok"
    meta = client.get("/api/meta").json()
    assert meta["months"] == 36 and "Travel" in meta["categories"]


def test_overview_filters(client):
    all_ = client.get("/api/overview").json()
    travel = client.get("/api/overview", params={"category": "Travel"}).json()
    assert travel["kpis"]["total_spend"] < all_["kpis"]["total_spend"]
    assert len(all_["monthly"]) == 36


def test_overview_empty_filter(client):
    r = client.get("/api/overview", params={"start": "2099-01-01"}).json()
    assert r["empty"] is True


def test_overview_bad_date_rejected(client):
    assert client.get("/api/overview", params={"start": "not-a-date"}).status_code == 422


def test_transactions_paging(client):
    r = client.get("/api/transactions", params={"limit": 5, "region": "West"}).json()
    assert len(r["table"]) == 5 and {t["region"] for t in r["table"]} == {"West"}
    assert len(r["histogram"]) == 30


def test_forecast(client):
    r = client.get("/api/forecast", params={"horizon": 4}).json()
    assert len(r["future"]) == 4 and r["holdout_months"] == 12
    assert {m["model"] for m in r["metrics"]} >= {"Last-month naive", "Seasonal naive (t-12)"}


def test_forecast_horizon_validation(client):
    assert client.get("/api/forecast", params={"horizon": 99}).status_code == 422


def test_segments_and_campaign(client):
    s = client.get("/api/segments").json()
    assert sum(x["customers"] for x in s["summary"]) == s["total_customers"]
    c = client.get("/api/campaign").json()
    assert 0 <= c["metrics"]["roc_auc"] <= 1 and sum(c["confusion"].values()) == c["split"]["test_rows"]


def test_sql_endpoint(client):
    ok = client.post("/api/sql", json={"query": "SELECT COUNT(*) AS n FROM transactions"}).json()
    assert ok["columns"] == ["n"] and ok["rows"][0][0] > 0
    for q in ["DROP TABLE transactions", "SELECT * FROM read_csv('C:/Windows/win.ini')",
              "SELECT 1; SELECT 2"]:
        assert client.post("/api/sql", json={"query": q}).status_code == 400


def test_governance(client):
    g = client.get("/api/governance").json()
    assert g["provenance"]["rows"] > 10000 and "compliance" in g["disclaimer"]
