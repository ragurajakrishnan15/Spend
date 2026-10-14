"use client";

import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Loadable } from "@/components/Loadable";
import { Insight } from "@/components/Insight";
import { Card, Container, ErrorState, Kpi, Notice, PageHeader } from "@/components/ui";
import { useApi } from "@/lib/api";
import { humanize, int, pct } from "@/lib/format";
import type { CampaignResponse } from "@/lib/types";

export default function CampaignsPage() {
  const state = useApi<CampaignResponse>("/api/campaign");
  return (
    <>
      <PageHeader eyebrow="Campaign Analytics" title="Campaign response modelling"
        description="A transaction-level classifier trained on earlier transactions and scored on later ones. A synthetic demonstration — not a targeting or eligibility model." />
      <Container className="space-y-6">
        <Loadable state={state}>
          {(d) => {
            if (d.error) return <ErrorState message={d.error} />;
            const m = d.metrics;
            const cm = d.confusion;
            const maxImp = Math.max(...d.importance.map((i) => Math.abs(i.importance)), 1e-9);
            return (
              <>
                <Notice tone="warn">
                  Synthetic transaction-level demonstration: each row is one transaction and the same customers appear in both the training and test periods.
                  Scores must not be used for credit, eligibility or access decisions.
                </Notice>
                <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
                  <Kpi label="ROC-AUC" value={m.roc_auc.toFixed(3)} hint={`Exposure only: ${d.baseline.roc_auc_exposure_only.toFixed(3)}`} />
                  <Kpi label="Precision" value={m.precision.toFixed(3)} />
                  <Kpi label="Recall" value={m.recall.toFixed(3)} />
                  <Kpi label="F1" value={m.f1.toFixed(3)} />
                  <Kpi label="Test response rate" value={pct(Number(d.split.test_response_rate))} hint={`${int(Number(d.split.test_rows))} test rows`} />
                </div>

                <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                  <Card title="Lift by score decile" subtitle="Observed response rate on held-out transactions (decile 10 = highest scores)">
                    <div className="h-72 w-full" role="img" aria-label="Bar chart of response rate by score decile">
                      <ResponsiveContainer>
                        <BarChart data={d.lift} margin={{ left: 4, right: 12 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#dbe5f3" vertical={false} />
                          <XAxis dataKey="decile" label={{ value: "Score decile", position: "insideBottom", offset: -2 }} />
                          <YAxis tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} width={48} />
                          <Tooltip formatter={(v) => pct(Number(v))} labelFormatter={(l) => `Decile ${l}`} />
                          <Bar dataKey="response_rate" name="Response rate" fill="#1b3b69" radius={[4, 4, 0, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  </Card>
                  <Card title="Permutation importance" subtitle="Drop in test ROC-AUC when a feature is shuffled">
                    <div className="h-72 w-full" role="img" aria-label="Bar chart of permutation importance">
                      <ResponsiveContainer>
                        <BarChart data={d.importance.map((i) => ({ ...i, label: humanize(i.feature) }))} layout="vertical" margin={{ left: 24, right: 16 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#dbe5f3" horizontal={false} />
                          <XAxis type="number" domain={[Math.min(0, -maxImp * 0.1), "auto"]} tickFormatter={(v) => Number(v).toFixed(3)} />
                          <YAxis type="category" dataKey="label" width={150} />
                          <Tooltip formatter={(v) => Number(v).toFixed(4)} />
                          <Bar dataKey="importance" name="AUC drop" radius={[0, 4, 4, 0]}>
                            {d.importance.map((i, k) => <Cell key={k} fill={i.importance > 0 ? "#1b3b69" : "#94a3b8"} />)}
                          </Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  </Card>
                </div>

                <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                  <Card title="Confusion matrix" subtitle="Held-out transactions, threshold 0.5">
                    <div className="grid grid-cols-[auto_1fr_1fr] gap-2 text-center text-sm">
                      <div />
                      <div className="font-semibold text-slate-500">Predicted no</div>
                      <div className="font-semibold text-slate-500">Predicted response</div>
                      <div className="self-center text-right font-semibold text-slate-500">Actual no</div>
                      <div className="rounded-lg bg-navy-50 p-4"><p className="text-xl font-semibold text-navy-900">{int(cm.tn)}</p><p className="text-xs text-slate-500">True negatives</p></div>
                      <div className="rounded-lg bg-amber-50 p-4"><p className="text-xl font-semibold text-amber-900">{int(cm.fp)}</p><p className="text-xs text-slate-500">False positives</p></div>
                      <div className="self-center text-right font-semibold text-slate-500">Actual response</div>
                      <div className="rounded-lg bg-amber-50 p-4"><p className="text-xl font-semibold text-amber-900">{int(cm.fn)}</p><p className="text-xs text-slate-500">False negatives</p></div>
                      <div className="rounded-lg bg-navy-50 p-4"><p className="text-xl font-semibold text-navy-900">{int(cm.tp)}</p><p className="text-xs text-slate-500">True positives</p></div>
                    </div>
                  </Card>
                  <Card title="Evaluation design">
                    <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
                      <dt className="text-slate-500">Training window</dt>
                      <dd className="text-navy-900">{String(d.split.train_start)} → {String(d.split.train_end)}</dd>
                      <dt className="text-slate-500">Test window</dt>
                      <dd className="text-navy-900">{String(d.split.test_start)} → {String(d.split.test_end)}</dd>
                      <dt className="text-slate-500">Training rows</dt>
                      <dd className="tabular-nums text-navy-900">{int(Number(d.split.train_rows))}</dd>
                      <dt className="text-slate-500">Features</dt>
                      <dd className="text-navy-900">{d.features.map(humanize).join(", ")}</dd>
                    </dl>
                  </Card>
                </div>
                <ul className="list-disc space-y-1 pl-5 text-sm text-slate-600">
                  {d.notes.map((n) => <li key={n}>{n}</li>)}
                </ul>
                <Insight section="campaign" context={{ roc_auc: d.metrics.roc_auc }} />
              </>
            );
          }}
        </Loadable>
      </Container>
    </>
  );
}
