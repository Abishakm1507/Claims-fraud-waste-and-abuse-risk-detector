"""
PHASE 8 - Dataset catalogue.

Written AFTER inspecting the real files. Every fact here was measured, not
assumed.

WHAT THE INSPECTION FOUND
=========================

The datasets form TWO DISCONNECTED UNIVERSES. They share no identifier and no
overlapping year range, so they are never joined.

  UNIVERSE A - Medicare public aggregate data, keyed on 10-digit NPI, 2020-2024
    provider_service    NPI x HCPCS x year x place-of-service
    provider_features   NPI x year, with peer deviation z-scores
    geo_benchmark       State/National x HCPCS  (the peer benchmark table)

  UNIVERSE B - CMS synthetic claims, keyed on CLM_ID, 2015-2022
    carrier_claims      CLM_ID, carrier/professional claims
    inpatient_claims    clm_id + prvdr_num (6-digit CCN, NOT an NPI)
    outpatient_claims   CLM_ID only

TWO CONSTRAINTS THAT SHAPE EVERY QUERY
======================================

1. provider_service and provider_features overlap on only 141 NPIs (1.6%).
   They cannot be merged into one provider view. A provider lookup reports
   which source holds that NPI, and says plainly when the other has no record.

2. outpatient_claims has NO provider identifier column. It carries pre-computed
   provider aggregates but not the key they were computed from, so outpatient
   supports claim-level lookups only - never provider-level.

Neither is a defect to work around. Both are stated to the investigator.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Source files. Keys are table names; values are accepted filenames in
# priority order, so the original download names work without renaming.
# ---------------------------------------------------------------------------

SOURCE_FILES: dict[str, list[str]] = {
    "provider_service": [
        "provider_service__cleaned.csv",
        "provider_service_cleaned.csv",
        "provider_service.csv",
    ],
    "provider_features": [
        "provider_features.csv",
        "Untitled.csv",
    ],
    "geo_benchmark": [
        "geo_benchmark.csv",
        "MUP_PHY_R26_P05_V10_D24_Geo_cleaned.csv",
        "merged_50000_cleaned.csv",
    ],
    "carrier_claims": [
        "carrier_claim_features.csv",
        "carrier_claim_features_FINAL.csv",
    ],
    "inpatient_claims": [
        "inpatient_CLEANED_v2.csv",
        "inpatient_cleaned.csv",
    ],
    "inpatient_features": [
        "inpatient_claim_features.csv",
    ],
    "outpatient_claims": [
        "outpatient_cleaned.csv",
    ],
    "leie": [
        "LEIE_CLEANED.csv",
        "LEIE-cleaned.csv",
        "leie.csv",
    ],
    # Phase 9 - output of the platform's provider risk model.
    "provider_risk": [
        "provider_risk_scores.csv",
    ],
}

# Tables the system can run without. Missing ones degrade capability rather
# than blocking startup.
OPTIONAL_TABLES = set(SOURCE_FILES)

# ---------------------------------------------------------------------------
# Measured profile of each table. Used to explain capability and limits.
# ---------------------------------------------------------------------------

TABLE_PROFILE: dict[str, dict] = {
    "provider_service": {
        "universe": "A",
        "grain": "NPI x HCPCS x year x place of service",
        "rows": 200_000,
        "entities": "8,848 providers",
        "years": "2020-2023",
        "key": "Rndrng_NPI",
        "answers": [
            "provider totals: payment, allowed, submitted charges",
            "provider service and beneficiary counts",
            "provider specialty, name, city, state",
            "which procedures a provider bills most",
            "provider rankings and threshold filters",
        ],
    },
    "provider_features": {
        "universe": "A",
        "grain": "NPI x year",
        "rows": 50_000,
        "entities": "18,306 providers",
        "years": "2020-2024",
        "key": "Rndrng_NPI",
        "answers": [
            "peer deviation score and peer group size",
            "per-metric peer z-scores (charge per service, services per "
            "beneficiary, payment-to-charge ratio)",
            "derived ratios: charge per beneficiary, services per beneficiary",
            "beneficiary chronic-condition mix and average age",
        ],
        "note": "Overlaps provider_service on only 141 NPIs. Not joinable.",
    },
    "geo_benchmark": {
        "universe": "A",
        "grain": "geography (State or National) x HCPCS",
        "rows": 268_345,
        "entities": "62 geographies, 9,403 HCPCS codes",
        "key": "rndrng_prvdr_geo_desc + hcpcs_cd",
        "answers": [
            "state and national averages for a procedure",
            "peer comparison for a provider's procedure mix",
            "how many providers nationally bill a procedure",
        ],
        "note": "2,419 of 2,512 HCPCS in provider_service match here.",
    },
    "carrier_claims": {
        "universe": "B",
        "grain": "CLM_ID",
        "rows": 6_665,
        "entities": "6,665 claims, 644 beneficiaries, 295 performing NPIs",
        "years": "2015-2022",
        "key": "CLM_ID",
        "answers": [
            "claim-level payment, charge and allowed amounts",
            "line counts, diagnosis counts, claim duration",
            "claims for a performing or billing NPI",
        ],
    },
    "inpatient_claims": {
        "universe": "B",
        "grain": "clm_id",
        "rows": 20_867,
        "entities": "20,867 claims, 4,876 facility CCNs",
        "years": "2015-2022",
        "key": "clm_id",
        "answers": [
            "inpatient claim payment, charge, length of stay",
            "facility-level totals by 6-digit CCN",
            "pre-computed anomaly flags and anomaly count",
        ],
        "note": "prvdr_num is a 6-digit facility CCN, not an NPI. 4.4% null.",
    },
    "outpatient_claims": {
        "universe": "B",
        "grain": "CLM_ID",
        "rows": 402_653,
        "entities": "402,653 claims",
        "years": "2015-2022",
        "key": "CLM_ID",
        "answers": [
            "outpatient claim payment, charge, line and diagnosis counts",
            "claim-level date and weekend indicators",
        ],
        "note": "NO provider identifier column. Claim-level lookups only.",
    },
}


def capability_summary() -> str:
    """Plain-language description of what the data layer can answer."""
    return (
        "Provider lookups and rankings come from Medicare aggregate data "
        "(NPI-keyed, 2020-2024). Claim lookups come from CMS claims data "
        "(CLM_ID-keyed, 2015-2022). The two sets share no identifiers and are "
        "never joined."
    )
