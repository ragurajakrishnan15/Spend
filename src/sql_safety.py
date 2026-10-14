"""Single, shared read-only SQL execution path (used by the API and the Streamlit app).

Defence in depth:
1. Parse with DuckDB's own parser; accept exactly one SELECT statement.
2. Open the database read-only with external access disabled (no file/URL reads,
   no ATTACH/COPY/INSTALL) and lock the configuration so queries cannot undo it.
3. Run each query in a short-lived child process (``sql_worker``) with a DuckDB memory limit and a
   wall-clock timeout; on timeout the process is killed, so even non-interruptible work is stopped.
4. Cap the number of returned rows.
"""
from __future__ import annotations

import json
import pickle
import re
import subprocess
import sys
from pathlib import Path

import duckdb
import pandas as pd

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_LEADING_COMMENTS = re.compile(r"^(\s+|--[^\n]*\n?|/\*.*?\*/)+", re.S)
_ALLOWED_START = re.compile(r"^(select|with|from|values)\b|^\(", re.I)

MAX_QUERY_CHARS = 5000
DEFAULT_MAX_ROWS = 1000
DEFAULT_TIMEOUT_SECONDS = 10.0
MEMORY_LIMIT = "512MB"
MEMORY_LIMIT_BYTES = 512 * 1024 * 1024
MAX_THREADS = 2


class UnsafeQueryError(ValueError):
    """Raised when a query is rejected before execution."""


def validate_query(query: str) -> str:
    if not isinstance(query, str) or not query.strip():
        raise UnsafeQueryError("Query is empty.")
    if len(query) > MAX_QUERY_CHARS:
        raise UnsafeQueryError(f"Query is too long (max {MAX_QUERY_CHARS} characters).")
    try:
        statements = duckdb.extract_statements(query)
    except Exception as exc:  # parser error
        raise UnsafeQueryError(f"Query could not be parsed: {exc}") from exc
    if len(statements) != 1:
        raise UnsafeQueryError("Exactly one statement is allowed.")
    if statements[0].type != duckdb.StatementType.SELECT:
        raise UnsafeQueryError("Only SELECT / WITH queries are allowed.")
    # DuckDB reports some PRAGMA/CALL forms as SELECT, so also require a query-style first keyword.
    body = _LEADING_COMMENTS.sub("", query)
    if not _ALLOWED_START.match(body):
        raise UnsafeQueryError("Only SELECT / WITH queries are allowed.")
    return query.strip().rstrip(";")


def run_sql(query: str, db_path: str | Path, max_rows: int = DEFAULT_MAX_ROWS,
            timeout: float = DEFAULT_TIMEOUT_SECONDS) -> pd.DataFrame:
    """Execute a validated read-only query in a child process (killed on timeout).

    Result `.attrs['truncated']` flags row capping.
    """
    clean = validate_query(query)
    db_path = str(db_path)
    if not Path(db_path).exists():
        raise FileNotFoundError(f"Database not found: {db_path}")
    request = {"query": clean, "db_path": db_path, "max_rows": max_rows, "memory_limit": MEMORY_LIMIT,
               "memory_bytes": MEMORY_LIMIT_BYTES, "threads": MAX_THREADS}
    try:
        proc = subprocess.run([sys.executable, "-m", "src.sql_worker"], input=json.dumps(request).encode(),
                              capture_output=True, timeout=timeout, cwd=str(_PROJECT_ROOT))
    except subprocess.TimeoutExpired as exc:  # run() kills the child before raising
        raise UnsafeQueryError(f"Query exceeded the {timeout:g}s time limit.") from exc
    try:
        status, *rest = pickle.loads(proc.stdout)
    except Exception as exc:  # child died (e.g. killed by the OS for memory) before replying
        raise UnsafeQueryError("Query was terminated: it exceeded the resource limits.") from exc
    if status == "error":
        raise RuntimeError(rest[0])
    columns, rows = rest
    truncated = len(rows) > max_rows
    out = pd.DataFrame(rows[:max_rows], columns=columns)
    out.attrs["truncated"] = truncated
    return out
