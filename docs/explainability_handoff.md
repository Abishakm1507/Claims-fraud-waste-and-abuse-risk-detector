# Explainability Handoff — Claims SHAP Audit & Integration Status

**Date:** August 18, 2026  
**Audience:** ML Team, GenAI Team, Multi-Agent Team, RAG Team  
**Status:** Claims explainability is PARTIALLY production-ready — see below

---

## 1. What Is Ready

### 1.1 Provider SHAP — READY (unchanged)

- `ProviderExplainer` in `explainability/provider_explainer.py`
- 9/9 Provider regression tests pass
- Uses the persisted `provider_risk_pipeline.joblib` (46 features)

### 1.2 Outpatient Claim SHAP — READY

- Uses persisted artifacts under `/models/claims/outpatient/`
- 38 features from `outpatient_final_risk_scores.csv`
- Stored `IF_score` reproduces from the model (`score_samples()` inverted min-max)
- Ensures ensemble weights are read from `model_config.pkl` (IF=20%, LOF=20%, OCSVM=60%)

### 1.3 Carrier Claim SHAP — PARTIAL

- 38 features from `data/raw/carrier_claim_features_FINAL.csv`
- Model output (`score_samples()`) reproduces
- SHAP values are finite and correctly shaped
- ⚠️ **Stored IF_score does NOT correlate with recomputed model** (r = 0.037)
  - The persisted feature matrix may differ from what was used in the original training scoring.
  - SHAP is still valid for the persisted model, but the risk scores cannot be reproduced.

### 1.4 Inpatient Claim SHAP — PARTIAL

- 49 features from `feature_columns.pkl`
- Artifacts load correctly (scaler, IsolationForest)
- ⚠️ **Feature matrix is NOT persisted** in any CSV
  - `inpatient_final_risk_scores.csv` has only scores, not features
  - Callers must supply the 49-feature vector explicitly
  - Without features, the explainer returns `feature_data_required`

---

## 2. Integration Contract

### 2.1 Main Entry Point

```python
from explainability.claims_explainer_prod import explain_claim

# Outpatient / Carrier
result = explain_claim(claim_id, "OUTPATIENT")   # features auto-loaded
result = explain_claim(claim_id, "CARRIER")      # features auto-loaded

# Inpatient (features must be provided)
features = {...}  # 49 features
result = explain_claim(claim_id, "INPATIENT", features=features)
```

### 2.2 Response

```json
{
  "status": "success | not_found | feature_data_required | error",
  "entity_type": "claim",
  "claim_id": "...",
  "claim_type": "CARRIER | INPATIENT | OUTPATIENT",
  "model_evidence": { ... },
  "shap": {
    "explained_model": "IsolationForest",
    "model_output": -0.67,
    "base_value": 12.41,
    "top_features": [...],
    "reconciliation": { ... }
  }
}
```

### 2.3 Status Meanings

| Status | Meaning |
|--------|---------|
| `success` | SHAP computed successfully |
| `not_found` | Claim ID not found in the data source |
| `feature_data_required` | Inpatient: feature vector not supplied |
| `error` | A validation/processing error occurred (with descriptive message) |

---

## 3. What "SHAP Target" Means

```
SHAP explains → IsolationForest internal tree outputs (negative path lengths)

MODEL OUTPUT  → IsolationForest.score_samples()   (raw anomaly score)
STORED SCORE  → Normalized per-claim risk score (min-max / rank)
RISK BAND     → Critical / High / Medium / Low
ENSEMBLE      → Weighted combination of IF + LOF + OCSVM
```

These are **distinct concepts**. The SHAP output does NOT directly sum to the stored risk score or ensemble score.

---

## 4. Known Blockers

1. **Carrier feature-vector mismatch** (stored scores don't reproduce)
2. **Inpatient feature matrix not persisted**
3. **sklearn version mismatch** (1.6.1/1.8.0 artifacts loaded with 1.9.0)

---

## 5. Files

| File | Purpose |
|------|---------|
| `explainability/claims_explainer_prod.py` | **Production claims SHAP explainer (audited)** |
| `explainability/claims_explainer.py` | Legacy generic explainer (kept for backward compat) |
| `explainability/claims_explainer_v2.py` | Legacy per-type explainer (kept for reference) |
| `explainability/claims_explainer_v3.py` | Legacy unified-data explainer (kept for reference) |
| `tests/test_claims_explainability.py` | New regression tests (**18 tests**) |
| `tests/test_explainability_phase1.py` | Provider + legacy claim tests (**9 tests**) |
| `docs/claims_explainability.md` | Full audit & status documentation |

---

## 6. Next Steps

1. **Obtain the original Carrier feature matrix** used during training (to reproduce stored scores)
2. **Persist the Inpatient feature matrix** (or provide a feature-engineering script)
3. **Rename** `models/claims/outpatient/lof .pkl` → `lof.pkl`
4. **Align sklearn versions** for production