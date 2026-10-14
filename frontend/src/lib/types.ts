export interface Meta {
  categories: string[];
  channels: string[];
  regions: string[];
  start: string;
  end: string;
  rows: number;
  customers: number;
  months: number;
}

export interface Overview {
  empty: boolean;
  kpis: {
    total_spend: number;
    transactions: number;
    customers: number;
    avg_transaction: number;
    latest_month: string;
    latest_month_spend: number;
    mom_change_pct: number | null;
    campaign_response_rate: number;
  } | null;
  monthly: { month: string; spend: number }[];
  categories: { category: string; spend: number }[];
  channels: { channel: string; transactions: number; spend: number }[];
  regions: { region: string; transactions: number; spend: number }[];
}

export interface TransactionRow {
  transaction_id: string;
  customer_id: string;
  timestamp: string;
  amount: number;
  category: string;
  channel: string;
  region: string;
  campaign_exposed: number;
  campaign_response: number;
  merchant_descriptor: string;
  merchant_clean: string;
}

export interface TransactionsResponse {
  empty: boolean;
  summary: { transactions: number; spend: number; mean: number; median: number; p95: number; max: number } | null;
  monthly: { month: string; spend: number }[];
  daily: { date: string; spend: number; transactions: number }[];
  weekday: { day: string; spend: number; transactions: number }[];
  histogram: { bin_start: number; bin_end: number; count: number }[];
  histogram_note?: string;
  table: TransactionRow[];
  total_rows: number;
}

export interface ForecastMetric {
  key: string;
  model: string;
  MAE: number;
  RMSE: number;
  MAPE_pct: number;
  best: boolean;
}

export interface ForecastResponse {
  method: string;
  seasonal: boolean;
  holdout_months: number;
  best_model: string | null;
  history: { month: string; spend: number }[];
  future: { month: string; forecast: number; lower?: number; upper?: number }[];
  metrics: ForecastMetric[];
  selected_model_key: string | null;
  future_by_model: Record<string, number[]>;
  backtest: {
    month: string;
    actual: number;
    model: number;
    xgboost: number | null;
    ets: number | null;
    arima: number | null;
    last_month: number;
    seasonal_naive: number | null;
  }[];
  notes: string[];
}

export interface SegmentsResponse {
  empty: boolean;
  summary: {
    segment: string;
    customers: number;
    avg_recency_days: number;
    avg_transactions: number;
    avg_spend: number;
    total_spend: number;
  }[];
  points: { customer_id: string; frequency: number; monetary: number; recency_days: number; segment: string }[];
  total_customers: number;
  note?: string;
}

export interface CampaignResponse {
  error?: string;
  metrics: { precision: number; recall: number; f1: number; roc_auc: number };
  baseline: { roc_auc_exposure_only: number; roc_auc_no_skill: number };
  importance: { feature: string; importance: number }[];
  lift: { decile: number; customers: number; response_rate: number; avg_score: number }[];
  confusion: { tn: number; fp: number; fn: number; tp: number };
  split: Record<string, string | number>;
  features: string[];
  notes: string[];
}

export interface SqlExamples {
  examples: { name: string; query: string; snowflake: string; athena: string }[];
  max_rows: number;
  schema: { column: string; type: string }[];
}

export interface SqlResult {
  columns: string[];
  rows: (string | number | null)[][];
  row_count: number;
  truncated: boolean;
}

export interface Governance {
  provenance: { source: string; rows: number; customers: number; period: string; data_version: number };
  evaluation: { forecast_holdout_months: number; forecast_best_model: string | null; campaign_test_rows: number | null };
  controls: string[];
  limitations: string[];
  out_of_scope: string[];
  disclaimer: string;
}

export interface Filters {
  category: string;
  channel: string;
  region: string;
  start: string;
  end: string;
}

export interface MerchantsResponse {
  classification: {
    rows: number;
    matched_rows: number;
    coverage: number;
    rules: number;
    precision?: number;
    recall?: number;
    category_agreement?: number;
    top_unmatched: { descriptor: string; count: number }[];
    rule_hits: { merchant: string; rows: number; category: string; pattern: string }[];
  };
  forecast:
    | { error: string }
    | {
        metrics: { model: string; WAPE_pct: number; best: boolean }[];
        best_model: string;
        next_month: string;
        backtest_months: number;
        backtest_rows: number;
        table: {
          merchant: string;
          category: string;
          last_month_spend: number;
          forecast_next_month: number;
          change_pct: number;
          trailing_12m_spend: number;
        }[];
      };
  notes: string[];
}

export interface ClassifyResult {
  descriptor: string;
  normalized: string;
  matched: boolean;
  merchant: string;
  category: string;
  pattern: string | null;
}

// ---- operations forecast, budget, macro, narrative
export interface OpsSeries {
  channel: string;
  history: { month: string; value: number }[];
  future: { month: string; value: number }[];
  xgb_mae: number;
  naive_mae: number;
  best_model: string;
}

export interface OpsForecast {
  transaction_count: OpsSeries[];
  avg_ticket: OpsSeries[];
  channels: string[];
  horizon: number;
  aggregate_metrics: { kpi: string; avg_xgb_mae: number }[];
  notes: string[];
}

export type Rag = "green" | "amber" | "red";

export interface BudgetResponse {
  detail: {
    category: string; month: string; actual: number; budget: number;
    variance: number; variance_pct: number; rag: Rag;
  }[];
  summary: {
    category: string; total_actual: number; total_budget: number; total_variance: number;
    months_over_budget: number; overall_variance_pct: number;
  }[];
  budgets: Record<string, number>;
  categories: string[];
  notes: string[];
}

export interface MacroIndicators {
  cpi_yoy: number;
  cpi_mom_change: number | null;
  consumer_sentiment: number;
  gdp_growth: number;
  retail_sales_growth: number;
}

export interface MacroResponse {
  context: {
    month: string;
    indicators: MacroIndicators;
    themes: string[];
    watch_items: { category: string; signal: string; severity: Rag }[];
    summary: string;
  };
  indicators: {
    month: string; cpi_yoy: number; consumer_sentiment: number; gdp_growth: number; retail_sales_growth: number;
  }[];
  notes: string[];
}

export interface MacroReport {
  id: string;
  title: string;
  date: string;
  category_tags: string[];
  source: string;
  headline: string;
  key_themes: string[];
  watch_items: string[];
  implications_for_forecast: string;
}

export interface ReportLibrary {
  reports: MacroReport[];
  total: number;
}

export interface NarrativeResponse {
  section: string;
  summary: string;
}
