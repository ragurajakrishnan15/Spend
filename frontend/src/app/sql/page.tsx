"use client";

import { useState } from "react";
import { Loadable } from "@/components/Loadable";
import { Card, Container, DataTable, ErrorState, Notice, PageHeader, Skeleton } from "@/components/ui";
import { apiPost, useApi } from "@/lib/api";
import { int } from "@/lib/format";
import type { SqlExamples, SqlResult } from "@/lib/types";

type Dialect = "duckdb" | "snowflake" | "athena";
const DIALECTS: { id: Dialect; label: string }[] = [
  { id: "duckdb", label: "DuckDB (runs here)" },
  { id: "snowflake", label: "Snowflake" },
  { id: "athena", label: "AWS Athena" },
];

const DEFAULT_QUERY = "SELECT category, COUNT(*) AS transactions, ROUND(SUM(amount), 2) AS spend FROM transactions GROUP BY category ORDER BY spend DESC";

export default function SqlPage() {
  const examples = useApi<SqlExamples>("/api/sql/examples");
  const [query, setQuery] = useState(DEFAULT_QUERY);
  const [result, setResult] = useState<SqlResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [dialect, setDialect] = useState<Dialect>("duckdb");
  const [selected, setSelected] = useState<string | null>(null);

  async function run() {
    setRunning(true);
    setError(null);
    try {
      setResult(await apiPost<SqlResult>("/api/sql", { query }));
    } catch (e) {
      setResult(null);
      setError(e instanceof Error ? e.message : "Query failed");
    } finally {
      setRunning(false);
    }
  }

  return (
    <>
      <PageHeader eyebrow="SQL Explorer" title="Query the synthetic ledger"
        description="Run read-only DuckDB SQL against the transactions table. Queries are parsed server-side: one SELECT/WITH statement, external file access disabled, results capped." />
      <Container className="space-y-6">
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <div className="space-y-4 lg:col-span-2">
            <Card title="Query">
              <label htmlFor="sql" className="sr-only">SQL query</label>
              <textarea id="sql" value={query} onChange={(e) => setQuery(e.target.value)} spellCheck={false} rows={7}
                onKeyDown={(e) => { if ((e.ctrlKey || e.metaKey) && e.key === "Enter") run(); }}
                className="w-full rounded-lg border border-navy-200 bg-navy-950 p-4 font-mono text-sm leading-relaxed text-navy-50 focus:border-navy-400 focus:outline-none focus:ring-2 focus:ring-navy-200" />
              <div className="mt-3 flex flex-wrap items-center gap-3">
                <button type="button" onClick={run} disabled={running || !query.trim()}
                  className="rounded-lg bg-navy-900 px-5 py-2.5 text-sm font-semibold text-white hover:bg-navy-800 disabled:opacity-50">
                  {running ? "Running…" : "Run query"}
                </button>
                <span className="text-xs text-slate-500">Ctrl + Enter to run</span>
              </div>
            </Card>

            {dialect !== "duckdb" && (
              <Loadable state={examples} skeleton={<Skeleton className="h-40" />}>
                {(ex) => {
                  const e = ex.examples.find((x) => x.name === selected);
                  const label = dialect === "snowflake" ? "Snowflake" : "AWS Athena";
                  return (
                    <Card title={`${label} equivalent`} subtitle={e ? e.name : "Pick an example to see its translation"}>
                      <Notice tone="warn">
                        Hand-written dialect translation. It has <strong>not been executed</strong> against a {label} account;
                        only the DuckDB version runs in this app.
                      </Notice>
                      {e && (
                        <pre className="mt-3 overflow-x-auto rounded-lg bg-navy-950 p-4 font-mono text-sm leading-relaxed text-navy-50">
                          {e[dialect]}
                        </pre>
                      )}
                    </Card>
                  );
                }}
              </Loadable>
            )}

            {error && <ErrorState message={error} />}
            {running && !result && <Skeleton className="h-48" />}
            {result && (
              <Card title="Results" subtitle={`${int(result.row_count)} row${result.row_count === 1 ? "" : "s"}${result.truncated ? " (truncated)" : ""}`}>
                {result.rows.length === 0 ? (
                  <p className="text-sm text-slate-500">The query returned no rows.</p>
                ) : (
                  <div className="max-h-[28rem] overflow-auto">
                    <DataTable caption="Query results"
                      columns={result.columns.map((c, i) => ({
                        key: String(i), label: c,
                        align: typeof result.rows[0][i] === "number" ? ("right" as const) : ("left" as const),
                      }))}
                      rows={result.rows.map((r) => Object.fromEntries(r.map((v, i) => [String(i), v])))} />
                  </div>
                )}
                {result.truncated && <Notice tone="warn">Only the first rows are shown. Add a LIMIT or aggregate to narrow the output.</Notice>}
              </Card>
            )}
          </div>

          <div className="space-y-4">
            <Loadable state={examples} skeleton={<Skeleton className="h-72" />}>
              {(ex) => (
                <>
                  <Card title="Examples">
                    <div role="group" aria-label="Warehouse mode" className="mb-3 flex flex-wrap gap-1.5">
                      {DIALECTS.map((d) => (
                        <button key={d.id} type="button" onClick={() => setDialect(d.id)} aria-pressed={dialect === d.id}
                          className={`rounded-md border px-2.5 py-1 text-xs font-semibold ${dialect === d.id ? "border-navy-900 bg-navy-900 text-white" : "border-navy-200 bg-white text-navy-800 hover:bg-navy-50"}`}>
                          {d.label}
                        </button>
                      ))}
                    </div>
                    <ul className="space-y-2">
                      {ex.examples.map((e) => (
                        <li key={e.name}>
                          <button type="button" onClick={() => { setQuery(e.query); setSelected(e.name); }}
                            className="w-full rounded-lg border border-navy-100 px-3 py-2 text-left text-sm font-medium text-navy-800 hover:border-navy-300 hover:bg-navy-50">
                            {e.name}
                          </button>
                        </li>
                      ))}
                    </ul>
                  </Card>
                  <Card title="transactions table">
                    <ul className="space-y-1 font-mono text-xs">
                      {ex.schema.map((s) => (
                        <li key={s.column} className="flex justify-between gap-2">
                          <span className="text-navy-900">{s.column}</span>
                          <span className="text-slate-500">{s.type.replace("datetime64[ns]", "timestamp").replace("object", "varchar").replace("int64", "integer").replace("float64", "double")}</span>
                        </li>
                      ))}
                    </ul>
                  </Card>
                </>
              )}
            </Loadable>
          </div>
        </div>
      </Container>
    </>
  );
}
