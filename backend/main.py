"""SpendIQ FastAPI backend. Reuses the pandas / DuckDB / scikit-learn code in ``src``.

Run from the project root:  python -m uvicorn backend.main:app --reload --port 8000
All data is synthetic.
"""
from __future__ import annotations

import json
import os
import sys
import threading
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.ratelimit import limit  # noqa: E402
from src.analytics import (category_spend, customer_rfm, filter_transactions, forecast_merchant_spend,  # noqa: E402
                           forecast_monthly_spend, monthly_spend, run_campaign_model, run_sql, segment_summary,
                           run_operations_forecast, budget_variance, DEFAULT_BUDGETS)
from src.exports import build_context, build_excel, build_pptx  # noqa: E402
from src.merchants import BY_NAME, CATALOG, classification_report, classify_descriptors  # noqa: E402
from src.data import DATA_VERSION, DB_PATH, load_or_create_data  # noqa: E402
from src.sql_safety import DEFAULT_MAX_ROWS, UnsafeQueryError  # noqa: E402
from src.macro_intelligence import get_all_indicators, get_macro_context, get_report_library  # noqa: E402
from src.narrative import generate_summary  # noqa: E402


def _warm_up() -> None:
    """Populate the dataset and the default (unfiltered) cached results so first requests are fast."""
    steps = (("data", get_df), ("campaign", lambda: _campaign()),
             ("forecast", lambda: _forecast_cached("All", "All", "All", 3)),
             ("segments", lambda: _segments()))
    for name, fn in steps:
        try:
            fn()
        except Exception as exc:  # warm-up is best effort; endpoints recompute on demand
            print(f"[warmup] {name} failed: {exc}", flush=True)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Background thread: the server accepts requests immediately instead of blocking startup.
    if os.environ.get("SPENDIQ_WARMUP", "1") != "0":
        threading.Thread(target=_warm_up, name="spendiq-warmup", daemon=True).start()
    yield


app = FastAPI(title="SpendIQ API", version="1.0.0", lifespan=lifespan,
              description="Synthetic banking analytics. Not a production banking system.")
_EXTRA_ORIGINS = [o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", *_EXTRA_ORIGINS],
                   allow_methods=["GET", "POST"], allow_headers=["*"])

_lock = threading.Lock()
_df: Optional[pd.DataFrame] = None


def get_df() -> pd.DataFrame:
    global _df
    with _lock:
        if _df is None:
            _df = load_or_create_data()
        return _df


def records(df: pd.DataFrame) -> list[dict]:
    return json.loads(df.to_json(orient="records", date_format="iso", double_precision=4))


def _month_str(s: pd.Series) -> list[str]:
    return s.dt.strftime("%Y-%m").tolist()


def filtered(category, channel, region, start, end) -> pd.DataFrame:
    try:
        return filter_transactions(get_df(), category, channel, region, start, end)
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, f"Invalid filter: {exc}") from exc


# Common filter query parameters
Category = Query(None, description="Merchant category or 'All'")
Channel = Query(None)
Region = Query(None)
Start = Query(None, description="YYYY-MM-DD", pattern=r"^\d{4}-\d{2}-\d{2}$")
End = Query(None, description="YYYY-MM-DD", pattern=r"^\d{4}-\d{2}-\d{2}$")


@app.get("/api/health")
def health():
    df = get_df()
    return {"status": "ok", "rows": int(len(df)), "data_version": DATA_VERSION, "synthetic": True}


@app.get("/api/meta")
def meta():
    df = get_df()
    return {
        "categories": sorted(df["category"].unique().tolist()),
        "channels": sorted(df["channel"].unique().tolist()),
        "regions": sorted(df["region"].unique().tolist()),
        "start": df["timestamp"].min().strftime("%Y-%m-%d"),
        "end": df["timestamp"].max().strftime("%Y-%m-%d"),
        "rows": int(len(df)),
        "customers": int(df["customer_id"].nunique()),
        "months": int(df["timestamp"].dt.to_period("M").nunique()),
    }


@app.get("/api/overview")
def overview(category: Optional[str] = Category, channel: Optional[str] = Channel,
             region: Optional[str] = Region, start: Optional[str] = Start, end: Optional[str] = End):
    d = filtered(category, channel, region, start, end)
    if d.empty:
        return {"empty": True, "kpis": None, "monthly": [], "categories": [], "channels": [], "regions": []}
    m = monthly_spend(d)
    last = float(m["spend"].iloc[-1])
    prev = float(m["spend"].iloc[-2]) if len(m) > 1 else None
    mom = None if not prev else (last / prev - 1) * 100
    ch = d.groupby("channel", as_index=False).agg(transactions=("amount", "size"), spend=("amount", "sum"))
    rg = d.groupby("region", as_index=False).agg(transactions=("amount", "size"), spend=("amount", "sum"))
    m_out = m.assign(month=_month_str(m["month"]))
    return {
        "empty": False,
        "kpis": {
            "total_spend": float(d["amount"].sum()), "transactions": int(len(d)),
            "customers": int(d["customer_id"].nunique()), "avg_transaction": float(d["amount"].mean()),
            "latest_month": m_out["month"].iloc[-1], "latest_month_spend": last, "mom_change_pct": mom,
            "campaign_response_rate": float(d["campaign_response"].mean()),
        },
        "monthly": records(m_out),
        "categories": records(category_spend(d)),
        "channels": records(ch),
        "regions": records(rg),
    }


@app.get("/api/transactions")
def transactions(category: Optional[str] = Category, channel: Optional[str] = Channel,
                 region: Optional[str] = Region, start: Optional[str] = Start, end: Optional[str] = End,
                 limit: int = Query(25, ge=1, le=200), offset: int = Query(0, ge=0)):
    d = filtered(category, channel, region, start, end)
    if d.empty:
        return {"empty": True, "summary": None, "monthly": [], "daily": [], "weekday": [],
                "histogram": [], "table": [], "total_rows": 0}
    a = d["amount"]
    daily = (d.assign(date=d["timestamp"].dt.strftime("%Y-%m-%d")).groupby("date", as_index=False)["amount"]
             .agg(spend="sum", transactions="size"))
    weekday = (d.assign(day=d["timestamp"].dt.dayofweek).groupby("day", as_index=False)["amount"]
               .agg(spend="sum", transactions="size"))
    names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    weekday["day"] = weekday["day"].map(lambda i: names[int(i)])
    cap = float(a.quantile(.99))
    hist = pd.cut(a.clip(upper=cap), bins=30, include_lowest=True).value_counts(sort=False)
    histogram = [{"bin_start": round(float(i.left), 2), "bin_end": round(float(i.right), 2), "count": int(c)}
                 for i, c in hist.items()]
    page = d.sort_values("timestamp", ascending=False).iloc[offset:offset + limit]
    table = page.assign(timestamp=page["timestamp"].dt.strftime("%Y-%m-%d %H:%M"))
    monthly = monthly_spend(d)
    return {
        "empty": False,
        "summary": {"transactions": int(len(d)), "spend": float(a.sum()), "mean": float(a.mean()),
                    "median": float(a.median()), "p95": float(a.quantile(.95)), "max": float(a.max())},
        "monthly": records(monthly.assign(month=_month_str(monthly["month"]))),
        "daily": records(daily),
        "weekday": records(weekday),
        "histogram": histogram,
        "histogram_note": "Amounts above the 99th percentile are grouped in the last bin.",
        "table": records(table),
        "total_rows": int(len(d)),
    }


@lru_cache(maxsize=64)
def _forecast_cached(category, channel, region, horizon):
    d = filter_transactions(get_df(), category, channel, region)
    return forecast_monthly_spend(monthly_spend(d), horizon=horizon)


@app.get("/api/forecast", dependencies=[Depends(limit("forecast", 30))])
def forecast(category: Optional[str] = Category, channel: Optional[str] = Channel,
             region: Optional[str] = Region, horizon: int = Query(3, ge=1, le=12)):
    res = _forecast_cached(category or "All", channel or "All", region or "All", horizon)
    hist = res["plot_data"][res["plot_data"]["series"] == "Actual"]
    bt, fut = res["backtest"], res["future"]
    return {
        "method": res["method"], "seasonal": res["seasonal"], "holdout_months": res["holdout_months"],
        "best_model": res.get("best_model"),
        "selected_model_key": res.get("selected_model_key"),
        "future_by_model": res.get("future_by_model", {}),
        "history": [{"month": m, "spend": round(float(s), 2)} for m, s in zip(_month_str(hist["month"]), hist["spend"])],
        "future": records(fut.assign(month=_month_str(fut["month"]))) if len(fut) else [],
        "metrics": res["metrics"],
        "backtest": records(bt.assign(month=_month_str(bt["month"]))) if len(bt) else [],
        "notes": [
            "Metrics come from a rolling-origin backtest: every prediction uses only earlier months.",
            "The displayed forecast is the lowest-MAE model on that same backtest, so its error estimate is mildly optimistic.",
            "Seasonal patterns in the synthetic data are generated by construction; real data would differ.",
            "The prediction band is the 10th-90th percentile of backtest errors, widened with horizon.",
        ],
    }


@lru_cache(maxsize=1)
def _segments():
    return customer_rfm(get_df())


@app.get("/api/segments")
def segments(limit: int = Query(300, ge=1, le=1000)):
    seg = _segments()
    if seg.empty:
        return {"empty": True, "summary": [], "points": [], "total_customers": 0}
    sample = seg.sort_values("monetary", ascending=False).head(limit)
    return {"empty": False, "summary": records(segment_summary(seg)), "points": records(sample.round(2)),
            "total_customers": int(len(seg)),
            "note": "Segments describe observed synthetic behaviour (log-scaled RFM, KMeans k=4); they are not value judgments."}


@lru_cache(maxsize=1)
def _campaign():
    return run_campaign_model(get_df())


@app.get("/api/campaign")
def campaign():
    res = _campaign()
    if res.get("error"):
        return {"error": res["error"]}
    cm, sp = res["confusion"], res["split"]
    return {
        "metrics": res["metrics"], "baseline": res["baseline"],
        "importance": records(res["importance"].round(5)),
        "lift": records(res["lift"].round(4)),
        "confusion": {"tn": int(cm[0][0]), "fp": int(cm[0][1]), "fn": int(cm[1][0]), "tp": int(cm[1][1])},
        "split": {k: (v.strftime("%Y-%m-%d") if hasattr(v, "strftime") else v) for k, v in sp.items()},
        "features": res["features"],
        "notes": [
            "Synthetic transaction-level demonstration: each row is one transaction, and customers appear in both train and test periods.",
            "Chronological split: the model trains on earlier transactions and is scored on later ones.",
            "Customer-history features use only earlier transactions; responses are assumed to be observed immediately.",
            "Feature importance is permutation importance on the test set and is not causal evidence.",
            "Scores must not be used for credit, eligibility or access decisions.",
        ],
    }


class SqlRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=5000)


SQL_EXAMPLES = [
    {"name": "Monthly spend", "query": "SELECT date_trunc('month', timestamp) AS month, ROUND(SUM(amount), 2) AS spend FROM transactions GROUP BY 1 ORDER BY 1"},
    {"name": "Top categories", "query": "SELECT category, COUNT(*) AS transactions, ROUND(SUM(amount), 2) AS spend FROM transactions GROUP BY category ORDER BY spend DESC"},
    {"name": "Top customers", "query": "SELECT customer_id, COUNT(*) AS transactions, ROUND(SUM(amount), 2) AS spend FROM transactions GROUP BY customer_id ORDER BY spend DESC LIMIT 20"},
    {"name": "Channel mix", "query": "SELECT channel, COUNT(*) AS transactions, ROUND(AVG(amount), 2) AS avg_amount FROM transactions GROUP BY channel ORDER BY transactions DESC"},
    {"name": "Regex: descriptors matching a pattern", "query": r"SELECT merchant_descriptor, merchant_clean, ROUND(amount, 2) AS amount FROM transactions WHERE regexp_matches(upper(merchant_descriptor), 'GREEN\s?F(IE)?LD|GRNFLD') ORDER BY timestamp DESC LIMIT 25"},
    {"name": "Regex: unmatched descriptors", "query": r"SELECT regexp_replace(upper(merchant_descriptor), '#\s?\d+|\b\d{3,}\b', '') AS pattern, COUNT(*) AS n FROM transactions WHERE merchant_clean = 'Unknown' GROUP BY 1 ORDER BY n DESC LIMIT 20"},
    {"name": "Merchant spend by month", "query": "SELECT merchant_clean, date_trunc('month', timestamp) AS month, ROUND(SUM(amount), 2) AS spend FROM transactions WHERE merchant_clean <> 'Unknown' GROUP BY 1, 2 ORDER BY 1, 2"},
    {"name": "Seasonality by calendar month", "query": "SELECT month(timestamp) AS cal_month, ROUND(AVG(amount), 2) AS avg_amount, COUNT(*) AS transactions FROM transactions GROUP BY 1 ORDER BY 1"},
]


_BUDGET_ROWS = ", ".join(f"('{c}', {int(v)})" for c, v in DEFAULT_BUDGETS.items())
_BUDGET_TAIL = """,
monthly AS (
  SELECT category, {trunc} AS month, SUM(amount) AS actual
  FROM transactions GROUP BY 1, 2
)
SELECT m.month, m.category, ROUND(m.actual, 2) AS actual, b.budget,
       ROUND((m.actual - b.budget) / b.budget * 100, 2) AS variance_pct,
       CASE WHEN m.actual <= b.budget THEN 'green'
            WHEN m.actual <= b.budget * 1.1 THEN 'amber'
            ELSE 'red' END AS rag
FROM monthly m JOIN budgets b ON b.category = m.category
ORDER BY m.month, m.category"""
SQL_EXAMPLES += [
    {"name": "Quarterly spend by category",
     "query": "SELECT date_trunc('quarter', timestamp) AS quarter, category, ROUND(SUM(amount), 2) AS spend FROM transactions GROUP BY 1, 2 ORDER BY 1, 2"},
    {"name": "Operations: volume by channel",
     "query": "SELECT date_trunc('month', timestamp) AS month, channel, COUNT(*) AS transactions, ROUND(AVG(amount), 2) AS avg_ticket FROM transactions GROUP BY 1, 2 ORDER BY 1, 2"},
    {"name": "Budget variance with RAG status",
     "query": f"WITH budgets(category, budget) AS (VALUES {_BUDGET_ROWS})" + _BUDGET_TAIL.format(trunc="date_trunc('month', timestamp)")},
    {"name": "Campaign response by exposure",
     "query": "SELECT category, campaign_exposed, COUNT(*) AS transactions, ROUND(AVG(campaign_response) * 100, 2) AS response_rate_pct FROM transactions GROUP BY 1, 2 ORDER BY 1, 2"},
]

# Hand-written warehouse translations of the DuckDB examples above. They are NOT executed by this app or its tests
# (only DuckDB runs); see docs/WAREHOUSE_SQL.md. Keys match SQL_EXAMPLES names.
_PORTABLE = ("Top categories", "Top customers", "Channel mix", "Campaign response by exposure")
WAREHOUSE_SQL = {
    "Monthly spend": {
        "snowflake": "SELECT DATE_TRUNC('MONTH', timestamp) AS month, ROUND(SUM(amount), 2) AS spend\nFROM transactions GROUP BY 1 ORDER BY 1",
        "athena": "SELECT date_trunc('month', \"timestamp\") AS month, ROUND(SUM(amount), 2) AS spend\nFROM transactions GROUP BY 1 ORDER BY 1",
    },
    # Snowflake string literals treat backslash as an escape, so regex escapes are doubled there.
    "Regex: descriptors matching a pattern": {
        "snowflake": ("SELECT merchant_descriptor, merchant_clean, ROUND(amount, 2) AS amount\nFROM transactions\n"
                      r"WHERE REGEXP_LIKE(UPPER(merchant_descriptor), '.*(GREEN\\s?F(IE)?LD|GRNFLD).*')" "\n"
                      "ORDER BY timestamp DESC LIMIT 25"),
        "athena": ("SELECT merchant_descriptor, merchant_clean, ROUND(amount, 2) AS amount\nFROM transactions\n"
                   r"WHERE regexp_like(upper(merchant_descriptor), 'GREEN\s?F(IE)?LD|GRNFLD')" "\n"
                   'ORDER BY "timestamp" DESC LIMIT 25'),
    },
    "Regex: unmatched descriptors": {
        "snowflake": (r"SELECT REGEXP_REPLACE(UPPER(merchant_descriptor), '#\\s?\\d+|\\b\\d{3,}\\b', '') AS pattern, COUNT(*) AS n" "\n"
                      "FROM transactions WHERE merchant_clean = 'Unknown'\nGROUP BY 1 ORDER BY n DESC LIMIT 20"),
        "athena": (r"SELECT regexp_replace(upper(merchant_descriptor), '#\s?\d+|\b\d{3,}\b', '') AS pattern, COUNT(*) AS n" "\n"
                   "FROM transactions WHERE merchant_clean = 'Unknown'\nGROUP BY 1 ORDER BY n DESC LIMIT 20"),
    },
    "Merchant spend by month": {
        "snowflake": "SELECT merchant_clean, DATE_TRUNC('MONTH', timestamp) AS month, ROUND(SUM(amount), 2) AS spend\n"
                     "FROM transactions WHERE merchant_clean <> 'Unknown'\nGROUP BY 1, 2 ORDER BY 1, 2",
        "athena": "SELECT merchant_clean, date_trunc('month', \"timestamp\") AS month, ROUND(SUM(amount), 2) AS spend\n"
                  "FROM transactions WHERE merchant_clean <> 'Unknown'\nGROUP BY 1, 2 ORDER BY 1, 2",
    },
    "Quarterly spend by category": {
        "snowflake": "SELECT DATE_TRUNC('QUARTER', timestamp) AS quarter, category, ROUND(SUM(amount), 2) AS spend\n"
                     "FROM transactions GROUP BY 1, 2 ORDER BY 1, 2",
        "athena": "SELECT date_trunc('quarter', \"timestamp\") AS quarter, category, ROUND(SUM(amount), 2) AS spend\n"
                  "FROM transactions GROUP BY 1, 2 ORDER BY 1, 2",
    },
    "Operations: volume by channel": {
        "snowflake": "SELECT DATE_TRUNC('MONTH', timestamp) AS month, channel, COUNT(*) AS transactions, ROUND(AVG(amount), 2) AS avg_ticket\n"
                     "FROM transactions GROUP BY 1, 2 ORDER BY 1, 2",
        "athena": "SELECT date_trunc('month', \"timestamp\") AS month, channel, COUNT(*) AS transactions, ROUND(AVG(amount), 2) AS avg_ticket\n"
                  "FROM transactions GROUP BY 1, 2 ORDER BY 1, 2",
    },
    "Budget variance with RAG status": {
        "snowflake": (f"WITH budgets AS (SELECT column1 AS category, column2 AS budget FROM VALUES {_BUDGET_ROWS})"
                      + _BUDGET_TAIL.format(trunc="DATE_TRUNC('MONTH', timestamp)")),
        "athena": (f"WITH budgets(category, budget) AS (VALUES {_BUDGET_ROWS})"
                   + _BUDGET_TAIL.format(trunc="date_trunc('month', \"timestamp\")")),
    },
    "Seasonality by calendar month": {
        "snowflake": "SELECT MONTH(timestamp) AS cal_month, ROUND(AVG(amount), 2) AS avg_amount, COUNT(*) AS transactions\n"
                     "FROM transactions GROUP BY 1 ORDER BY 1",
        "athena": "SELECT month(\"timestamp\") AS cal_month, ROUND(AVG(amount), 2) AS avg_amount, COUNT(*) AS transactions\n"
                  "FROM transactions GROUP BY 1 ORDER BY 1",
    },
}
for _ex in SQL_EXAMPLES:
    if _ex["name"] in _PORTABLE:  # plain ANSI aggregation - identical text on all three engines
        _ex["snowflake"] = _ex["athena"] = _ex["query"]
    else:
        _ex.update(WAREHOUSE_SQL[_ex["name"]])


@app.get("/api/sql/examples")
def sql_examples():
    return {"examples": SQL_EXAMPLES, "max_rows": DEFAULT_MAX_ROWS,
            "schema": [{"column": c, "type": str(t)} for c, t in get_df().dtypes.items()]}


@app.post("/api/sql", dependencies=[Depends(limit("sql", 20))])
def sql(req: SqlRequest):
    get_df()  # make sure the database file exists
    try:
        out = run_sql(req.query, DB_PATH)
    except UnsafeQueryError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:  # DuckDB execution error (bad column, blocked file access, ...)
        raise HTTPException(400, f"Query failed: {str(exc).splitlines()[0]}") from exc
    return {"columns": list(out.columns), "rows": json.loads(out.to_json(orient="values", date_format="iso")),
            "row_count": int(len(out)), "truncated": bool(out.attrs.get("truncated", False))}


@lru_cache(maxsize=1)
def _merchant_report():
    df = get_df()
    classified = classify_descriptors(df["merchant_descriptor"])
    return classification_report(df, classified)


@lru_cache(maxsize=1)
def _merchant_forecast():
    return forecast_merchant_spend(get_df())


@app.get("/api/merchants")
def merchants():
    rep = _merchant_report()
    fc = _merchant_forecast()
    out = {"classification": rep}
    if fc.get("error"):
        out["forecast"] = {"error": fc["error"]}
    else:
        out["forecast"] = {
            "metrics": fc["metrics"], "best_model": fc["best_model"],
            "next_month": fc["next_month"].strftime("%Y-%m"), "backtest_months": fc["backtest_months"],
            "backtest_rows": fc["backtest_rows"], "table": records(fc["table"]),
        }
    out["notes"] = [
        "Merchant names are fictional. Descriptors are synthetic imitations of card-statement text.",
        "Rules are ordered regular expressions applied after stripping prefixes, store numbers and state codes.",
        "Precision and recall are measured against the generator's true merchant, which real data would not provide.",
        "About 7% of descriptors are deliberately garbled; they remain Unknown and are excluded from merchant forecasts.",
    ]
    return out


class ClassifyRequest(BaseModel):
    descriptor: str = Field(..., min_length=1, max_length=200)


@app.post("/api/merchants/classify", dependencies=[Depends(limit("classify", 60))])
def classify(req: ClassifyRequest):
    import pandas as pd
    res = classify_descriptors(pd.Series([req.descriptor])).iloc[0]
    matched = res["merchant_clean"] != "Unknown"
    rule = CATALOG[int(res["rule_id"])] if matched else None
    return {"descriptor": req.descriptor, "normalized": res["normalized"], "matched": bool(matched),
            "merchant": res["merchant_clean"], "category": res["category_clean"],
            "pattern": rule.pattern if rule else None}


def _scope_label(category, channel, region, start, end) -> str:
    parts = [f"{k}: {v}" for k, v in (("Category", category), ("Channel", channel), ("Region", region))
             if v and v != "All"]
    if start or end:
        parts.append(f"Dates: {start or 'start'} to {end or 'end'}")
    return ", ".join(parts) or "All transactions"


@app.get("/api/export/excel", dependencies=[Depends(limit("export", 6))])
def export_excel(category: Optional[str] = Category, channel: Optional[str] = Channel,
                 region: Optional[str] = Region, start: Optional[str] = Start, end: Optional[str] = End):
    d = filtered(category, channel, region, start, end)
    if d.empty:
        raise HTTPException(404, "No transactions match the selected filters.")
    ctx = build_context(d, _scope_label(category, channel, region, start, end))
    return Response(build_excel(ctx), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": 'attachment; filename="spendiq-report.xlsx"'})


@app.get("/api/export/pptx", dependencies=[Depends(limit("export", 6))])
def export_pptx(category: Optional[str] = Category, channel: Optional[str] = Channel,
                region: Optional[str] = Region, start: Optional[str] = Start, end: Optional[str] = End):
    d = filtered(category, channel, region, start, end)
    if d.empty:
        raise HTTPException(404, "No transactions match the selected filters.")
    ctx = build_context(d, _scope_label(category, channel, region, start, end))
    return Response(build_pptx(ctx), media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    headers={"Content-Disposition": 'attachment; filename="spendiq-briefing.pptx"'})


@app.get("/api/governance")
def governance():
    df = get_df()
    camp = _campaign()
    fc = _forecast_cached("All", "All", "All", 3)
    return {
        "provenance": {
            "source": "Synthetic, generated locally by src/data.py with a fixed seed (42).",
            "rows": int(len(df)), "customers": int(df["customer_id"].nunique()),
            "period": f"{df['timestamp'].min():%Y-%m-%d} to {df['timestamp'].max():%Y-%m-%d}",
            "data_version": DATA_VERSION,
        },
        "evaluation": {
            "forecast_holdout_months": fc["holdout_months"],
            "forecast_best_model": fc.get("best_model"),
            "campaign_test_rows": None if camp.get("error") else camp["split"]["test_rows"],
        },
        "controls": [
            "Rolling-origin forecast backtest with last-month and seasonal-naive baselines.",
            "Chronological campaign train/test split; customer-history features use only earlier rows.",
            "Single shared read-only SQL path: one parsed SELECT, DuckDB external file access disabled, row cap.",
            "Schema, duplicate-ID, null, non-negative and binary-label validation on load.",
            "Regex merchant-cleaning rules with measured coverage and precision against synthetic ground truth.",
            "Six forecast approaches (RF, XGBoost, ETS, ARIMA, two naive baselines) compared on one backtest.",
            "Reproducible generator covered by automated tests.",
        ],
        "limitations": [
            "Synthetic data: results do not establish real-world model performance.",
            "Seasonality and response effects are built into the generator, so model skill is partly by construction.",
            "The campaign model is transaction-level; it is not a causal uplift model.",
            "Fairness analysis, drift monitoring and privacy review are not comprehensive in this demo.",
            "Human, legal and compliance review would be required before any real-world use.",
        ],
        "out_of_scope": ["Credit or lending decisions", "Eligibility or access to financial services",
                         "Fraud decisions", "Pricing", "Targeting real customers"],
        "disclaimer": "SpendIQ is an independent educational project. It is not affiliated with any bank and makes no claim of regulatory compliance.",
    }


# ─────────────────────────────────────────────── operations forecasting
@lru_cache(maxsize=4)
def _ops_forecast_cached(horizon):
    return run_operations_forecast(get_df(), horizon=horizon)


@app.get("/api/ops-forecast")
def ops_forecast(horizon: int = Query(3, ge=1, le=12)):
    """Forecast monthly transaction volume and average ticket per channel."""
    res = _ops_forecast_cached(horizon)
    if res.get("error"):
        raise HTTPException(422, res["error"])
    return res


# ─────────────────────────────────────────────── budget management
@lru_cache(maxsize=1)
def _budget_cached():
    return budget_variance(get_df())


@app.get("/api/budget")
def budget():
    """Monthly actual vs. budget variance with RAG status per category."""
    res = _budget_cached()
    if res.get("error"):
        raise HTTPException(422, res["error"])
    return res


# ─────────────────────────────────────────────── macro intelligence
@app.get("/api/macro")
def macro(month: Optional[str] = Query(None, description="YYYY-MM, defaults to latest")):
    """Current macro snapshot: CPI, consumer sentiment, GDP, watch items, themes."""
    return {
        "context": get_macro_context(month),
        "indicators": get_all_indicators(),
        "notes": [
            "All macro indicators are synthetic, generated from a fixed seed correlated with the transaction data.",
            "Watch items are derived from indicator thresholds and do not reflect real market conditions.",
        ],
    }


@app.get("/api/report-library")
def report_library(category: Optional[str] = Query(None, description="Filter by category tag or 'All'")):
    """Curated library of synthetic macro/industry reports with watch items and forecast implications."""
    reports = get_report_library(category)
    return {"reports": reports, "total": len(reports)}


# ─────────────────────────────────────────────── narrative summaries
class NarrativeContext(BaseModel):
    context: dict = Field(default_factory=dict)


@app.post("/api/narrative/{section}", dependencies=[Depends(limit("narrative", 20))])
def narrative(section: str, req: NarrativeContext = NarrativeContext()):
    """Generate a plain-English narrative summary for a dashboard section.
    
    Sections: overview, forecast, segments, campaign, ops, budget, macro, merchants.
    Uses Gemini API if GEMINI_API_KEY env var is set; otherwise returns template text.
    """
    valid = {"overview", "forecast", "segments", "campaign", "ops", "budget", "macro", "merchants"}
    if section not in valid:
        raise HTTPException(400, f"Unknown section '{section}'. Valid sections: {sorted(valid)}")
    text = generate_summary(section, req.context)
    return {"section": section, "summary": text}

