"""
Data quality reporting.

Every curated table is profiled, and the profile is written alongside it. The
point is that a downstream module can check whether a field is trustworthy
before relying on it, instead of discovering a 40% null rate through a wrong
answer in front of an investigator.

Nothing here modifies data. It only measures and reports.
"""

from __future__ import annotations

import pandas as pd


def profile_table(name: str, df: pd.DataFrame,
                  key_columns: list[str] | None = None) -> dict:
    if df is None or df.empty:
        return {"table": name, "rows": 0, "status": "EMPTY"}

    keys = [k for k in (key_columns or []) if k in df.columns]
    prof = {
        "table": name,
        "rows": int(len(df)),
        "columns": int(len(df.columns)),
        "duplicate_rows": int(df.duplicated().sum()),
        "memory_mb": round(df.memory_usage(deep=True).sum() / 1e6, 1),
    }
    if keys:
        prof["key_columns"] = keys
        prof["duplicate_keys"] = int(df.duplicated(subset=keys).sum())
        prof["key_is_unique"] = prof["duplicate_keys"] == 0
        prof["key_null_rows"] = int(df[keys].isna().any(axis=1).sum())

    nulls = df.isna().mean().mul(100).round(2)
    prof["columns_fully_null"] = sorted(nulls[nulls == 100].index.tolist())
    worst = nulls[(nulls > 0) & (nulls < 100)].sort_values(ascending=False)
    prof["highest_null_pct"] = {k: float(v) for k, v in worst.head(8).items()}

    num = df.select_dtypes("number")
    if not num.empty:
        neg = {c: int((num[c] < 0).sum()) for c in num.columns
               if (num[c] < 0).any()}
        if neg:
            prof["negative_values"] = neg
    return prof


def orphan_check(child: pd.DataFrame, child_key: str,
                 parent: pd.DataFrame, parent_key: str,
                 label: str) -> dict:
    """
    Count child rows whose key is absent from the parent.

    Orphans are reported rather than deleted. A high orphan rate usually means
    the two tables cover different populations - which is a finding, not a bug
    to silently discard rows over.
    """
    if child is None or child.empty or parent is None or parent.empty:
        return {"relationship": label, "status": "skipped"}
    if child_key not in child.columns or parent_key not in parent.columns:
        return {"relationship": label, "status": "column missing"}

    child_ids = child[child_key].dropna().astype(str)
    parent_ids = set(parent[parent_key].dropna().astype(str))
    orphans = ~child_ids.isin(parent_ids)
    n = int(orphans.sum())
    return {
        "relationship": label,
        "child_rows_with_key": int(len(child_ids)),
        "orphan_rows": n,
        "orphan_pct": round(n / max(len(child_ids), 1) * 100, 2),
        "status": "ok" if n == 0 else ("high" if n / max(len(child_ids), 1) > 0.5
                                       else "some"),
    }


def coverage_by_year(df: pd.DataFrame, year_col: str = "year") -> dict:
    if df is None or df.empty or year_col not in df.columns:
        return {}
    counts = df[year_col].value_counts().sort_index()
    return {int(k): int(v) for k, v in counts.items()}
