"use client";

import { useCallback, useEffect, useState } from "react";
import type { Filters } from "./types";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function readError(res: Response): Promise<string> {
  try {
    const body = await res.json();
    if (typeof body?.detail === "string") return body.detail;
    if (Array.isArray(body?.detail)) return body.detail.map((d: { msg: string }) => d.msg).join("; ");
  } catch {
    /* fall through */
  }
  return `Request failed (${res.status})`;
}

export async function apiGet<T>(url: string, signal?: AbortSignal): Promise<T> {
  let res: Response;
  try {
    res = await fetch(url, { signal, headers: { Accept: "application/json" } });
  } catch (e) {
    if (signal?.aborted) throw e;
    throw new ApiError("Cannot reach the SpendIQ API. Is the backend running on port 8000?", 0);
  }
  if (!res.ok) throw new ApiError(await readError(res), res.status);
  return res.json() as Promise<T>;
}

export async function apiPost<T>(url: string, body: unknown): Promise<T> {
  let res: Response;
  try {
    res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    throw new ApiError("Cannot reach the SpendIQ API. Is the backend running on port 8000?", 0);
  }
  if (!res.ok) throw new ApiError(await readError(res), res.status);
  return res.json() as Promise<T>;
}

export function buildQuery(params: Record<string, string | number | undefined | null>): string {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "" || v === "All") continue;
    q.set(k, String(v));
  }
  const s = q.toString();
  return s ? `?${s}` : "";
}

export function filterQuery(f: Filters, extra: Record<string, string | number | undefined> = {}): string {
  return buildQuery({ ...f, ...extra });
}

interface ApiState<T> {
  key: string;
  data?: T;
  error?: string;
}

/** Fetch JSON for `url`; refetches when the url changes. `loading` is derived, never set synchronously. */
export function useApi<T>(url: string | null) {
  const [tick, setTick] = useState(0);
  const [state, setState] = useState<ApiState<T> | null>(null);
  const key = `${url}#${tick}`;

  useEffect(() => {
    if (!url) return;
    const ctrl = new AbortController();
    apiGet<T>(url, ctrl.signal)
      .then((data) => setState({ key, data }))
      .catch((e: unknown) => {
        if (ctrl.signal.aborted) return;
        setState({ key, error: e instanceof Error ? e.message : "Unexpected error" });
      });
    return () => ctrl.abort();
  }, [url, key]);

  const current = state && state.key === key ? state : null;
  const reload = useCallback(() => setTick((t) => t + 1), []);
  return { data: current?.data, error: current?.error, loading: !!url && !current, reload };
}
