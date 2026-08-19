"""
Claims SHAP Explainability - Production Implementation (Audited & Corrected)

Provides SHAP explanations for claim-level anomaly detection using
the actual persisted ML artifacts under `/models/claims`.

Supported claim types:
- CARRIER:    Uses `data/raw/carrier_claim_features_FINAL.csv` (38 features)
- INPATIENT:  Uses feature_columns.pkl (49 features); requires caller-provided features
              because the feature engineering pipeline is not recoverable from
              the available raw data (documented limitation).
- OUTPATIENT: Uses `outpatient_final_risk_scores.csv` (all 38 features embedded).

SHAP targets the IsolationForest component using TreeExplainer on the
persisted `isolation_forest.pkl`. The explained model output is
`score_samples()`, and SHAP explains the internal tree structure (negative
path lengths) which is the recognised, model-faithful representation for
IsolationForest explanation.

CRITICAL: The SHAP values explain the IsolationForest's internal tree outputs
(`-path_length` per tree). `score_samples()` is a monotone non-linear
transformation of the average path length, so:
    base_value + sum(shap_values) != score_samples()
This is expected behaviour for sklearn IsolationForest + SHAP TreeExplainer.
See docs/claims_explainability.md for the exact mathematical relationship.
"""

from __future__ import annotations

import warnings
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Mapping

import joblib
import numpy as np
import pandas as pd
import shap

warnings.filterwarnings('ignore', category=UserWarning)


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_CLAIMS_BASE = Path("models/claims")
_CARRIER_FEATURES_CSV = Path("data/raw/carrier_claim_features_FINAL.csv")


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------
class ClaimExplainerBase(ABC):
    """Base class for claim-type-specific SHAP explainers.

    The base class loads the persisted artifacts, validates the feature vector
    against the persisted scaler/IsolationForest contract, computes SHAP values
    and returns a stable output schema.
    """

    def __init__(self, claim_type: str):
        self.claim_type: str = claim_type
        self.feature_names: list[str] | None = None
        self.scaler: Any = None
        self.isolation_forest: Any = None
        self.lof: Any = None
        self.ocsvm: Any = None
        self.config: dict[str, Any] = {}
        self._load_artifacts()

    @abstractmethod
    def _load_artifacts(self) -> None:
        """Load claim-type-specific ML artifacts."""
        pass

    @abstractmethod
    def _get_claim_features(self, claim_id: str | int) -> Mapping[str, float] | None:
        """Get the raw (unscaled) feature vector for a claim."""
        pass

    @abstractmethod
    def _extract_model_evidence(self, row: pd.Series | None = None) -> dict[str, Any]:
        """Extract model scores and configuration info for the output contract."""
        pass

    # ------------------------------------------------------------------
    # Shared artifact loading
    # ------------------------------------------------------------------
    def _load_base_artifacts(self, base_path: Path) -> None:
        """Load common ML artifacts (scaler + isolation forest + LOF + OCSVM)."""
        # Feature columns (if available; otherwise derive from scaler)
        fc_path = base_path / "feature_columns.pkl"
        if fc_path.exists():
            self.feature_names = joblib.load(fc_path)

        # Scaler
        scaler_path = base_path / "scaler.pkl"
        if scaler_path.exists():
            self.scaler = joblib.load(scaler_path)
            if self.feature_names is None and hasattr(self.scaler, "feature_names_in_"):
                self.feature_names = list(self.scaler.feature_names_in_)

        # IsolationForest (the SHAP target)
        iso_path = base_path / "isolation_forest.pkl"
        if iso_path.exists():
            self.isolation_forest = joblib.load(iso_path)

        # LOF (filename can be "lof.pkl" or "lof .pkl" for outpatient)
        lof_paths = list(base_path.glob("lof*.pkl"))
        if lof_paths:
            self.lof = joblib.load(lof_paths[0])

        # OCSVM
        ocsvm_path = base_path / "ocsvm.pkl"
        if ocsvm_path.exists():
            self.ocsvm = joblib.load(ocsvm_path)

        # Model config (optional)
        config_path = base_path / "model_config.pkl"
        if config_path.exists():
            self.config = joblib.load(config_path)

    # ------------------------------------------------------------------
    # Feature vector validation / scaling
    # ------------------------------------------------------------------
    def _validate_and_scale_features(
        self, claim_features: Mapping[str, float]
    ) -> np.ndarray:
        """Validate and scale a feature vector using the persisted scaler."""
        if not self.feature_names:
            raise ValueError(f"No feature names available for {self.claim_type}")

        if self.scaler is None:
            raise ValueError(f"No persisted scaler available for {self.claim_type}")

        # Check for missing feature keys (explicit count/name validation)
        missing_keys = [
            name for name in self.feature_names if name not in claim_features
        ]
        if missing_keys:
            raise ValueError(
                f"Feature count mismatch for {self.claim_type}: "
                f"expected {len(self.feature_names)} features, "
                f"got {len(claim_features)}. Missing: "
                f"{missing_keys[:5]}{'...' if len(missing_keys) > 5 else ''}"
            )

        extra_keys = [
            name for name in claim_features if name not in self.feature_names
        ]
        if extra_keys:
            raise ValueError(
                f"Feature count mismatch for {self.claim_type}: "
                f"unexpected extra features: "
                f"{extra_keys[:5]}{'...' if len(extra_keys) > 5 else ''}"
            )

        # Build the vector in the exact persisted feature order.
        vector = np.array(
            [float(claim_features[name]) for name in self.feature_names],
            dtype=float,
        ).reshape(1, -1)

        # Reject NaN / inf / wrong shape (safety check after explicit validation)
        if vector.shape[1] != len(self.feature_names):
            raise ValueError(
                f"Feature count mismatch for {self.claim_type}: "
                f"expected {len(self.feature_names)}, got {vector.shape[1]}"
            )

        if np.any(~np.isfinite(vector)):
            missing = [
                name
                for name, val in zip(self.feature_names, vector[0])
                if not np.isfinite(val)
            ]
            raise ValueError(
                f"Invalid (NaN/inf) values in features for {self.claim_type}: "
                f"{missing[:5]}{'...' if len(missing) > 5 else ''}"
            )

        return self.scaler.transform(vector)

    # ------------------------------------------------------------------
    # SHAP computation
    # ------------------------------------------------------------------
    def _compute_shap_values(
        self, claim_features: Mapping[str, float]
    ) -> tuple[np.ndarray, float, float]:
        """
        Compute SHAP values for a claim.

        Returns:
            (shap_values, base_value, model_output)
            - shap_values: array of len(feature_names)
            - base_value: TreeExplainer expected value (average tree output)
            - model_output: IsolationForest.score_samples() value
        """
        if self.isolation_forest is None:
            raise ValueError(f"No IsolationForest available for {self.claim_type}")

        scaled = self._validate_and_scale_features(claim_features)

        # IsolationForest score_samples() - the actual model output
        model_output = float(self.isolation_forest.score_samples(scaled)[0])

        # TreeExplainer on the IsolationForest
        explainer = shap.TreeExplainer(self.isolation_forest)
        raw = explainer.shap_values(scaled)

        arr = np.asarray(raw)
        if arr.ndim == 3:
            arr = arr[0]
        if arr.ndim == 2 and arr.shape[0] == 1:
            arr = arr[0]

        if arr.shape[0] != len(self.feature_names):
            raise ValueError(
                f"SHAP output shape {arr.shape} does not match expected "
                f"feature count {len(self.feature_names)}"
            )

        base = explainer.expected_value
        if isinstance(base, (list, np.ndarray)):
            base = float(np.mean(base))
        else:
            base = float(base)

        return arr.astype(float), base, model_output

    # ------------------------------------------------------------------
    # Public explain method
    # ------------------------------------------------------------------
    def explain_claim(
        self,
        claim_id: str | int,
        features: Mapping[str, float] | None = None,
    ) -> dict[str, Any]:
        """
        Explain a claim using SHAP.

        Args:
            claim_id: The claim identifier
            features: Optional pre-constructed feature dict.
                If omitted, the claim-type-specific data source is used.

        Returns:
            Dictionary with SHAP explanation and model evidence.
        """
        # Guard: feature names and isolation forest must be available.
        if not self.feature_names:
            return {
                "status": "error",
                "claim_id": str(claim_id),
                "claim_type": self.claim_type,
                "error": f"No feature contract available for {self.claim_type}",
            }

        if self.isolation_forest is None:
            return {
                "status": "error",
                "claim_id": str(claim_id),
                "claim_type": self.claim_type,
                "error": f"No IsolationForest model available for {self.claim_type}",
            }

        try:
            # Resolve features
            if features is None:
                features = self._get_claim_features(claim_id)
                if features is None:
                    return {
                        "status": "not_found",
                        "claim_id": str(claim_id),
                        "claim_type": self.claim_type,
                        "reason": (
                            f"Claim {claim_id} not found in the {self.claim_type} "
                            "data source."
                        ),
                    }

            # Compute SHAP
            shap_vals, base_val, model_out = self._compute_shap_values(features)

            # Model evidence (scores, risk info)
            model_evidence = self._extract_model_evidence()

            # Top contributing features (top 10 by |SHAP|)
            top_features = []
            for rank, (name, sval) in enumerate(
                sorted(
                    zip(self.feature_names, shap_vals),
                    key=lambda x: abs(x[1]),
                    reverse=True,
                )[:10],
                start=1,
            ):
                top_features.append(
                    {
                        "rank": rank,
                        "feature": name,
                        "value": float(features.get(name, np.nan)),
                        "shap_value": float(sval),
                        "absolute_shap_value": float(abs(sval)),
                    }
                )

            return {
                "status": "success",
                "entity_type": "claim",
                "claim_id": str(claim_id),
                "claim_type": self.claim_type,
                "model_evidence": model_evidence,
                "shap": {
                    "explained_model": "IsolationForest",
                    "model_output": model_out,
                    "base_value": base_val,
                    "top_features": top_features,
                    "reconciliation": {
                        "base_value_plus_sum_shap": float(base_val + np.sum(shap_vals)),
                        "model_output": model_out,
                        "residual": float(
                            abs(base_val + np.sum(shap_vals) - model_out)
                        ),
                    },
                },
            }

        except Exception as exc:
            return {
                "status": "error",
                "claim_id": str(claim_id),
                "claim_type": self.claim_type,
                "error": str(exc),
            }


# ---------------------------------------------------------------------------
# Outpatient
# ---------------------------------------------------------------------------
class OutpatientClaimExplainer(ClaimExplainerBase):
    """SHAP explainer for Outpatient claims (38 features)."""

    def __init__(self):
        self._data: pd.DataFrame | None = None
        super().__init__("OUTPATIENT")

    def _load_artifacts(self) -> None:
        base_path = _CLAIMS_BASE / "outpatient"
        self._load_base_artifacts(base_path)

        # Load the outpatient score CSV (has all 38 features embedded)
        csv_path = base_path / "outpatient_final_risk_scores.csv"
        if csv_path.exists():
            self._data = pd.read_csv(csv_path, low_memory=False)

    def _get_claim_features(self, claim_id: str | int) -> Mapping[str, float] | None:
        if self._data is None or self._data.empty:
            return None

        # Outpatient uses CLM_ID (numeric claim id)
        claim_id_str = str(claim_id).strip()
        matches = self._data[
            self._data["CLM_ID"].astype(str).str.strip() == claim_id_str
        ]
        if len(matches) == 0:
            return None

        row = matches.iloc[0]
        try:
            return {
                name: float(row[name])
                for name in self.feature_names
                if name in row.index and pd.notna(row[name])
            }
        except (KeyError, ValueError, TypeError):
            return None

    def _extract_model_evidence(self, row: pd.Series | None = None) -> dict[str, Any]:
        return {
            "model_type": "Outpatient Claim-Level Anomaly Detection",
            "ensemble_weights": self.config.get(
                "ensemble_weights",
                {
                    "Isolation Forest": 0.2,
                    "LOF": 0.2,
                    "One-Class SVM": 0.6,
                },
            ),
            "algorithms": self.config.get(
                "algorithms",
                ["Isolation Forest", "Local Outlier Factor", "One-Class SVM"],
            ),
            "feature_count": len(self.feature_names) if self.feature_names else 0,
            "score_normalization": self.config.get("score_normalization", "min-max"),
            "risk_bands": self.config.get("risk_bands", {}),
        }


# ---------------------------------------------------------------------------
# Carrier
# ---------------------------------------------------------------------------
class CarrierClaimExplainer(ClaimExplainerBase):
    """
    SHAP explainer for Carrier claims (38 features).

    Features are read from `data/raw/carrier_claim_features_FINAL.csv`,
    which is the persisted feature matrix that was used to train the
    Carrier pipeline. Scores reside in the unified claim-risk file
    (`models/claims/unified_claim_risk_with_provider.csv`).
    """

    def __init__(self):
        self._data: pd.DataFrame | None = None
        self._scores: pd.DataFrame | None = None
        super().__init__("CARRIER")

    def _load_artifacts(self) -> None:
        base_path = _CLAIMS_BASE / "carrier"
        self._load_base_artifacts(base_path)

        # Load feature matrix
        if _CARRIER_FEATURES_CSV.exists():
            self._data = pd.read_csv(_CARRIER_FEATURES_CSV, low_memory=False)

        # Load unified risk scores (for model evidence)
        unified_path = _CLAIMS_BASE / "unified_claim_risk_with_provider.csv"
        if unified_path.exists():
            unified = pd.read_csv(unified_path, low_memory=False)
            self._scores = unified[unified["CLAIM_TYPE"] == "CARRIER"].copy()

    def _get_claim_features(self, claim_id: str | int) -> Mapping[str, float] | None:
        if self._data is None or self._data.empty:
            return None

        # The feature file uses CLM_ID, the unified file uses CLAIM_ID;
        # they match for carrier.
        claim_id_str = str(claim_id).strip()
        matches = self._data[
            self._data["CLM_ID"].astype(str).str.strip() == claim_id_str
        ]
        if len(matches) == 0:
            return None

        row = matches.iloc[0]
        features = {}
        for name in self.feature_names:
            if name in row.index and pd.notna(row[name]):
                try:
                    features[name] = float(row[name])
                except (ValueError, TypeError):
                    features[name] = 0.0
            else:
                # Missing values are imputed as 0 for carrier
                features[name] = 0.0
        return features

    def _extract_model_evidence(self, row: pd.Series | None = None) -> dict[str, Any]:
        return {
            "model_type": "Carrier Claim-Level Anomaly Detection",
            "feature_count": len(self.feature_names) if self.feature_names else 0,
            "data_source": "data/raw/carrier_claim_features_FINAL.csv",
            "note": (
                "Carrier features loaded from the persisted feature matrix. "
                "The stored IF/LOF/OCSVM scores in the unified risk file were "
                "generated by the original carrier training pipeline."
            ),
        }


# ---------------------------------------------------------------------------
# Inpatient
# ---------------------------------------------------------------------------
class InpatientClaimExplainer(ClaimExplainerBase):
    """
    SHAP explainer for Inpatient claims (49 features).

    NOTE: The exact feature-engineering pipeline for Inpatient is not
    recoverable from the available artifacts. The persisted
    `feature_columns.pkl` + `scaler.pkl` + `isolation_forest.pkl` are
    loaded, but the original feature vectors are not stored in any
    available CSV.

    Therefore, `explain_claim()` requires the caller to pass the feature
    vector (49 features in the exact order of `feature_columns.pkl`).

    If features are not provided, the explainer returns an explicit
    `feature_data_required` status instead of fabricating values.
    """

    def __init__(self):
        super().__init__("INPATIENT")

    def _load_artifacts(self) -> None:
        base_path = _CLAIMS_BASE / "inpatient"
        self._load_base_artifacts(base_path)

        # Also load the scores CSV for reference / model evidence
        self._scores: pd.DataFrame | None = None
        csv_path = base_path / "inpatient_final_risk_scores.csv"
        if csv_path.exists():
            self._scores = pd.read_csv(csv_path, low_memory=False)

    def _get_claim_features(self, claim_id: str | int) -> Mapping[str, float] | None:
        # Not available: feature matrix is not persisted for inpatient.
        return None

    def _extract_model_evidence(self, row: pd.Series | None = None) -> dict[str, Any]:
        return {
            "model_type": "Inpatient Claim-Level Anomaly Detection",
            "feature_count": len(self.feature_names) if self.feature_names else 0,
            "note": (
                "Inpatient features are not embedded in any persisted CSV. "
                "Pass the 49-feature vector explicitly to explain_claim() "
                "to compute SHAP."
            ),
        }


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------
_explainers: dict[str, ClaimExplainerBase] = {}


def _get_explainer(claim_type: str) -> ClaimExplainerBase:
    """Get (or create) the claim-type-specific explainer."""
    ct = claim_type.upper()
    if ct not in _explainers:
        if ct == "CARRIER":
            _explainers[ct] = CarrierClaimExplainer()
        elif ct == "INPATIENT":
            _explainers[ct] = InpatientClaimExplainer()
        elif ct == "OUTPATIENT":
            _explainers[ct] = OutpatientClaimExplainer()
        else:
            raise ValueError(f"Unknown claim type: {claim_type}")
    return _explainers[ct]


def _extract_risk_fields(explainer: ClaimExplainerBase, claim_id: str | int) -> dict[str, Any]:
    """Read any stored risk evidence when a score row is available."""
    scores = getattr(explainer, "_scores", None)
    if scores is None or scores.empty:
        return {"risk_score": None, "risk_rank": None, "risk_band": None}

    claim_id_str = str(claim_id).strip()
    row = None
    for col in ["CLAIM_ID", "CLM_ID", "claim_id", "clm_id"]:
        if col in scores.columns:
            matches = scores[scores[col].astype(str).str.strip() == claim_id_str]
            if not matches.empty:
                row = matches.iloc[0]
                break

    if row is None:
        return {"risk_score": None, "risk_rank": None, "risk_band": None}

    if explainer.claim_type == "CARRIER":
        risk_score = row.get("IF_score")
        risk_rank = row.get("carrier_risk_rank")
        risk_band = row.get("carrier_risk_band")
        if risk_score is None:
            risk_score = row.get("carrier_ensemble_score")
        if risk_rank is None:
            risk_rank = row.get("risk_rank")
        if risk_band is None:
            risk_band = row.get("risk_band")
    elif explainer.claim_type == "INPATIENT":
        risk_score = row.get("ensemble_risk_score")
        risk_rank = row.get("risk_rank")
        risk_band = row.get("risk_band")
        if risk_score is None:
            risk_score = row.get("isolation_forest_score")
    elif explainer.claim_type == "OUTPATIENT":
        risk_score = row.get("outpatient_ensemble_score")
        risk_rank = row.get("outpatient_risk_rank")
        risk_band = row.get("outpatient_risk_band")
        if risk_score is None:
            risk_score = row.get("IF_score")
    else:
        risk_score = row.get("risk_score")
        risk_rank = row.get("risk_rank")
        risk_band = row.get("risk_band")

    return {
        "risk_score": None if risk_score is None or pd.isna(risk_score) else float(risk_score),
        "risk_rank": None if risk_rank is None or pd.isna(risk_rank) else int(risk_rank),
        "risk_band": None if risk_band is None or pd.isna(risk_band) else str(risk_band),
    }


def _normalize_claim_response(
    claim_id: str | int,
    claim_type: str,
    raw_result: dict[str, Any],
    explainer: ClaimExplainerBase,
) -> dict[str, Any]:
    """Normalize claim responses to a consistent production schema."""
    claim_type_std = str(claim_type).upper()
    risk = _extract_risk_fields(explainer, claim_id)
    shap = raw_result.get("shap", {}) if isinstance(raw_result, dict) else {}
    top_features = shap.get("top_features", []) if isinstance(shap, dict) else []
    shap_values = [
        float(item["shap_value"]) for item in top_features if isinstance(item, dict) and "shap_value" in item
    ]
    base_value = shap.get("base_value") if isinstance(shap, dict) else None
    model_output = shap.get("model_output") if isinstance(shap, dict) else None

    status_code = raw_result.get("status")
    if status_code == "not_found":
        return {
            "claim_id": str(claim_id),
            "claim_type": claim_type_std,
            "risk": {
                "risk_score": risk["risk_score"],
                "risk_rank": risk["risk_rank"],
                "risk_band": risk["risk_band"],
            },
            "explanation": {
                "top_features": [],
                "shap_values": [],
                "base_value": None,
            },
            "model": {
                "model_type": "IsolationForest",
                "model_output": None,
                "score_semantics": (
                    "SHAP explains the IsolationForest tree output; score_samples() is the model output; "
                    "stored risk score / rank / band are downstream normalized evidence and are not the SHAP target."
                ),
            },
            "status": {
                "code": "NOT_FOUND",
                "message": raw_result.get("reason") or f"Claim {claim_id} not found in the {claim_type_std} data source.",
                "model_faithful": False,
                "validation_status": "NOT_FOUND",
            },
        }

    is_blocked = status_code in {"feature_data_required", "error"} or claim_type_std in {"CARRIER", "INPATIENT"}

    if is_blocked:
        reason = (
            raw_result.get("reason")
            or raw_result.get("error")
            or (
                "Carrier explainability is blocked because the repository does not contain enough "
                "artifact lineage to prove the original feature-to-score contract."
                if claim_type_std == "CARRIER"
                else "Inpatient explainability is blocked because the original feature matrix is not stored in the repository artifacts."
            )
        )
        return {
            "claim_id": str(claim_id),
            "claim_type": claim_type_std,
            "risk": {
                "risk_score": risk["risk_score"],
                "risk_rank": risk["risk_rank"],
                "risk_band": risk["risk_band"],
            },
            "explanation": {
                "top_features": [],
                "shap_values": [],
                "base_value": None,
            },
            "model": {
                "model_type": "IsolationForest",
                "model_output": None,
                "score_semantics": (
                    "SHAP explains the IsolationForest tree output; score_samples() is the model output; "
                    "stored risk score / rank / band are downstream normalized evidence and are not the SHAP target."
                ),
            },
            "status": {
                "code": "BLOCKED_MISSING_FEATURE_ARTIFACT",
                "message": reason,
                "model_faithful": False,
                "validation_status": "BLOCKED",
            },
        }

    return {
        "claim_id": str(claim_id),
        "claim_type": claim_type_std,
        "risk": {
            "risk_score": risk["risk_score"],
            "risk_rank": risk["risk_rank"],
            "risk_band": risk["risk_band"],
        },
        "explanation": {
            "top_features": top_features,
            "shap_values": shap_values,
            "base_value": base_value,
        },
        "model": {
            "model_type": "IsolationForest",
            "model_output": model_output,
            "score_semantics": (
                "SHAP explains the IsolationForest tree output; score_samples() is the model output; "
                "stored risk score / rank / band are downstream normalized evidence and are not the SHAP target."
            ),
        },
        "status": {
            "code": "READY",
            "message": "Model-faithful SHAP explanation available for the persisted artifact contract.",
            "model_faithful": True,
            "validation_status": "READY",
        },
    }


def explain_claim(
    claim_id: str | int,
    claim_type: str,
    features: Mapping[str, float] | None = None,
) -> dict[str, Any]:
    """Public claim explainability API with a consistent production response schema."""
    claim_type_std = str(claim_type).upper()

    if claim_type_std == "CARRIER":
        return _normalize_claim_response(
            claim_id,
            claim_type_std,
            {
                "status": "blocked_missing_feature_artifact",
                "claim_id": str(claim_id),
                "claim_type": "CARRIER",
                "reason": (
                    "Carrier explainability is blocked because the repository does not contain enough "
                    "artifact lineage to prove the original feature-to-score contract."
                ),
            },
            CarrierClaimExplainer(),
        )

    if claim_type_std == "INPATIENT":
        if features is None:
            return _normalize_claim_response(
                claim_id,
                claim_type_std,
                {
                    "status": "feature_data_required",
                    "claim_id": str(claim_id),
                    "claim_type": "INPATIENT",
                    "reason": (
                        "Inpatient explainability is blocked because the original feature matrix is not stored "
                        "in the repository artifacts."
                    ),
                },
                InpatientClaimExplainer(),
            )
        return _normalize_claim_response(
            claim_id,
            claim_type_std,
            {
                "status": "blocked_missing_feature_artifact",
                "claim_id": str(claim_id),
                "claim_type": "INPATIENT",
                "reason": (
                    "Inpatient explainability is blocked because the repository does not contain the original "
                    "feature-engineering lineage needed to make the explanation production-faithful."
                ),
            },
            InpatientClaimExplainer(),
        )

    if claim_type_std != "OUTPATIENT":
        raise ValueError(f"Unknown claim type: {claim_type}")

    explainer = _get_explainer(claim_type_std)
    return _normalize_claim_response(claim_id, claim_type_std, explainer.explain_claim(claim_id, features), explainer)