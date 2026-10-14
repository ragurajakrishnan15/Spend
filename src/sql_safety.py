"""Single, shared read-only SQL execution path (used by the API and the Streamlit app).

Defence in depth:
1. Parse with DuckDB's own parser; accept exactly one SELECT statement.
2. Open the database read-only with external access disabled (no file/URL reads,
   no ATTACH/COPY/INSTALL) and lock the configuration so queries cannot undo it.
3. Cap the number of returned rows.
"""
from __future__ import annotations

from pathlib import Path

import re

import duckdb
import pandas as pd

_LEADING_COMMENTS = re.compile(r"^(\s+|--[^\n]*\n?|/\*.*?\*/)+", re.S)
_ALLOWED_START = re.compile(r"^(select|with|from|values)\b|^\(", re.I)

MAX_QUERY_CHARS = 5000
DEFAULT_MAX_ROWS = 1000


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


def run_sql(query: str, db_path: str | Path, max_rows: int = DEFAULT_MAX_ROWS) -> pd.DataFrame:
    """Execute a validated read-only query. Result `.attrs['truncated']` flags row capping."""
    clean = validate_query(query)
    db_path = str(db_path)
    if not Path(db_path).exists():
        raise FileNotFoundError(f"Database not found: {db_path}")
    con = duckdb.connect(db_path, read_only=True, config={"enable_external_access": False})
    try:
        con.execute("SET lock_configuration = true")
        cur = con.execute(clean)
        columns = [d[0] for d in cur.description]
        rows = cur.fetchmany(max_rows + 1)
    finally:
        con.close()
    truncated = len(rows) > max_rows
    out = pd.DataFrame(rows[:max_rows], columns=columns)
    out.attrs["truncated"] = truncated
    return out
