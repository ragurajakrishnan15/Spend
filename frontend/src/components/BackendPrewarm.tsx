"use client";

/**
 * BackendPrewarm
 *
 * Silently hits /api/health as soon as the app mounts so the Railway backend
 * wakes up from its idle sleep *before* the user navigates to a data page.
 *
 * While the backend is still waking up a subtle dismissible banner is shown.
 * Once the health check returns OK (or fails) the banner disappears automatically.
 */

import { useEffect, useState } from "react";

type Status = "warming" | "ready" | "error";

export default function BackendPrewarm() {
    const [status, setStatus] = useState<Status>("warming");
    const [dismissed, setDismissed] = useState(false);

    useEffect(() => {
        let cancelled = false;
        let timer: ReturnType<typeof setTimeout> | undefined;
        const start = Date.now();

        // A cold Railway start can take ~30-60 s and returns 502/timeouts meanwhile,
        // so keep retrying with exponential backoff (1 s, 2 s, 4 s ... capped at 8 s)
        // and only report an error once the total wait budget is spent.
        const MAX_WAIT_MS = 90_000;
        const REQUEST_TIMEOUT_MS = 15_000;

        async function ping(attempt: number) {
            const controller = new AbortController();
            const abort = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
            let ok = false;
            try {
                const res = await fetch("/api/health", {
                    headers: { Accept: "application/json" },
                    cache: "no-store",
                    signal: controller.signal,
                });
                ok = res.ok;
            } catch {
                ok = false;
            } finally {
                clearTimeout(abort);
            }
            if (cancelled) return;

            if (ok) {
                const elapsed = Date.now() - start;
                setStatus("ready");
                // Auto-hide the banner after 2 s so it doesn't linger on fast connections
                setTimeout(() => setDismissed(true), elapsed > 3000 ? 2000 : 0);
                return;
            }

            const delay = Math.min(1000 * 2 ** attempt, 8000);
            if (Date.now() - start + delay > MAX_WAIT_MS) {
                setStatus("error");
                return;
            }
            timer = setTimeout(() => ping(attempt + 1), delay);
        }

        ping(0);
        return () => {
            cancelled = true;
            if (timer) clearTimeout(timer);
        };
    }, []);

    // Nothing to show once dismissed or immediately ready (fast local dev)
    if (dismissed || status === "ready") return null;

    const isError = status === "error";

    return (
        <div
            role="status"
            aria-live="polite"
            style={{
                position: "fixed",
                bottom: "1.25rem",
                right: "1.25rem",
                zIndex: 50,
                display: "flex",
                alignItems: "center",
                gap: "0.6rem",
                padding: "0.6rem 1rem",
                borderRadius: "0.625rem",
                fontSize: "0.8125rem",
                fontFamily: "var(--font-inter, sans-serif)",
                fontWeight: 500,
                lineHeight: 1.4,
                boxShadow: "0 4px 20px rgba(0,0,0,0.18)",
                background: isError ? "#fef2f2" : "#f0f9ff",
                color: isError ? "#b91c1c" : "#0369a1",
                border: `1px solid ${isError ? "#fecaca" : "#bae6fd"}`,
                maxWidth: "22rem",
                transition: "opacity 0.3s",
            }}
        >
            {!isError && (
                <span
                    aria-hidden="true"
                    style={{
                        width: "0.7rem",
                        height: "0.7rem",
                        borderRadius: "50%",
                        flexShrink: 0,
                        background: "#38bdf8",
                        animation: "spendiq-pulse 1.4s ease-in-out infinite",
                    }}
                />
            )}
            <span>
                {isError
                    ? "⚠️ Backend is unreachable. Some pages may not load."
                    : "Waking up the API — first page load may take ~30 s…"}
            </span>
            <button
                onClick={() => setDismissed(true)}
                aria-label="Dismiss"
                style={{
                    marginLeft: "auto",
                    background: "none",
                    border: "none",
                    cursor: "pointer",
                    padding: "0 0.2rem",
                    fontSize: "1rem",
                    lineHeight: 1,
                    color: "inherit",
                    opacity: 0.6,
                }}
            >
                ×
            </button>
            <style>{`
        @keyframes spendiq-pulse {
          0%, 100% { opacity: 1; transform: scale(1); }
          50%  { opacity: 0.4; transform: scale(0.75); }
        }
      `}</style>
        </div>
    );
}
