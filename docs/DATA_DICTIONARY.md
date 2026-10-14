# Data Dictionary

All records are synthetically generated for demonstration and do not represent actual people or financial activity.

| Field | Type | Description |
|---|---|---|
| transaction_id | string | Synthetic unique transaction identifier |
| customer_id | string | Synthetic customer key |
| timestamp | datetime | Synthetic transaction time |
| amount | float | Positive transaction amount in USD-like demo units |
| category | string | Synthetic merchant category |
| channel | string | Card-present, e-commerce, or mobile wallet |
| region | string | Broad synthetic region |
| campaign_exposed | integer | Whether synthetic campaign exposure occurred (0/1) |
| campaign_response | integer | Synthetic response label (0/1) |

The generator (`src/data.py`) uses a fixed seed (42) and produces 36 months (2023-01 to 2025-12), 36,000 transactions and 1,000 customers by default. It builds in calendar seasonality (December peak; summer travel/fuel; winter utilities), a ~0.8%/month volume trend, ~0.2%/month ticket inflation, heterogeneous customer activity and a latent customer response propensity. Values exist only to demonstrate analytics. Cached files `data/transactions.csv` and `data/spendiq.duckdb` are rebuilt when `DATA_VERSION` changes.

## Merchant fields (added in data version 3)

| Field | Type | Description |
|---|---|---|
| merchant_descriptor | string | Raw, noisy card-statement text (prefixes, store numbers, abbreviations, locations). Fictional merchants only. |
| true_merchant | string | Generator ground truth. Used **only** to evaluate the regex rules; real data would not have it. |
| merchant_clean | string | Derived at load time by the ordered regex rules in `src/merchants.py`; `Unknown` when no rule matches. Present in DuckDB and the API, not in the raw CSV. |
| category_clean | string | Category implied by the matched rule (`Unknown` when unmatched). |

About 7% of descriptors are deliberately garbled so coverage is below 100%.
