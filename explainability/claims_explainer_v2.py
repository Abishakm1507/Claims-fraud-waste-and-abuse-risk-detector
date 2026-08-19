"""
Claims SHAP Explainability Module

Provides model-faithful SHAP explanations for claim-level anomaly detection models.
Supports three independent claim pipelines: Carrier, Inpatient, Outpatient.

Each claim type uses its own:
- Feature set (Carrier: 38, Inpatient: 49, Outpatient: 38)
- Preprocessing/scaler
- Anomaly detection models (IsolationForest, LOF, OCSVM)
- SHAP TreeExplainer targeting IsolationForest output

All explainers validate against persisted model artifacts to ensure model-faithfulness.
"""

from __future__ import annotations

import warnings
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Mapping, Sequence

import joblib
import numpy as np
import pandas as pd
import shap

warnings.filterwarnings('ignore', category=UserWarning)


class ClaimExplainerBase(ABC):
    """Base class for claim-type-specific SHAP explainers."""

    def __init__(self):
        self.claim_type: str = ""
        self.feature_names: list[str] | None = None
        self.scaler: Any = None
        self.isolation_forest: Any = None
        self.lof: Any = None
        self.ocsvm: Any = None
        self.config: dict[str, Any] = {}
        self.risk_scores_df: pd.DataFrame | None = None
        self._load_artifacts()

    @abstractmethod
    def _load_artifacts(self) -> None:
        """Load claim-type-specific artifacts."""
        pass

    @abstractmethod
    def _get_isolated_model_output(self, scaled_features: np.ndarray) -> float:
        """Get the IsolationForest score (the SHAP target)."""
        pass

    @abstractmethod
    def _extract_model_evidence(self, claim_row: pd.Series) -> dict[str, Any]:
        """Extract model scores and risk info from claim data."""
        pass

    def _load_base_artifacts(self, base_path: Path) -> None:
        """Load common artifacts for all claim types."""
        # Load feature columns (if available)
        fc_path = base_path / "feature_columns.pkl"
        if fc_path.exists():
            self.feature_names = joblib.load(fc_path)

        # Load scaler
        scaler_path = base_path / "scaler.pkl"
        if scaler_path.exists():
            self.scaler = joblib.load(scaler_path)
            # If feature_names not loaded from feature_columns.pkl, try to get from scaler
            if self.feature_names is None and hasattr(self.scaler, 'feature_names_in_'):
                self.feature_names = list(self.scaler.feature_names_in_)

        # Load models
        iso_path = base_path / "isolation_forest.pkl"
        if iso_path.exists():
            self.isolation_forest = joblib.load(iso_path)

        lof_paths = list(base_path.glob("lof*.pkl"))
        if lof_paths:
            self.lof = joblib.load(lof_paths[0])

        ocsvm_path = base_path / "ocsvm.pkl"
        if ocsvm_path.exists():
            self.ocsvm = joblib.load(ocsvm_path)

    def _validate_feature_vector(self, claim_features: Mapping[str, float]) -> np.ndarray:
        """Validate and convert feature dict to scaled numpy array."""
        if not self.feature_names:
            raise ValueError(f"No feature names available for {self.claim_type}")

        # Build vector in correct feature order
        vector = np.array(
            [float(claim_features.get(fname, np.nan)) for fname in self.feature_names],
            dtype=float
        ).reshape(1, -1)

        # Check for NaN/inf
        if np.any(~np.isfinite(vector)):
            raise ValueError(f"Invalid values (NaN/inf) in feature vector for claim")

        # Scale
        if self.scaler is None:
            raise ValueError(f"No scaler available for {self.claim_type}")

        scaled = self.scaler.transform(vector)
        return scaled

    def _compute_shap_values(self, claim_features: Mapping[str, float]) -> tuple[np.ndarray, float, float]:
        """
        Compute SHAP values for a claim.
        
        Returns:
            (shap_values, base_value, model_output)
        """
        if not self.isolation_forest:
            raise ValueError(f"No IsolationForest available for {self.claim_type}")

        # Validate and scale features
        scaled_features = self._validate_feature_vector(claim_features)

        # Get model output
        model_output = self._get_isolated_model_output(scaled_features)

        # Compute SHAP
        explainer = shap.TreeExplainer(self.isolation_forest)
        shap_values_raw = explainer.shap_values(scaled_features)

        # Handle multi-dimensional output
        shap_array = np.asarray(shap_values_raw)
        if shap_array.ndim == 3:
            shap_array = shap_array[0]
        if shap_array.ndim == 2:
            shap_array = shap_array[0]

        base_value = explainer.expected_value
        if isinstance(base_value, (list, np.ndarray)):
            base_value = float(np.mean(base_value))
        else:
            base_value = float(base_value)

        return shap_array.astype(float), base_value, float(model_output)

    def explain_claim(self, claim_id: str | int) -> dict[str, Any]:
        """
        Explain a claim using SHAP.
        
        Args:
            claim_id: The claim identifier to explain
            
        Returns:
            Dictionary with SHAP explanation and model evidence
        """
        if self.risk_scores_df is None:
            return {
                "status": "unavailable",
                "reason": f"Risk scores not available for {self.claim_type}",
            }

        # Find claim in risk scores
        claim_row = self._find_claim(claim_id)
        if claim_row is None:
            return {
                "status": "not_found",
                "claim_id": str(claim_id),
                "reason": f"Claim not found in {self.claim_type} dataset",
            }

        # Extract features for this claim
        claim_features = self._extract_features_for_claim(claim_row)

        try:
            # Compute SHAP
            shap_values, base_value, model_output = self._compute_shap_values(claim_features)

            # Get model evidence
            model_evidence = self._extract_model_evidence(claim_row)

            # Build feature explanations (top 10)
            feature_contributions = []
            for rank, (fname, shap_val) in enumerate(
                sorted(
                    zip(self.feature_names, shap_values),
                    key=lambda x: abs(x[1]),
                    reverse=True,
                )[:10],
                start=1,
            ):
                feature_contributions.append({
                    "rank": rank,
                    "feature": fname,
                    "value": float(claim_features[fname]),
                    "shap_value": float(shap_val),
                    "absolute_shap_value": float(abs(shap_val)),
                })

            return {
                "status": "success",
                "entity_type": "claim",
                "claim_id": str(claim_id),
                "claim_type": self.claim_type,
                "model_evidence": model_evidence,
                "shap": {
                    "explained_model": "IsolationForest",
                    "model_output": model_output,
                    "base_value": base_value,
                    "top_features": feature_contributions,
                    "reconciliation": {
                        "base_value_plus_sum": float(base_value + np.sum(shap_values)),
                        "model_output": model_output,
                        "residual": float(abs(base_value + np.sum(shap_values) - model_output)),
                    }
                },
            }
        except Exception as e:
            return {
                "status": "error",
                "claim_id": str(claim_id),
                "error": str(e),
            }

    @abstractmethod
    def _find_claim(self, claim_id: str | int) -> pd.Series | None:
        """Find claim row in risk scores."""
        pass

    @abstractmethod
    def _extract_features_for_claim(self, claim_row: pd.Series) -> Mapping[str, float]:
        """Extract feature dict from claim row."""
        pass


class CarrierClaimExplainer(ClaimExplainerBase):
    """SHAP explainer for Carrier claims (38 features)."""

    def __init__(self):
        self.claim_type = "CARRIER"
        super().__init__()

    def _load_artifacts(self) -> None:
        """Load Carrier-specific artifacts."""
        base_path = Path("models/claims/carrier")
        self._load_base_artifacts(base_path)

        # Load model config if available
        config_path = base_path / "model_config.pkl"
        if config_path.exists():
            self.config = joblib.load(config_path)

        # Load risk scores from unified file
        # (Carrier has no dedicated CSV, use unified)
        unified_path = Path("models/claims/unified_claim_risk_with_provider.csv")
        if unified_path.exists():
            df = pd.read_csv(unified_path, low_memory=False)
            self.risk_scores_df = df[df['CLAIM_TYPE'] == 'CARRIER'].copy()

    def _get_isolated_model_output(self, scaled_features: np.ndarray) -> float:
        """Get IsolationForest score_samples output."""
        # IsolationForest.score_samples returns anomaly scores
        scores = self.isolation_forest.score_samples(scaled_features)
        return float(scores[0])

    def _extract_model_evidence(self, claim_row: pd.Series) -> dict[str, Any]:
        """Extract Carrier-specific model outputs."""
        return {
            "if_score": float(claim_row.get("IF_score", np.nan)),
            "lof_score": float(claim_row.get("LOF_score", np.nan)),
            "ocsvm_score": float(claim_row.get("OCSVM_score", np.nan)),
            "ensemble_score": float(claim_row.get("carrier_ensemble_score", np.nan)),
            "risk_rank": int(claim_row.get("carrier_risk_rank", -1)) if pd.notna(claim_row.get("carrier_risk_rank")) else None,
            "risk_band": str(claim_row.get("carrier_risk_band", "Unknown")),
        }

    def _find_claim(self, claim_id: str | int) -> pd.Series | None:
        """Find claim in risk scores."""
        if self.risk_scores_df is None or self.risk_scores_df.empty:
            return None
        matching = self.risk_scores_df[
            self.risk_scores_df['CLM_ID'].astype(str) == str(claim_id)
        ]
        return matching.iloc[0] if len(matching) > 0 else None

    def _extract_features_for_claim(self, claim_row: pd.Series) -> Mapping[str, float]:
        """Extract features from unified file claim row."""
        # Map unified column names to feature names
        feature_dict = {}
        for fname in self.feature_names:
            # Direct lookup first
            if fname in claim_row.index:
                feature_dict[fname] = float(claim_row[fname])
            else:
                # Try alternate names or default to NaN
                feature_dict[fname] = float(claim_row.get(fname, np.nan))
        return feature_dict


class InpatientClaimExplainer(ClaimExplainerBase):
    """SHAP explainer for Inpatient claims (49 features)."""

    def __init__(self):
        self.claim_type = "INPATIENT"
        super().__init__()

    def _load_artifacts(self) -> None:
        """Load Inpatient-specific artifacts."""
        base_path = Path("models/claims/inpatient")
        self._load_base_artifacts(base_path)

        # Load risk scores
        csv_path = base_path / "inpatient_final_risk_scores.csv"
        if csv_path.exists():
            self.risk_scores_df = pd.read_csv(csv_path, low_memory=False)

    def _get_isolated_model_output(self, scaled_features: np.ndarray) -> float:
        """Get IsolationForest score_samples output."""
        scores = self.isolation_forest.score_samples(scaled_features)
        return float(scores[0])

    def _extract_model_evidence(self, claim_row: pd.Series) -> dict[str, Any]:
        """Extract Inpatient-specific model outputs."""
        return {
            "isolation_forest_score": float(claim_row.get("isolation_forest_score", np.nan)),
            "lof_score": float(claim_row.get("lof_score", np.nan)),
            "ocsvm_score": float(claim_row.get("one_class_svm_score", np.nan)),
            "ensemble_score": float(claim_row.get("ensemble_risk_score", np.nan)),
            "isolation_forest_flag": int(claim_row.get("isolation_forest_flag", 0)),
            "lof_flag": int(claim_row.get("lof_flag", 0)),
            "ocsvm_flag": int(claim_row.get("one_class_svm_flag", 0)),
            "model_consensus_count": int(claim_row.get("model_consensus_count", 0)),
            "model_consensus": str(claim_row.get("model_consensus", "Unknown")),
            "risk_percentile": float(claim_row.get("risk_percentile", np.nan)),
            "risk_rank": int(claim_row.get("risk_rank", -1)) if pd.notna(claim_row.get("risk_rank")) else None,
            "risk_band": str(claim_row.get("risk_band", "Unknown")),
        }

    def _find_claim(self, claim_id: str | int) -> pd.Series | None:
        """Find claim in risk scores."""
        if self.risk_scores_df is None or self.risk_scores_df.empty:
            return None
        matching = self.risk_scores_df[
            self.risk_scores_df['clm_id'].astype(str) == str(claim_id)
        ]
        return matching.iloc[0] if len(matching) > 0 else None

    def _extract_features_for_claim(self, claim_row: pd.Series) -> Mapping[str, float]:
        """Extract features from claim row."""
        feature_dict = {}
        for fname in self.feature_names:
            if fname in claim_row.index:
                feature_dict[fname] = float(claim_row[fname])
            else:
                feature_dict[fname] = float(claim_row.get(fname, np.nan))
        return feature_dict


class OutpatientClaimExplainer(ClaimExplainerBase):
    """SHAP explainer for Outpatient claims (38 features)."""

    def __init__(self):
        self.claim_type = "OUTPATIENT"
        super().__init__()

    def _load_artifacts(self) -> None:
        """Load Outpatient-specific artifacts."""
        base_path = Path("models/claims/outpatient")
        self._load_base_artifacts(base_path)

        # Load model config with ensemble weights
        config_path = base_path / "model_config.pkl"
        if config_path.exists():
            self.config = joblib.load(config_path)

        # Load risk scores
        csv_path = base_path / "outpatient_final_risk_scores.csv"
        if csv_path.exists():
            self.risk_scores_df = pd.read_csv(csv_path, low_memory=False)

    def _get_isolated_model_output(self, scaled_features: np.ndarray) -> float:
        """Get IsolationForest score_samples output."""
        scores = self.isolation_forest.score_samples(scaled_features)
        return float(scores[0])

    def _extract_model_evidence(self, claim_row: pd.Series) -> dict[str, Any]:
        """Extract Outpatient-specific model outputs."""
        return {
            "if_score": float(claim_row.get("IF_score", np.nan)),
            "lof_score": float(claim_row.get("LOF_score", np.nan)),
            "ocsvm_score": float(claim_row.get("OCSVM_score", np.nan)),
            "ensemble_score": float(claim_row.get("outpatient_ensemble_score", np.nan)),
            "ensemble_weights": self.config.get("ensemble_weights", {
                "Isolation Forest": 0.2,
                "LOF": 0.2,
                "One-Class SVM": 0.6,
            }),
            "risk_rank": int(claim_row.get("outpatient_risk_rank", -1)) if pd.notna(claim_row.get("outpatient_risk_rank")) else None,
            "risk_band": str(claim_row.get("outpatient_risk_band", "Unknown")),
        }

    def _find_claim(self, claim_id: str | int) -> pd.Series | None:
        """Find claim in risk scores."""
        if self.risk_scores_df is None or self.risk_scores_df.empty:
            return None
        matching = self.risk_scores_df[
            self.risk_scores_df['CLM_ID'].astype(str) == str(claim_id)
        ]
        return matching.iloc[0] if len(matching) > 0 else None

    def _extract_features_for_claim(self, claim_row: pd.Series) -> Mapping[str, float]:
        """Extract features from claim row."""
        feature_dict = {}
        for fname in self.feature_names:
            if fname in claim_row.index:
                feature_dict[fname] = float(claim_row[fname])
            else:
                feature_dict[fname] = float(claim_row.get(fname, np.nan))
        return feature_dict


# Global explainer instances
_explainers: dict[str, ClaimExplainerBase] = {}


def _get_explainer(claim_type: str) -> ClaimExplainerBase:
    """Get or create explainer for claim type."""
    claim_type_upper = claim_type.upper()
    if claim_type_upper not in _explainers:
        if claim_type_upper == "CARRIER":
            _explainers[claim_type_upper] = CarrierClaimExplainer()
        elif claim_type_upper == "INPATIENT":
            _explainers[claim_type_upper] = InpatientClaimExplainer()
        elif claim_type_upper == "OUTPATIENT":
            _explainers[claim_type_upper] = OutpatientClaimExplainer()
        else:
            raise ValueError(f"Unknown claim type: {claim_type}")
    return _explainers[claim_type_upper]


def explain_claim(claim_id: str | int, claim_type: str) -> dict[str, Any]:
    """
    Explain a claim using SHAP TreeExplainer on IsolationForest.
    
    Common interface for all claim types.
    
    Args:
        claim_id: The claim to explain
        claim_type: "CARRIER", "INPATIENT", or "OUTPATIENT"
        
    Returns:
        Dictionary with SHAP explanation and model evidence
    """
    explainer = _get_explainer(claim_type)
    return explainer.explain_claim(claim_id)
