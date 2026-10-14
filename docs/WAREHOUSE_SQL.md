# Warehouse SQL notes (Snowflake and AWS Athena)

SpendIQ runs on **DuckDB** locally. This note shows how the same logic maps to Snowflake and AWS Athena (Trino/Presto).

> **Status:** these dialect translations were written from documentation and have **not been executed** against
> a Snowflake or Athena account. Only the DuckDB versions are exercised by the test suite.
> A Parquet extract (`data/transactions.parquet`) is written on first run so the table can be loaded into either warehouse.

## Loading the Parquet extract

| Engine | Approach |
|---|---|
| Snowflake | `PUT` the file to a stage, then `COPY INTO transactions FROM @stage FILE_FORMAT = (TYPE = PARQUET) MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE;` |
| Athena | Upload to S3, then `CREATE EXTERNAL TABLE transactions (...) STORED AS PARQUET LOCATION 's3://<bucket>/spendiq/';` |
| DuckDB | `SELECT * FROM read_parquet('data/transactions.parquet')` (disabled in the app's SQL Explorer by design) |

## Function mapping used in this project

| Purpose | DuckDB (used here) | Snowflake | Athena (Trino) |
|---|---|---|---|
| Regex test | `regexp_matches(s, 'pat')` | `REGEXP_LIKE(s, 'pat')` (whole-string match - wrap pattern as `.*pat.*`) | `regexp_like(s, 'pat')` |
| Regex replace | `regexp_replace(s, 'pat', '')` | `REGEXP_REPLACE(s, 'pat', '')` | `regexp_replace(s, 'pat', '')` |
| Regex extract | `regexp_extract(s, 'pat', 1)` | `REGEXP_SUBSTR(s, 'pat', 1, 1, 'e', 1)` | `regexp_extract(s, 'pat', 1)` |
| Month bucket | `date_trunc('month', ts)` | `DATE_TRUNC('MONTH', ts)` | `date_trunc('month', ts)` |
| Month number | `month(ts)` | `MONTH(ts)` | `month(ts)` |

## Example: merchant descriptor search

DuckDB (runs in the SQL Explorer):

```sql
SELECT merchant_descriptor, merchant_clean, amount
FROM transactions
WHERE regexp_matches(upper(merchant_descriptor), 'GREEN\s?F(IE)?LD|GRNFLD')
ORDER BY timestamp DESC LIMIT 25;
```

Snowflake (untested translation):

```sql
SELECT merchant_descriptor, merchant_clean, amount
FROM transactions
WHERE REGEXP_LIKE(UPPER(merchant_descriptor), '.*(GREEN\\s?F(IE)?LD|GRNFLD).*')
ORDER BY timestamp DESC LIMIT 25;
```

Athena (untested translation):

```sql
SELECT merchant_descriptor, merchant_clean, amount
FROM transactions
WHERE regexp_like(upper(merchant_descriptor), 'GREEN\s?F(IE)?LD|GRNFLD')
ORDER BY "timestamp" DESC LIMIT 25;
```

## Example: merchant-month panel (feeds the merchant forecast)

```sql
SELECT merchant_clean,
       date_trunc('month', timestamp) AS month,
       SUM(amount) AS spend,
       COUNT(*)    AS transactions
FROM transactions
WHERE merchant_clean <> 'Unknown'
GROUP BY 1, 2
ORDER BY 1, 2;
```

This statement is portable to Snowflake and Athena unchanged apart from quoting `timestamp` in Athena.

## Operational patterns

Five patterns used for the operational analytics in this project. The DuckDB version of each is a SQL Explorer example and is **executed by the test suite**. The Snowflake and Athena versions are the same text the SQL Explorer shows in Warehouse Mode and are **not executed** against those engines. This section is generated from `SQL_EXAMPLES` / `WAREHOUSE_SQL` in `backend/main.py`.

### 1. Merchant regex search

Finds raw card descriptors that match a merchant rule. Snowflake `REGEXP_LIKE` is whole-string, so the pattern is wrapped in `.*...*`, and backslashes are doubled inside Snowflake string literals.

DuckDB (executed):

```sql
SELECT merchant_descriptor, merchant_clean, ROUND(amount, 2) AS amount FROM transactions WHERE regexp_matches(upper(merchant_descriptor), 'GREEN\s?F(IE)?LD|GRNFLD') ORDER BY timestamp DESC LIMIT 25
```

Snowflake (untested translation):

```sql
SELECT merchant_descriptor, merchant_clean, ROUND(amount, 2) AS amount
FROM transactions
WHERE REGEXP_LIKE(UPPER(merchant_descriptor), '.*(GREEN\\s?F(IE)?LD|GRNFLD).*')
ORDER BY timestamp DESC LIMIT 25
```

Athena / Trino (untested translation):

```sql
SELECT merchant_descriptor, merchant_clean, ROUND(amount, 2) AS amount
FROM transactions
WHERE regexp_like(upper(merchant_descriptor), 'GREEN\s?F(IE)?LD|GRNFLD')
ORDER BY "timestamp" DESC LIMIT 25
```

### 2. Spend by calendar quarter

Quarter-level category totals, the grain at which macro reports are usually joined to spend.

DuckDB (executed):

```sql
SELECT date_trunc('quarter', timestamp) AS quarter, category, ROUND(SUM(amount), 2) AS spend FROM transactions GROUP BY 1, 2 ORDER BY 1, 2
```

Snowflake (untested translation):

```sql
SELECT DATE_TRUNC('QUARTER', timestamp) AS quarter, category, ROUND(SUM(amount), 2) AS spend
FROM transactions GROUP BY 1, 2 ORDER BY 1, 2
```

Athena / Trino (untested translation):

```sql
SELECT date_trunc('quarter', "timestamp") AS quarter, category, ROUND(SUM(amount), 2) AS spend
FROM transactions GROUP BY 1, 2 ORDER BY 1, 2
```

### 3. Budget variance with RAG status

Mirrors `budget_variance()` in `src/analytics.py`: green = at/under budget, amber = up to 10% over, red = more than 10% over. A test asserts this SQL returns the same status as the Python code for every category-month.

DuckDB (executed):

```sql
WITH budgets(category, budget) AS (VALUES ('Groceries', 12800), ('Dining', 6500), ('Travel', 21000), ('Retail', 20000), ('Utilities', 13000), ('Entertainment', 4500), ('Health', 6200), ('Fuel', 5500)),
monthly AS (
  SELECT category, date_trunc('month', timestamp) AS month, SUM(amount) AS actual
  FROM transactions GROUP BY 1, 2
)
SELECT m.month, m.category, ROUND(m.actual, 2) AS actual, b.budget,
       ROUND((m.actual - b.budget) / b.budget * 100, 2) AS variance_pct,
       CASE WHEN m.actual <= b.budget THEN 'green'
            WHEN m.actual <= b.budget * 1.1 THEN 'amber'
            ELSE 'red' END AS rag
FROM monthly m JOIN budgets b ON b.category = m.category
ORDER BY m.month, m.category
```

Snowflake (untested translation):

```sql
WITH budgets AS (SELECT column1 AS category, column2 AS budget FROM VALUES ('Groceries', 12800), ('Dining', 6500), ('Travel', 21000), ('Retail', 20000), ('Utilities', 13000), ('Entertainment', 4500), ('Health', 6200), ('Fuel', 5500)),
monthly AS (
  SELECT category, DATE_TRUNC('MONTH', timestamp) AS month, SUM(amount) AS actual
  FROM transactions GROUP BY 1, 2
)
SELECT m.month, m.category, ROUND(m.actual, 2) AS actual, b.budget,
       ROUND((m.actual - b.budget) / b.budget * 100, 2) AS variance_pct,
       CASE WHEN m.actual <= b.budget THEN 'green'
            WHEN m.actual <= b.budget * 1.1 THEN 'amber'
            ELSE 'red' END AS rag
FROM monthly m JOIN budgets b ON b.category = m.category
ORDER BY m.month, m.category
```

Athena / Trino (untested translation):

```sql
WITH budgets(category, budget) AS (VALUES ('Groceries', 12800), ('Dining', 6500), ('Travel', 21000), ('Retail', 20000), ('Utilities', 13000), ('Entertainment', 4500), ('Health', 6200), ('Fuel', 5500)),
monthly AS (
  SELECT category, date_trunc('month', "timestamp") AS month, SUM(amount) AS actual
  FROM transactions GROUP BY 1, 2
)
SELECT m.month, m.category, ROUND(m.actual, 2) AS actual, b.budget,
       ROUND((m.actual - b.budget) / b.budget * 100, 2) AS variance_pct,
       CASE WHEN m.actual <= b.budget THEN 'green'
            WHEN m.actual <= b.budget * 1.1 THEN 'amber'
            ELSE 'red' END AS rag
FROM monthly m JOIN budgets b ON b.category = m.category
ORDER BY m.month, m.category
```

### 4. Operations volume by channel

Monthly transaction count and average ticket per channel, the input to the operations forecast.

DuckDB (executed):

```sql
SELECT date_trunc('month', timestamp) AS month, channel, COUNT(*) AS transactions, ROUND(AVG(amount), 2) AS avg_ticket FROM transactions GROUP BY 1, 2 ORDER BY 1, 2
```

Snowflake (untested translation):

```sql
SELECT DATE_TRUNC('MONTH', timestamp) AS month, channel, COUNT(*) AS transactions, ROUND(AVG(amount), 2) AS avg_ticket
FROM transactions GROUP BY 1, 2 ORDER BY 1, 2
```

Athena / Trino (untested translation):

```sql
SELECT date_trunc('month', "timestamp") AS month, channel, COUNT(*) AS transactions, ROUND(AVG(amount), 2) AS avg_ticket
FROM transactions GROUP BY 1, 2 ORDER BY 1, 2
```

### 5. Campaign response by exposure

Response rate for exposed vs. unexposed transactions per category. Descriptive only, not a causal lift estimate.

Identical on DuckDB, Snowflake and Athena:

```sql
SELECT category, campaign_exposed, COUNT(*) AS transactions, ROUND(AVG(campaign_response) * 100, 2) AS response_rate_pct FROM transactions GROUP BY 1, 2 ORDER BY 1, 2
```
