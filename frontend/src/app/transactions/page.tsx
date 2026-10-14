"use client";

import { useState } from "react";
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { DEFAULT_FILTERS, FilterBar } from "@/components/FilterBar";
import { Loadable } from "@/components/Loadable";
import { Card, Container, DataTable, EmptyState, Kpi, PageHeader } from "@/components/ui";
import { filterQuery, useApi } from "@/lib/api";
import { compactUsd, int, monthLabel, usd } from "@/lib/format";
import type { Filters, TransactionsResponse } from "@/lib/types";

const PAGE_SIZE = 15;

export default function TransactionsPage() {
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS);
  const [offset, setOffset] = useState(0);
  const [view, setView] = useState<"daily" | "monthly">("monthly");
  const state = useApi<TransactionsResponse>(`/api/transactions${filterQuery(filters, { limit: PAGE_SIZE, offset })}`);

  const updateFilters = (f: Filters) => {
    setFilters(f);
    setOffset(0);
  };

  return (
    <>
      <PageHeader eyebrow="Transaction Analytics" title="Explore transaction behaviour"
        description="Slice synthetic transactions by category, channel, region and date. Compare trends, weekday patterns and the distribution of ticket sizes." />
      <Container className="space-y-6">
        <FilterBar filters={filters} onChange={updateFilters} />
        <Loadable state={state}>
          {(d) => {
            if (d.empty || !d.summary) return <EmptyState />;
            const s = d.summary;
            const series = view === "monthly" ? d.monthly.map((m) => ({ x: m.month, spend: m.spend })) : d.daily.map((m) => ({ x: m.date, spend: m.spend }));
            const page = Math.floor(offset / PAGE_SIZE) + 1;
            const pages = Math.max(1, Math.ceil(d.total_rows / PAGE_SIZE));
            return (
              <>
                <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
                  <Kpi label="Transactions" value={int(s.transactions)} />
                  <Kpi label="Total spend" value={usd(s.spend)} />
                  <Kpi label="Median ticket" value={usd(s.median, 2)} />
                  <Kpi label="Mean ticket" value={usd(s.mean, 2)} />
                  <Kpi label="95th percentile" value={usd(s.p95, 2)} />
                </div>

                <Card title="Spend over time" subtitle={view === "monthly" ? "Monthly totals" : "Daily totals"}
                  action={
                    <div role="group" aria-label="Time granularity" className="flex rounded-lg border border-navy-200 p-0.5 text-sm">
                      {(["monthly", "daily"] as const).map((v) => (
                        <button key={v} type="button" aria-pressed={view === v} onClick={() => setView(v)}
                          className={`rounded-md px-3 py-1 font-medium capitalize ${view === v ? "bg-navy-900 text-white" : "text-navy-700"}`}>
                          {v}
                        </button>
                      ))}
                    </div>
                  }>
                  <div className="h-72 w-full" role="img" aria-label="Line chart of spend over time">
                    <ResponsiveContainer>
                      <LineChart data={series} margin={{ left: 4, right: 12 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#dbe5f3" vertical={false} />
                        <XAxis dataKey="x" tickFormatter={(v) => (view === "monthly" ? monthLabel(String(v)) : String(v).slice(5))} minTickGap={32} />
                        <YAxis tickFormatter={compactUsd} width={64} />
                        <Tooltip formatter={(v) => usd(Number(v))} />
                        <Line type="monotone" dataKey="spend" name="Spend" stroke="#1b3b69" strokeWidth={2} dot={false} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </Card>

                <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                  <Card title="Ticket size distribution" subtitle={d.histogram_note}>
                    <div className="h-64 w-full" role="img" aria-label="Histogram of transaction amounts">
                      <ResponsiveContainer>
                        <BarChart data={d.histogram.map((h) => ({ label: Math.round(h.bin_start), count: h.count }))} barCategoryGap={1}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#dbe5f3" vertical={false} />
                          <XAxis dataKey="label" tickFormatter={(v) => `$${v}`} minTickGap={20} />
                          <YAxis width={48} />
                          <Tooltip labelFormatter={(l) => `From $${l}`} />
                          <Bar dataKey="count" name="Transactions" fill="#3b82c4" />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  </Card>
                  <Card title="Spend by weekday">
                    <div className="h-64 w-full" role="img" aria-label="Bar chart of spend by weekday">
                      <ResponsiveContainer>
                        <BarChart data={d.weekday}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#dbe5f3" vertical={false} />
                          <XAxis dataKey="day" />
                          <YAxis tickFormatter={compactUsd} width={64} />
                          <Tooltip formatter={(v) => usd(Number(v))} />
                          <Bar dataKey="spend" name="Spend" fill="#1b3b69" radius={[4, 4, 0, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  </Card>
                </div>

                <Card title="Transaction ledger" subtitle={`Showing ${int(offset + 1)}–${int(Math.min(offset + PAGE_SIZE, d.total_rows))} of ${int(d.total_rows)}, newest first`}>
                  <DataTable caption="Transactions"
                    columns={[
                      { key: "timestamp", label: "Time" },
                      { key: "transaction_id", label: "ID" },
                      { key: "customer_id", label: "Customer" },
                      { key: "merchant_clean", label: "Merchant" },
                      { key: "category", label: "Category" },
                      { key: "channel", label: "Channel" },
                      { key: "region", label: "Region" },
                      { key: "amount", label: "Amount", align: "right", render: (v) => usd(Number(v), 2) },
                    ]}
                    rows={d.table as unknown as Record<string, unknown>[]} />
                  <div className="mt-4 flex items-center justify-between text-sm">
                    <button type="button" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
                      className="rounded-lg border border-navy-200 px-4 py-2 font-medium text-navy-800 hover:bg-navy-50 disabled:opacity-40">
                      Previous
                    </button>
                    <span className="text-slate-500">Page {int(page)} of {int(pages)}</span>
                    <button type="button" disabled={page >= pages} onClick={() => setOffset(offset + PAGE_SIZE)}
                      className="rounded-lg border border-navy-200 px-4 py-2 font-medium text-navy-800 hover:bg-navy-50 disabled:opacity-40">
                      Next
                    </button>
                  </div>
                </Card>
              </>
            );
          }}
        </Loadable>
      </Container>
    </>
  );
}
