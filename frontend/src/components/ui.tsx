"use client";

import type { ReactNode } from "react";

export function PageHeader({ eyebrow, title, description, children }: {
  eyebrow?: string; title: string; description?: string; children?: ReactNode;
}) {
  return (
    <div className="border-b border-navy-100 bg-white">
      <div className="mx-auto flex max-w-7xl flex-col gap-4 px-4 py-8 sm:px-6 lg:px-8">
        {eyebrow && <p className="text-xs font-semibold uppercase tracking-[0.18em] text-navy-500">{eyebrow}</p>}
        <h1 className="font-serif text-3xl font-semibold text-navy-900 sm:text-4xl">{title}</h1>
        {description && <p className="max-w-3xl text-base leading-relaxed text-slate-600">{description}</p>}
        {children}
      </div>
    </div>
  );
}

export function Container({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8 ${className}`}>{children}</div>;
}

export function Card({ title, subtitle, action, children, className = "" }: {
  title?: string; subtitle?: string; action?: ReactNode; children: ReactNode; className?: string;
}) {
  return (
    <section className={`rounded-xl border border-navy-100 bg-white p-5 shadow-sm ${className}`}>
      {(title || action) && (
        <header className="mb-4 flex items-start justify-between gap-3">
          <div>
            {title && <h2 className="text-base font-semibold text-navy-900">{title}</h2>}
            {subtitle && <p className="mt-0.5 text-sm text-slate-500">{subtitle}</p>}
          </div>
          {action}
        </header>
      )}
      {children}
    </section>
  );
}

export function Kpi({ label, value, hint, tone }: {
  label: string; value: string; hint?: string; tone?: "up" | "down" | "neutral";
}) {
  const toneClass = tone === "up" ? "text-emerald-700" : tone === "down" ? "text-red-700" : "text-slate-500";
  return (
    <div className="rounded-xl border border-navy-100 bg-white p-5 shadow-sm">
      <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold tabular-nums text-navy-900 sm:text-3xl">{value}</p>
      {hint && <p className={`mt-1 text-sm ${toneClass}`}>{hint}</p>}
    </div>
  );
}

export function Skeleton({ className = "h-64" }: { className?: string }) {
  return <div role="status" aria-label="Loading" className={`skeleton rounded-xl ${className}`} />;
}

export function LoadingGrid({ kpis = 4, charts = 2 }: { kpis?: number; charts?: number }) {
  return (
    <div className="space-y-6" aria-busy="true">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: kpis }).map((_, i) => <Skeleton key={i} className="h-28" />)}
      </div>
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {Array.from({ length: charts }).map((_, i) => <Skeleton key={i} className="h-80" />)}
      </div>
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-6">
      <h2 className="text-base font-semibold text-red-900">Something went wrong</h2>
      <p className="mt-1 text-sm text-red-800">{message}</p>
      {onRetry && (
        <button onClick={onRetry} className="mt-4 rounded-lg bg-red-900 px-4 py-2 text-sm font-medium text-white hover:bg-red-800">
          Try again
        </button>
      )}
    </div>
  );
}

export function EmptyState({ title = "No data matches these filters", hint = "Widen the date range or reset the filters." }: {
  title?: string; hint?: string;
}) {
  return (
    <div className="rounded-xl border border-dashed border-navy-200 bg-white p-10 text-center">
      <p className="text-base font-semibold text-navy-900">{title}</p>
      <p className="mt-1 text-sm text-slate-500">{hint}</p>
    </div>
  );
}

export function Notice({ children, tone = "info" }: { children: ReactNode; tone?: "info" | "warn" }) {
  const cls = tone === "warn" ? "border-amber-300 bg-amber-50 text-amber-900" : "border-navy-200 bg-navy-50 text-navy-800";
  return <div className={`rounded-lg border px-4 py-3 text-sm leading-relaxed ${cls}`}>{children}</div>;
}

export function DataTable({ columns, rows, caption }: {
  columns: { key: string; label: string; align?: "left" | "right"; render?: (v: unknown, row: Record<string, unknown>) => ReactNode }[];
  rows: Record<string, unknown>[];
  caption?: string;
}) {
  return (
    <div className="overflow-x-auto rounded-lg border border-navy-100">
      <table className="min-w-full divide-y divide-navy-100 text-sm">
        {caption && <caption className="sr-only">{caption}</caption>}
        <thead className="bg-navy-50">
          <tr>
            {columns.map((c) => (
              <th key={c.key} scope="col"
                className={`whitespace-nowrap px-3 py-2.5 text-xs font-semibold uppercase tracking-wide text-navy-700 ${c.align === "right" ? "text-right" : "text-left"}`}>
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-navy-50 bg-white">
          {rows.map((r, i) => (
            <tr key={i} className="hover:bg-navy-50/60">
              {columns.map((c) => (
                <td key={c.key} className={`whitespace-nowrap px-3 py-2 tabular-nums text-slate-700 ${c.align === "right" ? "text-right" : ""}`}>
                  {c.render ? c.render(r[c.key], r) : String(r[c.key] ?? "—")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Select({ label, value, onChange, options, allLabel = "All" }: {
  label: string; value: string; onChange: (v: string) => void; options: string[]; allLabel?: string;
}) {
  return (
    <label className="flex min-w-[9rem] flex-1 flex-col gap-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
      {label}
      <select value={value} onChange={(e) => onChange(e.target.value)}
        className="rounded-lg border border-navy-200 bg-white px-3 py-2 text-sm font-normal normal-case tracking-normal text-navy-900 focus:border-navy-500 focus:outline-none focus:ring-2 focus:ring-navy-200">
        <option value="All">{allLabel}</option>
        {options.map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    </label>
  );
}
