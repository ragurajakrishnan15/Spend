"use client";

import { useState } from "react";
import { CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Insight } from "@/components/Insight";
import { Loadable } from "@/components/Loadable";
import { Card, Container, DataTable, Kpi, Notice, PageHeader } from "@/components/ui";
import { useApi } from "@/lib/api";
import { CHART_COLORS, int, monthLabel, usd } from "@/lib/format";
import type { OpsForecast } from "@/lib/types";

type Metric = "transaction_count" | "avg_ticket";
const METRIC_LABEL: Record<Metric, string> = { transaction_count: "Transaction volume", avg_ticket: "Average ticket" };

export default function OpsForecastPage() {
  const [horizon, setHorizon] = useState(3);
  const [metric, setMetric] = useState<Metric>("transaction_count");
  const state = useApi<OpsForecast>(`/api/ops-forecast?horizon=${horizon}`);
  const fmt = (v: number) => (metric === "avg_ticket" ? usd(v, 2) : int(v));

  return (
    <>
      <PageHeader eyebrow="Operations Forecasting" title="Volume and ticket size by channel"
        description="Monthly transaction counts and average ticket size are forecast per channel with an XGBoost lag-ratio model, benchmarked against a last-month baseline in a rolling-origin backtest." />
      <Container className="space-y-6">
        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
            Metric
            <select value={metric} onChange={(e) => setMetric(e.target.value as Metric)}
              className="rounded-lg border border-navy-200 bg-white px-3 py-2 text-sm font-normal normal-case tracking-normal text-navy-900">
              {(Object.keys(METRIC_LABEL) as Metric[]).map((k) => <option key={k} value={k}>{METRIC_LABEL[k]}</option>)}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
            Horizon
            <select value={horizon} onChange={(e) => setHorizon(Number(e.target.value))}
              className="rounded-lg border border-navy-200 bg-white px-3 py-2 text-sm font-normal normal-case tracking-normal text-navy-900">
              {[1, 3, 6, 9, 12].map((h) => <option key={h} value={h}>{h} month{h > 1 ? "s" : ""}</option>)}
            </select>
          </label>
        </div>

        <Loadable state={state}>
          {(d) => {
            const series = d[metric];
            if (series.length === 0) return <Notice tone="warn">Not enough history to forecast this metric.</Notice>;
            const months = [...series[0].history.map((h) => h.month), ...series[0].future.map((f) => f.month)];
            const lastHist = series[0].history[series[0].history.length - 1]?.month;
            const rows = months.map((m) => {
              const row: Record<string, string | number | undefined> = { month: m };
              series.forEach((s) => {
                const h = s.history.find((x) => x.month === m);
                const f = s.future.find((x) => x.month === m);
                if (h) row[`${s.channel} actual`] = h.value;
                if (f) row[`${s.channel} forecast`] = f.value;
                if (m === lastHist && h) row[`${s.channel} forecast`] = h.value; // join the dashed line to history
              });
              return row;
            });
            const nextMonth = series[0].future[0]?.month;
            return (
              <>
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                  {series.slice(0, 4).map((s) => {
                    const last = s.history[s.history.length - 1]?.value ?? 0;
                    const next = s.future[0]?.value ?? 0;
                    const chg = last ? ((next - last) / last) * 100 : 0;
                    return (
                      <Kpi key={s.channel} label={`${s.channel} · ${nextMonth ? monthLabel(nextMonth) : "next"}`} value={fmt(next)}
                        hint={`${chg >= 0 ? "+" : ""}${chg.toFixed(1)}% vs last actual`} tone={chg >= 0 ? "up" : "down"} />
                    );
                  })}
                </div>

                <Card title={`${METRIC_LABEL[metric]} by channel`} subtitle="Solid = actual, dashed = forecast">
                  <div className="h-96 w-full" role="img" aria-label={`Line chart of ${METRIC_LABEL[metric]} by channel with forecast`}>
                    <ResponsiveContainer>
                      <ComposedChart data={rows} margin={{ left: 4, right: 12 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#dbe5f3" vertical={false} />
                        <XAxis dataKey="month" tickFormatter={monthLabel} minTickGap={24} />
                        <YAxis tickFormatter={(v) => (metric === "avg_ticket" ? usd(Number(v)) : int(Number(v)))} width={64} />
                        <Tooltip formatter={(v) => fmt(Number(v))} labelFormatter={(l) => monthLabel(String(l))} />
                        <Legend />
                        {series.map((s, i) => (
                          <Line key={`${s.channel}-a`} dataKey={`${s.channel} actual`} name={s.channel}
                            stroke={CHART_COLORS[i % CHART_COLORS.length]} strokeWidth={2} dot={false} connectNulls />
                        ))}
                        {series.map((s, i) => (
                          <Line key={`${s.channel}-f`} dataKey={`${s.channel} forecast`} name={`${s.channel} (forecast)`} legendType="none"
                            stroke={CHART_COLORS[i % CHART_COLORS.length]} strokeWidth={2} strokeDasharray="6 4" dot={{ r: 3 }} connectNulls />
                        ))}
                      </ComposedChart>
                    </ResponsiveContainer>
                  </div>
                </Card>

                <Card title="Backtest accuracy by channel" subtitle="Mean absolute error over the held-out months · lower is better">
                  <DataTable caption="Operations forecast accuracy"
                    columns={[
                      { key: "channel", label: "Channel" },
                      { key: "xgb_mae", label: "XGBoost MAE", align: "right", render: (v) => fmt(Number(v)) },
                      { key: "naive_mae", label: "Last-month MAE", align: "right", render: (v) => fmt(Number(v)) },
                      { key: "best_model", label: "Better model" },
                    ]}
                    rows={series as unknown as Record<string, unknown>[]} />
                </Card>

                <Insight section="ops" context={{ metric, channels: d.channels.length }} />
                <ul className="list-disc space-y-1 pl-5 text-sm text-slate-600">
                  {d.notes.map((n) => <li key={n}>{n}</li>)}
                </ul>
              </>
            );
          }}
        </Loadable>
      </Container>
    </>
  );
}
