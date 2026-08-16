import pandas as pd
from pathlib import Path


# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

INPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "unified_claim_risk_with_provider.csv"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "final_unified_claim_risk.csv"
)


# ============================================================
# HEADER
# ============================================================

print("=" * 70)
print("FINAL CLAIM RISK GENERATION")
print("=" * 70)


# ============================================================
# LOAD DATA
# ============================================================

print("\nLoading unified claim risk...")

df = pd.read_csv(
    INPUT_FILE,
    low_memory=False
)

print(
    f"Rows loaded: {len(df):,}"
)


# ============================================================
# REQUIRED COLUMN CHECK
# ============================================================

required_columns = [
    "CLAIM_ID",
    "CLAIM_TYPE",
    "PROVIDER_ID",
    "CLAIM_RISK_SCORE",
    "CLAIM_RISK_RANK"
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
# CLAIM ID VALIDATION
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
# RISK SCORE VALIDATION
# ============================================================

print("\nValidating Claim Risk Scores...")

df["CLAIM_RISK_SCORE"] = pd.to_numeric(
    df["CLAIM_RISK_SCORE"],
    errors="coerce"
)

missing_scores = (
    df["CLAIM_RISK_SCORE"]
    .isna()
    .sum()
)

scores_below_zero = (
    df["CLAIM_RISK_SCORE"] < 0
).sum()

scores_above_100 = (
    df["CLAIM_RISK_SCORE"] > 100
).sum()

print(
    f"Missing scores      : {missing_scores:,}"
)

print(
    f"Scores below 0      : {scores_below_zero:,}"
)

print(
    f"Scores above 100    : {scores_above_100:,}"
)

if missing_scores > 0:
    raise ValueError(
        "Missing Claim Risk Scores detected."
    )

if scores_below_zero > 0:
    raise ValueError(
        "Claim Risk Score below 0 detected."
    )

if scores_above_100 > 0:
    raise ValueError(
        "Claim Risk Score above 100 detected."
    )


# ============================================================
# CREATE FINAL RISK LEVEL
# ============================================================

print("\nCreating final risk levels...")


def assign_risk_level(score):

    if score >= 80:
        return "CRITICAL"

    elif score >= 60:
        return "VERY HIGH"

    elif score >= 40:
        return "HIGH"

    elif score >= 20:
        return "MEDIUM"

    else:
        return "LOW"


df["FINAL_RISK_LEVEL"] = (
    df["CLAIM_RISK_SCORE"]
    .apply(assign_risk_level)
)


# ============================================================
# RISK PRIORITY
# ============================================================

print("\nCreating final risk priority...")

risk_priority_map = {
    "LOW": 1,
    "MEDIUM": 2,
    "HIGH": 3,
    "VERY HIGH": 4,
    "CRITICAL": 5
}

df["FINAL_RISK_PRIORITY"] = (
    df["FINAL_RISK_LEVEL"]
    .map(risk_priority_map)
)


# ============================================================
# SORT BY FINAL RISK
# ============================================================

df = df.sort_values(
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
# CREATE FINAL RANK
# ============================================================

df["FINAL_CLAIM_RANK"] = (
    range(1, len(df) + 1)
)


# ============================================================
# VALIDATION
# ============================================================

print("\n" + "=" * 70)
print("FINAL RISK VALIDATION")
print("=" * 70)


print(
    f"\nTotal claims: {len(df):,}"
)

print(
    f"Unique Claim IDs: "
    f"{df['CLAIM_ID'].nunique():,}"
)

print(
    f"Duplicate Claim IDs: "
    f"{df['CLAIM_ID'].duplicated().sum():,}"
)


print("\nFinal Risk Level Distribution:")

print(
    df["FINAL_RISK_LEVEL"]
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
# CLAIM TYPE + RISK DISTRIBUTION
# ============================================================

print("\nRisk Distribution by Claim Type:")

risk_by_type = pd.crosstab(
    df["CLAIM_TYPE"],
    df["FINAL_RISK_LEVEL"]
)

risk_by_type = risk_by_type.reindex(
    columns=[
        "LOW",
        "MEDIUM",
        "HIGH",
        "VERY HIGH",
        "CRITICAL"
    ],
    fill_value=0
)

print(
    risk_by_type
)


# ============================================================
# TOP SUSPICIOUS CLAIMS
# ============================================================

print("\n" + "=" * 70)
print("TOP 20 MOST SUSPICIOUS CLAIMS")
print("=" * 70)


top_columns = [
    "FINAL_CLAIM_RANK",
    "CLAIM_ID",
    "CLAIM_TYPE",
    "PROVIDER_ID",
    "CLAIM_RISK_SCORE",
    "FINAL_RISK_LEVEL",
    "FINAL_RISK_PRIORITY"
]

print(
    df[top_columns]
    .head(20)
    .to_string(index=False)
)


# ============================================================
# PROVIDER COVERAGE
# ============================================================

print("\n" + "=" * 70)
print("PROVIDER COVERAGE")
print("=" * 70)

print(
    f"\nMissing Provider IDs: "
    f"{df['PROVIDER_ID'].isna().sum():,}"
)

print(
    f"Available Provider IDs: "
    f"{df['PROVIDER_ID'].notna().sum():,}"
)


# ============================================================
# SAVE
# ============================================================

print("\n" + "=" * 70)
print("SAVING FINAL CLAIM RISK")
print("=" * 70)

df.to_csv(
    OUTPUT_FILE,
    index=False
)

print(
    f"\nFinal file created:"
)

print(
    OUTPUT_FILE
)


# ============================================================
# COMPLETED
# ============================================================

print("\n" + "=" * 70)
print("FINAL CLAIM RISK COMPLETED SUCCESSFULLY")
print("=" * 70)

print("\nDone.")