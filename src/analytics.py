"""Analytics for SpendIQ: aggregates, RFM segmentation, forecasting and campaign modelling.

All functions operate on the synthetic transaction frame produced by ``src.data``.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.inspection import permutation_importance
from sklearn.metrics import (confusion_matrix, f1_score, mean_absolute_error, mean_squared_error,
                             precision_score, recall_score, roc_auc_score)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from src.sql_safety import run_sql, validate_query, UnsafeQueryError  # noqa: F401  (re-exported)


# --------------------------------------------------------------------------- aggregates
def filter_transactions(df: pd.DataFrame, category=None, channel=None, region=None,
                        start=None, end=None) -> pd.DataFrame:
    out = df
    if category and category != "All":
        out = out[out["category"] == category]
    if channel and channel != "All":
        out = out[out["channel"] == channel]
    if region and region != "All":
        out = out[out["region"] == region]
    if start:
        out = out[out["timestamp"] >= pd.Timestamp(start)]
    if end:
        out = out[out["timestamp"] < pd.Timestamp(end) + pd.Timedelta(days=1)]
    return out


def monthly_spend(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame({"month": pd.to_datetime([]), "spend": []})
    out = (df.assign(month=df["timestamp"].dt.to_period("M").dt.to_timestamp())
             .groupby("month", as_index=False)["amount"].sum())
    return out.rename(columns={"amount": "spend"}).sort_values("month").reset_index(drop=True)


def category_spend(df: pd.DataFrame) -> pd.DataFrame:
    return (df.groupby("category", as_index=False)["amount"].sum()
              .rename(columns={"amount": "spend"}).sort_values("spend", ascending=False))


# --------------------------------------------------------------------------- segmentation
def _name_segments(profile: pd.DataFrame) -> dict:
    """Descriptive names from cluster means (z-scored against the overall spread)."""
    z = (profile - profile.mean()) / profile.std(ddof=0).replace(0, 1)
    names, used = {}, {}
    for cluster, row in z.iterrows():
        if row["recency_days"] > .5:
            name = "Lapsing"
        elif row["monetary"] > .5 and row["frequency"] > .0:
            name = "High-spend active"
        elif row["monetary"] < -.5:
            name = "Light activity"
        else:
            name = "Steady core"
        used[name] = used.get(name, 0) + 1
        names[cluster] = name if used[name] == 1 else f"{name} {used[name]}"
    return names


def customer_rfm(df: pd.DataFrame, n_clusters: int = 4) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    reference = df["timestamp"].max() + pd.Timedelta(days=1)
    rfm = df.groupby("customer_id").agg(
        last_seen=("timestamp", "max"),
        frequency=("transaction_id", "count"),
        monetary=("amount", "sum"),
    ).reset_index()
    rfm["recency_days"] = (reference - rfm["last_seen"]).dt.days
    rfm = rfm.drop(columns=["last_seen"])
    k = min(n_clusters, len(rfm))
    if k < 2:
        rfm["segment"] = "Segment 1"
        return rfm
    features = np.log1p(rfm[["recency_days", "frequency", "monetary"]].clip(lower=0))
    scaled = StandardScaler().fit_transform(features)
    labels = KMeans(n_clusters=k, random_state=42, n_init=10).fit_predict(scaled)
    profile = rfm.assign(cluster=labels).groupby("cluster")[["recency_days", "frequency", "monetary"]].mean()
    names = _name_segments(profile.sort_values("monetary"))
    rfm["segment"] = pd.Series(labels, index=rfm.index).map(names)
    return rfm


def segment_summary(segments: pd.DataFrame) -> pd.DataFrame:
    if segments.empty:
        return pd.DataFrame(columns=["segment", "customers", "avg_recency_days", "avg_transactions", "avg_spend", "total_spend"])
    out = segments.groupby("segment", as_index=False).agg(
        customers=("customer_id", "count"),
        avg_recency_days=("recency_days", "mean"),
        avg_transactions=("frequency", "mean"),
        avg_spend=("monetary", "mean"),
        total_spend=("monetary", "sum"),
    )
    return out.sort_values("total_spend", ascending=False).round(2).reset_index(drop=True)


# --------------------------------------------------------------------------- forecasting
MIN_HISTORY = 6          # below this, only a flat naive forecast is produced
SEASONAL_MIN_ROWS = 24   # seasonal-ratio features need >= 24 months of history
MAX_HOLDOUT = 12         # evaluate on up to the final 12 months (one seasonal cycle)


def _row_features(prior: list[float], month: pd.Timestamp, seasonal: bool) -> dict | None:
    """Features for predicting `month` using ONLY values strictly before it."""
    need = 13 if seasonal else 3
    if len(prior) < need or min(prior[-need:]) <= 0:
        return None
    lag1, lag2 = prior[-1], prior[-2]
    roll3 = float(np.mean(prior[-3:]))
    feats = {"month_num": month.month, "mom_prev": lag1 / lag2, "lag1_vs_roll3": lag1 / roll3}
    if seasonal:
        feats["seasonal_ratio"] = prior[-12] / prior[-13]   # same-month-last-year MoM ratio
        feats["lag1_vs_lag12"] = lag1 / prior[-12]
    return feats


def _make_model() -> RandomForestRegressor:
    return RandomForestRegressor(n_estimators=200, min_samples_leaf=2, random_state=42, n_jobs=1)


def _error_row(name: str, actual: np.ndarray, pred: np.ndarray) -> dict:
    return {
        "model": name,
        "MAE": round(float(mean_absolute_error(actual, pred)), 2),
        "RMSE": round(float(np.sqrt(mean_squared_error(actual, pred))), 2),
        "MAPE_pct": round(float(np.mean(np.abs((actual - pred) / actual)) * 100), 2),
    }


def _make_xgb():
    from xgboost import XGBRegressor
    return XGBRegressor(n_estimators=150, max_depth=2, learning_rate=0.08, subsample=0.9,
                        reg_lambda=2.0, random_state=42, n_jobs=1, verbosity=0)


def _ets_forecast(train: list[float], h: int) -> np.ndarray:
    """Holt-Winters; additive seasonality only when two full cycles are available."""
    import warnings
    from statsmodels.tsa.holtwinters import ExponentialSmoothing
    kw = {"trend": "add", "damped_trend": True}
    if len(train) >= 24:
        kw.update(seasonal="add", seasonal_periods=12)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fit = ExponentialSmoothing(np.asarray(train, dtype=float), initialization_method="estimated", **kw).fit()
        return np.asarray(fit.forecast(h), dtype=float)


def _arima_forecast(train: list[float], h: int) -> np.ndarray:
    """ARIMA(1,1,1) on log spend (so forecasts stay positive)."""
    import warnings
    from statsmodels.tsa.arima.model import ARIMA
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fit = ARIMA(np.log(np.asarray(train, dtype=float)), order=(1, 1, 1), trend="t").fit()
        return np.exp(np.asarray(fit.forecast(h), dtype=float))


MODEL_LABELS = {
    "model": "Random forest (lag features)",
    "xgboost": "XGBoost (lag features)",
    "ets": "Holt-Winters ETS",
    "arima": "ARIMA(1,1,1) on log spend",
    "last_month": "Last-month naive",
    "seasonal_naive": "Seasonal naive (t-12)",
}


def forecast_monthly_spend(monthly: pd.DataFrame, horizon: int = 3) -> dict:
    """Forecast monthly spend; benchmark six approaches in a rolling-origin backtest.

    Models: random forest and XGBoost (month-over-month-ratio lag features), Holt-Winters ETS,
    ARIMA, plus last-month and seasonal-naive baselines. Every backtest prediction is made by a model
    fit strictly on months before the one predicted. The forecast shown is from the model with the
    lowest backtest MAE (selection on the same backtest is noted in the docs).
    """
    if horizon < 1:
        raise ValueError("horizon must be >= 1")
    monthly = monthly.copy().sort_values("month").reset_index(drop=True)
    n = len(monthly)
    spend = monthly["spend"].astype(float).tolist()

    def future_dates(h):
        last = monthly["month"].max() if n else pd.Timestamp.today().to_period("M").to_timestamp()
        return pd.date_range(last + pd.offsets.MonthBegin(1), periods=h, freq="MS")

    def assemble(future: pd.DataFrame, label: str, metrics, backtest, by_model=None) -> dict:
        actual = monthly.assign(series="Actual")[["month", "spend", "series"]]
        fut = future.rename(columns={"forecast": "spend"}).assign(series=label)[["month", "spend", "series"]]
        return {"future": future, "plot_data": pd.concat([actual, fut], ignore_index=True),
                "metrics": metrics, "backtest": backtest, "holdout_months": len(backtest),
                "method": label, "seasonal": False, "future_by_model": by_model or {}}

    if n < MIN_HISTORY or min(spend, default=0) <= 0:
        last = spend[-1] if n else 0.0
        future = pd.DataFrame({"month": future_dates(horizon), "forecast": [round(float(last), 2)] * horizon})
        return assemble(future, "Last-month naive", [], pd.DataFrame())

    seasonal = n >= SEASONAL_MIN_ROWS
    months = monthly["month"].tolist()
    samples = []   # (index, features, target_ratio)
    for i in range(n):
        f = _row_features(spend[:i], months[i], seasonal)
        if f is not None:
            samples.append((i, f, spend[i] / spend[i - 1]))
    min_train = 3
    n_test = min(MAX_HOLDOUT, max(1, len(samples) - min_train))
    cols = list(samples[0][1].keys())
    X = pd.DataFrame([s[1] for s in samples])[cols]
    y = np.array([s[2] for s in samples])

    def safe(fn, *args):
        try:
            return fn(*args)
        except Exception:   # a statistical fit can fail on odd slices; that model is then omitted
            return None

    rows = []
    for j in range(len(samples) - n_test, len(samples)):
        i = samples[j][0]
        train_vals = spend[:i]
        rf = _make_model().fit(X.iloc[:j], y[:j])
        xg = _make_xgb().fit(X.iloc[:j], y[:j])
        ets = safe(_ets_forecast, train_vals, 1)
        ari = safe(_arima_forecast, train_vals, 1)
        rows.append({
            "month": months[i], "actual": spend[i],
            "model": spend[i - 1] * float(rf.predict(X.iloc[[j]])[0]),
            "xgboost": spend[i - 1] * float(xg.predict(X.iloc[[j]])[0]),
            "ets": float(ets[0]) if ets is not None else np.nan,
            "arima": float(ari[0]) if ari is not None else np.nan,
            "last_month": spend[i - 1],
            "seasonal_naive": spend[i - 12] if i >= 12 else np.nan,
        })
    backtest = pd.DataFrame(rows)
    # Compare on the months where every included model has a prediction.
    use = ["model", "xgboost", "ets", "arima", "last_month", "seasonal_naive"]
    use = [c for c in use if backtest[c].notna().any()]
    comparable = backtest.dropna(subset=use)
    if comparable.empty:
        use = ["model", "xgboost", "last_month"]
        comparable = backtest.dropna(subset=use)
    act = comparable["actual"].to_numpy()
    metrics = [_error_row(MODEL_LABELS[c], act, comparable[c].to_numpy()) | {"key": c} for c in use]
    best_row = min(metrics, key=lambda r: r["MAE"])
    best_key, best = best_row["key"], best_row["model"]
    for r in metrics:
        r["best"] = r["key"] == best_key

    # Future forecasts for every model, fit on all history.
    h = horizon
    fdates = future_dates(h)
    by_model: dict[str, list[float]] = {}

    def recursive(make):
        mdl = make().fit(X, y)
        hist, vals = list(spend), []
        for month in fdates:
            f = _row_features(hist, month, seasonal)
            v = max(0.0, hist[-1] * float(mdl.predict(pd.DataFrame([f])[cols])[0]))
            hist.append(v)
            vals.append(v)
        return vals

    by_model["model"] = recursive(_make_model)
    by_model["xgboost"] = recursive(_make_xgb)
    if "ets" in use:
        r = safe(_ets_forecast, spend, h)
        if r is not None:
            by_model["ets"] = np.maximum(r, 0).tolist()
    if "arima" in use:
        r = safe(_arima_forecast, spend, h)
        if r is not None:
            by_model["arima"] = r.tolist()
    by_model["last_month"] = [spend[-1]] * h
    if n >= 12:
        by_model["seasonal_naive"] = [spend[-12 + (k % 12)] for k in range(h)]

    chosen = by_model.get(best_key, by_model["model"])
    resid = (backtest["actual"] - backtest[best_key]).dropna().to_numpy()
    lo, hi = (np.percentile(resid, 10), np.percentile(resid, 90)) if len(resid) >= 3 else (0.0, 0.0)
    out = []
    for k, (month, val) in enumerate(zip(fdates, chosen)):
        widen = np.sqrt(k + 1)   # uncertainty grows with horizon
        out.append({"month": month, "forecast": round(float(val), 2),
                    "lower": round(max(0.0, val + lo * widen), 2), "upper": round(val + hi * widen, 2)})
    result = assemble(pd.DataFrame(out), "Model forecast", metrics, backtest,
                      {MODEL_LABELS[k]: [round(float(x), 2) for x in v] for k, v in by_model.items()})
    result["seasonal"] = seasonal
    result["best_model"] = best
    result["selected_model_key"] = best_key
    return result


# --------------------------------------------------------------------------- merchant-level forecasting
def forecast_merchant_spend(df: pd.DataFrame, merchant_col: str = "merchant_clean", holdout: int = 6) -> dict:
    """Pooled one-step-ahead merchant spend model (XGBoost) vs last-month and seasonal-naive baselines.

    Each merchant-month is a row; features use only that merchant's earlier months. The backtest
    refits before every held-out month. Unknown (unmatched) descriptors are excluded.
    """
    d = df[df[merchant_col] != "Unknown"]
    if d.empty:
        return {"error": "No classified merchants available."}
    panel = (d.assign(month=d["timestamp"].dt.to_period("M").dt.to_timestamp())
               .groupby([merchant_col, "month"], as_index=False)
               .agg(spend=("amount", "sum"), transactions=("amount", "size"), category=("category", "first")))
    all_months = sorted(panel["month"].unique())
    if len(all_months) < 15:
        return {"error": "Need at least 15 months of history for merchant-level forecasting."}
    cat_codes = {c: i for i, c in enumerate(sorted(panel["category"].unique()))}
    wide = panel.pivot(index="month", columns=merchant_col, values="spend").reindex(all_months).fillna(0.0)
    cats = panel.drop_duplicates(merchant_col).set_index(merchant_col)["category"]

    rows = []
    for m in wide.columns:
        v = wide[m].to_numpy()
        for t in range(13, len(all_months)):
            prior = v[:t]
            if prior[-1] <= 0 or prior[-12] <= 0 or prior[-13] <= 0 or v[t] <= 0:
                continue
            rows.append({
                "merchant": m, "t": t, "month": all_months[t], "actual": v[t], "last": prior[-1],
                "seasonal": prior[-12],
                "month_num": all_months[t].month, "cat": cat_codes[cats[m]],
                "mom_prev": prior[-1] / prior[-2] if prior[-2] > 0 else 1.0,
                "lag1_vs_roll3": prior[-1] / max(prior[-3:].mean(), 1e-9),
                "lag1_vs_lag12": prior[-1] / prior[-12],
                "seasonal_ratio": prior[-12] / prior[-13],
                "ratio": v[t] / prior[-1],
            })
    P = pd.DataFrame(rows)
    if P.empty:
        return {"error": "Not enough merchant history for a backtest."}
    feats = ["month_num", "cat", "mom_prev", "lag1_vs_roll3", "lag1_vs_lag12", "seasonal_ratio"]
    test_ts = sorted(P["t"].unique())[-holdout:]
    preds = []
    for t in test_ts:
        tr, te = P[P["t"] < t], P[P["t"] == t]
        if len(tr) < 30:
            continue
        mdl = _make_xgb().fit(tr[feats], tr["ratio"])
        preds.append(te.assign(model=te["last"] * mdl.predict(te[feats])))
    if not preds:
        return {"error": "Not enough merchant history for a backtest."}
    bt = pd.concat(preds, ignore_index=True)

    def wape(col):
        return float(np.abs(bt["actual"] - bt[col]).sum() / bt["actual"].sum() * 100)

    metrics = [
        {"model": "XGBoost (pooled, merchant features)", "WAPE_pct": round(wape("model"), 2)},
        {"model": "Last-month naive", "WAPE_pct": round(wape("last"), 2)},
        {"model": "Seasonal naive (t-12)", "WAPE_pct": round(wape("seasonal"), 2)},
    ]
    best = min(metrics, key=lambda r: r["WAPE_pct"])["model"]
    for r in metrics:
        r["best"] = r["model"] == best

    # Next-month forecast per merchant from a model fit on all rows.
    final = _make_xgb().fit(P[feats], P["ratio"])
    nxt = all_months[-1] + pd.offsets.MonthBegin(1)
    out = []
    for m in wide.columns:
        v = wide[m].to_numpy()
        if v[-1] <= 0 or v[-12] <= 0 or v[-13] <= 0:
            continue
        x = pd.DataFrame([{"month_num": nxt.month, "cat": cat_codes[cats[m]],
                           "mom_prev": v[-1] / v[-2] if v[-2] > 0 else 1.0,
                           "lag1_vs_roll3": v[-1] / max(v[-3:].mean(), 1e-9),
                           "lag1_vs_lag12": v[-1] / v[-12], "seasonal_ratio": v[-12] / v[-13]}])
        f = float(v[-1] * final.predict(x[feats])[0])
        out.append({"merchant": m, "category": cats[m], "last_month_spend": round(float(v[-1]), 2),
                    "forecast_next_month": round(max(f, 0.0), 2),
                    "change_pct": round((f / v[-1] - 1) * 100, 1),
                    "trailing_12m_spend": round(float(v[-12:].sum()), 2)})
    table = pd.DataFrame(out).sort_values("trailing_12m_spend", ascending=False).reset_index(drop=True)
    return {"metrics": metrics, "best_model": best, "table": table, "next_month": nxt,
            "backtest_months": len(test_ts), "backtest_rows": int(len(bt)), "n_merchants": int(table.shape[0])}


# --------------------------------------------------------------------------- campaign model
CAMPAIGN_CATEGORICAL = ["category", "channel", "region"]
CAMPAIGN_NUMERIC = ["amount", "campaign_exposed", "month_num", "day_of_week",
                    "prior_txn_count", "prior_response_rate", "prior_spend", "days_since_prev_txn"]
PRIOR_ALPHA, PRIOR_BETA = 1.0, 4.0   # fixed Beta prior => 20% response rate, not learned from the full data


def build_campaign_features(df: pd.DataFrame) -> pd.DataFrame:
    """Leakage-safe features. Customer-history features use only transactions strictly earlier in time
    (cumulative sums minus the current row). Assumes earlier responses are observed immediately - a
    simplification of real campaign feedback delays."""
    d = df.sort_values(["timestamp", "transaction_id"], kind="stable").reset_index(drop=True)
    g = d.groupby("customer_id", sort=False)
    d["prior_txn_count"] = g.cumcount()
    prior_resp = g["campaign_response"].cumsum() - d["campaign_response"]
    d["prior_response_rate"] = (prior_resp + PRIOR_ALPHA) / (d["prior_txn_count"] + PRIOR_ALPHA + PRIOR_BETA)
    d["prior_spend"] = g["amount"].cumsum() - d["amount"]
    gap = g["timestamp"].diff().dt.total_seconds() / 86400
    d["days_since_prev_txn"] = gap.fillna(-1.0)
    d["month_num"] = d["timestamp"].dt.month
    d["day_of_week"] = d["timestamp"].dt.dayofweek
    return d


def run_campaign_model(df: pd.DataFrame, test_fraction: float = .2) -> dict:
    if df.empty:
        return {"error": "No transactions available."}
    d = build_campaign_features(df)
    split_pos = int(len(d) * (1 - test_fraction))
    if split_pos < 1 or split_pos >= len(d):
        return {"error": "Not enough transactions for a chronological split."}
    cutoff = d["timestamp"].iloc[split_pos]
    train, test = d[d["timestamp"] < cutoff], d[d["timestamp"] >= cutoff]
    if train.empty or test.empty:
        return {"error": "Not enough transactions for a chronological split."}
    y_train, y_test = train["campaign_response"].astype(int), test["campaign_response"].astype(int)
    if y_train.nunique() < 2 or y_test.nunique() < 2:
        return {"error": "Not enough class variation in chronological train/test split."}

    features = CAMPAIGN_CATEGORICAL + CAMPAIGN_NUMERIC
    pre = ColumnTransformer([("cat", OneHotEncoder(handle_unknown="ignore"), CAMPAIGN_CATEGORICAL)],
                            remainder="passthrough")
    model = Pipeline([("pre", pre), ("rf", RandomForestClassifier(
        n_estimators=200, min_samples_leaf=10, class_weight="balanced", random_state=42, n_jobs=1))])
    model.fit(train[features], y_train)
    proba = model.predict_proba(test[features])[:, 1]
    pred = (proba >= .5).astype(int)
    metrics = {
        "precision": float(precision_score(y_test, pred, zero_division=0)),
        "recall": float(recall_score(y_test, pred, zero_division=0)),
        "f1": float(f1_score(y_test, pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_test, proba)),
    }
    # Reference points: exposure-only score, and the no-skill AUC.
    baseline = {"roc_auc_exposure_only": float(roc_auc_score(y_test, test["campaign_exposed"])),
                "roc_auc_no_skill": 0.5}

    imp = permutation_importance(model, test[features], y_test, scoring="roc_auc",
                                 n_repeats=3, random_state=42, n_jobs=1)
    importance = (pd.DataFrame({"feature": features, "importance": imp.importances_mean})
                  .sort_values("importance", ascending=False).reset_index(drop=True))

    scored = pd.DataFrame({"p": proba, "y": y_test.to_numpy()})
    try:
        scored["decile"] = pd.qcut(scored["p"].rank(method="first"), 10, labels=False) + 1
    except ValueError:
        scored["decile"] = 1
    lift = (scored.groupby("decile").agg(customers=("y", "size"), response_rate=("y", "mean"), avg_score=("p", "mean"))
            .reset_index().sort_values("decile", ascending=False))
    return {
        "metrics": metrics, "baseline": baseline, "importance": importance, "lift": lift,
        "confusion": confusion_matrix(y_test, pred, labels=[0, 1]),
        "split": {
            "cutoff": cutoff, "train_rows": int(len(train)), "test_rows": int(len(test)),
            "train_start": train["timestamp"].min(), "train_end": train["timestamp"].max(),
            "test_start": test["timestamp"].min(), "test_end": test["timestamp"].max(),
            "train_response_rate": float(y_train.mean()), "test_response_rate": float(y_test.mean()),
        },
        "features": features,
    }


# --------------------------------------------------------------------------- operations forecasting
_OPS_CHANNELS = None   # lazily cached channel list


def run_operations_forecast(df: pd.DataFrame, horizon: int = 3) -> dict:
    """Forecast monthly transaction *volume* (count) and *average ticket* per channel.

    Uses the same rolling-origin XGBoost + last-month naive backtest as spend forecasting,
    applied to two operational KPIs that map to the JD's 'operations forecasting' requirement:
    - transaction_count : total transactions per channel per month
    - avg_ticket        : mean transaction amount per channel per month

    Returns per-channel forecasts and aggregate error metrics.
    """
    if df.empty:
        return {"error": "No transactions available."}

    panel = (
        df.assign(month=df["timestamp"].dt.to_period("M").dt.to_timestamp())
          .groupby(["channel", "month"], as_index=False)
          .agg(transaction_count=("amount", "size"), avg_ticket=("amount", "mean"))
          .sort_values(["channel", "month"])
    )
    channels = sorted(panel["channel"].unique())
    all_months = sorted(panel["month"].unique())
    n_months = len(all_months)

    if n_months < MIN_HISTORY:
        return {"error": f"Need at least {MIN_HISTORY} months of data."}

    results: dict[str, dict] = {}
    aggregate_metrics: list[dict] = []

    for kpi in ("transaction_count", "avg_ticket"):
        ch_forecasts = []
        mae_list = []
        for ch in channels:
            sub = panel[panel["channel"] == ch].set_index("month").reindex(all_months).fillna(0)
            vals = sub[kpi].astype(float).tolist()
            if min(vals, default=0) <= 0 or len(vals) < MIN_HISTORY:
                continue

            # Build lag features (same pattern as main forecast)
            seasonal = len(vals) >= SEASONAL_MIN_ROWS
            samples = []
            for i in range(len(vals)):
                f = _row_features(vals[:i], all_months[i], seasonal)
                if f is not None:
                    samples.append((i, f, vals[i] / vals[i - 1]))
            if len(samples) < 4:
                continue
            cols = list(samples[0][1].keys())
            X = pd.DataFrame([s[1] for s in samples])[cols]
            y = np.array([s[2] for s in samples])

            n_test = min(MAX_HOLDOUT, max(1, len(samples) - 3))
            bt_rows = []
            for j in range(len(samples) - n_test, len(samples)):
                i_idx = samples[j][0]
                xg = _make_xgb().fit(X.iloc[:j], y[:j])
                xg_pred = vals[i_idx - 1] * float(xg.predict(X.iloc[[j]])[0])
                bt_rows.append({"month": all_months[i_idx], "actual": vals[i_idx],
                                 "xgboost": xg_pred, "naive": vals[i_idx - 1]})
            bt = pd.DataFrame(bt_rows)
            if bt.empty:
                continue
            act = bt["actual"].to_numpy()
            xg_mae = float(mean_absolute_error(act, bt["xgboost"].to_numpy()))
            naive_mae = float(mean_absolute_error(act, bt["naive"].to_numpy()))
            mae_list.append(xg_mae)

            # Future forecast
            final = _make_xgb().fit(X, y)
            hist = list(vals)
            last_month = all_months[-1]
            fdates = pd.date_range(last_month + pd.offsets.MonthBegin(1), periods=horizon, freq="MS")
            future_vals = []
            for fm in fdates:
                f = _row_features(hist, fm, seasonal)
                if f is None:
                    future_vals.append(hist[-1])
                else:
                    v = max(0.0, hist[-1] * float(final.predict(pd.DataFrame([f])[cols])[0]))
                    future_vals.append(v)
                hist.append(future_vals[-1])

            ch_forecasts.append({
                "channel": ch,
                "history": [{"month": m.strftime("%Y-%m"), "value": round(float(v), 2)}
                             for m, v in zip(all_months, vals)],
                "future": [{"month": str(m)[:7], "value": round(float(v), 2)}
                            for m, v in zip(fdates, future_vals)],
                "xgb_mae": round(xg_mae, 2),
                "naive_mae": round(naive_mae, 2),
                "best_model": "XGBoost" if xg_mae <= naive_mae else "Last-month naive",
            })
        results[kpi] = ch_forecasts
        if mae_list:
            aggregate_metrics.append({"kpi": kpi, "avg_xgb_mae": round(float(np.mean(mae_list)), 2)})

    return {
        "transaction_count": results.get("transaction_count", []),
        "avg_ticket": results.get("avg_ticket", []),
        "channels": channels,
        "horizon": horizon,
        "aggregate_metrics": aggregate_metrics,
        "notes": [
            "Transaction count = number of transactions per channel per month.",
            "Avg ticket = mean transaction amount per channel per month.",
            "XGBoost lag-ratio features; rolling-origin backtest identical to spend forecast.",
        ],
    }


# --------------------------------------------------------------------------- budget management
# Synthetic default monthly budgets by category (in USD).
# Set ~3-5% above each category's mean monthly spend so a realistic mix of RAG statuses appears.
DEFAULT_BUDGETS: dict[str, float] = {
    "Groceries": 12_800.0,
    "Dining": 6_500.0,
    "Travel": 21_000.0,
    "Retail": 20_000.0,
    "Utilities": 13_000.0,
    "Entertainment": 4_500.0,
    "Health": 6_200.0,
    "Fuel": 5_500.0,
}
_FALLBACK_BUDGET = 10_000.0
_RAG_AMBER = 0.10   # within 10% over budget → amber
_RAG_RED = 0.0      # any overspend → red


def budget_variance(df: pd.DataFrame,
                    budgets: dict[str, float] | None = None) -> dict:
    """Monthly actual spend vs. synthetic budgets, with RAG status per category-month.

    RAG rules:
      green  = actual ≤ budget
      amber  = actual > budget by ≤ 10 %
      red    = actual > budget by > 10 %

    Returns a summary table and a month-by-month detail table.
    """
    if df.empty:
        return {"error": "No transactions available."}

    budgets = budgets or DEFAULT_BUDGETS

    agg = (
        df.assign(month=df["timestamp"].dt.to_period("M").dt.to_timestamp())
          .groupby(["category", "month"], as_index=False)["amount"].sum()
          .rename(columns={"amount": "actual"})
    )
    agg["budget"] = agg["category"].map(budgets).fillna(_FALLBACK_BUDGET)
    agg["variance"] = agg["actual"] - agg["budget"]
    agg["variance_pct"] = (agg["variance"] / agg["budget"] * 100).round(2)

    def rag(row):
        if row["actual"] <= row["budget"]:
            return "green"
        elif row["variance_pct"] <= _RAG_AMBER * 100:
            return "amber"
        return "red"

    agg["rag"] = agg.apply(rag, axis=1)
    agg["month"] = agg["month"].dt.strftime("%Y-%m")
    agg = agg.round({"actual": 2, "budget": 2, "variance": 2})

    # Summary: per-category over all months
    summary = (
        agg.groupby("category", as_index=False)
           .agg(total_actual=("actual", "sum"), total_budget=("budget", "sum"),
                total_variance=("variance", "sum"), months_over_budget=("rag", lambda x: (x != "green").sum()))
           .assign(overall_variance_pct=lambda r: (r["total_variance"] / r["total_budget"] * 100).round(2))
           .sort_values("total_variance", ascending=False)
           .reset_index(drop=True)
           .round({"total_actual": 2, "total_budget": 2, "total_variance": 2})
    )

    return {
        "detail": agg.sort_values(["category", "month"]).to_dict(orient="records"),
        "summary": summary.to_dict(orient="records"),
        "budgets": budgets,
        "categories": sorted(agg["category"].unique().tolist()),
        "notes": [
            "Budgets are synthetic defaults calibrated to the generator's mean spend per category.",
            "RAG: green = on/under budget; amber = 0-10% over; red = >10% over.",
            "All figures are in synthetic USD; not real financial targets.",
        ],
    }
