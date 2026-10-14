"use client";

import { useApi } from "@/lib/api";
import type { Filters, Meta } from "@/lib/types";
import { Select } from "./ui";

export const DEFAULT_FILTERS: Filters = { category: "All", channel: "All", region: "All", start: "", end: "" };

export function FilterBar({ filters, onChange, show = ["category", "channel", "region", "dates"] }: {
  filters: Filters;
  onChange: (f: Filters) => void;
  show?: ("category" | "channel" | "region" | "dates")[];
}) {
  const { data: meta } = useApi<Meta>("/api/meta");
  const set = (patch: Partial<Filters>) => onChange({ ...filters, ...patch });
  const dirty = JSON.stringify(filters) !== JSON.stringify(DEFAULT_FILTERS);
  const dateInput = "rounded-lg border border-navy-200 bg-white px-3 py-2 text-sm font-normal normal-case tracking-normal text-navy-900 focus:border-navy-500 focus:outline-none focus:ring-2 focus:ring-navy-200";

  return (
    <form onSubmit={(e) => e.preventDefault()} aria-label="Filters"
      className="flex flex-wrap items-end gap-3 rounded-xl border border-navy-100 bg-white p-4 shadow-sm">
      {show.includes("category") && <Select label="Category" value={filters.category} onChange={(v) => set({ category: v })} options={meta?.categories ?? []} />}
      {show.includes("channel") && <Select label="Channel" value={filters.channel} onChange={(v) => set({ channel: v })} options={meta?.channels ?? []} />}
      {show.includes("region") && <Select label="Region" value={filters.region} onChange={(v) => set({ region: v })} options={meta?.regions ?? []} />}
      {show.includes("dates") && (
        <>
          <label className="flex min-w-[9rem] flex-1 flex-col gap-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
            From
            <input type="date" value={filters.start} min={meta?.start} max={filters.end || meta?.end}
              onChange={(e) => set({ start: e.target.value })} className={dateInput} />
          </label>
          <label className="flex min-w-[9rem] flex-1 flex-col gap-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
            To
            <input type="date" value={filters.end} min={filters.start || meta?.start} max={meta?.end}
              onChange={(e) => set({ end: e.target.value })} className={dateInput} />
          </label>
        </>
      )}
      <button type="button" disabled={!dirty} onClick={() => onChange(DEFAULT_FILTERS)}
        className="rounded-lg border border-navy-200 px-4 py-2 text-sm font-medium text-navy-700 hover:bg-navy-50 disabled:cursor-not-allowed disabled:opacity-40">
        Reset
      </button>
    </form>
  );
}
