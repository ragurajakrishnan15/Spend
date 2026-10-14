"""Synthetic macroeconomic intelligence layer for SpendIQ.

Generates synthetic macro indicators (CPI, consumer sentiment, GDP growth proxy)
that are correlated with the transaction data's seasonality. Also provides a
curated 'report library' of synthetic industry/macro briefs — mapping directly
to the JD requirement: 'Review existing reports on private companies, industries,
and macroeconomic conditions to identify relevant themes and risks.'

All data is SYNTHETIC. No external APIs are called.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# Fixed seed matching the transaction generator
_RNG = np.random.default_rng(42)

# ───────────────────────────────────── synthetic indicator generation

_MONTHS = pd.date_range("2023-01", periods=36, freq="MS")


def _seasonal_signal(months: pd.DatetimeIndex, amplitude: float, phase_month: int) -> np.ndarray:
    """Annual cosine wave peaking at `phase_month`."""
    angles = 2 * np.pi * (months.month - phase_month) / 12
    return amplitude * np.cos(angles)


def _build_indicators() -> pd.DataFrame:
    n = len(_MONTHS)
    trend = np.linspace(0, 1, n)

    # CPI YoY % — starts ~4.5%, trends down to ~2.8%, with holiday spikes
    cpi = (4.5 - 1.7 * trend
           + _seasonal_signal(_MONTHS, 0.3, 12)          # holiday / year-end spike
           + _RNG.normal(0, 0.08, n))

    # Consumer Sentiment Index (100 = neutral) — mild downtrend then recovery
    sentiment = (95 + 8 * np.sin(np.linspace(0, np.pi, n))
                 + _seasonal_signal(_MONTHS, 3.0, 6)     # summer optimism
                 + _RNG.normal(0, 1.2, n))

    # GDP Growth proxy (annualised %) — moderate growth with Q4 dip
    gdp = (2.4 + _seasonal_signal(_MONTHS, 0.6, 3)       # Q1 rebound
           - _seasonal_signal(_MONTHS, 0.4, 10)           # Q4 slowdown
           + _RNG.normal(0, 0.15, n))

    # Retail Sales Growth YoY %
    retail_sales = (3.1 + _seasonal_signal(_MONTHS, 1.5, 12)
                    + trend * 0.5 + _RNG.normal(0, 0.2, n))

    return pd.DataFrame({
        "month": _MONTHS.strftime("%Y-%m"),
        "cpi_yoy": cpi.round(2),
        "consumer_sentiment": sentiment.round(1),
        "gdp_growth": gdp.round(2),
        "retail_sales_growth": retail_sales.round(2),
    })


_INDICATORS: pd.DataFrame = _build_indicators()


def get_all_indicators() -> list[dict]:
    return _INDICATORS.to_dict(orient="records")


def get_macro_context(month: str | None = None) -> dict:
    """Return macro snapshot for a given YYYY-MM month (defaults to latest).

    Also returns derived 'watch items' and 'themes' for stakeholder narratives.
    """
    df = _INDICATORS.copy()
    if month and month in df["month"].values:
        row = df[df["month"] == month].iloc[0]
    else:
        row = df.iloc[-1]
        month = row["month"]

    cpi = float(row["cpi_yoy"])
    sent = float(row["consumer_sentiment"])
    gdp = float(row["gdp_growth"])
    retail = float(row["retail_sales_growth"])

    # Derive qualitative themes
    themes: list[str] = []
    watch_items: list[dict] = []

    if cpi > 3.5:
        themes.append("Elevated inflation squeezing consumer discretionary spend")
        watch_items.append({"category": "Dining & Entertainment", "signal": "Likely softness as consumers trade down",
                             "severity": "amber"})
    elif cpi < 2.5:
        themes.append("Inflation approaching target — consumer purchasing power recovering")

    if sent < 90:
        themes.append("Below-average consumer confidence — watch premium category performance")
        watch_items.append({"category": "Travel", "signal": "Bookings may lag seasonal norms",
                             "severity": "amber"})
    elif sent > 100:
        themes.append("Above-average sentiment supports discretionary spending growth")
        watch_items.append({"category": "Travel & Entertainment", "signal": "Outperformance likely in coming months",
                             "severity": "green"})

    if gdp < 1.5:
        themes.append("GDP growth slowing — defensive categories (Groceries, Utilities) may outperform")
        watch_items.append({"category": "Groceries", "signal": "Trade-up to essentials; budget pressure on Dining",
                             "severity": "green"})
    elif gdp > 3.0:
        themes.append("Strong GDP supports broad-based consumer spending expansion")

    if retail < 2.0:
        watch_items.append({"category": "Retail", "signal": "Retail sales growth below trend — monitor closely",
                             "severity": "red" if retail < 0 else "amber"})

    if not themes:
        themes.append("Macro environment stable; no significant headwinds or tailwinds identified")

    # MoM change for CPI
    idx = df.index[df["month"] == month].tolist()
    cpi_mom = None
    if idx and idx[0] > 0:
        cpi_mom = round(cpi - float(df.iloc[idx[0] - 1]["cpi_yoy"]), 2)

    return {
        "month": month,
        "indicators": {
            "cpi_yoy": cpi,
            "cpi_mom_change": cpi_mom,
            "consumer_sentiment": sent,
            "gdp_growth": gdp,
            "retail_sales_growth": retail,
        },
        "themes": themes,
        "watch_items": watch_items,
        "summary": f"CPI at {cpi:.1f}% YoY, consumer sentiment {sent:.0f}, GDP growth {gdp:.1f}%.",
    }


# ───────────────────────────────────── curated report library

REPORT_LIBRARY: list[dict] = [
    {
        "id": "RPT-001",
        "title": "Holiday Spending Outlook Q4 2025",
        "date": "2025-10",
        "category_tags": ["Dining", "Retail", "Travel", "Entertainment"],
        "source": "Synthetic Consumer Research Quarterly",
        "headline": "Holiday spend expected to rise 4.2% YoY, led by Travel and Dining recovery.",
        "key_themes": [
            "Early booking surge in Travel (October) driven by post-pandemic pent-up demand",
            "Gift card and digital purchases growing as share of Shopping category",
            "Dining spend shifts to premium experiences vs. fast casual",
        ],
        "watch_items": ["Supply-chain driven price increases in Electronics sub-category",
                        "Consumer credit utilization rising — monitor default risk proxies"],
        "implications_for_forecast": "Upside risk to Q4 spend in Travel and Dining; apply +3-5% seasonal adjustment.",
        "approved": True,
    },
    {
        "id": "RPT-002",
        "title": "Grocery Inflation & Consumer Trade-Down Patterns",
        "date": "2025-08",
        "category_tags": ["Groceries", "Dining"],
        "source": "Synthetic Retail Analytics Monitor",
        "headline": "Grocery inflation moderating to 2.1% YoY, but private-label share still elevated.",
        "key_themes": [
            "Private-label penetration at 38% — highest in 10 years",
            "Consumers substituting Dining out with grocery spending",
            "Health & organic sub-segment remains resilient despite inflation",
        ],
        "watch_items": ["Protein price volatility could reverse moderation trend",
                        "Restaurant traffic recovering could reduce Grocery uplift by H2"],
        "implications_for_forecast": "Groceries likely to outperform budget through mid-2025; Dining recovery is a headwind.",
        "approved": True,
    },
    {
        "id": "RPT-003",
        "title": "Travel Sector Recovery: Business vs. Leisure Split",
        "date": "2025-07",
        "category_tags": ["Travel"],
        "source": "Synthetic Travel Industry Intelligence",
        "headline": "Leisure travel at 112% of pre-pandemic levels; business travel still at 87%.",
        "key_themes": [
            "Blended 'bleisure' travel growing — average trip duration +1.4 days vs. 2019",
            "International travel outpacing domestic for first time since 2020",
            "Hotel and accommodation spend shifting to experiential properties",
        ],
        "watch_items": ["Airfare price sensitivity increasing as fares normalise",
                        "Credit card rewards redemption peak in Q3 may depress net spend"],
        "implications_for_forecast": "Travel category likely on-budget or slightly above through Q3; Q4 depends on holiday demand.",
        "approved": True,
    },
    {
        "id": "RPT-004",
        "title": "Digital Payments & Channel Mix Shift 2025",
        "date": "2025-06",
        "category_tags": ["Retail", "Entertainment"],
        "source": "Synthetic Payments Research Group",
        "headline": "Online channel share reaches 42% of total consumer spend, up from 35% in 2023.",
        "key_themes": [
            "Mobile wallet adoption accelerating — now 58% of online transactions",
            "Buy-Now-Pay-Later utilization up 22% among 25-34 cohort",
            "Subscription economy growing at 9% CAGR — new revenue stream for monitoring",
        ],
        "watch_items": ["Fraud rates in online channel 2.3x higher than in-store — monitor anomalies",
                        "BNPL delinquencies rising — forward-looking credit quality signal"],
        "implications_for_forecast": "Online channel volume beats operations forecast by ~8%; in-store declining.",
        "approved": True,
    },
    {
        "id": "RPT-005",
        "title": "Healthcare & Wellness Consumer Spending Trends",
        "date": "2025-05",
        "category_tags": ["Health"],
        "source": "Synthetic Health Economy Monitor",
        "headline": "Healthcare consumer spend growing at 6.8% YoY — fastest of all categories.",
        "key_themes": [
            "Telehealth and digital health co-pays now 18% of Healthcare spend",
            "Wellness and preventive care (gym, supplements) growing at 11% YoY",
            "Aging demographic driving higher per-customer spend in 55+ cohort",
        ],
        "watch_items": ["Insurance reimbursement changes could shift out-of-pocket dynamics",
                        "GLP-1 medication spend may emerge as new Healthcare sub-category"],
        "implications_for_forecast": "Healthcare consistently above budget; consider adjusting monthly default upward by 8%.",
        "approved": True,
    },
    {
        "id": "RPT-006",
        "title": "Utilities & Energy Cost Outlook H2 2025",
        "date": "2025-04",
        "category_tags": ["Utilities"],
        "source": "Synthetic Energy & Utilities Research",
        "headline": "Utility bills projected flat to -2% in H2 2025 as energy prices normalize.",
        "key_themes": [
            "Natural gas prices down 18% from 2024 peak — relief for household energy costs",
            "EV charging spend emerging as new Utilities sub-category",
            "Summer cooling costs offset by efficiency gains in newer housing stock",
        ],
        "watch_items": ["Extreme weather events could cause spike months — monitor outliers",
                        "Grid infrastructure investment may push rates higher in 2026"],
        "implications_for_forecast": "Utilities likely to come in under budget H2 2025; adjust seasonal factors downward.",
        "approved": True,
    },
]


def get_report_library(category_tag: str | None = None) -> list[dict]:
    """Return all approved reports, optionally filtered by category tag."""
    reports = [r for r in REPORT_LIBRARY if r["approved"]]
    if category_tag and category_tag != "All":
        reports = [r for r in reports if category_tag in r["category_tags"]]
    return reports
