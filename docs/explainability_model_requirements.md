# Claims Model Requirements for Phase 2 Explainability Integration

**Status:** Specification for Future Handoff  
**Purpose:** Define the exact artifacts and metadata required to enable SHAP-based claim explainability  
**Audience:** ML Team (Claims Model Owners), Explainability Team

---

## 1. Executive Summary

To integrate claims into the Phase 2 explainability layer, the ML team must **persist and expose**:

1. **The trained claim IsolationForest model** (or equivalent anomaly model)
2. **The exact feature preprocessing pipeline** (transformations, imputation, scaling)
3. **Feature metadata** (names, types, transformations, human-readable labels)
4. **Validation dataset** (sample of original training features)

Currently, only the **output risk score dataset** is available (`final_unified_claim_risk.csv`). This is insufficient for SHAP explainability.

---

## 2. What We Currently Have (Insufficient)

### 2.1 Current Claim Artifacts

| Artifact | Location | Content | Status |
|----------|----------|---------|--------|
| `final_unified_claim_risk.csv` | `models/claims/` | Risk scores, derived fields, metadata | ✅ Available |
| `README.txt` | `models/claims/` | States "output dataset, not complete feature matrix" | ✅ Available |
| `old_claims_scripts/build_unified_claim_risk.py` | `models/claims/` | Shows downstream processing; **not** the model training code | ✅ Available |

### 2.2 What's Missing

- ❌ **Trained claim IsolationForest model artifact** (joblib/pickle file)
- ❌ **Feature preprocessing pipeline** (sklearn Pipeline or custom transformer)
- ❌ **Original feature matrix** used to train the model
- ❌ **Feature names and types** (canonical list)
- ❌ **Preprocessing details** (imputation strategy, scaling, transformations)
- ❌ **Feature-to-human-label mapping** (e.g., "CLM_PMT_AMT_first" → "First Claim Payment Amount")

---

## 3. Required Deliverables

### 3.1 Model Artifact

**File:** `models/claims/claim_risk_pipeline.joblib`  
**Format:** Serialized sklearn Pipeline or estimator (same as provider)

**Content:** Must include preprocessing and the fitted IsolationForest model

```python
# Example structure (same pattern as provider):
pipeline = sklearn.pipeline.Pipeline([
    ('preprocess', CustomFeaturePreprocessor(...)),  # OR StandardScaler
    ('clip', CustomClipTransformer(...)),            # Optional; for scaling [-10, 10]
    ('iforest', IsolationForest(n_estimators=100, contamination=0.1, ...))
])

joblib.dump(pipeline, 'models/claims/claim_risk_pipeline.joblib')
```

**Constraints:**
- Must load without errors in Python 3.13
- All custom transformer classes must be importable (e.g., from a `claim_preprocessing.py` module)
- Feature order must be deterministic and stable across runs

### 3.2 Feature Preprocessing Module

**File:** `models/claims/claim_preprocessing.py`  
**Format:** Python module with custom transformer classes

**Requirements:**

```python
# Example structure:
class ClaimFeaturePreprocessor(BaseEstimator, TransformerMixin):
    """Transform raw claim data into model features."""
    
    def fit(self, X, y=None):
        # Learn statistics (e.g., median for imputation)
        return self
    
    def transform(self, X):
        # Apply transformations (log, ratio, imputation, etc.)
        return transformed_X
    
    def get_feature_names_out(self, input_features=None):
        # Return canonical list of output feature names
        return np.array([
            'CLM_PMT_AMT_first',
            'NCH_CARR_CLM_SBMTD_CHRG_AMT_first',
            'NCH_CARR_CLM_ALOWD_AMT_first',
            'claim_line_count',
            'unique_revenue_center_count',
            'payment_to_charge_ratio',
            'claim_duration_days',
            # ... all features used by the model ...
        ])
```

**Key Points:**
- Must inherit from `sklearn.base.BaseEstimator` and `TransformerMixin`
- Must implement `fit()`, `transform()`, and `get_feature_names_out()`
- Imputation and scaling logic must be **deterministic and reproducible**
- Missingness handling must be **explicit and documented**

### 3.3 Feature Metadata

**File:** `models/claims/claim_feature_columns.json`  
**Format:** JSON with feature details

```json
{
  "raw_features": [
    "CLM_PMT_AMT",
    "NCH_CARR_CLM_SBMTD_CHRG_AMT",
    "NCH_CARR_CLM_ALOWD_AMT",
    "claim_line_count",
    "unique_revenue_center_count",
    "payment_to_charge_ratio",
    "claim_duration_days"
  ],
  "model_features": [
    "CLM_PMT_AMT_first",
    "NCH_CARR_CLM_SBMTD_CHRG_AMT_first",
    "NCH_CARR_CLM_ALOWD_AMT_first",
    "claim_line_count",
    "unique_revenue_center_count",
    "payment_to_charge_ratio",
    "claim_duration_days"
  ],
  "feature_order": [
    "CLM_PMT_AMT_first",
    "NCH_CARR_CLM_SBMTD_CHRG_AMT_first",
    ...
  ],
  "feature_types": {
    "CLM_PMT_AMT_first": "float",
    "claim_line_count": "int",
    ...
  },
  "transformations": {
    "CLM_PMT_AMT_first": "none",
    "claim_duration_days": "log1p"
  },
  "missingness_strategy": {
    "CLM_PMT_AMT_first": "median_imputation",
    "claim_line_count": "zero_fill"
  }
}
```

### 3.4 Feature-to-Label Mapping

**File:** `models/claims/claim_feature_mapping.json`  
**Format:** JSON with human-readable feature names

```json
{
  "CLM_PMT_AMT_first": "First Claim Payment Amount (USD)",
  "NCH_CARR_CLM_SBMTD_CHRG_AMT_first": "First Submitted Charge Amount (USD)",
  "NCH_CARR_CLM_ALOWD_AMT_first": "First Allowed Amount (USD)",
  "claim_line_count": "Number of Claim Lines",
  "unique_revenue_center_count": "Unique Revenue Centers",
  "payment_to_charge_ratio": "Payment-to-Charge Ratio",
  "claim_duration_days": "Claim Duration (Days)"
}
```

### 3.5 Model Metadata

**File:** `models/claims/claim_model_metadata.json`  
**Format:** JSON with model configuration and statistics

```json
{
  "model_type": "sklearn.ensemble.IsolationForest",
  "bundled_as": "sklearn.pipeline.Pipeline (preprocess -> [clip] -> IsolationForest)",
  "n_features": 7,
  "n_estimators": 100,
  "contamination": 0.1,
  "random_state": 42,
  "feature_names": ["CLM_PMT_AMT_first", ...],
  "training_data_shape": [100000, 7],
  "training_set_period": "2020-2024",
  "preprocessor_type": "ClaimFeaturePreprocessor",
  "sklearn_version": "1.9.0",
  "python_version": "3.13"
}
```

### 3.6 Validation Dataset

**File:** `models/claims/claim_training_sample.csv`  
**Format:** CSV with sample of preprocessed features used in training

**Purpose:** Allows the explainability team to verify:
- Feature ranges and distributions
- Presence of expected columns
- Preprocessing is working correctly

**Size:** At least 100 representative rows

---

## 4. Integration Path (Phase 2)

### 4.1 Explainability Code Changes

Once deliverables are provided, the `ClaimExplainer` will be updated:

```python
# Before (Phase 1 — blocker)
explainer = ClaimExplainer()
result = explainer.explain_claim(...)
# Returns: {"status": "model_artifact_unavailable", ...}

# After (Phase 2 — with model)
explainer = ClaimExplainer.load_from_artifact(
    model_path="models/claims/claim_risk_pipeline.joblib",
    feature_names_path="models/claims/claim_feature_columns.json",
    feature_mapping_path="models/claims/claim_feature_mapping.json"
)
result = explainer.explain_claim(...)
# Returns: {"entity_type": "claim", "shap": {"base_value": ..., "top_features": [...]}}
```

### 4.2 Validation Steps

1. **Model Load Test:** Verify pipeline loads without errors
2. **Feature Contract Test:** Confirm get_feature_names_out() returns expected 7+ features
3. **SHAP Compatibility Test:** Run TreeExplainer on sample claim feature vectors
4. **Integration Test:** End-to-end explanation generation for 100 random claims

---

## 5. Quality Criteria

### 5.1 Model Reproducibility

- ✅ Same input feature vectors must produce **identical risk scores** across runs
- ✅ SHAP values must be **deterministic** (not random)
- ✅ Feature order must be **stable** (no sorting or shuffling)

### 5.2 Preprocessing Transparency

- ✅ All transformations must be **documented**
- ✅ Missingness handling must be **explicit**
- ✅ Imputation strategies must be **data-driven** (median, not arbitrary)

### 5.3 Compatibility

- ✅ Model must be picklable/serializable
- ✅ Custom classes must be importable from `models/claims/`
- ✅ Must work with `shap.TreeExplainer` (for IsolationForest)
- ✅ Python 3.13 compatible

---

## 6. Timeline & Ownership

| Phase | Responsible Team | Deliverable | Estimated Timeline |
|-------|------------------|-------------|---------------------|
| **Phase 1** | Explainability | Provider SHAP (complete) | ✅ Done |
| **Phase 2** | ML Team (Claims) | Model + metadata + preprocessing | 2-4 weeks |
| **Phase 2** | Explainability | Integration, validation, testing | 1-2 weeks |

---

## 7. Common Pitfalls to Avoid

1. **❌ Serializing only the IsolationForest, not the preprocessing**
   - **Why it fails:** SHAP requires exact feature order and preprocessing
   - **Solution:** Persist as sklearn.pipeline.Pipeline

2. **❌ Using a different feature order in the model than in the CSV**
   - **Why it fails:** SHAP values won't align with risk scores
   - **Solution:** Enforce consistent feature order via `get_feature_names_out()`

3. **❌ Omitting imputation or scaling logic from the persistent model**
   - **Why it fails:** SHAP computes on preprocessed features; if preprocessing is missing, values are meaningless
   - **Solution:** Include all preprocessing in the Pipeline

4. **❌ Non-deterministic imputation (e.g., random sampling)**
   - **Why it fails:** Same claim produces different SHAP values each time
   - **Solution:** Use deterministic strategies (median, mode, forward-fill)

5. **❌ Losing custom transformer classes after model serialization**
   - **Why it fails:** joblib.load() fails if custom classes are not importable
   - **Solution:** Persist classes in a dedicated `claim_preprocessing.py` module on the Python path

---

## 8. Questions & Support

**For questions during delivery:**
- **What feature transformations were used?** → Review model training logs, training data EDA
- **How were missing values handled?** → Check data cleaning scripts, describe in `claim_preprocessing.py`
- **What was the training set?** → Provide sample data in `claim_training_sample.csv`
- **Is the model frozen, or will it be retrained?** → If retrained, will the feature contract change?

---

## 9. Example Handoff Checklist

Before Phase 2 integration can begin, verify:

- [ ] `models/claims/claim_risk_pipeline.joblib` exists and loads without error
- [ ] `models/claims/claim_preprocessing.py` exists with `ClaimFeaturePreprocessor` class
- [ ] `models/claims/claim_feature_columns.json` lists all model features
- [ ] `models/claims/claim_feature_mapping.json` provides human-readable labels
- [ ] `models/claims/claim_model_metadata.json` documents model configuration
- [ ] `models/claims/claim_training_sample.csv` contains 100+ sample rows
- [ ] Sample code can load the model and call `predict()` on sample data
- [ ] Feature order is stable: `pipeline.named_steps['preprocess'].get_feature_names_out()` returns same order every time
- [ ] SHAP TreeExplainer works on the IsolationForest component

---

## 10. Success Criteria

Phase 2 is considered **complete** when:

1. ✅ Claims can be explained with SHAP (same interface as providers)
2. ✅ SHAP values are **deterministic and reproducible**
3. ✅ **Top 10 features** are ranked by absolute contribution
4. ✅ **base_value** is included in the output
5. ✅ **All regression tests pass** (100% coverage of provider path + claims path)
6. ✅ **No error messages** from joblib.load() or preprocessing
7. ✅ **Feature names** are consistent across model, SHAP output, and mapping

---

**Document Version:** 1.0  
**Created:** Phase 1 Completion (Blocking Status → Requirements for Phase 2)  
**Status:** Ready for ML Team Handoff
