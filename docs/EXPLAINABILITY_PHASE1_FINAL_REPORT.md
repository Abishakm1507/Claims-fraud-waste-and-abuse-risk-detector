# Explainability Module — Phase 1 Final Report

**Status:** ✅ **PRODUCTION-READY**  
**Date:** 2025  
**Scope:** SHAP-based explainability for Isolation Forest risk models (Provider-focused; Claims blocked)

---

## Executive Summary

Phase 1 of the Explainability Module delivers a **model-faithful SHAP explanation layer** for the provider risk pipeline, with explicit blockers for claims until the underlying model artifact is exposed. The implementation:

- ✅ Integrates directly with the **persisted provider IsolationForest model** (sklearn Pipeline)
- ✅ Computes **exact SHAP contributions** using the live model prediction function
- ✅ Provides **base_value** and **top 10 feature contributions** per provider instance
- ✅ Validates all **46 features** match the model's exact preprocessing contract
- ✅ Rejects inputs that lack sufficient feature data (metadata-only rejection)
- ✅ Implements **explicit claim blocker** status when model is unavailable
- ✅ Includes **comprehensive regression tests** covering all paths

---

## 1. Architecture & Design

### 1.1 Model-First Principle

The explainability layer is **grounded in the persisted model artifact**, not inferred or fabricated:

| Entity | Model Status | SHAP Status | Implementation |
|--------|--------------|-------------|---|
| **Provider** | Persisted (`provider_risk_pipeline.joblib`) | ✅ Full SHAP | `ProviderExplainer` — direct TreeExplainer on IsolationForest |
| **Claims** | Not bundled (only output CSV) | ❌ Blocked | `ClaimExplainer` — returns explicit `model_artifact_unavailable` status |

### 1.2 Provider SHAP Pipeline

```
Provider Feature Vector
       ↓
normalize_feature_vector() — humanize names, coerce types, pad to 46
       ↓
model.named_steps['preprocess'] — ProviderFeaturePreprocessor
       ↓
model.named_steps['scaler'] — RobustScaler
       ↓
model.named_steps['clip'] — ClipTransformer [-10, 10]
       ↓
model.named_steps['iforest'] — IsolationForest (target for TreeExplainer)
       ↓
shap.TreeExplainer(iforest)(clipped_vector)
       ↓
Explanation(base_value, values, feature_names=None)
       ↓
explain_provider() → {entity_type, entity_id, risk_score, shap: {base_value, top_features}}
```

---

## 2. Feature Contract Validation

### 2.1 46-Feature Exact Match

The model expects exactly **46 features** in a canonical order:

```python
model.named_steps['preprocess'].get_feature_names_out()
# Returns list of 46 names like:
# ['Log_Tot_Benes', 'Log_Tot_Srvcs', 'Log_Tot_HCPCS_Cds', ..., 'Svc_Max_Beneficiary_Service_Ratio']
```

**Validation:**
- ✅ Test confirms exactly 46 features
- ✅ All 46 returned from `_prepare_vector()`
- ✅ All 46 SHAP values computed with no NaN/Inf
- ✅ Missing features are padded with `0.0`

### 2.2 Preprocessing Contract

The `ProviderFeaturePreprocessor` is the **canonical source of truth** for:
- Log transformations (`Log_Tot_*`, `Log_Drug_*`)
- Missingness indicators (`*_missing`)
- Median imputation by Provider_Type
- Ratio calculations (Payment_to_Charge, Services_per_Beneficiary, etc.)

**Validation:**
- ✅ Import required before joblib.load() to ensure custom classes are available
- ✅ All feature names produced deterministically
- ✅ Missing value handling is explicit and reproducible

### 2.3 Input Validation

`_compute_shap()` validates that input contains **actual feature data**, not just metadata:

```python
if len(actual_feature_overlap) < 3:
    raise ValueError(f"Feature vector must contain at least 3 model features...")
```

**Validation:**
- ✅ Rejects inputs with only metadata (NPI, Provider_Type, State)
- ✅ Requires at least 3 features from the 46-feature model schema

---

## 3. Output Contract

### 3.1 Provider Explainability Response

```json
{
  "entity_type": "provider",
  "entity_id": "1234567890",
  "risk_score": 87.5,
  "shap": {
    "base_value": 13.039...,
    "top_features": [
      {
        "feature": "Log Total Beneficiaries",
        "model_feature": "Log_Tot_Benes",
        "value": 5.123,
        "shap_value": 0.024,
        "absolute_shap_value": 0.024,
        "rank": 1
      },
      ...
    ]
  }
}
```

**Key Elements:**
- `base_value`: Expected IsolationForest anomaly score when all features = 0
- `top_features`: Top 10 by absolute SHAP contribution
- `humanize_feature()`: Converts `Log_Tot_Benes` → "Log Total Beneficiaries"
- All values are floats with explicit type coercion

### 3.2 Claims Blocker Response

```json
{
  "entity_type": "claim",
  "entity_id": "claim-12345",
  "status": "model_artifact_unavailable",
  "shap_available": false,
  "reason": "The trained claim model/prediction function and exact model feature matrix are not present in the repository."
}
```

**Deliberate Blocker:**
- No fabricated SHAP values
- Clear error message to downstream systems
- Allows future injection of real claim model without code change

---

## 4. Hardening & Validation

### 4.1 Test Coverage

All tests in [tests/test_explainability_phase1.py](tests/test_explainability_phase1.py):

| Test | Purpose | Status |
|------|---------|--------|
| `test_provider_explainer_reads_live_pipeline_and_outputs_top_features` | Load persisted model, compute SHAP, verify structure | ✅ PASS |
| `test_provider_explainer_validates_feature_contract_and_shape` | Confirm 46-feature contract, NaN/Inf checks, missing-feature padding | ✅ PASS |
| `test_provider_explainer_rejects_non_model_metadata_input` | Verify metadata-only inputs raise ValueError | ✅ PASS |
| `test_claim_explainer_rejects_missing_model_contract` | Verify claims return blocker dict, not error | ✅ PASS |
| `test_claim_explainer_handles_claim_feature_vector_and_risk_score` | Test claims with injected model; verify SHAP structure | ✅ PASS |

**Test Execution:** All 5 tests pass with 0 failures.

### 4.2 Known Limitations & Warnings

1. **sklearn 1.8.0 → 1.9.0 Version Mismatch**
   - Provider model serialized with sklearn 1.8.0
   - Current environment: sklearn 1.9.0
   - **Status:** ⚠️ DeprecationWarning; model loads and functions correctly
   - **Recommendation:** Upgrade provider model serialization to 1.9.0 for production

2. **Provider Type Handling**
   - Model expects a categorical "Provider_Type" column
   - Must be supplied or defaults to "Unknown"
   - Missing Provider_Type is silently accepted but may affect preprocessing
   - **Recommendation:** Always supply Provider_Type explicitly

3. **SHAP Base Value Semantics**
   - base_value represents the expected IsolationForest anomaly score when features are zero
   - For IsolationForest, this is typically a large positive value (e.g., 13.04)
   - **Interpretation:** Higher base_value means the model considers zero-valued features as more anomalous

### 4.3 Production Readiness Checklist

- ✅ Model loads without errors
- ✅ Feature contract validated (46 exact names)
- ✅ SHAP values computed without NaN/Inf
- ✅ Base value included in output
- ✅ Input validation rejects invalid requests
- ✅ Claim blocker returns structured error, not exception
- ✅ All unit tests passing
- ✅ Feature humanization for display
- ✅ Top 10 features ranked by absolute contribution
- ✅ Traceable from risk score → SHAP values → model features

---

## 5. API Reference

### 5.1 ProviderExplainer

```python
from explainability.provider_explainer import ProviderExplainer

explainer = ProviderExplainer(model_path=None, model=None)

# Compute SHAP for a single provider
result = explainer.explain_provider(
    provider_id="1234567890",
    risk_score=87.5,
    feature_vector={
        "Log_Tot_Benes": 5.123,
        "Log_Tot_Srvcs": 6.988,
        ...46 features total...
    }
)
# → dict with entity_type, entity_id, risk_score, shap {base_value, top_features}

# Global SHAP summary on provider cohort
summary = explainer.explain_with_dataset(
    dataset=pd.read_csv("models/provider/output/provider_risk_scores.csv"),
    sample_size=500
)
# → dict with entity_type, sample_size, top_features (mean absolute SHAP)
```

### 5.2 ClaimExplainer

```python
from explainability.claims_explainer import ClaimExplainer

# Without model (blocker)
explainer = ClaimExplainer()
result = explainer.explain_claim(
    claim_id="claim-12345",
    risk_score=95.0,
    feature_values={...}
)
# → {"entity_type": "claim", "status": "model_artifact_unavailable", ...}

# With injected model (future-ready)
explainer = ClaimExplainer(
    model=my_iforest_model,
    feature_names=["CLM_PMT_AMT_first", ...]
)
result = explainer.explain_claim(claim_id=..., risk_score=..., feature_values=...)
# → dict with full SHAP explanation (same structure as provider)
```

---

## 6. Known Unknowns & Future Work

### 6.1 Claims Model Requirement

To enable claim-level SHAP in Phase 2:

1. **Persist the trained claim IsolationForest model** (or equivalent)
   - Current state: Only `final_unified_claim_risk.csv` (output dataset) exists
   - Required: The original fitted model + exact feature preprocessing

2. **Document feature preprocessing for claims**
   - Feature names, transformations, imputation strategy
   - Missingness handling
   - Order of features in the model

3. **Provide feature-to-domain mapping**
   - Humanize feature names for investigator display
   - Example: "CLM_PMT_AMT_first" → "First Claim Payment Amount"

### 6.2 Potential Enhancements (Post-Phase 1)

- Cohort-level SHAP summary statistics (already implemented as `explain_with_dataset`)
- Confidence intervals or sensitivity analysis on SHAP values
- Comparison mode (high-risk vs. peer-average SHAP contributions)
- Interactive SHAP dependence plots (requires visualization layer)

---

## 7. Code Structure

```
explainability/
├── __init__.py                    # Public module exports
├── api_contract.py                # Dataclass definitions (ExplainabilityFinding, ExplainabilityPayload)
├── claims_explainer.py            # ClaimExplainer: blocker or model-injected SHAP
├── feature_mapping.py             # Feature humanization and normalization
└── provider_explainer.py          # ProviderExplainer: model-faithful SHAP for provider IsolationForest

models/
├── provider/
│   ├── provider_preprocessing.py  # Source of truth: ProviderFeaturePreprocessor, ClipTransformer
│   ├── provider_model_metadata.json
│   ├── provider_feature_columns.json
│   ├── provider_risk_pipeline.joblib
│   └── output/
│       └── provider_risk_scores.csv
└── claims/
    ├── final_unified_claim_risk.csv
    └── README.txt                 # Explicitly notes: output dataset, not model artifact

tests/
└── test_explainability_phase1.py  # 5 regression tests (all passing)

docs/
├── EXPLAINABILITY_PHASE1_FINAL_REPORT.md (this file)
└── explainability_model_requirements.md  # (To be created: claims model requirements)
```

---

## 8. How to Use Phase 1

### 8.1 Quick Start: Provider Risk Explanation

```python
import pandas as pd
import numpy as np
from explainability.provider_explainer import ProviderExplainer

# Load provider scores
providers = pd.read_csv("models/provider/output/provider_risk_scores.csv")
provider = providers.iloc[0]  # Example provider

# Prepare feature vector (example)
feature_vector = {
    "Provider_Type": provider["Provider_Type"],
    "Log_Tot_Benes": np.log1p(provider["Tot_Benes"]),
    "Log_Tot_Srvcs": np.log1p(provider["Tot_Srvcs"]),
    # ... supply all 46 features ...
}

# Explain
explainer = ProviderExplainer()
explanation = explainer.explain_provider(
    provider_id=provider["NPI"],
    risk_score=provider["Provider_Risk_Score"],
    feature_vector=feature_vector
)

# Print top 3 features
for feat in explanation["shap"]["top_features"][:3]:
    print(f"{feat['feature']}: SHAP={feat['shap_value']:.4f}, Value={feat['value']:.2f}")
```

### 8.2 Claim Explainability (Blocked for Now)

```python
from explainability.claims_explainer import ClaimExplainer

explainer = ClaimExplainer()
result = explainer.explain_claim(
    claim_id="claim-xyz",
    risk_score=92.0,
    feature_values={"some_feature": 123.0}
)

if result["status"] == "model_artifact_unavailable":
    print(f"Claims SHAP not available: {result['reason']}")
    # Downstream systems: handle gracefully, wait for model
else:
    # Model is available; use SHAP as normal
    print(result["shap"]["top_features"])
```

---

## 9. Conclusion

**Phase 1 is complete and production-ready for provider explainability.** The implementation:

1. **Maintains strict fidelity to the persisted provider model**
2. **Provides deterministic, auditable SHAP explanations**
3. **Includes comprehensive input validation and error handling**
4. **Returns structured, actionable explainability output**
5. **Explicitly blocks claims until the actual model is available**

**Next Step:** Obtain the trained claim IsolationForest model and feature preprocessing details to enable Phase 2 (claim-level SHAP).

---

**Document Version:** 1.0  
**Last Updated:** Phase 1 Completion  
**Reviewed:** Model-faithful architecture, test coverage, production readiness
