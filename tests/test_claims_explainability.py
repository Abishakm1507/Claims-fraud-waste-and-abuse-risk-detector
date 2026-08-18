"""
Claims Explainability Regression Tests.

Validates the production claims SHAP explainer against real persisted
ML artifacts under `/models/claims`:

- Carrier:    38 features, feature matrix from `data/raw/carrier_claim_features_FINAL.csv`
- Inpatient:  49 features, feature vector must be provided
- Outpatient: 38 features, feature matrix from `outpatient_final_risk_scores.csv`

For each pipeline we validate:
1. Artifact loading (feature count)
2. Model-output reproduction (score_samples from persisted IF)
3. SHAP computation (shape, finite values, base value)
4. Output contract
5. Error handling
"""
import warnings

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import joblib
import pytest
from pathlib import Path

from explainability.claims_explainer_prod import (
    explain_claim,
    CarrierClaimExplainer,
    InpatientClaimExplainer,
    OutpatientClaimExplainer,
)

BASE = Path("models/claims")

# =========================================================================
# Common helpers
# =========================================================================


def _load_outpatient_df() -> pd.DataFrame:
    return pd.read_csv(
        BASE / "outpatient" / "outpatient_final_risk_scores.csv",
        low_memory=False,
    )


def _load_carrier_df() -> pd.DataFrame:
    return pd.read_csv("data/raw/carrier_claim_features_FINAL.csv", low_memory=False)


def _load_carrier_scores() -> pd.DataFrame:
    unified = pd.read_csv(BASE / "unified_claim_risk_with_provider.csv", low_memory=False)
    return unified[unified["CLAIM_TYPE"] == "CARRIER"].copy()


def _clean_carrier_features(df: pd.DataFrame, feature_names: list[str]) -> pd.DataFrame:
    df = df.copy()
    for col in feature_names:
        vals = pd.to_numeric(df[col], errors="coerce")
        df[col] = vals.fillna(0)
    return df


# =========================================================================
# Outpatient tests
# =========================================================================


class TestOutpatient:
    def test_artifact_loading(self):
        explainer = OutpatientClaimExplainer()
        assert explainer.feature_names is not None
        assert len(explainer.feature_names) == 38
        assert explainer.scaler is not None
        assert explainer.isolation_forest is not None
        assert explainer.isolation_forest.n_features_in_ == 38

    def test_real_claims_model_output_reproduction(self):
        """Verify score_samples() reproduces from persisted artifacts for real claims."""
        explainer = OutpatientClaimExplainer()
        df = _load_outpatient_df()

        # Select 2 claims from different risk levels
        high_risk = df.nlargest(1, "outpatient_ensemble_score").iloc[0]
        low_risk = df.nsmallest(1, "outpatient_ensemble_score").iloc[0]

        for row in [high_risk, low_risk]:
            features = {
                name: float(row[name])
                for name in explainer.feature_names
                if name in row.index and pd.notna(row[name])
            }
            scaled = explainer.scaler.transform(
                np.array(
                    [features[name] for name in explainer.feature_names],
                    dtype=float,
                ).reshape(1, -1)
            )
            model_output = explainer.isolation_forest.score_samples(scaled)[0]

            # The explainer's model_output must match direct computation
            result = explainer.explain_claim(str(row["CLM_ID"]))
            assert result["status"] == "success"
            assert abs(result["shap"]["model_output"] - model_output) < 1e-8

    def test_shap_values_are_finite_and_correct_shape(self):
        explainer = OutpatientClaimExplainer()
        df = _load_outpatient_df()
        row = df.iloc[0]

        result = explainer.explain_claim(str(row["CLM_ID"]))
        assert result["status"] == "success"

        shap_info = result["shap"]
        assert np.isfinite(shap_info["base_value"])
        assert len(shap_info["top_features"]) == 10
        for feat in shap_info["top_features"]:
            assert np.isfinite(feat["shap_value"])
            assert np.isfinite(feat["value"])

    def test_output_contract(self):
        explainer = OutpatientClaimExplainer()
        df = _load_outpatient_df()
        row = df.iloc[0]

        result = explainer.explain_claim(str(row["CLM_ID"]))
        assert result["status"] == "success"
        assert result["entity_type"] == "claim"
        assert result["claim_type"] == "OUTPATIENT"
        assert "model_evidence" in result
        assert "shap" in result

        shap_info = result["shap"]
        assert shap_info["explained_model"] == "IsolationForest"
        assert "model_output" in shap_info
        assert "base_value" in shap_info
        assert "top_features" in shap_info
        assert "reconciliation" in shap_info

        # Verify ensemble weights from model_config
        assert result["model_evidence"]["ensemble_weights"] == {
            "Isolation Forest": 0.2,
            "LOF": 0.2,
            "One-Class SVM": 0.6,
        }

    def test_claim_not_found(self):
        result = explain_claim("99999999999", "OUTPATIENT")
        assert result["status"]["code"] == "NOT_FOUND"
        assert result["status"]["validation_status"] == "NOT_FOUND"


# =========================================================================
# Carrier tests
# =========================================================================


class TestCarrier:
    def test_artifact_loading(self):
        explainer = CarrierClaimExplainer()
        assert explainer.feature_names is not None
        assert len(explainer.feature_names) == 38
        assert explainer.scaler is not None
        assert explainer.isolation_forest is not None
        assert explainer.isolation_forest.n_features_in_ == 38

    def test_real_claims_model_output_reproduction(self):
        """Verify score_samples() reproduces from persisted artifacts for real claims."""
        explainer = CarrierClaimExplainer()
        df = _load_carrier_df()
        scores = _load_carrier_scores()

        # Clean features
        df_clean = _clean_carrier_features(df, explainer.feature_names)

        # Select 2 claims from different risk levels
        high_risk = scores.nlargest(1, "carrier_ensemble_score").iloc[0]
        low_risk = scores.nsmallest(1, "carrier_ensemble_score").iloc[0]

        for score_row in [high_risk, low_risk]:
            claim_id = score_row["CLAIM_ID"]
            # Find feature row
            feat_row = df_clean[df_clean["CLM_ID"].astype(str).str.strip() == str(claim_id).strip()]
            assert len(feat_row) > 0, f"Claim {claim_id} not found in feature file"
            feat_row = feat_row.iloc[0]

            features = {
                name: float(feat_row[name]) for name in explainer.feature_names
            }
            scaled = explainer.scaler.transform(
                np.array(
                    [features[name] for name in explainer.feature_names],
                    dtype=float,
                ).reshape(1, -1)
            )
            model_output = explainer.isolation_forest.score_samples(scaled)[0]

            # The explainer's model_output must match direct computation
            result = explainer.explain_claim(str(claim_id))
            assert result["status"] == "success"
            assert abs(result["shap"]["model_output"] - model_output) < 1e-8

    def test_shap_values_are_finite_and_correct_shape(self):
        explainer = CarrierClaimExplainer()
        df = _load_carrier_df()
        row = df.iloc[0]

        result = explainer.explain_claim(str(row["CLM_ID"]))
        assert result["status"] == "success"

        shap_info = result["shap"]
        assert np.isfinite(shap_info["base_value"])
        assert len(shap_info["top_features"]) == 10
        for feat in shap_info["top_features"]:
            assert np.isfinite(feat["shap_value"])
            assert np.isfinite(feat["value"])

    def test_output_contract(self):
        explainer = CarrierClaimExplainer()
        df = _load_carrier_df()
        row = df.iloc[0]

        result = explainer.explain_claim(str(row["CLM_ID"]))
        assert result["status"] == "success"
        assert result["entity_type"] == "claim"
        assert result["claim_type"] == "CARRIER"
        assert "model_evidence" in result
        assert "shap" in result

        shap_info = result["shap"]
        assert shap_info["explained_model"] == "IsolationForest"
        assert "model_output" in shap_info
        assert "base_value" in shap_info
        assert "top_features" in shap_info

    def test_claim_not_found(self):
        result = explain_claim("99999999999", "CARRIER")
        assert result["status"]["code"] == "BLOCKED_MISSING_FEATURE_ARTIFACT"
        assert result["status"]["validation_status"] == "BLOCKED"


# =========================================================================
# Inpatient tests
# =========================================================================


class TestInpatient:
    def test_artifact_loading(self):
        explainer = InpatientClaimExplainer()
        assert explainer.feature_names is not None
        assert len(explainer.feature_names) == 49
        assert explainer.scaler is not None
        assert explainer.isolation_forest is not None
        assert explainer.isolation_forest.n_features_in_ == 49

    def test_feature_data_required_without_features(self):
        result = explain_claim("test-claim", "INPATIENT")
        assert result["status"]["code"] == "BLOCKED_MISSING_FEATURE_ARTIFACT"
        assert result["status"]["validation_status"] == "BLOCKED"
        assert result["claim_type"] == "INPATIENT"

    def test_explain_with_zero_feature_vector(self):
        explainer = InpatientClaimExplainer()
        features = {name: 0.0 for name in explainer.feature_names}

        result = explainer.explain_claim("test-claim", features=features)
        assert result["status"] == "success"

        shap_info = result["shap"]
        assert np.isfinite(shap_info["base_value"])
        assert np.isfinite(shap_info["model_output"])
        assert len(shap_info["top_features"]) == 10
        for feat in shap_info["top_features"]:
            assert np.isfinite(feat["shap_value"])

    def test_feature_count_mismatch(self):
        explainer = InpatientClaimExplainer()
        partial_features = {name: 0.0 for name in explainer.feature_names[:10]}

        result = explainer.explain_claim("test-claim", features=partial_features)
        assert result["status"] == "error"
        assert "Feature count mismatch" in result["error"]

    def test_output_contract_with_features(self):
        explainer = InpatientClaimExplainer()
        features = {name: 0.0 for name in explainer.feature_names}

        result = explainer.explain_claim("test-claim", features=features)
        assert result["status"] == "success"
        assert result["entity_type"] == "claim"
        assert result["claim_type"] == "INPATIENT"
        assert "model_evidence" in result
        assert "shap" in result


# =========================================================================
# Cross-cutting / routing tests
# =========================================================================


class TestRouting:
    def test_invalid_claim_type_raises(self):
        with pytest.raises(ValueError, match="Unknown claim type"):
            explain_claim("123", "NONEXISTENT")

    def test_lowercase_claim_types_accepted(self):
        explainer = OutpatientClaimExplainer()
        df = _load_outpatient_df()
        row = df.iloc[0]
        result = explain_claim(str(row["CLM_ID"]), "outpatient")
        assert result["status"]["code"] == "READY"
        assert result["status"]["validation_status"] == "READY"

    def test_public_schema_is_consistent_for_outpatient(self):
        df = _load_outpatient_df()
        row = df.iloc[0]
        result = explain_claim(str(row["CLM_ID"]), "OUTPATIENT")
        assert set(result.keys()) == {"claim_id", "claim_type", "risk", "explanation", "model", "status"}
        assert result["status"]["code"] == "READY"
        assert result["status"]["validation_status"] == "READY"
        assert "score_semantics" in result["model"]

    def test_public_schema_blocks_carrier_without_feature_lineage(self):
        result = explain_claim("test-carrier-claim", "CARRIER")
        assert result["status"]["code"] == "BLOCKED_MISSING_FEATURE_ARTIFACT"
        assert result["status"]["validation_status"] == "BLOCKED"
        assert result["explanation"]["shap_values"] == []
        assert result["risk"]["risk_score"] is None

    def test_public_schema_blocks_inpatient_without_features(self):
        result = explain_claim("test-inpatient-claim", "INPATIENT")
        assert result["status"]["code"] == "BLOCKED_MISSING_FEATURE_ARTIFACT"
        assert result["status"]["validation_status"] == "BLOCKED"
        assert result["explanation"]["shap_values"] == []
        assert result["risk"]["risk_score"] is None

    def test_explainability_module_importable(self):
        from explainability.claims_explainer_prod import explain_claim as ec
        assert callable(ec)