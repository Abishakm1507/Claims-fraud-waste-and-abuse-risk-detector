"""
Warehouse connection.

TWO SOURCES, ONE PRECEDENCE RULE
1. The ETL's curated tables, if present. These are the shared source of truth -
   every fact computed once, so the assistant and the ML agents can never report
   different numbers for the same question.
2. The assistant's own DuckDB file, built from raw CSVs, as a fallback so the
   assistant still runs before the ETL has been executed.

Which source is in use is reported rather than silent. A number's provenance
should never be ambiguous.
"""

from __future__ import annotations

from typing import Any

from backend.config import WAREHOUSE_PATH

_con = None
_tables: set[str] | None = None
_source: str = "none"


def source() -> str:
    """'curated', 'local warehouse', 'both', or 'none'."""
    get_connection()
    return _source


def is_built() -> bool:
    """True if either data source is available."""
    from backend.data.curated_loader import find_curated_dir

    return WAREHOUSE_PATH.exists() or find_curated_dir() is not None


def get_connection():
    """Shared connection over curated tables and/or the local warehouse."""
    global _con, _tables, _source
    if _con is not None:
        return _con

    from backend.data import curated_loader

    curated = curated_loader.find_curated_dir()
    have_local = WAREHOUSE_PATH.exists()
    if curated is None and not have_local:
        return None

    import duckdb

    if have_local and curated is None:
        # Read-only: the assistant must never modify source data.
        _con = duckdb.connect(str(WAREHOUSE_PATH), read_only=True)
        _source = "local warehouse"
    else:
        # Curated views must be created, which a read-only connection forbids,
        # so an in-memory database holds the views and ATTACHes the local file
        # read-only for any table curated output does not provide.
        _con = duckdb.connect(":memory:")
        if have_local:
            try:
                _con.execute(
                    f"ATTACH '{WAREHOUSE_PATH.as_posix()}' AS localdb (READ_ONLY)")
                for (name,) in _con.execute(
                        "SELECT table_name FROM localdb.information_schema.tables"
                ).fetchall():
                    _con.execute(f"CREATE OR REPLACE VIEW {name} AS "
                                 f"SELECT * FROM localdb.{name}")
                _source = "local warehouse"
            except Exception as exc:                           # noqa: BLE001
                print(f"  ! could not attach local warehouse: "
                      f"{type(exc).__name__}: {exc}")

    if curated is not None:
        try:
            registered = curated_loader.register(_con, curated)
            if registered:
                curated_loader.build_compatibility_views(_con)
                curated_loader.build_provider_summary(_con)
                _source = "curated + local warehouse" if have_local else "curated"
        except Exception as exc:                               # noqa: BLE001
            print(f"  ! could not load curated tables: {type(exc).__name__}: {exc}")

        # Risk model output is a model artifact rather than ETL output, so it
        # is located and registered separately - and its absence must not stop
        # the curated tables from loading.
        try:
            curated_loader.register_risk(_con, curated)
        except Exception as exc:                               # noqa: BLE001
            print(f"  ! could not load provider risk scores: "
                  f"{type(exc).__name__}: {exc}")

    _tables = {r[0] for r in _con.execute("SHOW TABLES").fetchall()}
    return _con


def tables() -> set[str]:
    get_connection()
    return _tables or set()


def columns(table: str) -> set[str]:
    """
    Column names of a table.

    Used so queries can adapt to schema differences between ETL versions
    rather than failing on a renamed column.
    """
    con = get_connection()
    if con is None:
        return set()
    try:
        return {r[0] for r in con.execute(f"DESCRIBE {table}").fetchall()}
    except Exception:                                          # noqa: BLE001
        return set()


def has(*names: str) -> bool:
    """True only if every named table exists."""
    t = tables()
    return all(n in t for n in names)


def query(sql: str, params: list | None = None) -> list[dict[str, Any]]:
    """Run SQL and return rows as dicts. Always parameterised by the caller."""
    con = get_connection()
    if con is None:
        return []
    cur = con.execute(sql, params or [])
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def one(sql: str, params: list | None = None) -> dict[str, Any] | None:
    rows = query(sql, params)
    return rows[0] if rows else None


def scalar(sql: str, params: list | None = None):
    con = get_connection()
    if con is None:
        return None
    row = con.execute(sql, params or []).fetchone()
    return row[0] if row else None
