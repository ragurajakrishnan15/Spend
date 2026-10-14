"""AI narrative summary generator for SpendIQ.

Generates 2-3 sentence plain-English summaries of each dashboard section to help
non-technical stakeholders understand findings — mapping to the JD requirement:
'crafting data stories and presentations of findings to stakeholders.'

Uses the Gemini API when GEMINI_API_KEY is set; falls back to data-driven
template strings that work without any API key.
"""
from __future__ import annotations

import os
from typing import Any


_GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")


def _template_summary(section: str, ctx: dict[str, Any]) -> str:
    """Data-driven fallback narrative — no API required."""
    if section == "overview":
        total = ctx.get("total_spend", 0)
        txns = ctx.get("transactions", 0)
        mom = ctx.get("mom_change_pct")
        mom_str = f"Month-over-month spend {'increased' if (mom or 0) > 0 else 'decreased'} {abs(mom or 0):.1f}%. " if mom is not None else ""
        return (f"Total synthetic customer spend reached ${total:,.0f} across {txns:,} transactions. "
                f"{mom_str}"
                "Top categories and regional breakdowns are shown below.")

    if section == "forecast":
        model = ctx.get("best_model", "the selected model")
        mae = ctx.get("mae")
        mae_str = f" with a backtest MAE of ${mae:,.0f}" if mae else ""
        return (f"The spending forecast is produced by {model}{mae_str}. "
                "A rolling-origin backtest — where every prediction uses only earlier months — "
                "provides an unbiased view of model accuracy before deployment.")

    if section == "segments":
        n = ctx.get("total_customers", 0)
        top = ctx.get("top_segment", "High-spend active")
        return (f"Customer base of {n:,} is segmented into four behavioral groups using log-scaled RFM and KMeans clustering. "
                f"The '{top}' segment drives the largest share of total spend and should be the primary retention focus. "
                "Lapsing customers represent the highest re-engagement opportunity.")

    if section == "campaign":
        auc = ctx.get("roc_auc", 0)
        return (f"The campaign response model achieves a ROC-AUC of {auc:.2f} on a held-out chronological test set. "
                "Top-decile customers are significantly more likely to respond, enabling targeted outreach "
                "that improves ROI compared to mass campaigns. Feature importance highlights transaction history "
                "and channel as the strongest response predictors.")

    if section == "ops":
        return ("Operations forecasting tracks transaction volume and average ticket size per channel month-over-month. "
                "XGBoost lag-ratio models are benchmarked against last-month naive baselines using rolling-origin backtests. "
                "These KPIs drive staffing, fraud monitoring, and infrastructure planning decisions.")

    if section == "budget":
        over = ctx.get("categories_over_budget", 0)
        total_cat = ctx.get("total_categories", 0)
        return (f"{over} of {total_cat} categories exceeded their monthly budget target at least once. "
                "Red flags indicate spending more than 10% above budget and warrant immediate review. "
                "Amber flags (0-10% over) should be monitored in the following month's planning cycle.")

    if section == "macro":
        cpi = ctx.get("cpi_yoy", 0)
        sentiment = ctx.get("consumer_sentiment", 0)
        return (f"Current macro backdrop: CPI at {cpi:.1f}% YoY with consumer sentiment at {sentiment:.0f}. "
                "Watch items highlight categories most exposed to macro headwinds or tailwinds. "
                "The report library provides approved reference materials for planning and forecast context.")

    if section == "merchants":
        coverage = ctx.get("coverage_pct", 0)
        return (f"Merchant intelligence classifies {coverage:.0f}% of transaction descriptors using ordered regex rules. "
                "Unmatched descriptors (~7%) are flagged as Unknown and excluded from merchant-level forecasts. "
                "The pooled XGBoost model forecasts next-month spend per merchant using seasonal and lag features.")

    return "No narrative available for this section."


def _gemini_summary(section: str, ctx: dict[str, Any]) -> str:
    """Call Gemini API to generate a dynamic narrative. Falls back to template on error."""
    try:
        import google.generativeai as genai  # type: ignore
        genai.configure(api_key=_GEMINI_KEY)
        model = genai.GenerativeModel("gemini-1.5-flash")
        prompt = (
            f"You are a senior data scientist presenting analysis to non-technical banking executives. "
            f"Write a 2-3 sentence plain-English insight for the '{section}' section of a consumer spending analytics dashboard. "
            f"Context data: {ctx}. "
            f"Be specific with numbers, avoid jargon, and end with one actionable recommendation. "
            f"Do not use bullet points."
        )
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception:
        return _template_summary(section, ctx)


def generate_summary(section: str, context: dict[str, Any] | None = None) -> str:
    """Generate a plain-English narrative summary for a dashboard section.

    If GEMINI_API_KEY is set, uses Gemini 1.5 Flash.
    Otherwise falls back gracefully to data-driven templates.

    Args:
        section: one of 'overview', 'forecast', 'segments', 'campaign',
                         'ops', 'budget', 'macro', 'merchants'
        context: dict of key metrics to include in the narrative
    """
    ctx = context or {}
    if _GEMINI_KEY:
        return _gemini_summary(section, ctx)
    return _template_summary(section, ctx)
