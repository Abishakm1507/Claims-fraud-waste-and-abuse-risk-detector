# Data Contract Validation v1

## Scope

This validation checks whether the real upstream ML exports can populate the Investigation Contract v1 without fabricating missing evidence.

Datasets audited:
- `data/claims/final_unified_claim_risk.csv`
- `models/provider/output/provider_risk_scores.csv`

## Verified Dataset Facts

From the actual files in this workspace:
- Claim rows: 65,941
- Provider rows: 36,108
- Claim claim types:
  - OUTPATIENT: 38,409
  - INPATIENT: 20,867
  - CARRIER: 6,665

The exported data contains the canonical fields needed to populate a valid deterministic investigation context:
- `CLAIM_ID`
- `PROVIDER_ID`
- `PROVIDER_ID_TYPE`
- `CLAIM_TYPE`
- `CLAIM_RISK_SCORE`
- `FINAL_RISK_LEVEL`
- `FINAL_RISK_PRIORITY`
- `FINAL_CLAIM_RANK`
- provider-level `NPI`, `Provider_Risk_Score`, and related anomaly fields

## Contract Fit Assessment

### Result
Yes — the current Provider ML + Claims ML outputs are sufficient to reliably populate `InvestigationContext` and produce a valid `InvestigationCase` in the deterministic pipeline.

### Why
- The claim export contains all required claim-level identifiers, claim type, and canonical risk score/rank fields.
- The provider export contains the provider identifier and provider risk score needed for provider-side context.
- The project enforces the required ID distinction:
  - CARRIER → `NPI`
  - INPATIENT / OUTPATIENT → `PRVDR_NUM`
- The project already preserves `UNKNOWN` and explicit missing values instead of coercing or inventing values.

## Explicit Limitations

The real exports are not perfect, and the contract records these limitations explicitly rather than silently fabricating them:

1. Some claim rows do not include a populated `PROVIDER_ID_TYPE` value; the contract defaults to `UNKNOWN` rather than guessing.
2. The current claim export does not include explicit `model_consensus` / `model_consensus_count` fields for inpatient rule trigger logic, so inpatient clinical rule evidence is limited to what is actually exported.
3. The provider export does not always include a full peer benchmark set for all metrics, so peer median and peer benchmark values may be absent and must stay `None`.
4. LEIE exclusion status may be missing in some provider rows, and the data contract treats that as unavailable rather than false.

## Contract Behavior

The validation logic in the project maintains the intended contract discipline:
- required fields are checked against the actual CSV schema
- missing data is reported as `NOT_AVAILABLE` or `None`
- no fabricated peer metrics, risk values, or fraud conclusions are introduced
- deterministic pipeline outputs remain valid while preserving explicit uncertainty

## Conclusion

The data contract is compatible with the real upstream ML exports for deterministic investigation flow. The system can hand off a valid `InvestigationCase`, with limitations represented explicitly instead of being disguised as real evidence.
