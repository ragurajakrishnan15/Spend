"""Synthetic transaction data generation, validation and loading.

Everything here is synthetic. The generator is fully reproducible for a given seed and
encodes explicit calendar seasonality and a gentle upward trend so forecasting
baselines (last month / seasonal naive) are meaningful to compare.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from src.merchants import CATALOG, classify_descriptors, make_descriptor

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
CSV_PATH = DATA_DIR / "transactions.csv"
DB_PATH = DATA_DIR / "spendiq.duckdb"

# Bump when the generator changes so stale cached CSV/DuckDB files are rebuilt.
DATA_VERSION = 3
DEFAULT_START = "2023-01-01"
DEFAULT_MONTHS = 36

CATEGORIES = ["Groceries", "Dining", "Travel", "Retail", "Utilities", "Entertainment", "Health", "Fuel"]
CATEGORY_PROBS = np.array([.20, .16, .08, .18, .12, .09, .08, .09])
CATEGORY_BASE_AMOUNT = {"Groceries": 52, "Dining": 34, "Travel": 180, "Retail": 78, "Utilities": 95,
                        "Entertainment": 42, "Health": 66, "Fuel": 48}
CHANNELS = ["Card-present", "E-commerce", "Mobile wallet"]
CHANNEL_PROBS = [.49, .34, .17]
REGIONS = ["Northeast", "South", "Midwest", "West"]

# Overall calendar seasonality of transaction volume (index 0 = January).
MONTH_VOLUME_WEIGHT = np.array([.90, .85, .98, .97, 1.02, 1.04, 1.06, 1.03, .97, 1.00, 1.12, 1.30])
TREND_PER_MONTH = 0.008      # +0.8% transaction volume per month
AMOUNT_INFLATION = 0.002     # +0.2% average ticket per month

REQUIRED_COLUMNS = {"transaction_id", "customer_id", "timestamp", "amount", "category",
                    "channel", "region", "campaign_exposed", "campaign_response",
                    "merchant_descriptor", "true_merchant"}


def category_month_multiplier(category: str, month: int) -> float:
    """Category-specific seasonal multiplier for a calendar month (1-12)."""
    m = month
    g = lambda c, w: float(np.exp(-((m - c) ** 2) / w))
    if category == "Travel":
        return 1 + .6 * g(7, 4) + .4 * g(12, 2)
    if category == "Retail":
        return 1 + .8 * g(12, 1.5) + .4 * g(11, 1.5)
    if category == "Utilities":
        return 1 + .25 * float(np.cos(2 * np.pi * (m - 1) / 12))
    if category == "Fuel":
        return 1 + .2 * g(7, 6)
    if category == "Dining":
        return 1 + .15 * g(12, 2)
    return 1.0


def generate_synthetic_data(seed: int = 42, customers: int = 1000, transactions: int = 36000,
                            months: int = DEFAULT_MONTHS, start: str = DEFAULT_START) -> pd.DataFrame:
    if customers < 1 or transactions < 1 or months < 1:
        raise ValueError("customers, transactions and months must be positive")
    rng = np.random.default_rng(seed)
    month_starts = pd.date_range(pd.Timestamp(start), periods=months, freq="MS")
    month_ends = month_starts + pd.offsets.MonthBegin(1)

    # Month of each transaction: calendar seasonality x trend.
    idx = np.arange(months)
    weights = MONTH_VOLUME_WEIGHT[month_starts.month.to_numpy() - 1] * (1 + TREND_PER_MONTH * idx)
    month_idx = rng.choice(months, size=transactions, p=weights / weights.sum())
    span = (month_ends - month_starts).total_seconds().to_numpy()[month_idx]
    offset = (rng.random(transactions) * span).astype(np.int64)
    timestamps = month_starts[month_idx] + pd.to_timedelta(offset, unit="s")
    cal_month = month_starts.month.to_numpy()[month_idx]

    # Customers have heterogeneous activity and a latent response propensity.
    cust_weight = rng.lognormal(0, .8, size=customers)
    cust_weight /= cust_weight.sum()
    cust_effect = rng.normal(0, .5, size=customers)
    cust_idx = rng.choice(customers, size=transactions, p=cust_weight)
    customer_ids = (10000 + cust_idx).astype(str)

    # Category mix varies by calendar month.
    mult = np.array([[category_month_multiplier(c, m) for c in CATEGORIES] for m in range(1, 13)])
    probs = CATEGORY_PROBS[None, :] * mult
    probs /= probs.sum(axis=1, keepdims=True)
    cum = probs[cal_month - 1].cumsum(axis=1)
    cat_idx = (rng.random(transactions)[:, None] > cum).sum(axis=1).clip(max=len(CATEGORIES) - 1)
    cat = np.array(CATEGORIES)[cat_idx]

    base = np.array([CATEGORY_BASE_AMOUNT[c] for c in cat], dtype=float)
    amount = rng.lognormal(np.log(base), .55) * (1 + AMOUNT_INFLATION * month_idx)
    amount = np.clip(amount, 2, 1800).round(2)

    channel = rng.choice(CHANNELS, size=transactions, p=CHANNEL_PROBS)
    region = rng.choice(REGIONS, size=transactions)
    exposed = rng.binomial(1, .38, size=transactions)

    # Synthetic response process (NOT a real-world targeting model).
    cat_eff = {"Retail": .35, "Travel": .30, "Dining": .25, "Entertainment": .10}
    chan_eff = {"Card-present": 0.0, "E-commerce": .30, "Mobile wallet": .45}
    reg_eff = {"Northeast": .10, "South": 0.0, "Midwest": -.05, "West": .15}
    logit = (-2.4 + .7 * exposed
             + np.array([cat_eff.get(c, 0.0) for c in cat])
             + np.array([chan_eff[c] for c in channel])
             + np.array([reg_eff[r] for r in region])
             + cust_effect[cust_idx]
             + .15 * np.log(amount / base)
             + rng.normal(0, .25, transactions))
    response = rng.binomial(1, 1 / (1 + np.exp(-logit)))

    # Merchants are drawn AFTER every earlier random draw so pre-existing columns are unchanged.
    true_merchant, descriptor = _assign_merchants(rng, cat, month_idx, months)

    df = pd.DataFrame({
        "customer_id": customer_ids,
        "timestamp": pd.to_datetime(timestamps),
        "amount": amount,
        "category": cat,
        "channel": channel,
        "region": region,
        "campaign_exposed": exposed.astype(int),
        "campaign_response": response.astype(int),
        "merchant_descriptor": descriptor,
        "true_merchant": true_merchant,
    }).sort_values("timestamp", kind="stable").reset_index(drop=True)
    df.insert(0, "transaction_id", [f"TX{i:07d}" for i in range(len(df))])
    validate_data(df)
    return df


def _assign_merchants(rng, cat: np.ndarray, month_idx: np.ndarray, months: int):
    """Pick a fictional merchant within each category (with differing growth) and a noisy raw descriptor."""
    by_cat: dict[str, list] = {}
    for m in CATALOG:
        by_cat.setdefault(m.category, []).append(m)
    base_w = np.array([.5, .3, .2])
    drift = np.array([0.5, 0.0, -0.4])     # first merchant grows, third shrinks over the period
    names = np.empty(len(cat), dtype=object)
    desc = np.empty(len(cat), dtype=object)
    t = month_idx / max(months - 1, 1)
    u = rng.random(len(cat))
    for c, merchants in by_cat.items():
        rows = np.flatnonzero(cat == c)
        w = base_w[None, :] * np.exp(drift[None, :] * t[rows, None])
        w /= w.sum(axis=1, keepdims=True)
        pick = (u[rows, None] > w.cumsum(axis=1)).sum(axis=1).clip(max=len(merchants) - 1)
        for r, k in zip(rows, pick):
            names[r] = merchants[k].name
            desc[r] = make_descriptor(rng, merchants[k])
    return names, desc


def validate_data(df: pd.DataFrame) -> None:
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")
    if df.empty:
        raise ValueError("Dataset is empty")
    if df["transaction_id"].duplicated().any():
        raise ValueError("Duplicate transaction IDs detected")
    if df["amount"].isna().any() or not np.isfinite(df["amount"].to_numpy(dtype=float)).all():
        raise ValueError("Transaction amounts must be finite and non-missing")
    if (df["amount"] < 0).any():
        raise ValueError("Transaction amounts must be non-negative")
    if df["timestamp"].isna().any():
        raise ValueError("Missing transaction timestamps")
    if not pd.api.types.is_datetime64_any_dtype(df["timestamp"]):
        raise ValueError("timestamp must be a datetime column")
    for col in ["customer_id", "category", "channel", "region", "merchant_descriptor"]:
        if df[col].isna().any():
            raise ValueError(f"{col} contains missing values")
    for col in ["campaign_exposed", "campaign_response"]:
        if df[col].isna().any() or not set(df[col].unique()).issubset({0, 1}):
            raise ValueError(f"{col} must be binary (0/1) with no missing values")


def _write_database(df: pd.DataFrame, db_path: Path) -> None:
    """Write the transactions table atomically (temp file + replace)."""
    tmp = db_path.with_suffix(".duckdb.tmp")
    for p in (tmp, Path(str(tmp) + ".wal")):
        p.unlink(missing_ok=True)
    con = duckdb.connect(str(tmp))
    try:
        con.register("df_view", df)
        con.execute("CREATE TABLE transactions AS SELECT * FROM df_view")
    finally:
        con.close()
    os.replace(tmp, db_path)


def load_or_create_data(data_dir: Path | None = None) -> pd.DataFrame:
    """Load the cached CSV (validated) or generate it; keep DuckDB in sync without needless rebuilds."""
    data_dir = Path(data_dir) if data_dir else DATA_DIR
    csv_path, db_path, meta_path = data_dir / "transactions.csv", data_dir / "spendiq.duckdb", data_dir / "transactions.meta.json"
    data_dir.mkdir(parents=True, exist_ok=True)
    try:
        meta = json.loads(meta_path.read_text())
    except (OSError, ValueError):
        meta = {}
    regenerate = not csv_path.exists() or meta.get("version") != DATA_VERSION
    if regenerate:
        df = generate_synthetic_data()
        df.to_csv(csv_path, index=False)
        meta_path.write_text(json.dumps({"version": DATA_VERSION, "seed": 42}))
    else:
        df = pd.read_csv(csv_path, parse_dates=["timestamp"])
        validate_data(df)
    # Enrich with regex-cleaned merchants (derived, never stored in the raw CSV).
    cleaned = classify_descriptors(df["merchant_descriptor"])[["merchant_clean", "category_clean"]]
    df = df.join(cleaned)
    if regenerate or not db_path.exists() or db_path.stat().st_mtime < csv_path.stat().st_mtime:
        _write_database(df, db_path)
        parquet = data_dir / "transactions.parquet"   # warehouse-style export (Snowflake / Athena friendly)
        con = duckdb.connect(str(db_path), read_only=True)
        try:
            con.execute(f"COPY transactions TO '{parquet.as_posix()}' (FORMAT PARQUET)")
        finally:
            con.close()
    return df
