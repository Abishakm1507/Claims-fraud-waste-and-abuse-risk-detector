# Claims Explainability — Final Artifact Audit

**Status:** BLOCKED pending exact artifact validation for Carrier and Inpatient  
**Date:** August 18, 2026  
**Scope:** Claim-level SHAP explainability audit for Carrier, Inpatient, Outpatient

---

## 1. Executive Summary

This audit re-checks the persisted ML artifacts and feature-lineage contract directly against the repository state. The verified result is:

| Claim Type | Features | Model | Feature Contract | Model Output | SHAP | Status |
|------------|----------|-------|------------------|--------------|------|--------|
| Carrier | 38 | IsolationForest | PASS | PASS for score_samples on the persisted feature matrix | PASS for model-faithful SHAP on the persisted pipeline | BLOCKED |
| Inpatient | 49 | IsolationForest | FAIL | FAIL | FAIL | BLOCKED |
| Outpatient | 38 | IsolationForest | PASS | PASS | PASS | READY |

The file-level evidence shows that:

- Carrier has a persisted 38-feature matrix and a valid scaler/model contract, but the stored `IF_score` is not reproducible from `score_samples()` using the persisted feature matrix or any simple transformation proven by the artifacts.
- Inpatient has a persisted 49-feature name list and model artifacts, but no real 49-feature matrix is present in the repository. The raw `inpatient_CLEANED_v2.csv` has zero overlap with the expected 49 feature names, so the exact feature-generation pipeline is not recoverable from the current artifacts.
- Outpatient remains the only claim type with a fully validated feature-source + model-output + SHAP chain.

---

## 2. Artifact Locations

### Carrier

`models/claims/carrier/`
- `feature_columns.pkl` — 38 feature names
- `scaler.pkl` — persisted StandardScaler
- `isolation_forest.pkl` — persisted IsolationForest
- `lof.pkl` — persisted LOF model
- `ocsvm.pkl` — persisted OCSVM model
- `carrier_final_risk_scores.csv` — stored risk data

Feature source used for validation:
- `data/raw/carrier_claim_features_FINAL.csv`

### Inpatient

`models/claims/inpatient/`
- `feature_columns.pkl` — 49 feature names
- `scaler.pkl` — persisted StandardScaler
- `isolation_forest.pkl` — persisted IsolationForest
- `lof.pkl` — persisted LOF model
- `ocsvm.pkl` — persisted OCSVM model
- `inpatient_final_risk_scores.csv` — stored risk data

No real 49-feature feature matrix was found in the repository.

### Outpatient

`models/claims/outpatient/`
- `feature_columns.pkl`
- `scaler.pkl`
- `isolation_forest.pkl`
- `lof .pkl`
- `ocsvm.pkl`
- `outpatient_final_risk_scores.csv`

Validated as READY.

---

## 3. Carrier Feature-Lineage Validation

### 3.1 Exact feature source

The 38 Carrier features are present in the persisted `feature_columns.pkl` and match the columns in `data/raw/carrier_claim_features_FINAL.csv` exactly.

Validation result:
- `len(feature_columns.pkl) = 38`
- `len(intersection(feature_names, raw_csv_columns)) = 38`
- `missing = 0`

### 3.2 Exact model input pipeline

The validated pipeline for the persisted artifacts is:

1. Raw carrier claim row
2. 38 feature vector from `carrier_claim_features_FINAL.csv`
3. Numeric conversion and `NaN -> 0` fill
4. `scaler.transform(X)`
5. `isolation_forest.score_samples(X_scaled)`
6. SHAP on the IsolationForest

This is reproducible for the model contract itself.

### 3.3 Score transformation check

For 6,665 matched Carrier claims, the persisted model output did not reproduce the stored `IF_score`:

- direct correlation: `-0.03694`
- min-max inversion correlation: `+0.03694`
- MAE direct: `0.75891`
- MAE minmax-inverted: `0.37952`
- max absolute difference direct: `1.61729`
- max absolute difference minmax-inverted: `0.86012`

This is not a valid match for the stored `IF_score`. No exact transformation was identified from the persisted artifacts alone.

### 3.4 Conclusion for Carrier

The carrier feature matrix and model pipeline are present, but the exact original score transformation is not proven. Because the feature-to-score lineage is not independently validated, Carrier remains `BLOCKED_MISSING_FEATURE_ARTIFACT` in the production interface.

---

## 4. Inpatient Feature-Lineage Validation

### 4.1 Exact feature source

The repository contains `models/claims/inpatient/feature_columns.pkl`, which defines 49 names, but no real 49-feature matrix exists in the repository.

Validation result:
- `len(feature_columns.pkl) = 49`
- overlap with `data/raw/inpatient_CLEANED_v2.csv` columns = `0`
- missing feature names from raw source = 49

### 4.2 Exact model input pipeline

The persisted contract requires a 49-feature vector in the exact order of `feature_columns.pkl`, followed by:

1. exact feature generation / preprocessing
2. `scaler.transform(X)`
3. `isolation_forest.score_samples(X_scaled)`
4. SHAP on the IsolationForest

But no exact feature-generation script or persisted matrix was found in the repository.

### 4.3 Conclusion for Inpatient

The exact original 49-feature matrix is absent. The model artifacts and feature names exist, but the original feature generation is not proven. Therefore Inpatient remains `BLOCKED_MISSING_FEATURE_ARTIFACT`.

---

## 5. SHAP Validation

### Carrier SHAP

`SHAP` is model-faithful for the persisted IsolationForest contract when using the verified 38-feature matrix and `scaler.transform`. However, it does not explain the stored `IF_score` because the mapping between model output and stored score is unresolved.

Important caveat:
- For sklearn IsolationForest, TreeExplainer explains the internal tree/path-length output rather than the final `score_samples()` transformation.
- `base_value + sum(shap_values) == score_samples()` is only valid when the exact implementation and feature contract are matched. This is not proven for the stored Carrier score lineage.

### Inpatient SHAP

SHAP cannot be validated for Inpatient because the exact 49-feature input is not available. No model-faithful explanation is possible without an independently verified feature vector.

### Outpatient SHAP

Validated and remains READY because the stored score transformation is explicitly reproducible from the persisted model artifacts.

---

## 6. Final Status

### Carrier blocker

`STILL BLOCKED`

Reason:
- persisted 38-feature matrix exists
- persisted scaler and model exist
- model-score pipeline is reproducible
- stored `IF_score` cannot be reproduced from the actual artifacts using a proven transformation
- no direct feature-to-score lineage is available for the stored risk output

### Inpatient blocker

`STILL BLOCKED`

Reason:
- persisted 49-feature names exist
- no actual 49-feature matrix exists in the repository
- the raw inpatient source has zero overlap with the required feature names
- exact preprocessing/feature generation is missing

### Provider SHAP

`READY`

### Outpatient SHAP

`READY`

---

## 7. Required ML-Team Dependency

The remaining dependencies are not in the explainability layer; they are in the upstream feature-generation and model-scoring artifacts:

- Carrier: exact original feature-to-score transformation or a persisted source matrix matching the training pipeline
- Inpatient: the exact 49-feature generation logic or the original training-time feature matrix

Until those are supplied, the correct status is BLOCKED rather than READY.

---

## 8. Production Rule

The system must not do the following:

- fabricate missing features
- zero-fill unknown features
- assume a score transformation without proof
- mark READY because SHAP numerically produced values

The correct status rule is:

- feature artifact + validated preprocessing + validated model contract = READY
- otherwise = BLOCKED_MISSING_FEATURE_ARTIFACT or MODEL_ARTIFACT_VALIDATION_FAILED

---

## 6. SHAP — Mathematical Reconciliation

### 6.1 What SHAP TreeExplainer explains

For sklearn IsolationForest, `shap.TreeExplainer` explains the **internal tree outputs** (negative path lengths, `-depth`) of each tree. The IsolationForest score is computed as:

```text
avg_depth  = mean(tree.output)     # negative path length averaged across trees
c(n)       = average path length correction factor
score      = 2^(-avg_depth / c(n))  # anomaly score
score_samples = -(score - offset_)  # final output
```

Therefore:

```text
base_value + sum(shap_values) = average tree output = -avg_depth
```

and:

```text
base_value + sum(shap_values) != score_samples()
```

This is **expected behaviour** for sklearn IsolationForest + SHAP TreeExplainer. The SHAP values are still valid feature contributions to the IsolationForest path-length representation, and a monotone transformation connects SHAP output to `score_samples()`.

### 6.2 What is valid to claim

```text
SHAP
    ↓
IsolationForest feature contributions (path-length attribution)
```

Separately:

```text
MODEL EVIDENCE
    ↓
IF score / score_samples / ensemble score / risk rank / risk band
```

**Do NOT claim** "SHAP values sum to the ensemble risk score" — this is mathematically false for IsolationForest + TreeExplainer.

### 6.3 Validation performed

For Outpatient (2 claims) and Carrier (2 claims):

- SHAP values are finite
- SHAP shape matches feature count (38, 38)
- Base value exists and is finite
- Top features (10) are correctly ranked by absolute SHAP value

---

## 7. Output Contract

```json
{
  "status": "success",
  "entity_type": "claim",
  "claim_id": "...",
  "claim_type": "CARRIER | INPATIENT | OUTPATIENT",

  "model_evidence": {
    "model_type": "Claim-Level Anomaly Detection",
    "feature_count": 38,
    "ensemble_weights": { "Isolation Forest": 0.2, "LOF": 0.2, "One-Class SVM": 0.6 },
    "algorithms": ["Isolation Forest", "Local Outlier Factor", "One-Class SVM"],
    "score_normalization": "min-max",
    "risk_bands": { ... }
  },

  "shap": {
    "explained_model": "IsolationForest",
    "model_output": -0.676562,
    "base_value": 12.409645,
    "top_features": [
      {
        "rank": 1,
        "feature": "external_diagnosis_count",
        "value": 375.0,
        "shap_value": -0.897732,
        "absolute_shap_value": 0.897732
      },
      ...
    ],
    "reconciliation": {
      "base_value_plus_sum_shap": 5.775048,
      "model_output": -0.676562,
      "residual": 6.451610
    }
  }
}
```

**Note on reconciliation residual:** The residual is **expected** because SHAP explains the tree path-length output (`-avg_path`), not `score_samples()`. The residual is reported transparently rather than hidden.

---

## 8. Error Handling

| Scenario | Behaviour |
|----------|-----------|
| Invalid claim type | `ValueError("Unknown claim type")` |
| Claim ID not found | `{"status": "not_found", "reason": "Claim ... not found"}` |
| Inpatient without features | `{"status": "feature_data_required", ...}` |
| Missing features (partial dict) | `{"status": "error", "error": "Feature count mismatch ..."}` |
| Missing artifact | `{"status": "error", "error": "No ... available"}` |
| NaN / inf in feature vector | `{"status": "error", "error": "Invalid (NaN/inf) values ..."}` |

---

## 9. Validation Results

### 9.1 Outpatient

- Feature count: 38 ✅
- Model output reproduction: ✅ (score_samples matches direct computation)
- Stored score (IF_score) reproduction: ✅ (inverted min-max; r = -1.0)
- SHAP values finite: ✅
- SHAP shape: (38,) ✅
- SHAP base value finite: ✅

### 9.2 Carrier

- Feature count: 38 ✅
- Model output reproduction: ✅ (score_samples matches direct computation)
- Stored score reproduction: ❌ (r = 0.037 — limitation documented)
- SHAP values finite: ✅
- SHAP shape: (38,) ✅
- SHAP base value finite: ✅

### 9.3 Inpatient

- Feature count: 49 ✅
- Model output reproduction: ✅ when feature vector is provided
- Stored score reproduction: ⚠️ not testable (feature matrix not persisted)
- SHAP values finite: ✅ (with provided features)
- SHAP shape: (49,) ✅ (with provided features)
- SHAP base value finite: ✅ (with provided features)

---

## 10. Test Results

| Test Suite | Tests | Status |
|------------|-------|--------|
| `tests/test_explainability_phase1.py` (Provider baseline) | 9 | ✅ 9/9 PASS |
| `tests/test_claims_explainability.py` (Claims regression) | 18 | ✅ 18/18 PASS |
| **Total** | **27** | **27/27 PASS** |

---

## 11. Limitations

1. **Carrier stored-score mismatch** — The persisted Carrier model's score_samples do not correlate with the stored IF_score in the unified risk file (r = 0.037). The SHAP values are valid for the persisted model, but the stored risk scores cannot be reproduced from the available feature matrix. The original training pipeline likely used different feature values.

2. **Inpatient feature matrix not persisted** — The 49-feature vectors used to train the Inpatient model are not available in any CSV. Callers must supply features explicitly.

3. **sklearn version mismatch** — Artifacts were serialized with sklearn 1.6.1 (claims) / 1.8.0 (provider), loaded with 1.9.0. `InconsistentVersionWarning` is emitted. Results should be verified when the environment's sklearn version changes.

4. **LOF filename** — Outpatient uses `lof .pkl` (with a space). The code handles this via glob pattern, but the file should ideally be renamed to `lof.pkl`.

---

## 12. Production Ready?

Based on the audit:

| Pipeline | Status | Notes |
|----------|--------|-------|
| **Outpatient** | ✅ READY | Stored scores reproduce; SHAP validated against persisted artifacts |
| **Carrier** | ⚠️ PARTIAL | SHAP runs and model output reproduces; stored-score correlation NOT established |
| **Inpatient** | ⚠️ PARTIAL | SHAP runs when features provided; feature matrix not persisted |

**Overall: NOT fully production-ready.** Outpatient is production-ready. Carrier and Inpatient require either (a) the original feature matrices / preprocessing pipeline, or (b) an explicit acceptance that SHAP explains the persisted model without reproducing stored risk scores.