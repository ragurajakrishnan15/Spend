"use client";

import { useState } from "react";
import { Area, CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { DEFAULT_FILTERS, FilterBar } from "@/components/FilterBar";
import { Insight } from "@/components/Insight";
import { Loadable } from "@/components/Loadable";
import { Card, Container, DataTable, Notice, PageHeader } from "@/components/ui";
import { filterQuery, useApi } from "@/lib/api";
import { compactUsd, monthLabel, usd } from "@/lib/format";
import type { Filters, ForecastResponse } from "@/lib/types";

export default function ForecastsPage() {
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS);
  const [horizon, setHorizon] = useState(6);
  const [view, setView] = useState("best");
  const state = useApi<ForecastResponse>(`/api/forecast${filterQuery(filters, { horizon })}`);

  return (
    <>
      <PageHeader eyebrow="Spending Forecasts" title="Forecasts, benchmarked honestly"
        description="Random forest, XGBoost, Holt-Winters ETS and ARIMA are compared with last-month and seasonal-naive baselines in a rolling-origin backtest — each prediction uses only earlier months." />
      <Container className="space-y-6">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end">
          <div className="flex-1">
            <FilterBar filters={filters} onChange={setFilters} show={["category", "channel", "region"]} />
          </div>
          <label className="flex flex-col gap-1 rounded-xl border border-navy-100 bg-white p-4 text-xs font-semibold uppercase tracking-wide text-slate-500 shadow-sm">
            Horizon
            <select value={horizon} onChange={(e) => setHorizon(Number(e.target.value))}
              className="rounded-lg border border-navy-200 bg-white px-3 py-2 text-sm font-normal normal-case tracking-normal text-navy-900">
              {[1, 3, 6, 9, 12].map((h) => <option key={h} value={h}>{h} month{h > 1 ? "s" : ""}</option>)}
            </select>
          </label>
        </div>

        <Loadable state={state}>
          {(d) => {
            const hist = d.history.map((h) => ({ month: h.month, actual: h.spend }));
            const bestLabel = d.metrics.find((m) => m.best)?.model;
            const alt = view !== "best" ? d.future_by_model[view] : undefined;
            const fut = d.future.map((f, i) => ({
              month: f.month,
              forecast: alt ? alt[i] : f.forecast,
              band: !alt && f.lower !== undefined && f.upper !== undefined ? [f.lower, f.upper] : undefined,
            }));
            // Connect the forecast line to the last actual point.
            const last = hist[hist.length - 1];
            const chart = [...hist.map((h, i) => (i === hist.length - 1 ? { ...h, forecast: h.actual } : h)), ...fut];
            const best = d.best_model;
            return (
              <>
                {d.metrics.length === 0 && (
                  <Notice tone="warn">
                    The selected slice has too little history for a backtest, so a flat last-month forecast is shown. Choose broader filters for model evaluation.
                  </Notice>
                )}
                <Card title="Historical spend and forecast"
                  subtitle={`${alt ? view : (bestLabel ?? d.method)} · next ${d.future.length} months${!alt && d.future[0]?.lower !== undefined ? " · shaded band is an empirical 10–90% error range" : ""}`}
                  action={
                    <label className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                      Model
                      <select value={view} onChange={(e) => setView(e.target.value)}
                        className="rounded-lg border border-navy-200 bg-white px-2 py-1.5 text-sm font-normal normal-case tracking-normal text-navy-900">
                        <option value="best">Best by backtest MAE</option>
                        {Object.keys(d.future_by_model).map((k) => <option key={k} value={k}>{k}</option>)}
                      </select>
                    </label>
                  }>
                  <div className="h-80 w-full" role="img" aria-label="Line chart of historical and forecast monthly spend">
                    <ResponsiveContainer>
                      <ComposedChart data={chart} margin={{ left: 4, right: 12 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#dbe5f3" vertical={false} />
                        <XAxis dataKey="month" tickFormatter={monthLabel} minTickGap={24} />
                        <YAxis tickFormatter={compactUsd} width={64} />
                        <Tooltip formatter={(v) => (Array.isArray(v) ? `${usd(Number(v[0]))} – ${usd(Number(v[1]))}` : usd(Number(v)))}
                          labelFormatter={(l) => monthLabel(String(l))} />
                        <Legend />
                        <Area dataKey="band" name="Prediction band" stroke="none" fill="#3b82c4" fillOpacity={0.18} />
                        <Line dataKey="actual" name="Actual" stroke="#1b3b69" strokeWidth={2.5} dot={false} />
                        <Line dataKey="forecast" name="Forecast" stroke="#c98a1b" strokeWidth={2.5} strokeDasharray="6 4" dot={{ r: 3 }} />
                      </ComposedChart>
                    </ResponsiveContainer>
                  </div>
                  {last && <p className="mt-2 text-xs text-slate-500">History ends {monthLabel(last.month)}.</p>}
                </Card>

                {d.metrics.length > 0 && (
                  <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                    <Card title="Backtest accuracy" subtitle={`One-step-ahead, final ${d.holdout_months} months · lower is better`}>
                      <DataTable caption="Forecast error by model"
                        columns={[
                          { key: "model", label: "Model", render: (v, r) => (
                            <span className="font-medium text-navy-900">{String(v)}{r.best ? <span className="ml-2 rounded bg-emerald-100 px-1.5 py-0.5 text-xs font-semibold text-emerald-800">Best MAE</span> : null}</span>
                          ) },
                          { key: "MAE", label: "MAE", align: "right", render: (v) => usd(Number(v)) },
                          { key: "RMSE", label: "RMSE", align: "right", render: (v) => usd(Number(v)) },
                          { key: "MAPE_pct", label: "MAPE", align: "right", render: (v) => `${Number(v).toFixed(1)}%` },
                        ]}
                        rows={d.metrics as unknown as Record<string, unknown>[]} />
                      <p className="mt-3 text-sm text-slate-600">
                        {best ? <>Lowest backtest MAE: <strong>{best}</strong>. </> : null}
                        {!d.seasonal && "Seasonal features are disabled because history is shorter than 24 months."}
                      </p>
                    </Card>
                    <Card title="Backtest: actual vs predicted" subtitle="Each model on the same held-out months">
                      <div className="h-72 w-full" role="img" aria-label="Backtest comparison chart">
                        <ResponsiveContainer>
                          <ComposedChart data={d.backtest} margin={{ left: 4, right: 12 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#dbe5f3" vertical={false} />
                            <XAxis dataKey="month" tickFormatter={monthLabel} minTickGap={16} />
                            <YAxis tickFormatter={compactUsd} width={64} domain={["auto", "auto"]} />
                            <Tooltip formatter={(v) => usd(Number(v))} labelFormatter={(l) => monthLabel(String(l))} />
                            <Legend />
                            <Line dataKey="actual" name="Actual" stroke="#0b1f3a" strokeWidth={2.5} dot={false} />
                            <Line dataKey="model" name="Random forest" stroke="#0f9d8a" strokeWidth={2} dot={false} />
                            <Line dataKey="xgboost" name="XGBoost" stroke="#7c6cc4" strokeWidth={2} dot={false} />
                            <Line dataKey="ets" name="Holt-Winters ETS" stroke="#c2410c" strokeWidth={2} dot={false} />
                            <Line dataKey="arima" name="ARIMA" stroke="#be3a6b" strokeWidth={1.5} dot={false} />
                            <Line dataKey="last_month" name="Last month" stroke="#94a3b8" strokeDasharray="4 3" dot={false} />
                            <Line dataKey="seasonal_naive" name="Seasonal naive" stroke="#c98a1b" strokeDasharray="4 3" dot={false} />
                          </ComposedChart>
                        </ResponsiveContainer>
                      </div>
                    </Card>
                  </div>
                )}

                <Card title="Forecast values">
                  <DataTable caption="Forecast values"
                    columns={[
                      { key: "month", label: "Month", render: (v) => monthLabel(String(v)) },
                      { key: "forecast", label: "Forecast", align: "right", render: (v) => usd(Number(v)) },
                      { key: "lower", label: "Low (10%)", align: "right", render: (v) => (v == null ? "—" : usd(Number(v))) },
                      { key: "upper", label: "High (90%)", align: "right", render: (v) => (v == null ? "—" : usd(Number(v))) },
                    ]}
                    rows={d.future as unknown as Record<string, unknown>[]} />
                </Card>
                <ul className="list-disc space-y-1 pl-5 text-sm text-slate-600">
                  {d.notes.map((n) => <li key={n}>{n}</li>)}
                </ul>
                <Insight section="forecast" context={{ best_model: best, mae: d.metrics.find((m) => m.best)?.MAE }} />
              </>
            );
          }}
        </Loadable>
      </Container>
    </>
  );
}
