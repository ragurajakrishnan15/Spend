import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data import generate_synthetic_data, validate_data, load_or_create_data
from src.analytics import (monthly_spend, customer_rfm, run_campaign_model, run_sql,
                           forecast_monthly_spend, build_campaign_features, filter_transactions)


# ------------------------------------------------------------------ fixtures
@pytest.fixture(scope="module")
def df():
    return generate_synthetic_data(seed=7, customers=150, transactions=6000)


@pytest.fixture()
def db(tmp_path, df):
    path = tmp_path / "t.duckdb"
    con = duckdb.connect(str(path))
    con.register("v", df)
    con.execute("CREATE TABLE transactions AS SELECT * FROM v")
    con.close()
    secret = tmp_path / "secret.csv"
    secret.write_text("a,b\n1,2\n")
    return path, secret


# ------------------------------------------------------------------ data
def test_synthetic_data_is_reproducible():
    a = generate_synthetic_data(seed=42, customers=40, transactions=500)
    b = generate_synthetic_data(seed=42, customers=40, transactions=500)
    pd.testing.assert_frame_equal(a, b)


def test_different_seed_differs():
    a = generate_synthetic_data(seed=1, customers=40, transactions=500)
    b = generate_synthetic_data(seed=2, customers=40, transactions=500)
    assert not a["amount"].equals(b["amount"])


def test_history_spans_36_months(df):
    m = monthly_spend(df)
    assert len(m) == 36
    assert (m["spend"] > 0).all()
    assert df["timestamp"].min().year == 2023 and df["timestamp"].max().year == 2025


def test_calendar_seasonality_december_peak_and_trend(df):
    m = monthly_spend(df).set_index("month")["spend"]
    by_cal = m.groupby(m.index.month).mean()
    assert by_cal.idxmax() == 12
    assert by_cal.loc[12] > by_cal.drop(12).mean() * 1.1
    # upward trend: last year spends more than first year
    assert m.iloc[-12:].sum() > m.iloc[:12].sum()


def test_validation_rejects_duplicate_ids(df):
    bad = df.copy()
    bad.loc[1, "transaction_id"] = bad.loc[0, "transaction_id"]
    with pytest.raises(ValueError, match="Duplicate"):
        validate_data(bad)


@pytest.mark.parametrize("mutate,match", [
    (lambda d: d.drop(columns=["region"]), "Missing required"),
    (lambda d: d.assign(amount=d["amount"].where(d.index != 0, -5)), "non-negative"),
    (lambda d: d.assign(amount=d["amount"].where(d.index != 0, np.nan)), "finite"),
    (lambda d: d.assign(campaign_response=d["campaign_response"].where(d.index != 0, 2)), "binary"),
    (lambda d: d.assign(category=d["category"].where(d.index != 0, None)), "category"),
    (lambda d: d.iloc[0:0], "empty"),
])
def test_validation_rejections(df, mutate, match):
    with pytest.raises(ValueError, match=match):
        validate_data(mutate(df.head(50).copy()))


def test_load_or_create_data_roundtrip_and_db(tmp_path):
    out = load_or_create_data(tmp_path)
    assert (tmp_path / "transactions.csv").exists() and (tmp_path / "spendiq.duckdb").exists()
    again = load_or_create_data(tmp_path)
    assert len(out) == len(again)
    n = duckdb.connect(str(tmp_path / "spendiq.duckdb"), read_only=True).execute("select count(*) from transactions").fetchone()[0]
    assert n == len(out)


def test_filter_transactions(df):
    f = filter_transactions(df, category="Travel", region="West")
    assert set(f["category"]) == {"Travel"} and set(f["region"]) == {"West"}
    assert len(filter_transactions(df, category="All")) == len(df)
    assert len(filter_transactions(df, start="2099-01-01")) == 0


# ------------------------------------------------------------------ segmentation
def test_segmentation_returns_labels(df):
    result = customer_rfm(df)
    assert "segment" in result.columns
    assert result["customer_id"].nunique() == len(result)


def test_segmentation_edge_cases(df):
    assert customer_rfm(df.iloc[0:0]).empty
    one = customer_rfm(df[df["customer_id"] == df["customer_id"].iloc[0]])
    assert len(one) == 1 and one["segment"].iloc[0] == "Segment 1"


# ------------------------------------------------------------------ forecasting
def test_forecast_compares_against_both_baselines(df):
    res = forecast_monthly_spend(monthly_spend(df), horizon=6)
    names = {m["model"] for m in res["metrics"]}
    assert {"Last-month naive", "Seasonal naive (t-12)"} <= names
    assert res["holdout_months"] == 12 and res["seasonal"] is True
    assert len(res["future"]) == 6 and (res["future"]["forecast"] >= 0).all()
    assert (res["future"]["lower"] <= res["future"]["upper"]).all()


def test_backtest_has_no_future_leakage(df):
    """Changing a test month's actual value must not change that month's own prediction."""
    m = monthly_spend(df)
    base = forecast_monthly_spend(m, 3)["backtest"]
    tweaked = m.copy()
    tweaked.loc[tweaked.index[-1], "spend"] *= 5
    new = forecast_monthly_spend(tweaked, 3)["backtest"]
    assert base["model"].iloc[-1] == pytest.approx(new["model"].iloc[-1])


def test_forecast_short_history_fallback():
    m = pd.DataFrame({"month": pd.date_range("2025-01-01", periods=4, freq="MS"), "spend": [10., 12., 11., 13.]})
    res = forecast_monthly_spend(m, 2)
    assert res["metrics"] == [] and list(res["future"]["forecast"]) == [13.0, 13.0]


def test_forecast_empty_and_bad_horizon():
    empty = pd.DataFrame({"month": pd.to_datetime([]), "spend": []})
    assert len(forecast_monthly_spend(empty, 3)["future"]) == 3
    with pytest.raises(ValueError):
        forecast_monthly_spend(empty, 0)


def test_forecast_medium_history_without_seasonal_features():
    m = pd.DataFrame({"month": pd.date_range("2024-01-01", periods=14, freq="MS"),
                      "spend": np.linspace(100, 140, 14)})
    res = forecast_monthly_spend(m, 2)
    assert res["seasonal"] is False and res["metrics"]


# ------------------------------------------------------------------ campaign model
def test_campaign_features_use_only_prior_data(df):
    d = build_campaign_features(df)
    first = d.groupby("customer_id").head(1)
    assert (first["prior_txn_count"] == 0).all() and (first["prior_spend"] == 0).all()
    # prior features of a row must not depend on that row's own label
    flipped = df.copy()
    flipped["campaign_response"] = 1 - flipped["campaign_response"]
    d2 = build_campaign_features(flipped)
    last_rows = d.groupby("customer_id").head(1).index
    assert np.allclose(d.loc[last_rows, "prior_response_rate"], d2.loc[last_rows, "prior_response_rate"])


def test_campaign_model_metrics_and_chronology(df):
    res = run_campaign_model(df)
    assert 0 <= res["metrics"]["f1"] <= 1 and 0 <= res["metrics"]["roc_auc"] <= 1
    assert res["split"]["train_end"] < res["split"]["test_start"]
    assert {"category", "channel", "region"} <= set(res["features"])
    assert res["confusion"].shape == (2, 2)
    assert len(res["lift"]) == 10


def test_campaign_model_edge_cases(df):
    assert "error" in run_campaign_model(df.iloc[0:0])
    one_class = df.assign(campaign_response=0)
    assert "error" in run_campaign_model(one_class)


# ------------------------------------------------------------------ SQL security
def test_sql_allows_select_and_with(db):
    path, _ = db
    out = run_sql("SELECT category, SUM(amount) AS s FROM transactions GROUP BY 1", str(path))
    assert len(out) == 8
    out = run_sql("WITH t AS (SELECT * FROM transactions) SELECT COUNT(*) AS n FROM t;", str(path))
    assert out["n"].iloc[0] == 6000


def test_sql_row_cap(db):
    path, _ = db
    out = run_sql("SELECT * FROM transactions", str(path), max_rows=25)
    assert len(out) == 25 and out.attrs["truncated"] is True


@pytest.mark.parametrize("q", [
    "DROP TABLE transactions",
    "DELETE FROM transactions",
    "INSERT INTO transactions SELECT * FROM transactions",
    "UPDATE transactions SET amount = 0",
    "CREATE TABLE x AS SELECT 1",
    "ATTACH 'other.duckdb'",
    "COPY transactions TO 'out.csv'",
    "PRAGMA database_list",
    "INSTALL httpfs",
    "SET enable_external_access = true",
    "SELECT 1; DROP TABLE transactions",
    "DROP\nTABLE transactions",
    "",
    "   ",
    "SELEC nonsense",
])
def test_sql_rejects_unsafe(db, q):
    path, _ = db
    with pytest.raises(ValueError):
        run_sql(q, str(path))
    # table must be intact
    assert duckdb.connect(str(path), read_only=True).execute("select count(*) from transactions").fetchone()[0] == 6000


def test_sql_rejects_missing_db_even_for_write(tmp_path):
    with pytest.raises(ValueError):
        run_sql("DROP TABLE transactions", str(tmp_path / "missing.duckdb"))


def test_sql_cannot_read_local_files(db):
    path, secret = db
    p = str(secret).replace("\\", "/")
    for q in [
        f"SELECT * FROM read_csv('{p}')",
        f"SELECT * FROM read_csv_auto('{p}')",
        f"SELECT * FROM '{p}'",
        f"SELECT * FROM read_text('{p}')",
        f"SELECT * FROM glob('{p}')",
        f"SELECT * FROM read_parquet('{p}')",
        "SELECT * FROM read_csv('https://example.com/x.csv')",
    ]:
        with pytest.raises(Exception):
            run_sql(q, str(path))
