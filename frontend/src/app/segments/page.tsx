"use client";

import { CartesianGrid, Legend, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis } from "recharts";
import { Loadable } from "@/components/Loadable";
import { Insight } from "@/components/Insight";
import { Card, Container, DataTable, EmptyState, Kpi, Notice, PageHeader } from "@/components/ui";
import { useApi } from "@/lib/api";
import { CHART_COLORS, compactUsd, int, usd } from "@/lib/format";
import type { SegmentsResponse } from "@/lib/types";

export default function SegmentsPage() {
  const state = useApi<SegmentsResponse>("/api/segments?limit=400");
  return (
    <>
      <PageHeader eyebrow="Customer Segmentation" title="Behavioural RFM segments"
        description="Customers are grouped on recency, frequency and monetary value (log-scaled, KMeans) and named from each cluster's average profile." />
      <Container className="space-y-6">
        <Loadable state={state}>
          {(d) => {
            if (d.empty) return <EmptyState title="Not enough data to build segments" hint="At least two customers with transactions are required." />;
            const names = d.summary.map((s) => s.segment);
            const total = d.summary.reduce((a, s) => a + s.total_spend, 0);
            return (
              <>
                <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
                  <Kpi label="Customers" value={int(d.total_customers)} />
                  <Kpi label="Segments" value={String(d.summary.length)} />
                  <Kpi label="Largest segment" value={d.summary.slice().sort((a, b) => b.customers - a.customers)[0].segment}
                    hint={`${int(d.summary.slice().sort((a, b) => b.customers - a.customers)[0].customers)} customers`} />
                  <Kpi label="Top spend share" value={`${((d.summary[0].total_spend / total) * 100).toFixed(0)}%`} hint={d.summary[0].segment} />
                </div>

                <Card title="Frequency vs spend" subtitle={`Top ${int(d.points.length)} customers by spend, coloured by segment`}>
                  <div className="h-96 w-full" role="img" aria-label="Scatter chart of customer frequency against spend by segment">
                    <ResponsiveContainer>
                      <ScatterChart margin={{ left: 4, right: 16, top: 8 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#dbe5f3" />
                        <XAxis type="number" dataKey="frequency" name="Transactions" />
                        <YAxis type="number" dataKey="monetary" name="Spend" tickFormatter={compactUsd} width={64} />
                        <ZAxis range={[40, 40]} />
                        <Tooltip cursor={{ strokeDasharray: "3 3" }}
                          formatter={(v, n) => (n === "Spend" ? usd(Number(v)) : String(v))} />
                        <Legend />
                        {names.map((n, i) => (
                          <Scatter key={n} name={n} data={d.points.filter((p) => p.segment === n)}
                            fill={CHART_COLORS[i % CHART_COLORS.length]} fillOpacity={0.75} />
                        ))}
                      </ScatterChart>
                    </ResponsiveContainer>
                  </div>
                </Card>

                <Card title="Segment profiles">
                  <DataTable caption="Segment profiles"
                    columns={[
                      { key: "segment", label: "Segment", render: (v) => <span className="font-medium text-navy-900">{String(v)}</span> },
                      { key: "customers", label: "Customers", align: "right", render: (v) => int(Number(v)) },
                      { key: "avg_recency_days", label: "Avg days since last", align: "right", render: (v) => Number(v).toFixed(0) },
                      { key: "avg_transactions", label: "Avg transactions", align: "right", render: (v) => Number(v).toFixed(1) },
                      { key: "avg_spend", label: "Avg spend", align: "right", render: (v) => usd(Number(v)) },
                      { key: "total_spend", label: "Total spend", align: "right", render: (v) => usd(Number(v)) },
                    ]}
                    rows={d.summary as unknown as Record<string, unknown>[]} />
                </Card>
                <Notice>{d.note} Segment names are descriptive labels for synthetic behaviour, not judgments about customer worth.</Notice>
                <Insight section="segments" context={{ total_customers: d.total_customers, top_segment: [...d.summary].sort((a, b) => b.total_spend - a.total_spend)[0]?.segment }} />
              </>
            );
          }}
        </Loadable>
      </Container>
    </>
  );
}
