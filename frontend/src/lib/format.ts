export const usd = (n: number, digits = 0) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: digits, minimumFractionDigits: digits }).format(n);

export const compactUsd = (n: number) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", notation: "compact", maximumFractionDigits: 1 }).format(n);

export const int = (n: number) => new Intl.NumberFormat("en-US").format(Math.round(n));

export const pct = (n: number, digits = 1) => `${(n * 100).toFixed(digits)}%`;

export const signedPct = (n: number, digits = 1) => `${n >= 0 ? "+" : ""}${n.toFixed(digits)}%`;

export function monthLabel(ym: string): string {
  const [y, m] = ym.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, 1)).toLocaleDateString("en-US", { month: "short", year: "2-digit", timeZone: "UTC" });
}

export const humanize = (s: string) => s.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());

// Colour-blind-considerate categorical palette on a navy base.
export const CHART_COLORS = ["#1b3b69", "#3b82c4", "#0f9d8a", "#c98a1b", "#7c6cc4", "#c2410c", "#64748b", "#be3a6b"];
