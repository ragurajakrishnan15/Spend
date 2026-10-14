"use client";

import { useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Loadable } from "@/components/Loadable";
import { Insight } from "@/components/Insight";
import { Card, Container, DataTable, ErrorState, Kpi, Notice, PageHeader } from "@/components/ui";
import { apiPost, useApi } from "@/lib/api";
import { int, pct, signedPct, usd } from "@/lib/format";
import type { ClassifyResult, MerchantsResponse } from "@/lib/types";

function Tester() {
  const [text, setText] = useState("POS DEBIT GRNFLD MARKET #4821 BROOKLYN NY");
  const [result, setResult] = useState<ClassifyResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function run() {
    setBusy(true);
    setError(null);
    try {
      setResult(await apiPost<ClassifyResult>("/api/merchants/classify", { descriptor: text }));
    } catch (e) {
      setResult(null);
      setError(e instanceof Error ? e.message : "Request failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title="Descriptor tester" subtitle="Run any raw card descriptor through the regex rules">
      <form onSubmit={(e) => { e.preventDefault(); run(); }} className="flex flex-col gap-3 sm:flex-row">
        <label htmlFor="descriptor" className="sr-only">Raw descriptor</label>
        <input id="descriptor" value={text} onChange={(e) => setText(e.target.value)} maxLength={200}
          className="flex-1 rounded-lg border border-navy-200 px-3 py-2 font-mono text-sm focus:border-navy-500 focus:outline-none focus:ring-2 focus:ring-navy-200" />
        <button type="submit" disabled={busy || !text.trim()}
          className="rounded-lg bg-navy-900 px-5 py-2 text-sm font-semibold text-white hover:bg-navy-800 disabled:opacity-50">
          {busy ? "Classifying…" : "Classify"}
        </button>
      </form>
      {error && <div className="mt-3"><ErrorState message={error} /></div>}
      {result && (
        <dl className="mt-4 grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
          <dt className="text-slate-500">Normalized</dt><dd className="font-mono text-navy-900">{result.normalized || "—"}</dd>
          <dt className="text-slate-500">Result</dt>
          <dd className={result.matched ? "font-semibold text-emerald-700" : "font-semibold text-amber-700"}>
            {result.matched ? `${result.merchant} (${result.category})` : "No rule matched — Unknown"}
          </dd>
          {result.pattern && (<><dt className="text-slate-500">Rule</dt><dd className="break-all font-mono text-xs text-navy-900">{result.pattern}</dd></>)}
        </dl>
      )}
    </Card>
  );
}

export default function MerchantsPage() {
  const state = useApi<MerchantsResponse>("/api/merchants");
  return (
    <>
      <PageHeader eyebrow="Merchant Intelligence" title="From raw descriptors to merchant forecasts"
        description="Ordered regular-expression rules clean noisy card descriptors into merchants; a pooled XGBoost model then forecasts next-month spend per merchant against naive baselines." />
      <Container className="space-y-6">
        <Loadable state={state}>
          {(d) => {
            const c = d.classification;
            const f = d.forecast;
            return (
              <>
                <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
                  <Kpi label="Rows classified" value={int(c.rows)} />
                  <Kpi label="Coverage" value={pct(c.coverage)} hint={`${int(c.matched_rows)} matched`} />
                  <Kpi label="Precision" value={c.precision === undefined ? "n/a" : pct(c.precision)} hint="vs synthetic truth" />
                  <Kpi label="Category agreement" value={c.category_agreement === undefined ? "n/a" : pct(c.category_agreement)} />
                  <Kpi label="Regex rules" value={String(c.rules)} />
                </div>
                <Tester />

                {"error" in f ? (
                  <ErrorState message={f.error} />
                ) : (
                  <>
                    <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
                      <Card title="Merchant forecast accuracy" subtitle={`WAPE over ${f.backtest_months} held-out months, ${int(f.backtest_rows)} merchant-months · lower is better`}>
                        <DataTable caption="Merchant forecast error"
                          columns={[
                            { key: "model", label: "Model", render: (v, r) => (
                              <span className="font-medium text-navy-900">{String(v)}{r.best ? <span className="ml-2 rounded bg-emerald-100 px-1.5 py-0.5 text-xs font-semibold text-emerald-800">Best</span> : null}</span>
                            ) },
                            { key: "WAPE_pct", label: "WAPE", align: "right", render: (v) => `${Number(v).toFixed(1)}%` },
                          ]}
                          rows={f.metrics as unknown as Record<string, unknown>[]} />
                        <p className="mt-3 text-sm text-slate-600">Lowest WAPE: <strong>{f.best_model}</strong>. Gaps between models can be small; treat rankings as indicative.</p>
                      </Card>
                      <Card title={`Next-month forecast (${f.next_month})`} subtitle="Top merchants by trailing-12-month spend" className="lg:col-span-2">
                        <div className="h-64 w-full" role="img" aria-label="Bar chart of forecast spend by merchant">
                          <ResponsiveContainer>
                            <BarChart data={f.table.slice(0, 10)} layout="vertical" margin={{ left: 24, right: 16 }}>
                              <CartesianGrid strokeDasharray="3 3" stroke="#dbe5f3" horizontal={false} />
                              <XAxis type="number" tickFormatter={(v) => usd(Number(v))} />
                              <YAxis type="category" dataKey="merchant" width={160} />
                              <Tooltip formatter={(v) => usd(Number(v))} />
                              <Bar dataKey="last_month_spend" name="Last month" fill="#94a3b8" radius={[0, 4, 4, 0]} />
                              <Bar dataKey="forecast_next_month" name="Forecast" fill="#1b3b69" radius={[0, 4, 4, 0]} />
                            </BarChart>
                          </ResponsiveContainer>
                        </div>
                      </Card>
                    </div>
                    <Card title="All merchants">
                      <DataTable caption="Merchant forecasts"
                        columns={[
                          { key: "merchant", label: "Merchant", render: (v) => <span className="font-medium text-navy-900">{String(v)}</span> },
                          { key: "category", label: "Category" },
                          { key: "last_month_spend", label: "Last month", align: "right", render: (v) => usd(Number(v)) },
                          { key: "forecast_next_month", label: "Forecast", align: "right", render: (v) => usd(Number(v)) },
                          { key: "change_pct", label: "Change", align: "right", render: (v) => signedPct(Number(v)) },
                          { key: "trailing_12m_spend", label: "Trailing 12m", align: "right", render: (v) => usd(Number(v)) },
                        ]}
                        rows={f.table as unknown as Record<string, unknown>[]} />
                    </Card>
                  </>
                )}

                <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                  <Card title="Rule hits" subtitle="Rows matched per merchant rule">
                    <div className="max-h-96 overflow-auto">
                      <DataTable caption="Rule hits"
                        columns={[
                          { key: "merchant", label: "Merchant" },
                          { key: "category", label: "Category" },
                          { key: "rows", label: "Rows", align: "right", render: (v) => int(Number(v)) },
                        ]}
                        rows={c.rule_hits as unknown as Record<string, unknown>[]} />
                    </div>
                  </Card>
                  <Card title="Most common unmatched descriptors" subtitle="Candidates for new or broader rules">
                    <DataTable caption="Unmatched descriptors"
                      columns={[
                        { key: "descriptor", label: "Normalized descriptor", render: (v) => <span className="font-mono text-xs">{String(v)}</span> },
                        { key: "count", label: "Rows", align: "right", render: (v) => int(Number(v)) },
                      ]}
                      rows={c.top_unmatched as unknown as Record<string, unknown>[]} />
                  </Card>
                </div>
                <Notice>
                  <ul className="list-disc space-y-1 pl-5">{d.notes.map((n) => <li key={n}>{n}</li>)}</ul>
                </Notice>
                <Insight section="merchants" context={{ coverage_pct: d.classification.coverage * 100 }} />
              </>
            );
          }}
        </Loadable>
      </Container>
    </>
  );
}
