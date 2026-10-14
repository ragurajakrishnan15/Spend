"use client";

import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Insight } from "@/components/Insight";
import { Loadable } from "@/components/Loadable";
import { Card, Container, DataTable, Kpi, PageHeader } from "@/components/ui";
import { useApi } from "@/lib/api";
import { monthLabel, signedPct, usd } from "@/lib/format";
import type { BudgetResponse, Rag } from "@/lib/types";

const RAG_STYLE: Record<Rag, string> = {
  green: "bg-emerald-100 text-emerald-800",
  amber: "bg-amber-100 text-amber-900",
  red: "bg-red-100 text-red-800",
};
const RAG_FILL: Record<Rag, string> = { green: "#0f9d8a", amber: "#c98a1b", red: "#b91c1c" };
const RAG_LABEL: Record<Rag, string> = { green: "On budget", amber: "0–10% over", red: ">10% over" };

function RagBadge({ rag }: { rag: Rag }) {
  return <span className={`rounded px-2 py-0.5 text-xs font-semibold ${RAG_STYLE[rag]}`}>{RAG_LABEL[rag]}</span>;
}

export default function BudgetPage() {
  const state = useApi<BudgetResponse>("/api/budget");
  return (
    <>
      <PageHeader eyebrow="Budget Management" title="Budget vs. actual spend"
        description="Monthly actual spend against synthetic category budgets, with a red / amber / green status per category-month. Budgets are illustrative defaults, not real targets." />
      <Container className="space-y-6">
        <Loadable state={state}>
          {(d) => {
            const months = [...new Set(d.detail.map((r) => r.month))].sort();
            const latest = months[months.length - 1];
            const latestRows = d.detail.filter((r) => r.month === latest).sort((a, b) => b.variance_pct - a.variance_pct);
            const count = (rag: Rag) => latestRows.filter((r) => r.rag === rag).length;
            const totalRed = d.detail.filter((r) => r.rag === "red").length;
            const overCats = d.summary.filter((s) => s.months_over_budget > 0).length;
            return (
              <>
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                  <Kpi label={`On budget (${monthLabel(latest)})`} value={`${count("green")} of ${latestRows.length}`} hint="categories" tone="up" />
                  <Kpi label="Amber" value={String(count("amber"))} hint="0–10% over budget" />
                  <Kpi label="Red" value={String(count("red"))} hint="more than 10% over" tone={count("red") ? "down" : "neutral"} />
                  <Kpi label="Red category-months" value={String(totalRed)} hint={`across ${months.length} months`} />
                </div>

                <Card title={`Variance vs. budget — ${monthLabel(latest)}`} subtitle="Percentage above (+) or below (−) the monthly budget">
                  <div className="h-80 w-full" role="img" aria-label="Bar chart of budget variance by category for the latest month">
                    <ResponsiveContainer>
                      <BarChart data={latestRows} margin={{ left: 4, right: 12 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#dbe5f3" vertical={false} />
                        <XAxis dataKey="category" />
                        <YAxis tickFormatter={(v) => `${v}%`} width={52} />
                        <Tooltip formatter={(v) => signedPct(Number(v))} />
                        <Bar dataKey="variance_pct" name="Variance">
                          {latestRows.map((r) => <Cell key={r.category} fill={RAG_FILL[r.rag]} />)}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </Card>

                <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                  <Card title="Latest month" subtitle={monthLabel(latest)}>
                    <DataTable caption="Latest month budget variance"
                      columns={[
                        { key: "category", label: "Category" },
                        { key: "actual", label: "Actual", align: "right", render: (v) => usd(Number(v)) },
                        { key: "budget", label: "Budget", align: "right", render: (v) => usd(Number(v)) },
                        { key: "variance_pct", label: "Variance", align: "right", render: (v) => signedPct(Number(v)) },
                        { key: "rag", label: "Status", render: (v) => <RagBadge rag={v as Rag} /> },
                      ]}
                      rows={latestRows as unknown as Record<string, unknown>[]} />
                  </Card>
                  <Card title="All months" subtitle={`${months.length} months, cumulative per category`}>
                    <DataTable caption="Cumulative budget variance by category"
                      columns={[
                        { key: "category", label: "Category" },
                        { key: "total_actual", label: "Actual", align: "right", render: (v) => usd(Number(v)) },
                        { key: "total_budget", label: "Budget", align: "right", render: (v) => usd(Number(v)) },
                        { key: "overall_variance_pct", label: "Variance", align: "right", render: (v) => signedPct(Number(v)) },
                        { key: "months_over_budget", label: "Months over", align: "right" },
                      ]}
                      rows={d.summary as unknown as Record<string, unknown>[]} />
                  </Card>
                </div>

                <Insight section="budget" context={{ categories_over_budget: overCats, total_categories: d.categories.length }} />
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
