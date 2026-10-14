from pathlib import Path
import sys
import streamlit as st
import pandas as pd
import plotly.express as px

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.data import load_or_create_data
from src.analytics import monthly_spend, category_spend, customer_rfm, run_campaign_model, forecast_monthly_spend, run_sql
from src.data import DB_PATH

st.set_page_config(page_title="SpendIQ", page_icon="📊", layout="wide")
st.markdown("""
<style>
.block-container {padding-top: 1.6rem; padding-bottom: 2rem;}
[data-testid="stMetric"] {background: #f4f7fb; padding: 14px 16px; border-radius: 12px;}
</style>
""", unsafe_allow_html=True)

@st.cache_data
def get_data():
    return load_or_create_data()

df = get_data()
st.sidebar.title("SpendIQ")
st.sidebar.caption("Synthetic banking analytics")
page = st.sidebar.radio("Navigate", [
    "Executive Overview", "Transaction Analytics", "Spending Forecasts",
    "Customer Segmentation", "Campaign Analytics", "SQL Explorer", "Model Governance"
])

st.title("SpendIQ")
st.caption("Banking Customer Intelligence & Spending Forecasting | Portfolio demonstration")
st.info("All data is synthetic and reproducible. This is not a JPMorgan Chase product or a production banking model.")

if page == "Executive Overview":
    st.header("Executive overview")
    total_spend = df["amount"].sum()
    customers = df["customer_id"].nunique()
    tx_count = len(df)
    avg_tx = df["amount"].mean()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total transaction volume", f"${total_spend:,.0f}")
    c2.metric("Transactions", f"{tx_count:,}")
    c3.metric("Customers", f"{customers:,}")
    c4.metric("Average transaction", f"${avg_tx:,.2f}")
    monthly = monthly_spend(df)
    cat = category_spend(df)
    left, right = st.columns(2)
    with left:
        st.subheader("Monthly spend")
        st.plotly_chart(px.line(monthly, x="month", y="spend", markers=True, title="Monthly transaction spend"), use_container_width=True)
    with right:
        st.subheader("Spend by merchant category")
        st.plotly_chart(px.bar(cat, x="category", y="spend", title="Total spend by category"), use_container_width=True)
    st.subheader("Recent synthetic transactions")
    st.dataframe(df.sort_values("timestamp", ascending=False).head(12), use_container_width=True)

elif page == "Transaction Analytics":
    st.header("Transaction analytics")
    categories = ["All"] + sorted(df["category"].unique().tolist())
    selected = st.selectbox("Merchant category", categories)
    filtered = df if selected == "All" else df[df["category"] == selected]
    daily = filtered.assign(date=filtered["timestamp"].dt.date).groupby("date", as_index=False)["amount"].sum()
    a, b, c = st.columns(3)
    a.metric("Transactions", f"{len(filtered):,}")
    b.metric("Spend", f"${filtered['amount'].sum():,.0f}")
    c.metric("Median transaction", f"${filtered['amount'].median():,.2f}")
    st.plotly_chart(px.line(daily, x="date", y="amount", title="Daily spend"), use_container_width=True)
    st.plotly_chart(px.histogram(filtered, x="amount", nbins=40, title="Transaction amount distribution"), use_container_width=True)
    st.dataframe(filtered.head(1000), use_container_width=True)

elif page == "Spending Forecasts":
    st.header("Monthly spending forecast")
    monthly = monthly_spend(df)
    result = forecast_monthly_spend(monthly, horizon=3)
    st.markdown("Forecasts are illustrative and trained on aggregated synthetic transaction history.")
    st.plotly_chart(px.line(result["plot_data"], x="month", y="spend", color="series", markers=True,
                            title="Historical spend and next three-month forecast"), use_container_width=True)
    if result.get("metrics"):
        st.subheader("Rolling-origin backtest")
        st.write(f"One-step-ahead predictions for the final {result['holdout_months']} months; each prediction uses only earlier months. Lower is better.")
        st.dataframe(pd.DataFrame(result["metrics"]), use_container_width=True)
    st.subheader("Forecast values")
    st.dataframe(result["future"], use_container_width=True)
    st.caption("A simple baseline is included. Synthetic data and a short history limit the conclusions that can be drawn.")

elif page == "Customer Segmentation":
    st.header("RFM customer segmentation")
    segments = customer_rfm(df)
    if segments.empty:
        st.warning("Not enough data to create segments.")
    else:
        st.plotly_chart(px.scatter(segments, x="frequency", y="monetary", color="segment",
                                   size="monetary", hover_data=["customer_id", "recency_days"],
                                   title="Customer segments: frequency vs. spend"), use_container_width=True)
        st.dataframe(segments.groupby("segment", as_index=False).agg(
            customers=("customer_id", "count"),
            avg_recency_days=("recency_days", "mean"),
            avg_transactions=("frequency", "mean"),
            avg_spend=("monetary", "mean")
        ).round(2), use_container_width=True)
        st.dataframe(segments.head(500), use_container_width=True)
    st.caption("Segments summarize synthetic observed behavior; they are not customer value judgments.")

elif page == "Campaign Analytics":
    st.header("Campaign response modeling")
    result = run_campaign_model(df)
    if result.get("error"):
        st.warning(result["error"])
    else:
        metrics = result["metrics"]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Precision", f"{metrics['precision']:.3f}")
        c2.metric("Recall", f"{metrics['recall']:.3f}")
        c3.metric("F1", f"{metrics['f1']:.3f}")
        c4.metric("ROC-AUC", f"{metrics['roc_auc']:.3f}" if pd.notna(metrics["roc_auc"]) else "N/A")
        st.plotly_chart(px.bar(result["importance"], x="feature", y="importance", title="Permutation importance (test-set ROC-AUC drop)"), use_container_width=True)
        st.subheader("Confusion matrix")
        st.dataframe(pd.DataFrame(result["confusion"], index=["Actual no response", "Actual response"],
                                  columns=["Predicted no response", "Predicted response"]), use_container_width=True)
        st.caption("Predictive association is not causal evidence. Campaign response scores must not be used for credit, eligibility, or access decisions.")

elif page == "SQL Explorer":
    st.header("SQL Explorer")
    st.write("Run read-only SQL against the synthetic `transactions` table using DuckDB.")
    examples = {
        "Monthly spend": "SELECT date_trunc('month', timestamp) AS month, ROUND(SUM(amount), 2) AS spend FROM transactions GROUP BY 1 ORDER BY 1",
        "Top categories": "SELECT category, COUNT(*) AS transactions, ROUND(SUM(amount), 2) AS spend FROM transactions GROUP BY category ORDER BY spend DESC",
        "Top customers": "SELECT customer_id, COUNT(*) AS transactions, ROUND(SUM(amount), 2) AS spend FROM transactions GROUP BY customer_id ORDER BY spend DESC LIMIT 20",
        "Channel mix": "SELECT channel, COUNT(*) AS transactions, ROUND(AVG(amount), 2) AS avg_amount FROM transactions GROUP BY channel ORDER BY transactions DESC",
    }
    choice = st.selectbox("Example query", list(examples))
    query = st.text_area("SQL (read-only SELECT/WITH only)", value=examples[choice], height=130)
    if st.button("Run query"):
        try:
            out = run_sql(query, DB_PATH)
            if out.attrs.get("truncated"):
                st.caption("Result truncated to the first 1,000 rows.")
            st.dataframe(out, use_container_width=True)
        except Exception as e:
            st.error(f"Query rejected or failed: {e}")

elif page == "Model Governance":
    st.header("Model governance & responsible use")
    st.subheader("Data provenance")
    st.write("- Dataset: synthetic, generated locally with a fixed random seed.")
    st.write("- No real customer records, external API calls, or cloud storage.")
    st.write("- Generated data is for portfolio demonstration only.")
    st.subheader("Model controls demonstrated")
    st.write("- Chronological holdout for forecast evaluation.")
    st.write("- Campaign model uses a chronological split with prior-only customer history features and reports multiple metrics.")
    st.write("- Single shared read-only SQL path: parsed single SELECT, DuckDB external file access disabled.")
    st.write("- Model limitations and use restrictions are documented.")
    st.subheader("Important limitations")
    st.write("- Synthetic results do not establish production performance.")
    st.write("- Feature importance is not causal explanation.")
    st.write("- Fairness checks and drift monitoring are not comprehensive in this starter version.")
    st.write("- Human review is required before any real-world use.")
    st.warning("This project does not claim compliance with JPMorgan Chase internal policies or any specific regulation.")

st.sidebar.divider()
st.sidebar.caption("SpendIQ • Local demo • Synthetic data only")
