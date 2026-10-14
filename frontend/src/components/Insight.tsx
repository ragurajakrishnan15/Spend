"use client";

import { useState } from "react";
import { ApiError, apiPost } from "@/lib/api";
import type { NarrativeResponse } from "@/lib/types";

export type InsightSection = "overview" | "forecast" | "segments" | "campaign" | "ops" | "budget" | "macro" | "merchants";

interface Loaded {
  key: string;
  text?: string;
  error?: string;
}

/** Collapsible plain-English summary of a page section, fetched from /api/narrative/{section} when opened. */
export function Insight({ section, context }: { section: InsightSection; context?: Record<string, unknown> }) {
  const key = `${section}:${JSON.stringify(context ?? {})}`;
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const [busy, setBusy] = useState(false);
  const current = loaded && loaded.key === key ? loaded : null;

  async function load() {
    if (current || busy) return;
    setBusy(true);
    try {
      const r = await apiPost<NarrativeResponse>(`/api/narrative/${section}`, { context: context ?? {} });
      setLoaded({ key, text: r.summary });
    } catch (e) {
      setLoaded({ key, error: e instanceof ApiError ? e.message : "Could not load the insight." });
    } finally {
      setBusy(false);
    }
  }

  return (
    <details onToggle={(e) => { if (e.currentTarget.open) void load(); }}
      className="rounded-xl border border-gold-500/40 bg-amber-50/60 p-4 shadow-sm">
      <summary className="cursor-pointer select-none text-sm font-semibold text-navy-900">
        Insight <span className="font-normal text-slate-500">— plain-English summary for stakeholders</span>
      </summary>
      <div className="mt-3 text-sm leading-relaxed text-slate-700" aria-live="polite">
        {busy && !current && <span className="text-slate-500">Generating summary…</span>}
        {current?.text && <p>{current.text}</p>}
        {current?.error && <p className="text-red-800">{current.error}</p>}
      </div>
    </details>
  );
}
