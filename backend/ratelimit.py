"""Small in-memory sliding-window rate limiter for the expensive endpoints.

State is per process (fine for the single-instance demo deploy). Disable with SPENDIQ_RATE_LIMIT=0.
The client IP comes from X-Forwarded-For: the browser -> Vercel rewrite -> Railway chain adds two
entries, so the entry ``SPENDIQ_PROXY_HOPS`` from the right (default 2) is used; spoofed leftmost
values are ignored. Falls back to the socket peer when the header is absent or too short.
"""
from __future__ import annotations

import os
import threading
import time
from collections import deque

from fastapi import HTTPException, Request

_PROXY_HOPS = max(1, int(os.environ.get("SPENDIQ_PROXY_HOPS", "2")))
_MAX_KEYS = 10_000

_lock = threading.Lock()
_hits: dict[tuple[str, str], deque[float]] = {}


def enabled() -> bool:
    return os.environ.get("SPENDIQ_RATE_LIMIT", "1") != "0"


def client_ip(request: Request) -> str:
    parts = [p.strip() for p in request.headers.get("x-forwarded-for", "").split(",") if p.strip()]
    if len(parts) >= _PROXY_HOPS:
        return parts[-_PROXY_HOPS]
    return request.client.host if request.client else "unknown"


def reset() -> None:
    with _lock:
        _hits.clear()


def limit(bucket: str, max_requests: int, window_seconds: float = 60.0):
    """FastAPI dependency allowing ``max_requests`` per client per ``window_seconds`` for ``bucket``."""
    def dependency(request: Request) -> None:
        if not enabled():
            return
        key, now = (bucket, client_ip(request)), time.monotonic()
        with _lock:
            q = _hits.setdefault(key, deque())
            while q and now - q[0] >= window_seconds:
                q.popleft()
            if len(q) >= max_requests:
                retry = max(1, int(window_seconds - (now - q[0])) + 1)
                raise HTTPException(429, f"Rate limit exceeded for this endpoint. Try again in {retry}s.",
                                    headers={"Retry-After": str(retry)})
            q.append(now)
            if len(_hits) > _MAX_KEYS:  # drop idle clients so the table cannot grow without bound
                for k in [k for k, v in _hits.items() if not v or now - v[-1] >= window_seconds]:
                    del _hits[k]
    return dependency
