import pandas as pd
from pathlib import Path


# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

UNIFIED_FILE = PROJECT_ROOT / "data" / "unified_claim_risk.csv"

MAPPING_FILE = (
    PROJECT_ROOT
    / "data"
    / "outpatient_claim_provider_unique_mapping.csv"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "unified_claim_risk_with_provider.csv"
)


# ============================================================
# HEADER
# ============================================================

print("=" * 70)
print("ADDING OUTPATIENT PROVIDER ID TO UNIFIED CLAIM RISK")
print("=" * 70)


# ============================================================
# LOAD UNIFIED CLAIM RISK
# ============================================================

print("\nLoading unified claim risk...")

unified = pd.read_csv(
    UNIFIED_FILE,
    low_memory=False
)

print(f"Unified rows: {len(unified):,}")


# ============================================================
# LOAD PROVIDER MAPPING
# ============================================================

print("\nLoading outpatient provider mapping...")

mapping = pd.read_csv(
    MAPPING_FILE,
    dtype=str,
    low_memory=False
)

print(f"Mapping rows: {len(mapping):,}")


# ============================================================
# CHECK REQUIRED COLUMNS
# ============================================================

required_unified = [
    "CLAIM_ID",
    "CLAIM_TYPE"
]

for column in required_unified:

    if column not in unified.columns:

        raise ValueError(
            f"Required column '{column}' "
            f"not found in unified_claim_risk.csv"
        )


required_mapping = [
    "CLM_ID",
    "PRVDR_NUM"
]

for column in required_mapping:

    if column not in mapping.columns:

        raise ValueError(
            f"Required column '{column}' "
            f"not found in provider mapping."
        )


# ============================================================
# STANDARDIZE CLAIM IDS
# ============================================================

print("\nStandardizing Claim IDs...")

unified["CLAIM_ID"] = (
    unified["CLAIM_ID"]
    .astype("string")
    .str.strip()
)

mapping["CLM_ID"] = (
    mapping["CLM_ID"]
    .astype("string")
    .str.strip()
)

mapping["PRVDR_NUM"] = (
    mapping["PRVDR_NUM"]
    .astype("string")
    .str.strip()
)


# ============================================================
# CHECK DUPLICATES
# ============================================================

duplicate_mapping = (
    mapping["CLM_ID"]
    .duplicated()
    .sum()
)

print(
    f"Duplicate mapping Claim IDs: "
    f"{duplicate_mapping:,}"
)

if duplicate_mapping > 0:

    raise ValueError(
        "Provider mapping contains duplicate Claim IDs."
    )


duplicate_unified = (
    unified["CLAIM_ID"]
    .duplicated()
    .sum()
)

print(
    f"Duplicate unified Claim IDs: "
    f"{duplicate_unified:,}"
)

if duplicate_unified > 0:

    raise ValueError(
        "Unified claim file contains duplicate Claim IDs."
    )


# ============================================================
# SAVE ORIGINAL COUNTS
# ============================================================

original_rows = len(unified)

original_unique_claims = (
    unified["CLAIM_ID"]
    .nunique()
)


# ============================================================
# CREATE SIMPLE CLAIM -> PROVIDER LOOKUP
# ============================================================

print("\nCreating Claim -> Provider lookup...")

provider_lookup = (
    mapping
    .set_index("CLM_ID")["PRVDR_NUM"]
)


# ============================================================
# IDENTIFY OUTPATIENT CLAIMS
# ============================================================

is_outpatient = (
    unified["CLAIM_TYPE"]
    .astype("string")
    .str.upper()
    .eq("OUTPATIENT")
)

outpatient_count = is_outpatient.sum()

print(
    f"Outpatient claims: "
    f"{outpatient_count:,}"
)


# ============================================================
# CREATE PROVIDER ID COLUMN IF NEEDED
# ============================================================

if "PROVIDER_ID" not in unified.columns:

    unified["PROVIDER_ID"] = pd.Series(
        pd.NA,
        index=unified.index,
        dtype="string"
    )

else:

    unified["PROVIDER_ID"] = (
        unified["PROVIDER_ID"]
        .astype("string")
        .str.strip()
    )


# ============================================================
# LOOK UP OUTPATIENT PROVIDERS
# ============================================================

print("\nLooking up outpatient Provider IDs...")

outpatient_provider_ids = (
    unified.loc[
        is_outpatient,
        "CLAIM_ID"
    ]
    .map(provider_lookup)
)


# ============================================================
# ASSIGN PROVIDER IDS
# ============================================================

unified.loc[
    is_outpatient,
    "PROVIDER_ID"
] = outpatient_provider_ids.values


# ============================================================
# VALIDATE ROW COUNT
# ============================================================

print("\n" + "=" * 70)
print("CLAIM COUNT VALIDATION")
print("=" * 70)

new_rows = len(unified)

new_unique_claims = (
    unified["CLAIM_ID"]
    .nunique()
)

print(
    f"Original rows       : {original_rows:,}"
)

print(
    f"New rows            : {new_rows:,}"
)

print(
    f"Original unique IDs : {original_unique_claims:,}"
)

print(
    f"New unique IDs      : {new_unique_claims:,}"
)


if new_rows != original_rows:

    raise ValueError(
        "ERROR: Row count changed."
    )


if new_unique_claims != original_unique_claims:

    raise ValueError(
        "ERROR: Unique Claim ID count changed."
    )


# ============================================================
# PROVIDER COVERAGE BY CLAIM TYPE
# ============================================================

print("\n" + "=" * 70)
print("PROVIDER MAPPING RESULTS")
print("=" * 70)


for claim_type in [
    "CARRIER",
    "INPATIENT",
    "OUTPATIENT"
]:

    subset = unified[
        unified["CLAIM_TYPE"]
        .astype("string")
        .str.upper()
        .eq(claim_type)
    ]

    total = len(subset)

    available = (
        subset["PROVIDER_ID"]
        .notna()
        .sum()
    )

    missing = total - available

    coverage = (
        available / total * 100
        if total > 0
        else 0
    )

    print(f"\n{claim_type}")

    print(
        f"Total claims       : {total:,}"
    )

    print(
        f"Provider available : {available:,}"
    )

    print(
        f"Provider missing   : {missing:,}"
    )

    print(
        f"Provider coverage  : {coverage:.2f}%"
    )


# ============================================================
# GLOBAL VALIDATION
# ============================================================

print("\n" + "=" * 70)
print("GLOBAL VALIDATION")
print("=" * 70)

print(
    f"\nTotal claims: "
    f"{len(unified):,}"
)

print(
    f"Unique Claim IDs: "
    f"{unified['CLAIM_ID'].nunique():,}"
)

print(
    f"Duplicate Claim IDs: "
    f"{unified['CLAIM_ID'].duplicated().sum():,}"
)

print(
    f"Missing Claim IDs: "
    f"{unified['CLAIM_ID'].isna().sum():,}"
)

print(
    f"Missing Provider IDs: "
    f"{unified['PROVIDER_ID'].isna().sum():,}"
)


# ============================================================
# RISK CHECK
# ============================================================

print("\n" + "=" * 70)
print("RISK COLUMN CHECK")
print("=" * 70)

for column in [
    "CLAIM_RISK_SCORE",
    "CLAIM_RISK_RANK",
    "CURRENT_RISK_LEVEL"
]:

    if column in unified.columns:

        print(
            f"{column}: "
            f"{unified[column].notna().sum():,} populated"
        )

    else:

        print(
            f"{column}: NOT FOUND"
        )


# ============================================================
# SAVE
# ============================================================

print("\n" + "=" * 70)
print("SAVING FILE")
print("=" * 70)

unified.to_csv(
    OUTPUT_FILE,
    index=False
)

print(
    f"\nCreated:\n{OUTPUT_FILE}"
)


# ============================================================
# COMPLETE
# ============================================================

print("\n" + "=" * 70)
print("PROVIDER MAPPING COMPLETED")
print("=" * 70)

print("\nDone.")