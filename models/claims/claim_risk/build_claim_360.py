import pandas as pd
from pathlib import Path


# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

INPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "claims"
    / "final_unified_claim_risk.csv"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "claims"
    / "claim_360.csv"
)


# ============================================================
# HEADER
# ============================================================

print("=" * 70)
print("BUILDING CLAIM 360 DATA")
print("=" * 70)


# ============================================================
# LOAD FINAL CLAIM RISK
# ============================================================

print("\nLoading final unified claim risk...")

df = pd.read_csv(
    INPUT_FILE,
    low_memory=False
)

print(
    f"Rows loaded: {len(df):,}"
)

print(
    f"Columns loaded: {len(df.columns):,}"
)


# ============================================================
# REQUIRED COLUMNS
# ============================================================

required_columns = [
    "CLAIM_ID",
    "CLAIM_TYPE",
    "PROVIDER_ID",
    "CLAIM_RISK_SCORE",
    "CLAIM_RISK_RANK",
    "FINAL_RISK_LEVEL",
    "FINAL_RISK_PRIORITY"
]

missing_columns = [
    column
    for column in required_columns
    if column not in df.columns
]

if missing_columns:

    raise ValueError(
        "Missing required columns: "
        + str(missing_columns)
    )


# ============================================================
# STANDARDIZE CLAIM ID
# ============================================================

df["CLAIM_ID"] = (
    df["CLAIM_ID"]
    .astype("string")
    .str.strip()
)


# ============================================================
# VALIDATE CLAIM IDs
# ============================================================

print("\nValidating Claim IDs...")

duplicate_claims = (
    df["CLAIM_ID"]
    .duplicated()
    .sum()
)

missing_claims = (
    df["CLAIM_ID"]
    .isna()
    .sum()
)

print(
    f"Duplicate Claim IDs: {duplicate_claims:,}"
)

print(
    f"Missing Claim IDs: {missing_claims:,}"
)

if duplicate_claims > 0:

    raise ValueError(
        "Duplicate Claim IDs detected."
    )

if missing_claims > 0:

    raise ValueError(
        "Missing Claim IDs detected."
    )


# ============================================================
# CREATE CLAIM 360
# ============================================================

print("\nCreating Claim 360 dataset...")


# Keep all existing claim information.
# Claim 360 is an organized view of the final claim-risk data.

claim_360 = df.copy()


# ============================================================
# ADD DISPLAY-FRIENDLY FIELDS
# ============================================================

claim_360["CLAIM_RISK_SCORE"] = pd.to_numeric(
    claim_360["CLAIM_RISK_SCORE"],
    errors="coerce"
)

claim_360["CLAIM_RISK_SCORE"] = (
    claim_360["CLAIM_RISK_SCORE"]
    .round(2)
)


# ============================================================
# CREATE CLAIM STATUS
# ============================================================

claim_360["CLAIM_STATUS"] = "FLAGGED"

claim_360.loc[
    claim_360["FINAL_RISK_LEVEL"] == "LOW",
    "CLAIM_STATUS"
] = "LOW RISK"

claim_360.loc[
    claim_360["FINAL_RISK_LEVEL"] == "MEDIUM",
    "CLAIM_STATUS"
] = "MONITOR"

claim_360.loc[
    claim_360["FINAL_RISK_LEVEL"] == "HIGH",
    "CLAIM_STATUS"
] = "REVIEW"

claim_360.loc[
    claim_360["FINAL_RISK_LEVEL"] == "VERY HIGH",
    "CLAIM_STATUS"
] = "PRIORITY REVIEW"

claim_360.loc[
    claim_360["FINAL_RISK_LEVEL"] == "CRITICAL",
    "CLAIM_STATUS"
] = "URGENT REVIEW"


# ============================================================
# CREATE PROVIDER AVAILABILITY
# ============================================================

claim_360["PROVIDER_INFORMATION_AVAILABLE"] = (
    claim_360["PROVIDER_ID"]
    .notna()
)


# ============================================================
# CREATE MODEL TYPE
# ============================================================

claim_360["RISK_MODEL_SOURCE"] = (
    claim_360["CLAIM_TYPE"]
    .astype("string")
    .str.upper()
    .map(
        {
            "CARRIER": "CARRIER ANOMALY MODEL",
            "INPATIENT": "INPATIENT ANOMALY MODEL",
            "OUTPATIENT": "OUTPATIENT ANOMALY MODEL"
        }
    )
)


# ============================================================
# SORT BY RISK
# ============================================================

claim_360 = claim_360.sort_values(
    by=[
        "CLAIM_RISK_SCORE",
        "CLAIM_RISK_RANK"
    ],
    ascending=[
        False,
        True
    ]
).reset_index(drop=True)


# ============================================================
# VALIDATION
# ============================================================

print("\n" + "=" * 70)
print("CLAIM 360 VALIDATION")
print("=" * 70)

print(
    f"\nTotal claims: "
    f"{len(claim_360):,}"
)

print(
    f"Unique Claim IDs: "
    f"{claim_360['CLAIM_ID'].nunique():,}"
)

print(
    f"Duplicate Claim IDs: "
    f"{claim_360['CLAIM_ID'].duplicated().sum():,}"
)

print(
    f"Missing Claim IDs: "
    f"{claim_360['CLAIM_ID'].isna().sum():,}"
)


# ============================================================
# CLAIM TYPE DISTRIBUTION
# ============================================================

print("\nClaim Type Distribution:")

print(
    claim_360["CLAIM_TYPE"]
    .value_counts()
)


# ============================================================
# RISK DISTRIBUTION
# ============================================================

print("\nRisk Level Distribution:")

print(
    claim_360["FINAL_RISK_LEVEL"]
    .value_counts()
    .reindex(
        [
            "LOW",
            "MEDIUM",
            "HIGH",
            "VERY HIGH",
            "CRITICAL"
        ],
        fill_value=0
    )
)


# ============================================================
# PROVIDER COVERAGE
# ============================================================

print("\nProvider Information:")

print(
    f"Provider available: "
    f"{claim_360['PROVIDER_ID'].notna().sum():,}"
)

print(
    f"Provider missing: "
    f"{claim_360['PROVIDER_ID'].isna().sum():,}"
)


# ============================================================
# TOP SUSPICIOUS CLAIMS
# ============================================================

print("\n" + "=" * 70)
print("TOP 10 CLAIMS")
print("=" * 70)

display_columns = [
    "CLAIM_ID",
    "CLAIM_TYPE",
    "PROVIDER_ID",
    "CLAIM_RISK_SCORE",
    "FINAL_CLAIM_RANK",
    "FINAL_RISK_LEVEL",
    "CLAIM_STATUS"
]

print(
    claim_360[
        display_columns
    ]
    .head(10)
    .to_string(index=False)
)


# ============================================================
# SAVE
# ============================================================

print("\n" + "=" * 70)
print("SAVING CLAIM 360")
print("=" * 70)

claim_360.to_csv(
    OUTPUT_FILE,
    index=False
)

print(
    f"\nClaim 360 file created:"
)

print(
    OUTPUT_FILE
)


# ============================================================
# COMPLETE
# ============================================================

print("\n" + "=" * 70)
print("CLAIM 360 CREATED SUCCESSFULLY")
print("=" * 70)

print("\nDone.")