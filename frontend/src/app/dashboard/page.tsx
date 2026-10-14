"use client";

import { useState } from "react";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { DEFAULT_FILTERS, FilterBar } from "@/components/FilterBar";
import { Loadable } from "@/components/Loadable";
import { Insight } from "@/components/Insight";
import { Card, Container, EmptyState, Kpi, PageHeader } from "@/components/ui";
import { filterQuery, useApi } from "@/lib/api";
import { CHART_COLORS, compactUsd, int, monthLabel, pct, signedPct, usd } from "@/lib/format";
import type { Filters, Overview } from "@/lib/types";

export default function DashboardPage() {
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS);
  const state = useApi<Overview>(`/api/overview${filterQuery(filters)}`);

  return (
    <>
      <PageHeader eyebrow="Executive Dashboard" title="Portfolio spend at a glance"
        description="Headline volume, customer activity and mix across the synthetic transaction portfolio. Every figure responds to the filters below." />
      <Container className="space-y-6">
        <FilterBar filters={filters} onChange={setFilters} />
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-sm font-medium text-slate-600">Export this view:</span>
          <a href={`/api/export/excel${filterQuery(filters)}`} download
            className="rounded-lg border border-navy-200 bg-white px-4 py-2 text-sm font-semibold text-navy-800 hover:bg-navy-50">
            Excel workbook (.xlsx)
          </a>
          <a href={`/api/export/pptx${filterQuery(filters)}`} download
            className="rounded-lg bg-navy-900 px-4 py-2 text-sm font-semibold text-white hover:bg-navy-800">
            PowerPoint briefing (.pptx)
          </a>
        </div>
        <Loadable state={state}>
          {(d) => {
            if (d.empty || !d.kpis) return <EmptyState />;
            const k = d.kpis;
            const mom = k.mom_change_pct;
            return (
              <>
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                  <Kpi label="Total spend" value={usd(k.total_spend)} hint={`${int(k.transactions)} transactions`} />
                  <Kpi label="Active customers" value={int(k.customers)} />
                  <Kpi label="Average transaction" value={usd(k.avg_transaction, 2)} />
                  <Kpi label={`Latest month (${monthLabel(k.latest_month)})`} value={usd(k.latest_month_spend)}
                    hint={mom === null ? "No prior month" : `${signedPct(mom)} vs prior month`}
                    tone={mom === null ? "neutral" : mom >= 0 ? "up" : "down"} />
                </div>

                <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
                  <Card title="Monthly spend" subtitle="Total transaction value by calendar month" className="lg:col-span-2">
                    <div className="h-72 w-full" role="img" aria-label="Area chart of monthly spend">
                      <ResponsiveContainer>
                        <AreaChart data={d.monthly} margin={{ left: 4, right: 12, top: 8 }}>
                          <defs>
                            <linearGradient id="spendFill" x1="0" y1="0" x2="0" y2="1">
                              <stop offset="0%" stopColor="#1b3b69" stopOpacity={0.35} />
                              <stop offset="100%" stopColor="#1b3b69" stopOpacity={0.02} />
                            </linearGradient>
                          </defs>
                          <CartesianGrid strokeDasharray="3 3" stroke="#dbe5f3" vertical={false} />
                          <XAxis dataKey="month" tickFormatter={monthLabel} minTickGap={24} />
                          <YAxis tickFormatter={compactUsd} width={64} />
                          <Tooltip formatter={(v) => usd(Number(v))} labelFormatter={(l) => monthLabel(String(l))} />
                          <Area type="monotone" dataKey="spend" name="Spend" stroke="#1b3b69" strokeWidth={2.5} fill="url(#spendFill)" />
                        </AreaChart>
                      </ResponsiveContainer>
                    </div>
                  </Card>

                  <Card title="Channel mix" subtitle="Share of spend">
                    <div className="h-72 w-full" role="img" aria-label="Donut chart of spend by channel">
                      <ResponsiveContainer>
                        <PieChart>
                          <Pie data={d.channels} dataKey="spend" nameKey="channel" innerRadius="55%" outerRadius="80%" paddingAngle={2}>
                            {d.channels.map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
                          </Pie>
                          <Tooltip formatter={(v) => usd(Number(v))} />
                          <Legend />
                        </PieChart>
                      </ResponsiveContainer>
                    </div>
                  </Card>
                </div>

                <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                  <Card title="Spend by merchant category">
                    <div className="h-72 w-full" role="img" aria-label="Bar chart of spend by category">
                      <ResponsiveContainer>
                        <BarChart data={d.categories} layout="vertical" margin={{ left: 16, right: 16 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#dbe5f3" horizontal={false} />
                          <XAxis type="number" tickFormatter={compactUsd} />
                          <YAxis type="category" dataKey="category" width={100} />
                          <Tooltip formatter={(v) => usd(Number(v))} />
                          <Bar dataKey="spend" name="Spend" fill="#1b3b69" radius={[0, 4, 4, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  </Card>
                  <Card title="Spend by region" subtitle={`Campaign response rate across filtered transactions: ${pct(k.campaign_response_rate)}`}>
                    <div className="h-72 w-full" role="img" aria-label="Bar chart of spend by region">
                      <ResponsiveContainer>
                        <BarChart data={d.regions} margin={{ left: 4, right: 12 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#dbe5f3" vertical={false} />
                          <XAxis dataKey="region" />
                          <YAxis tickFormatter={compactUsd} width={64} />
                          <Tooltip formatter={(v) => usd(Number(v))} />
                          <Bar dataKey="spend" name="Spend" fill="#3b82c4" radius={[4, 4, 0, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  </Card>
                </div>
                <Insight section="overview" context={{ total_spend: k.total_spend, transactions: k.transactions, mom_change_pct: mom }} />
              </>
            );
          }}
        </Loadable>
      </Container>
    </>
  );
}
