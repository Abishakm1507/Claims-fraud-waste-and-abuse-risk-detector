
============================================================
XAI CLAIMS PACKAGE
============================================================

Purpose:
This package contains the standardized claim-risk outputs,
source claim datasets, and previous feature-engineering
scripts required for building the Claim-level XAI layer.

------------------------------------------------------------
1. final_unified_claim_risk.csv
------------------------------------------------------------

Final standardized unified claim-risk dataset.

Contains:
- CLAIM_ID
- CLAIM_TYPE
- PROVIDER_ID
- MODEL_SCORE
- CLAIM_RISK_SCORE
- FINAL_RISK_LEVEL
- FINAL_CLAIM_RANK
- Other unified claim information

Claims:
65,941

Claim types:
- CARRIER
- INPATIENT
- OUTPATIENT

This is the main claim-risk OUTPUT dataset.

------------------------------------------------------------
2. unified_claim_risk_with_provider.csv
------------------------------------------------------------

Earlier unified claim-risk output containing provider mapping.

Useful for:
- Claim-provider analysis
- Provider-level investigation
- Connecting claim risk to provider information

------------------------------------------------------------
3. claims_clean.parquet
------------------------------------------------------------

Cleaned claims dataset.

Potential source for:
- Claim-level features
- Feature inspection
- XAI feature construction

------------------------------------------------------------
4. claims_master.parquet
------------------------------------------------------------

Master claims dataset.

Potential source for:
- Claim-level information
- Feature reconstruction
- XAI feature construction

------------------------------------------------------------
5. old_claims_scripts/
------------------------------------------------------------

Previous feature-engineering and claim-risk scripts.

Includes:
- build_claim_database.py
- build_claim_360.py
- build_unified_claim_risk.py
- finalize_claim_risk.py
- add_provider_to_unified_claims.py

These scripts are retained for understanding how the
previous claim features and risk outputs were generated.

------------------------------------------------------------
IMPORTANT
------------------------------------------------------------

The final_unified_claim_risk.csv is a standardized
RISK OUTPUT dataset.

It is NOT by itself the complete SHAP/XAI feature matrix.

For XAI, the next step is to identify the exact model
features used by the Carrier, Inpatient and Outpatient
models and connect those features to the standardized
claim risk output.

No model retraining is performed by this package.

============================================================
