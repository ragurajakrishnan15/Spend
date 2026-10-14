"use client";

import { useApi } from "@/lib/api";
import { int } from "@/lib/format";
import type { Meta } from "@/lib/types";

export function LiveStats() {
  const { data, error } = useApi<Meta>("/api/meta");
  const items = data
    ? [
        ["Transactions", int(data.rows)],
        ["Customers", int(data.customers)],
        ["Months of history", String(data.months)],
        ["Merchant categories", String(data.categories.length)],
      ]
    : null;
  return (
    <div className="mt-12 grid grid-cols-2 gap-4 border-t border-white/15 pt-8 sm:grid-cols-4" aria-live="polite">
      {items
        ? items.map(([l, v]) => (
            <div key={l}>
              <p className="text-3xl font-semibold tabular-nums">{v}</p>
              <p className="mt-1 text-xs uppercase tracking-wider text-navy-200">{l}</p>
            </div>
          ))
        : (
          <p className="col-span-full text-sm text-navy-200">
            {error ? "Start the API backend to see live dataset statistics." : "Loading dataset statistics…"}
          </p>
        )}
    </div>
  );
}
