"use client";

import { useState } from "react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Insight } from "@/components/Insight";
import { Loadable } from "@/components/Loadable";
import { Card, Container, Kpi, Notice, PageHeader, Skeleton } from "@/components/ui";
import { buildQuery, useApi } from "@/lib/api";
import { monthLabel } from "@/lib/format";
import type { MacroResponse, Meta, Rag, ReportLibrary } from "@/lib/types";

const SEVERITY: Record<Rag, string> = {
  green: "border-emerald-300 bg-emerald-50 text-emerald-900",
  amber: "border-amber-300 bg-amber-50 text-amber-900",
  red: "border-red-300 bg-red-50 text-red-900",
};
const SEVERITY_LABEL: Record<Rag, string> = { green: "Tailwind", amber: "Monitor", red: "Headwind" };

export default function MacroPage() {
  const [category, setCategory] = useState("All");
  const [open, setOpen] = useState<string | null>(null);
  const macro = useApi<MacroResponse>("/api/macro");
  const meta = useApi<Meta>("/api/meta");
  const lib = useApi<ReportLibrary>(`/api/report-library${buildQuery({ category })}`);

  return (
    <>
      <PageHeader eyebrow="Macro Intelligence" title="Macro backdrop and watch items"
        description="Synthetic CPI, consumer sentiment, GDP and retail-sales indicators translated into themes and watch items, alongside a library of reports with their forecast implications." />
      <Container className="space-y-6">
        <Notice>All indicators and reports are synthetic and exist only to demonstrate the workflow. They are not real economic data.</Notice>
        <Loadable state={macro}>
          {(m) => {
            const c = m.context;
            const i = c.indicators;
            return (
              <>
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                  <Kpi label={`CPI YoY (${monthLabel(c.month)})`} value={`${i.cpi_yoy.toFixed(1)}%`}
                    hint={i.cpi_mom_change === null ? undefined : `${i.cpi_mom_change >= 0 ? "+" : ""}${i.cpi_mom_change.toFixed(2)} pts vs prior month`}
                    tone={i.cpi_mom_change !== null && i.cpi_mom_change > 0 ? "down" : "up"} />
                  <Kpi label="Consumer sentiment" value={i.consumer_sentiment.toFixed(0)} hint="100 = neutral" />
                  <Kpi label="GDP growth" value={`${i.gdp_growth.toFixed(1)}%`} hint="annualised proxy" />
                  <Kpi label="Retail sales growth" value={`${i.retail_sales_growth.toFixed(1)}%`} hint="YoY" />
                </div>

                <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
                  <Card title="Indicator trends" className="lg:col-span-2">
                    <div className="h-72 w-full" role="img" aria-label="Line chart of macro indicators over time">
                      <ResponsiveContainer>
                        <LineChart data={m.indicators} margin={{ left: 4, right: 12 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#dbe5f3" vertical={false} />
                          <XAxis dataKey="month" tickFormatter={monthLabel} minTickGap={24} />
                          <YAxis yAxisId="pct" width={40} tickFormatter={(v) => `${v}%`} />
                          <YAxis yAxisId="idx" orientation="right" width={40} domain={["auto", "auto"]} />
                          <Tooltip labelFormatter={(l) => monthLabel(String(l))} />
                          <Legend />
                          <Line yAxisId="pct" dataKey="cpi_yoy" name="CPI YoY %" stroke="#c2410c" strokeWidth={2} dot={false} />
                          <Line yAxisId="pct" dataKey="gdp_growth" name="GDP growth %" stroke="#1b3b69" strokeWidth={2} dot={false} />
                          <Line yAxisId="pct" dataKey="retail_sales_growth" name="Retail sales %" stroke="#0f9d8a" strokeWidth={2} dot={false} />
                          <Line yAxisId="idx" dataKey="consumer_sentiment" name="Sentiment (right axis)" stroke="#7c6cc4" strokeWidth={2} strokeDasharray="5 3" dot={false} />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  </Card>
                  <Card title="Themes" subtitle={c.summary}>
                    <ul className="space-y-2 text-sm leading-relaxed text-slate-700">
                      {c.themes.map((t) => (
                        <li key={t} className="flex gap-2">
                          <span aria-hidden className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-navy-500" />
                          <span>{t}</span>
                        </li>
                      ))}
                    </ul>
                  </Card>
                </div>

                <Card title="Watch items" subtitle="Derived from indicator thresholds">
                  {c.watch_items.length === 0 ? (
                    <p className="text-sm text-slate-500">No watch items at the current indicator levels.</p>
                  ) : (
                    <ul className="grid grid-cols-1 gap-3 md:grid-cols-2">
                      {c.watch_items.map((w) => (
                        <li key={`${w.category}-${w.signal}`} className={`rounded-lg border px-4 py-3 text-sm ${SEVERITY[w.severity]}`}>
                          <p className="font-semibold">
                            {w.category} <span className="ml-1 text-xs font-medium uppercase tracking-wide">{SEVERITY_LABEL[w.severity]}</span>
                          </p>
                          <p className="mt-0.5">{w.signal}</p>
                        </li>
                      ))}
                    </ul>
                  )}
                </Card>
                <Insight section="macro" context={{ cpi_yoy: i.cpi_yoy, consumer_sentiment: i.consumer_sentiment }} />
              </>
            );
          }}
        </Loadable>

        <Card title="Report library" subtitle="Curated reports with key themes, watch items and forecast implications"
          action={
            <label className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
              Category
              <select value={category} onChange={(e) => setCategory(e.target.value)}
                className="rounded-lg border border-navy-200 bg-white px-2 py-1.5 text-sm font-normal normal-case tracking-normal text-navy-900">
                <option value="All">All</option>
                {(meta.data?.categories ?? []).map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            </label>
          }>
          <Loadable state={lib} skeleton={<Skeleton className="h-48" />}>
            {(l) => l.reports.length === 0 ? (
              <p className="text-sm text-slate-500">No reports are tagged with this category.</p>
            ) : (
              <ul className="divide-y divide-navy-100">
                {l.reports.map((r) => {
                  const isOpen = open === r.id;
                  return (
                    <li key={r.id} className="py-3">
                      <button type="button" onClick={() => setOpen(isOpen ? null : r.id)} aria-expanded={isOpen}
                        className="flex w-full items-start justify-between gap-4 text-left">
                        <span>
                          <span className="block text-sm font-semibold text-navy-900">{r.title}</span>
                          <span className="block text-sm text-slate-600">{r.headline}</span>
                          <span className="mt-1 block text-xs text-slate-500">{r.date} · {r.source} · {r.category_tags.join(", ")}</span>
                        </span>
                        <span aria-hidden className="mt-1 text-navy-500">{isOpen ? "−" : "+"}</span>
                      </button>
                      {isOpen && (
                        <div className="mt-3 grid grid-cols-1 gap-4 text-sm text-slate-700 md:grid-cols-3">
                          <div>
                            <p className="font-semibold text-navy-900">Key themes</p>
                            <ul className="mt-1 list-disc space-y-1 pl-5">{r.key_themes.map((t) => <li key={t}>{t}</li>)}</ul>
                          </div>
                          <div>
                            <p className="font-semibold text-navy-900">Watch items</p>
                            <ul className="mt-1 list-disc space-y-1 pl-5">{r.watch_items.map((t) => <li key={t}>{t}</li>)}</ul>
                          </div>
                          <div>
                            <p className="font-semibold text-navy-900">Forecast implication</p>
                            <p className="mt-1">{r.implications_for_forecast}</p>
                          </div>
                        </div>
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
          </Loadable>
        </Card>
      </Container>
    </>
  );
}
