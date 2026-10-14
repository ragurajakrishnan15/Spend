"""Child-process entry point for ``sql_safety.run_sql``.

Runs one already-validated query against a read-only DuckDB file and writes a pickle of
``("ok", columns, rows)`` or ``("error", message)`` to stdout. It deliberately imports only
``duckdb`` so start-up stays fast. The parent enforces the wall-clock limit by killing this
process, which also covers allocations DuckDB cannot interrupt.
Invoked as:  python -m src.sql_worker   (JSON request on stdin)
"""
import json
import pickle
import sys


def main() -> None:
    req = json.load(sys.stdin)
    out = sys.stdout.buffer
    try:
        if sys.platform != "win32":  # hard address-space cap where the OS supports it
            import resource
            cap = int(req["memory_bytes"]) * 4
            resource.setrlimit(resource.RLIMIT_AS, (cap, cap))
        import duckdb
        con = duckdb.connect(req["db_path"], read_only=True, config={
            "enable_external_access": False, "memory_limit": req["memory_limit"], "threads": req["threads"]})
        try:
            con.execute("SET lock_configuration = true")
            cur = con.execute(req["query"])
            columns = [d[0] for d in cur.description]
            rows = cur.fetchmany(req["max_rows"] + 1)
        finally:
            con.close()
        payload = ("ok", columns, rows)
    except MemoryError:
        payload = ("error", "Out of Memory Error: query exceeded the memory limit")
    except Exception as exc:  # duckdb errors, blocked file access, bad columns ...
        payload = ("error", str(exc).splitlines()[0] if str(exc) else type(exc).__name__)
    out.write(pickle.dumps(payload))
    out.flush()


if __name__ == "__main__":
    main()
