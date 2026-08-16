"""
validate_claim_export.py

Validates the Claims ML export update against the pre-change snapshot:

* row counts / CLAIM_ID uniqueness and values
* canonical risk fields (CLAIM_RISK_SCORE, FINAL_RISK_LEVEL,
  FINAL_RISK_PRIORITY, FINAL_CLAIM_RANK) are byte-identical before/after
* no new NaN introduced into previously existing columns
* no existing columns removed
* PROVIDER_ID_TYPE mapping is correct per claim type and null when
  PROVIDER_ID is missing (unified CSV, claim_360 CSV and claims.db tables)

Usage
-----
    python validate_claim_export.py [--before-dir PATH]

Run it after re-running finalize_claim_risk.py / build_claim_360.py /
sync_claims_db.py. Exit code is 0 when all checks pass.
"""

import argparse
import sqlite3
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

CANONICAL_RISK_FIELDS = [
    "CLAIM_RISK_SCORE",
    "FINAL_RISK_LEVEL",
    "FINAL_RISK_PRIORITY",
    "FINAL_CLAIM_RANK",
]

# All score/model-output columns that must remain untouched.
MODEL_OUTPUT_FIELDS = [
    "MODEL_SCORE",
    "IF_score",
    "LOF_score",
    "OCSVM_score",
    "carrier_ensemble_score",
    "isolation_forest_score",
    "lof_score",
    "one_class_svm_score",
    "ensemble_risk_score",
    "isolation_forest_flag",
    "lof_flag",
    "one_class_svm_flag",
    "model_consensus_count",
    "model_consensus",
    "risk_percentile",
    "risk_rank",
    "risk_band",
    "outpatient_ensemble_score",
    "outpatient_risk_rank",
    "outpatient_risk_band",
    "carrier_risk_rank",
    "carrier_risk_band",
]

EXPECTED_ID_TYPE = {
    "CARRIER": "NPI",
    "INPATIENT": "PRVDR_NUM",
    "OUTPATIENT": "PRVDR_NUM",
}


def _failures() -> list:
    return _FAILURES


_FAILURES: list = []


def _series_equal(a: pd.Series, b: pd.Series) -> bool:
    """NaN-aware equality: missing == missing, and order must match."""
    a = a.reset_index(drop=True)
    b = b.reset_index(drop=True)
    return bool(((a == b) | (a.isna() & b.isna())).all())


def check(name: str, ok: bool, detail: str = "") -> None:
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {name}" + (f"  ({detail})" if detail else ""))
    if not ok:
        _FAILURES.append(name)


def compare_frames(before: pd.DataFrame, after: pd.DataFrame, label: str) -> None:
    check(f"{label}: row count unchanged", len(before) == len(after),
          f"{len(before):,} -> {len(after):,}")
    check(f"{label}: no columns removed",
          set(before.columns) <= set(after.columns),
          f"{len(before.columns)} -> {len(after.columns)} columns")

    common = [c for c in before.columns if c in after.columns]
    for c in CANONICAL_RISK_FIELDS:
        if c in common:
            check(f"{label}: {c} unchanged",
                  _series_equal(before[c], after[c]))
    for c in MODEL_OUTPUT_FIELDS:
        if c in common:
            check(f"{label}: model output {c} unchanged",
                  _series_equal(before[c], after[c]))

    # No new NaN introduced into previously existing columns.
    new_nan_cols = []
    for c in common:
        if c in after.columns and c in before.columns:
            if after[c].isna().sum() > before[c].isna().sum():
                new_nan_cols.append(c)
    check(f"{label}: no new NaN in existing columns", not new_nan_cols,
          str(new_nan_cols) if new_nan_cols else "")

    # CLAIM_ID unchanged, unique, no new duplicates.
    if "CLAIM_ID" in common:
        check(f"{label}: CLAIM_ID values unchanged",
              (before["CLAIM_ID"].astype(str) == after["CLAIM_ID"].astype(str)).all())
        check(f"{label}: CLAIM_ID unique", after["CLAIM_ID"].is_unique)
        check(f"{label}: no duplicate claims introduced",
              after["CLAIM_ID"].duplicated().sum() == 0)


def validate_id_type(df: pd.DataFrame, label: str) -> None:
    df = df.copy()
    df["_ct"] = df["CLAIM_TYPE"].astype("string").str.upper()
    ok = True
    for ct, expected in EXPECTED_ID_TYPE.items():
        sub = df[df["_ct"] == ct]
        # Only rows with a PROVIDER_ID are required to carry the expected
        # type; rows with a missing PROVIDER_ID must have a null type
        # (verified by the dedicated check below).
        has_id = sub["PROVIDER_ID"].notna()
        valid = sub.loc[has_id, "PROVIDER_ID_TYPE"].eq(expected).all()
        if not valid:
            ok = False
        check(f"{label}: PROVIDER_ID_TYPE == {expected} for {ct}", bool(valid),
              f"{len(sub):,} rows ({int(has_id.sum()):,} with PROVIDER_ID)")
    # null type where PROVIDER_ID missing (and vice versa)
    both_null = (df["PROVIDER_ID"].isna() == df["PROVIDER_ID_TYPE"].isna()).all()
    check(f"{label}: PROVIDER_ID_TYPE null iff PROVIDER_ID missing",
          bool(both_null),
          f"missing IDs: {df['PROVIDER_ID'].isna().sum():,} | "
          f"missing types: {df['PROVIDER_ID_TYPE'].isna().sum():,}")
    # distribution printout
    print(f"\n  {label} PROVIDER_ID_TYPE distribution:")
    print(pd.crosstab(df["_ct"], df["PROVIDER_ID_TYPE"], dropna=False).to_string())
    if not ok:
        check(f"{label}: PROVIDER_ID_TYPE mapping overall", False)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--before-dir", default=str(
        Path(__file__).resolve().parent / "_validation_before"))
    args = ap.parse_args()
    before_dir = Path(args.before_dir)

    print("=" * 70)
    print("CLAIM EXPORT VALIDATION")
    print("=" * 70)

    unified_path = PROJECT_ROOT / "data" / "claims" / "final_unified_claim_risk.csv"
    claim360_path = PROJECT_ROOT / "data" / "claims" / "claim_360.csv"

    after_unified = pd.read_csv(unified_path, low_memory=False)
    after_360 = pd.read_csv(claim360_path, low_memory=False)

    before_unified = pd.read_csv(before_dir / "final_unified_claim_risk.csv", low_memory=False)
    before_360 = pd.read_csv(before_dir / "claim_360.csv", low_memory=False)

    print("\n--- unified output (final_unified_claim_risk.csv) ---")
    compare_frames(before_unified, after_unified, "unified")
    validate_id_type(after_unified, "unified")

    print("\n--- claim_360.csv ---")
    compare_frames(before_360, after_360, "claim_360")
    validate_id_type(after_360, "claim_360")

    print("\n--- claims.db tables ---")
    con = sqlite3.connect(PROJECT_ROOT / "data" / "claims" / "claims.db")
    for table in ["final_claim_risk", "claim_360"]:
        after_db = pd.read_sql(f"SELECT * FROM {table}", con)
        before_db = pd.read_csv(before_dir / f"db_{table}.csv", low_memory=False)
        compare_frames(before_db, after_db, f"db.{table}")
        validate_id_type(after_db, f"db.{table}")
    con.close()

    print("\n" + "=" * 70)
    if _FAILURES:
        print(f"VALIDATION FAILED ({len(_FAILURES)} checks): {_FAILURES}")
        sys.exit(1)
    print("ALL VALIDATION CHECKS PASSED")
    print("=" * 70)


if __name__ == "__main__":
    main()
