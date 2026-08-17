"""
sync_claims_db.py

Synchronises the new PROVIDER_ID_TYPE evidence column into the SQLite
artifacts (data/claims/claims.db) so the DB stays compatible with the
authoritative unified output:

    data/claims/final_unified_claim_risk.csv
    data/claims/claim_360.csv

Behaviour
---------
* For each table (`final_claim_risk`, `claim_360`): adds `PROVIDER_ID_TYPE`
  (TEXT) if it does not exist, then populates it from the authoritative CSV by
  matching on CLAIM_ID (existing rows/columns are otherwise untouched).
* Idempotent: safe to run repeatedly.
* Missing PROVIDER_ID rows keep a NULL PROVIDER_ID_TYPE (never a fabricated
  value).

Usage
-----
    python sync_claims_db.py
"""

import sqlite3
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

UNIFIED_CSV = (
    PROJECT_ROOT / "data" / "claims" / "final_unified_claim_risk.csv"
)

DB_FILE = PROJECT_ROOT / "data" / "claims" / "claims.db"

TABLES = ["final_claim_risk", "claim_360"]


def main() -> None:
    print("=" * 70)
    print("SYNC PROVIDER_ID_TYPE INTO CLAIMS DB")
    print("=" * 70)

    if not UNIFIED_CSV.exists():
        raise FileNotFoundError(
            f"Authoritative unified output not found: {UNIFIED_CSV}"
        )

    print(f"\nLoading {UNIFIED_CSV.name}...")
    df = pd.read_csv(UNIFIED_CSV, low_memory=False)
    print(f"Rows: {len(df):,}")

    if "PROVIDER_ID_TYPE" not in df.columns:
        raise ValueError(
            "PROVIDER_ID_TYPE missing from the unified CSV - run "
            "finalize_claim_risk.py first."
        )

    # The CSV stores CLAIM_ID as a number while the DB stores it as TEXT;
    # key the lookup on the string form so the UPDATE matches.
    id_lookup = {
        str(k): v for k, v in df.set_index("CLAIM_ID")["PROVIDER_ID_TYPE"].items()
    }

    con = sqlite3.connect(DB_FILE)
    cur = con.cursor()

    for table in TABLES:
        existing = [
            r[1] for r in cur.execute(f"PRAGMA table_info({table})").fetchall()
        ]

        if "PROVIDER_ID_TYPE" not in existing:
            print(f"\nAdding PROVIDER_ID_TYPE to {table}...")
            cur.execute(
                f"ALTER TABLE {table} ADD COLUMN PROVIDER_ID_TYPE TEXT"
            )
        else:
            print(f"\nPROVIDER_ID_TYPE already present in {table} - updating values...")

        # Populate from the authoritative CSV (NULL when the claim is unknown
        # or the PROVIDER_ID is missing in the CSV).
        cur.execute(f"SELECT CLAIM_ID FROM {table}")
        rows = cur.fetchall()
        updated = 0
        for (claim_id,) in rows:
            value = id_lookup.get(str(claim_id))
            cur.execute(
                f"UPDATE {table} SET PROVIDER_ID_TYPE = ? WHERE CLAIM_ID = ?",
                (value, claim_id),
            )
            updated += 1
        print(f"  updated {updated:,} rows")

        # distribution check
        dist = pd.read_sql(
            f"SELECT CLAIM_TYPE, PROVIDER_ID_TYPE, COUNT(*) AS n FROM {table} "
            "GROUP BY CLAIM_TYPE, PROVIDER_ID_TYPE ORDER BY CLAIM_TYPE",
            con,
        )
        print(dist.to_string(index=False))

    con.commit()
    con.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
