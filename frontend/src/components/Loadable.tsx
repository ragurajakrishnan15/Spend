"use client";

import type { ReactNode } from "react";
import { ErrorState, LoadingGrid } from "./ui";

export function Loadable<T>({ state, children, skeleton }: {
  state: { data?: T; error?: string; loading: boolean; reload: () => void };
  children: (data: T) => ReactNode;
  skeleton?: ReactNode;
}) {
  if (state.error) return <ErrorState message={state.error} onRetry={state.reload} />;
  if (state.loading || state.data === undefined) return <>{skeleton ?? <LoadingGrid />}</>;
  return <>{children(state.data)}</>;
}
