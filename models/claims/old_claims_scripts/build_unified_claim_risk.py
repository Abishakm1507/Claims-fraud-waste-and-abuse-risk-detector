import pandas as pd
from pathlib import Path


# ============================================================
# 1. PROJECT PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

CARRIER_FILE = (
    PROJECT_ROOT
    / "models"
    / "carrier"
    / "carrier_final_risk_scores.csv"
)

INPATIENT_FILE = (
    PROJECT_ROOT
    / "models"
    / "inpatient"
    / "inpatient_final_risk_scores.csv"
)

OUTPATIENT_FILE = (
    PROJECT_ROOT
    / "models"
    / "outpatient"
    / "outpatient_final_risk_scores.csv"
)

OUTPUT_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR.mkdir(exist_ok=True)

UNIFIED_FILE = OUTPUT_DIR / "unified_claim_risk.csv"
TOP_CLAIMS_FILE = OUTPUT_DIR / "top_suspicious_claims.csv"


# ============================================================
# 2. LOAD DATA
# ============================================================

print("=" * 70)
print("UNIFIED CLAIM RISK BUILD - CLEAN VERSION")
print("=" * 70)

print("\nLoading Carrier...")
carrier = pd.read_csv(
    CARRIER_FILE,
    low_memory=False
)

print("Loading Inpatient...")
inpatient = pd.read_csv(
    INPATIENT_FILE,
    low_memory=False
)

print("Loading Outpatient...")
outpatient = pd.read_csv(
    OUTPATIENT_FILE,
    low_memory=False
)


print("\nDataset sizes:")
print(f"Carrier    : {len(carrier):,}")
print(f"Inpatient  : {len(inpatient):,}")
print(f"Outpatient : {len(outpatient):,}")


# ============================================================
# 3. STANDARDIZE CLAIM ID
# ============================================================

def standardize_claim_id(df, source_name):

    if "CLM_ID" in df.columns:
        df["CLAIM_ID"] = df["CLM_ID"]

    elif "clm_id" in df.columns:
        df["CLAIM_ID"] = df["clm_id"]

    elif "CLAIM_ID" in df.columns:
        df["CLAIM_ID"] = df["CLAIM_ID"]

    elif "claim_id" in df.columns:
        df["CLAIM_ID"] = df["claim_id"]

    else:
        raise ValueError(
            f"No claim ID column found in {source_name}"
        )

    return df


carrier = standardize_claim_id(carrier, "Carrier")
inpatient = standardize_claim_id(inpatient, "Inpatient")
outpatient = standardize_claim_id(outpatient, "Outpatient")


# ============================================================
# 4. STANDARDIZE PROVIDER ID
# ============================================================

def standardize_provider_id(df, source_name):

    if "provider_id" in df.columns:
        df["PROVIDER_ID"] = df["provider_id"]

    elif "PROVIDER_ID" in df.columns:
        df["PROVIDER_ID"] = df["PROVIDER_ID"]

    elif "CARR_CLM_BLG_NPI_NUM_first" in df.columns:
        df["PROVIDER_ID"] = df[
            "CARR_CLM_BLG_NPI_NUM_first"
        ]

    elif "NPI" in df.columns:
        df["PROVIDER_ID"] = df["NPI"]

    elif "npi" in df.columns:
        df["PROVIDER_ID"] = df["npi"]

    else:
        df["PROVIDER_ID"] = pd.NA

        print(
            f"WARNING: Provider ID not found for {source_name}"
        )

    return df


carrier = standardize_provider_id(
    carrier,
    "Carrier"
)

inpatient = standardize_provider_id(
    inpatient,
    "Inpatient"
)

outpatient = standardize_provider_id(
    outpatient,
    "Outpatient"
)


# ============================================================
# 5. STANDARDIZE CLAIM TYPE
# ============================================================

carrier["CLAIM_TYPE"] = "CARRIER"

inpatient["CLAIM_TYPE"] = "INPATIENT"

outpatient["CLAIM_TYPE"] = "OUTPATIENT"


# ============================================================
# 6. FIND ORIGINAL MODEL SCORE
# ============================================================

def find_risk_column(df, source_name):

    preferred = [
        "carrier_ensemble_score",
        "ensemble_risk_score",
        "outpatient_ensemble_score",
        "ensemble_score",
        "claim_risk_score",
        "risk_score"
    ]

    for column in preferred:

        if column in df.columns:

            print(
                f"{source_name} model score: {column}"
            )

            return column

    possible = [
        column
        for column in df.columns
        if (
            "ensemble" in column.lower()
            or "risk_score" in column.lower()
        )
    ]

    if possible:

        print(
            f"{source_name} model score: {possible[0]}"
        )

        return possible[0]

    raise ValueError(
        f"Could not find model score for {source_name}"
    )


carrier_score_col = find_risk_column(
    carrier,
    "Carrier"
)

inpatient_score_col = find_risk_column(
    inpatient,
    "Inpatient"
)

outpatient_score_col = find_risk_column(
    outpatient,
    "Outpatient"
)


# ============================================================
# 7. SAVE ORIGINAL MODEL SCORE
# ============================================================

carrier["MODEL_SCORE"] = pd.to_numeric(
    carrier[carrier_score_col],
    errors="coerce"
)

inpatient["MODEL_SCORE"] = pd.to_numeric(
    inpatient[inpatient_score_col],
    errors="coerce"
)

outpatient["MODEL_SCORE"] = pd.to_numeric(
    outpatient[outpatient_score_col],
    errors="coerce"
)


# ============================================================
# 8. CREATE COMMON 0-100 RISK INDEX
#
# This is a percentile-based comparison within each
# claim type. It is NOT a probability of fraud.
# ============================================================

def create_risk_index(series):

    series = pd.to_numeric(
        series,
        errors="coerce"
    )

    return (
        series.rank(
            method="average",
            pct=True
        ) * 100
    )


carrier["CLAIM_RISK_SCORE"] = create_risk_index(
    carrier["MODEL_SCORE"]
)

inpatient["CLAIM_RISK_SCORE"] = create_risk_index(
    inpatient["MODEL_SCORE"]
)

outpatient["CLAIM_RISK_SCORE"] = create_risk_index(
    outpatient["MODEL_SCORE"]
)


# ============================================================
# 9. ROUND SCORE
# ============================================================

carrier["CLAIM_RISK_SCORE"] = carrier[
    "CLAIM_RISK_SCORE"
].round(4)

inpatient["CLAIM_RISK_SCORE"] = inpatient[
    "CLAIM_RISK_SCORE"
].round(4)

outpatient["CLAIM_RISK_SCORE"] = outpatient[
    "CLAIM_RISK_SCORE"
].round(4)


# ============================================================
# 10. COMBINE
# ============================================================

unified = pd.concat(
    [
        carrier,
        inpatient,
        outpatient
    ],
    ignore_index=True
)


# ============================================================
# 11. CLEAN COMMON IDENTIFIERS
# ============================================================

unified["CLAIM_ID"] = (
    unified["CLAIM_ID"]
    .astype("string")
    .str.strip()
)

unified["PROVIDER_ID"] = (
    unified["PROVIDER_ID"]
    .astype("string")
    .str.strip()
)


# ============================================================
# 12. GLOBAL RANK
# ============================================================

unified = unified.sort_values(
    by=[
        "CLAIM_RISK_SCORE",
        "MODEL_SCORE"
    ],
    ascending=[
        False,
        False
    ]
).reset_index(drop=True)


unified["CLAIM_RISK_RANK"] = (
    range(
        1,
        len(unified) + 1
    )
)


# ============================================================
# 13. SAVE
# ============================================================

unified.to_csv(
    UNIFIED_FILE,
    index=False
)


# ============================================================
# 14. TOP 100
# ============================================================

top_claims = unified.head(100).copy()

top_claims.to_csv(
    TOP_CLAIMS_FILE,
    index=False
)


# ============================================================
# 15. VALIDATION REPORT
# ============================================================

print("\n" + "=" * 70)
print("UNIFIED CLAIM RISK COMPLETED")
print("=" * 70)

print(
    f"\nTotal claims: {len(unified):,}"
)

print("\nClaim types:")

print(
    unified["CLAIM_TYPE"]
    .value_counts()
)


print("\nMissing common Claim IDs:")

print(
    unified["CLAIM_ID"]
    .isna()
    .sum()
)


print("\nMissing common Provider IDs:")

print(
    unified["PROVIDER_ID"]
    .isna()
    .sum()
)


print("\nDuplicate Claim IDs:")

print(
    unified["CLAIM_ID"]
    .duplicated()
    .sum()
)


print("\nRisk score summary:")

print(
    unified["CLAIM_RISK_SCORE"]
    .describe()
)


print("\nTop 20 suspicious claims:")

print(
    unified[
        [
            "CLAIM_RISK_RANK",
            "CLAIM_ID",
            "CLAIM_TYPE",
            "PROVIDER_ID",
            "MODEL_SCORE",
            "CLAIM_RISK_SCORE"
        ]
    ]
    .head(20)
    .to_string(index=False)
)


print("\nFiles created:")

print(
    f"1. {UNIFIED_FILE}"
)

print(
    f"2. {TOP_CLAIMS_FILE}"
)

print("\nDone.")