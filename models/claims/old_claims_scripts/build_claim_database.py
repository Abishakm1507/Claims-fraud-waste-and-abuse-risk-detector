import pandas as pd
import sqlite3
from pathlib import Path


# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

FINAL_RISK_FILE = (
    PROJECT_ROOT
    / "data"
    / "final_unified_claim_risk.csv"
)

CLAIM_360_FILE = (
    PROJECT_ROOT
    / "data"
    / "claim_360.csv"
)

DATABASE_FILE = (
    PROJECT_ROOT
    / "data"
    / "claims.db"
)


# ============================================================
# HEADER
# ============================================================

print("=" * 70)
print("BUILDING CLAIM RISK SQLITE DATABASE")
print("=" * 70)


# ============================================================
# CHECK INPUT FILES
# ============================================================

print("\nChecking input files...")

if not FINAL_RISK_FILE.exists():
    raise FileNotFoundError(
        f"Final claim risk file not found:\n{FINAL_RISK_FILE}"
    )

if not CLAIM_360_FILE.exists():
    raise FileNotFoundError(
        f"Claim 360 file not found:\n{CLAIM_360_FILE}"
    )

print("FINAL_RISK_FILE : FOUND")
print("CLAIM_360_FILE  : FOUND")


# ============================================================
# LOAD FILES
# ============================================================

print("\n" + "=" * 70)
print("LOADING FINAL CLAIM RISK")
print("=" * 70)

final_risk = pd.read_csv(
    FINAL_RISK_FILE,
    low_memory=False
)

print(f"Rows    : {len(final_risk):,}")
print(f"Columns : {len(final_risk.columns):,}")


print("\n" + "=" * 70)
print("LOADING CLAIM 360")
print("=" * 70)

claim_360 = pd.read_csv(
    CLAIM_360_FILE,
    low_memory=False
)

print(f"Rows    : {len(claim_360):,}")
print(f"Columns : {len(claim_360.columns):,}")


# ============================================================
# CHECK REQUIRED CLAIM ID
# ============================================================

for dataframe, name in [
    (final_risk, "final_unified_claim_risk"),
    (claim_360, "claim_360")
]:

    if "CLAIM_ID" not in dataframe.columns:

        raise ValueError(
            f"CLAIM_ID not found in {name}"
        )


# ============================================================
# REMOVE SQLITE-INCOMPATIBLE DUPLICATE COLUMNS
# ============================================================

print("\n" + "=" * 70)
print("CLEANING DATABASE COLUMN NAMES")
print("=" * 70)


def remove_case_insensitive_duplicates(
    dataframe,
    dataframe_name
):

    seen = set()
    columns_to_keep = []
    removed_columns = []

    for column in dataframe.columns:

        normalized = column.strip().lower()

        if normalized in seen:

            removed_columns.append(column)

        else:

            seen.add(normalized)
            columns_to_keep.append(column)

    cleaned = dataframe[
        columns_to_keep
    ].copy()

    if removed_columns:

        print(
            f"\n{dataframe_name}:"
        )

        print(
            "Removed duplicate columns:"
        )

        for column in removed_columns:

            print(
                f"  - {column}"
            )

    else:

        print(
            f"\n{dataframe_name}: "
            "No duplicate column names found."
        )

    return cleaned


final_risk = remove_case_insensitive_duplicates(
    final_risk,
    "FINAL CLAIM RISK"
)

claim_360 = remove_case_insensitive_duplicates(
    claim_360,
    "CLAIM 360"
)


print(
    f"\nFinal Claim Risk columns after cleaning: "
    f"{len(final_risk.columns):,}"
)

print(
    f"Claim 360 columns after cleaning: "
    f"{len(claim_360.columns):,}"
)


# ============================================================
# STANDARDIZE CLAIM IDs
# ============================================================

print("\n" + "=" * 70)
print("STANDARDIZING CLAIM IDs")
print("=" * 70)

final_risk["CLAIM_ID"] = (
    final_risk["CLAIM_ID"]
    .astype("string")
    .str.strip()
)

claim_360["CLAIM_ID"] = (
    claim_360["CLAIM_ID"]
    .astype("string")
    .str.strip()
)


# ============================================================
# VALIDATE FINAL RISK
# ============================================================

print("\n" + "=" * 70)
print("VALIDATING FINAL CLAIM RISK")
print("=" * 70)

final_duplicate_count = (
    final_risk["CLAIM_ID"]
    .duplicated()
    .sum()
)

final_missing_count = (
    final_risk["CLAIM_ID"]
    .isna()
    .sum()
)

print(
    f"Duplicate Claim IDs: "
    f"{final_duplicate_count:,}"
)

print(
    f"Missing Claim IDs: "
    f"{final_missing_count:,}"
)

if final_duplicate_count > 0:

    raise ValueError(
        "Duplicate CLAIM_ID values found "
        "in final_unified_claim_risk."
    )

if final_missing_count > 0:

    raise ValueError(
        "Missing CLAIM_ID values found "
        "in final_unified_claim_risk."
    )


# ============================================================
# VALIDATE CLAIM 360
# ============================================================

print("\n" + "=" * 70)
print("VALIDATING CLAIM 360")
print("=" * 70)

claim360_duplicate_count = (
    claim_360["CLAIM_ID"]
    .duplicated()
    .sum()
)

claim360_missing_count = (
    claim_360["CLAIM_ID"]
    .isna()
    .sum()
)

print(
    f"Duplicate Claim IDs: "
    f"{claim360_duplicate_count:,}"
)

print(
    f"Missing Claim IDs: "
    f"{claim360_missing_count:,}"
)

if claim360_duplicate_count > 0:

    raise ValueError(
        "Duplicate CLAIM_ID values found "
        "in claim_360."
    )

if claim360_missing_count > 0:

    raise ValueError(
        "Missing CLAIM_ID values found "
        "in claim_360."
    )


# ============================================================
# DELETE OLD DATABASE
# ============================================================

if DATABASE_FILE.exists():

    print("\nExisting database found.")

    print(
        "Removing old database..."
    )

    DATABASE_FILE.unlink()


# ============================================================
# CREATE SQLITE CONNECTION
# ============================================================

print("\n" + "=" * 70)
print("CREATING SQLITE DATABASE")
print("=" * 70)

connection = sqlite3.connect(
    DATABASE_FILE
)

print(
    f"Database:\n{DATABASE_FILE}"
)


# ============================================================
# CREATE FINAL CLAIM RISK TABLE
# ============================================================

print("\nCreating table: final_claim_risk")

final_risk.to_sql(
    "final_claim_risk",
    connection,
    if_exists="replace",
    index=False
)

print(
    f"Inserted rows: "
    f"{len(final_risk):,}"
)


# ============================================================
# CREATE CLAIM 360 TABLE
# ============================================================

print("\nCreating table: claim_360")

claim_360.to_sql(
    "claim_360",
    connection,
    if_exists="replace",
    index=False
)

print(
    f"Inserted rows: "
    f"{len(claim_360):,}"
)


# ============================================================
# CREATE INDEXES
# ============================================================

print("\n" + "=" * 70)
print("CREATING DATABASE INDEXES")
print("=" * 70)


# Only create indexes for columns that actually exist.

index_definitions = [

    (
        "idx_final_claim_id",
        "final_claim_risk",
        "CLAIM_ID"
    ),

    (
        "idx_final_claim_type",
        "final_claim_risk",
        "CLAIM_TYPE"
    ),

    (
        "idx_final_claim_score",
        "final_claim_risk",
        "CLAIM_RISK_SCORE"
    ),

    (
        "idx_final_risk_level",
        "final_claim_risk",
        "FINAL_RISK_LEVEL"
    ),

    (
        "idx_final_claim_rank",
        "final_claim_risk",
        "FINAL_CLAIM_RANK"
    ),

    (
        "idx_final_provider_id",
        "final_claim_risk",
        "PROVIDER_ID"
    ),

    (
        "idx_360_claim_id",
        "claim_360",
        "CLAIM_ID"
    ),

    (
        "idx_360_claim_type",
        "claim_360",
        "CLAIM_TYPE"
    ),

    (
        "idx_360_claim_score",
        "claim_360",
        "CLAIM_RISK_SCORE"
    ),

    (
        "idx_360_risk_level",
        "claim_360",
        "FINAL_RISK_LEVEL"
    ),

    (
        "idx_360_claim_rank",
        "claim_360",
        "FINAL_CLAIM_RANK"
    ),

    (
        "idx_360_provider_id",
        "claim_360",
        "PROVIDER_ID"
    )
]


for index_name, table_name, column_name in index_definitions:

    columns = (
        final_risk.columns
        if table_name == "final_claim_risk"
        else claim_360.columns
    )

    if column_name in columns:

        connection.execute(
            f"""
            CREATE INDEX {index_name}
            ON {table_name} ({column_name})
            """
        )

        print(
            f"Created: {index_name}"
        )

    else:

        print(
            f"Skipped: {index_name} "
            f"(column not found)"
        )


# ============================================================
# DATABASE VALIDATION
# ============================================================

print("\n" + "=" * 70)
print("DATABASE VALIDATION")
print("=" * 70)


# ------------------------------------------------------------
# TABLES
# ------------------------------------------------------------

tables = connection.execute(
    """
    SELECT name
    FROM sqlite_master
    WHERE type = 'table'
    ORDER BY name
    """
).fetchall()

print("\nTables:")

for table in tables:

    print(
        f"  - {table[0]}"
    )


# ------------------------------------------------------------
# ROW COUNTS
# ------------------------------------------------------------

final_count = connection.execute(
    """
    SELECT COUNT(*)
    FROM final_claim_risk
    """
).fetchone()[0]

claim_360_count = connection.execute(
    """
    SELECT COUNT(*)
    FROM claim_360
    """
).fetchone()[0]

print("\nRow counts:")

print(
    f"final_claim_risk : "
    f"{final_count:,}"
)

print(
    f"claim_360        : "
    f"{claim_360_count:,}"
)


# ============================================================
# CLAIM RISK RANGE
# ============================================================

print("\n" + "=" * 70)
print("CLAIM RISK SCORE CHECK")
print("=" * 70)

risk_min, risk_max = connection.execute(
    """
    SELECT
        MIN(CLAIM_RISK_SCORE),
        MAX(CLAIM_RISK_SCORE)
    FROM final_claim_risk
    """
).fetchone()

print(
    f"Minimum Risk Score: {risk_min}"
)

print(
    f"Maximum Risk Score: {risk_max}"
)


# ============================================================
# INVESTIGATION QUEUE TEST
# ============================================================

print("\n" + "=" * 70)
print("INVESTIGATION QUEUE TEST")
print("=" * 70)

queue = pd.read_sql_query(
    """
    SELECT
        CLAIM_ID,
        CLAIM_TYPE,
        PROVIDER_ID,
        CLAIM_RISK_SCORE,
        FINAL_CLAIM_RANK,
        FINAL_RISK_LEVEL,
        FINAL_RISK_PRIORITY
    FROM final_claim_risk
    ORDER BY CLAIM_RISK_SCORE DESC
    LIMIT 10
    """,
    connection
)

print(
    queue.to_string(index=False)
)


# ============================================================
# CLAIM 360 SEARCH TEST
# ============================================================

print("\n" + "=" * 70)
print("CLAIM 360 SEARCH TEST")
print("=" * 70)

test_claim_id = (
    final_risk.iloc[0]["CLAIM_ID"]
)

claim_result = pd.read_sql_query(
    """
    SELECT
        CLAIM_ID,
        CLAIM_TYPE,
        PROVIDER_ID,
        CLAIM_RISK_SCORE,
        FINAL_CLAIM_RANK,
        FINAL_RISK_LEVEL,
        FINAL_RISK_PRIORITY
    FROM claim_360
    WHERE CLAIM_ID = ?
    """,
    connection,
    params=(test_claim_id,)
)

print(
    claim_result.to_string(index=False)
)


# ============================================================
# CLOSE DATABASE
# ============================================================

connection.close()


# ============================================================
# FINAL
# ============================================================

print("\n" + "=" * 70)
print("CLAIM DATABASE CREATED SUCCESSFULLY")
print("=" * 70)

print(
    f"\nDatabase file:\n{DATABASE_FILE}"
)

print(
    f"\nFinal Claim Risk rows: "
    f"{final_count:,}"
)

print(
    f"Claim 360 rows: "
    f"{claim_360_count:,}"
)

print(
    "\nDatabase is ready for dashboard integration."
)

print("\nDone.")