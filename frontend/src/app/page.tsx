import Link from "next/link";
import { LiveStats } from "@/components/LiveStats";

const FEATURES = [
  { href: "/dashboard", title: "Executive Dashboard", text: "Volume, customers, category and channel mix with month-over-month movement at a glance." },
  { href: "/transactions", title: "Transaction Analytics", text: "Filter by category, channel, region and date. Distributions, weekday patterns and a pageable ledger." },
  { href: "/forecasts", title: "Spending Forecasts", text: "Random forest, XGBoost, Holt-Winters ETS and ARIMA benchmarked against last-month and seasonal-naive baselines in a rolling backtest." },
  { href: "/merchants", title: "Merchant Intelligence", text: "Regex rules clean raw card descriptors into merchants, with measured coverage and merchant-level spend forecasts." },
  { href: "/segments", title: "Customer Segmentation", text: "Log-scaled RFM with KMeans, summarised by descriptive behavioural segments." },
  { href: "/campaigns", title: "Campaign Analytics", text: "Chronological, leakage-aware response model with ROC-AUC, lift deciles and permutation importance." },
  { href: "/ops-forecast", title: "Operations Forecasting", text: "Transaction volume and average ticket size forecast per channel, benchmarked against a last-month baseline." },
  { href: "/budget", title: "Budget Management", text: "Actual spend against category budgets with red / amber / green variance status for every month." },
  { href: "/macro", title: "Macro Intelligence", text: "Synthetic CPI, sentiment and GDP indicators turned into themes, watch items and a report library." },
  { href: "/sql", title: "SQL Explorer", text: "Read-only DuckDB queries (including regex functions) behind a parsed single-SELECT guard, with Snowflake and Athena dialect equivalents alongside." },
  { href: "/dashboard", title: "Stakeholder exports", text: "One-click Excel workbook with live lookup formulas and a PowerPoint briefing built from the same numbers." },
];

export default function Home() {
  return (
    <>
      <section className="bg-gradient-to-br from-navy-950 via-navy-900 to-navy-700 text-white">
        <div className="mx-auto max-w-7xl px-4 py-20 sm:px-6 sm:py-28 lg:px-8">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-navy-200">Synthetic data · Educational demonstration</p>
          <h1 className="mt-4 max-w-3xl font-serif text-4xl font-semibold leading-tight sm:text-6xl">
            Clear answers from banking transaction data.
          </h1>
          <p className="mt-6 max-w-2xl text-lg leading-relaxed text-navy-100">
            SpendIQ brings transaction analytics, honest forecast benchmarking, customer segmentation and campaign modelling
            into one workspace — built on a reproducible three-year synthetic dataset.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link href="/dashboard" className="rounded-lg bg-white px-5 py-3 text-sm font-semibold text-navy-900 hover:bg-navy-50">
              Open the dashboard
            </Link>
            <Link href="/governance" className="rounded-lg border border-navy-300 px-5 py-3 text-sm font-semibold text-white hover:bg-white/10">
              Model governance
            </Link>
          </div>
          <LiveStats />
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8">
        <h2 className="font-serif text-3xl font-semibold text-navy-900">What is inside</h2>
        <div className="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f) => (
            <Link key={f.href} href={f.href}
              className="group rounded-xl border border-navy-100 bg-white p-6 shadow-sm transition hover:-translate-y-0.5 hover:border-navy-300 hover:shadow-md">
              <h3 className="text-lg font-semibold text-navy-900">{f.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-slate-600">{f.text}</p>
              <p className="mt-4 text-sm font-semibold text-navy-600 group-hover:text-navy-900">Open →</p>
            </Link>
          ))}
        </div>
      </section>

      <section className="border-t border-navy-100 bg-white">
        <div className="mx-auto grid max-w-7xl gap-8 px-4 py-14 sm:px-6 md:grid-cols-3 lg:px-8">
          {[
            ["Reproducible", "A seeded generator builds 36 months of transactions with calendar seasonality and trend, validated on every load."],
            ["Honest evaluation", "Chronological splits, rolling-origin backtests and explicit naive baselines. Numbers are computed live — never hard-coded."],
            ["Responsible by design", "Clear limitations, out-of-scope uses and no claim of regulatory compliance. Not for decisions about real people."],
          ].map(([t, d]) => (
            <div key={t}>
              <h3 className="text-base font-semibold text-navy-900">{t}</h3>
              <p className="mt-2 text-sm leading-relaxed text-slate-600">{d}</p>
            </div>
          ))}
        </div>
      </section>
    </>
  );
}
