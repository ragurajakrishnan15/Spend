# SpendIQ — Banking Customer Intelligence & Spending Forecasting

SpendIQ is a portfolio project demonstrating transaction analytics, spending forecasts,
customer segmentation, campaign-response modelling, SQL analytics, and lightweight model
governance using **synthetic data only**.

> This is an educational demonstration. It is an independent project, not affiliated with any
> bank, does not use real customer data, and does not claim compliance with any regulation or
> internal policy.

## Architecture

```
src/                 Python analytics (pandas, DuckDB, scikit-learn) – shared by every UI
  data.py            36-month seeded synthetic generator, validation, cached CSV/DuckDB
  analytics.py       aggregates, RFM, forecast backtest, campaign model
  sql_safety.py      the single read-only SQL execution path
backend/main.py      FastAPI JSON API (/api/*) reusing src/
frontend/            Next.js + React + TypeScript + Tailwind website (calls the API via /api proxy)
app.py               original Streamlit demo (kept, still works)
tests/               pytest suite (analytics, SQL security, API)
docs/                model card, data dictionary, governance notes
```

## Setup (Windows PowerShell, once)

```powershell
cd D:\SpendIQ\SpendIQ
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-dev.txt

cd frontend
npm install
cd ..
```

## Run the website (two terminals)

**Terminal 1 — backend (FastAPI, port 8000)**

```powershell
cd D:\SpendIQ\SpendIQ
.\.venv\Scripts\Activate.ps1
python -m uvicorn backend.main:app --reload --port 8000
```

**Terminal 2 — frontend (Next.js, port 3000)**

```powershell
cd D:\SpendIQ\SpendIQ\frontend
npm run dev
```

Open <http://localhost:3000>. API docs are at <http://localhost:8000/docs>.
The frontend proxies `/api/*` to `http://127.0.0.1:8000`; set `BACKEND_URL` before `npm run dev` / `npm run build`
to point elsewhere. The first backend start generates the synthetic dataset under `data/` (a few seconds).

> The first `npm run build` downloads Google Fonts (Inter, Source Serif), so it needs internet access.

### Production build of the frontend

```powershell
cd D:\SpendIQ\SpendIQ\frontend
npm run build
npm run start
```

## Verify

```powershell
cd D:\SpendIQ\SpendIQ
.\.venv\Scripts\Activate.ps1
python -m pytest -q

cd frontend
npm run lint
npm run typecheck
npm run build
```

## Legacy Streamlit version

```powershell
cd D:\SpendIQ\SpendIQ
.\.venv\Scripts\Activate.ps1
python -m streamlit run app.py
```

## What the analytics do

- **Data** – 36 months (2023-01 to 2025-12), 36,000 transactions, 1,000 customers. Calendar seasonality
  (December/holiday peak, summer travel, winter utilities…) and a ~0.8 %/month trend are generated from a fixed seed.
- **Forecast** – random forest, **XGBoost**, **Holt-Winters ETS** and **ARIMA** compared with **last-month** and
  **seasonal-naive (t-12)** baselines in a **rolling-origin backtest** over the final 12 months. The UI shows the
  lowest-MAE model (it can be a baseline) and lets you view any model's forecast.
- **Merchant intelligence** – ordered **regex rules** clean noisy synthetic card descriptors into fictional merchants
  (coverage/precision reported; ~7% deliberately unmatched), then a pooled XGBoost model forecasts **spend per merchant**.
- **Exports** – Excel workbook (live SUM/AVERAGE/INDEX-MATCH/VLOOKUP/RANK formulas, dropdown lookup, chart) and a
  9-slide PowerPoint briefing with native charts, from the Dashboard or `/api/export/excel|pptx`.
- **Warehouse notes** – `data/transactions.parquet` is written for loading elsewhere; `docs/WAREHOUSE_SQL.md` maps
  the SQL to Snowflake and Athena (translations are **not executed** against those engines).
- **Campaign model** – features: category, channel, region, amount, exposure, calendar and customer history
  computed from *earlier* transactions only. Chronological 80/20 split; metrics, lift deciles and permutation importance.
  This is a *transaction-level synthetic demonstration* (customers appear in both periods; no causal claim).
- **Segmentation** – log-scaled RFM + KMeans, with descriptive segment names.
- **SQL Explorer** – one shared function (`src/sql_safety.py`): DuckDB-parsed single `SELECT`, read-only database,
  `enable_external_access=false` (no local-file or URL reads), locked configuration, row cap. Used by both the API and Streamlit.
  **Warehouse Mode** shows hand-written Snowflake and Athena equivalents next to each example (not executed against those engines).
- **Operations forecast** (`/ops-forecast`) – monthly transaction volume and average ticket per channel, XGBoost lag-ratio
  model vs. a last-month baseline in a rolling-origin backtest.
- **Budget management** (`/budget`) – actual vs. synthetic category budgets with red / amber / green status. The same
  logic exists as SQL (`Budget variance with RAG status`) and a test asserts both agree for every category-month.
- **Macro intelligence** (`/macro`) – synthetic CPI, sentiment, GDP and retail-sales indicators turned into themes and
  watch items, plus a six-report library with forecast implications. All synthetic.
- **Insight cards** – collapsible plain-English summaries per page from `/api/narrative/{section}`. Uses Gemini when
  `GEMINI_API_KEY` is set (and `google-generativeai` installed); otherwise data-driven template text.

## Deploy (frontend on Vercel, backend on Render or Railway)

1. Push the repository to GitHub.
2. **Backend** – create a web service from the repo root. `render.yaml` and `railway.toml` hold the build/start commands
   (`pip install -r requirements.txt`, `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`, health check `/api/health`).
   The first start generates the dataset, so allow a minute for the health check.
3. **Frontend** – import the `frontend/` directory into Vercel and set `BACKEND_URL` to the backend's public URL.
   `BACKEND_URL` is read when Next.js is **built** (it feeds `rewrites()` in `next.config.ts`), so redeploy after changing it.
   The browser only talks to the frontend origin, so CORS is not involved; `CORS_ORIGINS` exists for direct API access.
4. Check `<backend>/api/health` returns `{"status":"ok", ...}`, then open the Vercel URL.

See `.env.example` for all variables.

## Responsible-use notes

- Campaign response scores are for demonstration and must not be used to make decisions about access to financial services.
- Correlation or predictive performance does not establish causality.
- Synthetic-data results are not evidence of real-world model performance; patterns such as seasonality are built into the generator.
- Governance materials are educational examples, not a legal or regulatory compliance certification.

## Skill map (consumer-banking data science)

| Capability | Where it lives | Status |
|---|---|---|
| SQL extraction and analysis | SQL Explorer, 12 DuckDB examples, `src/sql_safety.py` | Executed and tested |
| Snowflake / Athena dialects | Warehouse Mode, `docs/WAREHOUSE_SQL.md` | Translations written, **not executed** on those engines |
| Regex rules over transaction text | `src/merchants.py`, regex SQL examples | Executed and tested, coverage reported |
| Python analytics and ML | `src/analytics.py` (pandas, scikit-learn, XGBoost, statsmodels) | Executed and tested |
| Spend and sales forecasting | `/forecasts`, rolling-origin backtest vs. naive baselines | Executed and tested |
| Operations forecasting | `/ops-forecast` | Executed and tested |
| Merchant-level spend prediction | `/merchants` | Executed and tested |
| Budget variance management | `/budget`, budget SQL example | Executed; SQL and Python cross-checked |
| Campaign response and targeting | `/campaigns`, chronological split, lift deciles | Executed and tested |
| Macro / industry report review | `/macro`, report library, watch items | Synthetic content |
| Stakeholder communication | Insight cards, Excel (live formulas) and PowerPoint exports | Executed and tested |
| Model validation and governance | `/governance`, `docs/MODEL_CARD.md` | Educational, not a compliance claim |
