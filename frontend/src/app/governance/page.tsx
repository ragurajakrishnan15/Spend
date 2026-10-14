"use client";

import { Loadable } from "@/components/Loadable";
import { Card, Container, Notice, PageHeader, Skeleton } from "@/components/ui";
import { useApi } from "@/lib/api";
import { int } from "@/lib/format";
import type { Governance } from "@/lib/types";

function List({ items }: { items: string[] }) {
  return (
    <ul className="space-y-2 text-sm leading-relaxed text-slate-700">
      {items.map((i) => (
        <li key={i} className="flex gap-2">
          <span aria-hidden className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-navy-500" />
          <span>{i}</span>
        </li>
      ))}
    </ul>
  );
}

export default function GovernancePage() {
  const state = useApi<Governance>("/api/governance");
  return (
    <>
      <PageHeader eyebrow="Model Governance" title="Controls, limitations and responsible use"
        description="What this demonstration does to evaluate itself honestly — and what it does not do. Figures below are read from the running backend." />
      <Container className="space-y-6">
        <Loadable state={state} skeleton={<Skeleton className="h-96" />}>
          {(g) => (
            <>
              <Notice tone="warn">{g.disclaimer}</Notice>
              <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                <Card title="Data provenance">
                  <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
                    <dt className="text-slate-500">Source</dt><dd className="text-navy-900">{g.provenance.source}</dd>
                    <dt className="text-slate-500">Period</dt><dd className="text-navy-900">{g.provenance.period}</dd>
                    <dt className="text-slate-500">Transactions</dt><dd className="tabular-nums text-navy-900">{int(g.provenance.rows)}</dd>
                    <dt className="text-slate-500">Customers</dt><dd className="tabular-nums text-navy-900">{int(g.provenance.customers)}</dd>
                    <dt className="text-slate-500">Dataset version</dt><dd className="text-navy-900">v{g.provenance.data_version}</dd>
                  </dl>
                </Card>
                <Card title="Evaluation summary">
                  <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
                    <dt className="text-slate-500">Forecast backtest</dt>
                    <dd className="text-navy-900">{g.evaluation.forecast_holdout_months} held-out months, rolling origin</dd>
                    <dt className="text-slate-500">Best forecast model (MAE)</dt>
                    <dd className="text-navy-900">{g.evaluation.forecast_best_model ?? "n/a"}</dd>
                    <dt className="text-slate-500">Campaign test set</dt>
                    <dd className="text-navy-900">{g.evaluation.campaign_test_rows === null ? "n/a" : `${int(g.evaluation.campaign_test_rows)} later transactions`}</dd>
                  </dl>
                </Card>
              </div>
              <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                <Card title="Controls demonstrated"><List items={g.controls} /></Card>
                <Card title="Limitations"><List items={g.limitations} /></Card>
              </div>
              <Card title="Out of scope" subtitle="This project must not be used for:"><List items={g.out_of_scope} /></Card>
            </>
          )}
        </Loadable>
      </Container>
    </>
  );
}
