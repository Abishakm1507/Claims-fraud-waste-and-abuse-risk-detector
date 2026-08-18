from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import shap

from explainability.feature_mapping import humanize_feature, normalize_feature_vector


class ClaimExplainer:
    """Reusable SHAP explainer for claim-level IsolationForest scores.

    This component intentionally works with the exact feature vector used by the
    claim model. The repository currently exposes claims via the final unified risk
    CSV, and the actual claim model artifact is not bundled in the project. When a
    model instance is provided, SHAP is computed against that model; otherwise the
    explainer raises an explicit error rather than fabricating values.
    """

    def __init__(self, model: Any = None, feature_names: Sequence[str] | None = None, feature_mapping: Mapping[str, str] | None = None):
        self.model = model
        self.feature_names = list(feature_names) if feature_names is not None else None
        self.feature_mapping = dict(feature_mapping or {})

    def _resolve_feature_names(self, feature_values: Any) -> list[str]:
        if self.feature_names is not None:
            return list(self.feature_names)

        if isinstance(feature_values, Mapping):
            return [str(name) for name in feature_values.keys()]

        raise ValueError("Claim feature names are required unless the explainer was initialized with them.")

    def _compute_shap(self, feature_vector: Mapping[str, float], feature_names: Sequence[str]) -> np.ndarray:
        if self.model is None:
            raise ValueError("No claim model is available for SHAP explanation. Provide the exact IsolationForest instance and feature vector.")

        vector = np.asarray([float(feature_vector[name]) for name in feature_names], dtype=float).reshape(1, -1)
        explainer = shap.TreeExplainer(self.model)
        shap_values = explainer.shap_values(vector)
        arr = np.asarray(shap_values)

        if arr.ndim == 3:
            arr = arr[0]
        if arr.ndim == 2 and arr.shape[0] == 1:
            arr = arr[0]
        if arr.shape[0] != len(feature_names):
            raise ValueError(f"Unexpected SHAP output shape {arr.shape}; expected {len(feature_names)} contributions.")
        return arr.astype(float)

    def explain(self, claim_id: Any, model: Any | None = None, feature_vector: Any | None = None, risk_score: float | None = None, feature_names: Sequence[str] | None = None) -> dict[str, Any]:
        model_to_use = model or self.model
        if model_to_use is None:
            return {
                "entity_type": "claim",
                "entity_id": str(claim_id),
                "status": "model_artifact_unavailable",
                "shap_available": False,
                "reason": "The trained claim model/prediction function and exact model feature matrix are not present in the repository.",
            }

        names = list(feature_names) if feature_names is not None else self.feature_names
        if names is None:
            if hasattr(model_to_use, "feature_names_in_"):
                names = list(model_to_use.feature_names_in_)
            else:
                names = self._resolve_feature_names(feature_vector)

        formal_values = normalize_feature_vector(feature_vector, expected_names=names)
        shap_values = self._compute_shap(formal_values, names)

        ranked = []
        for rank, (name, value, shap_value) in enumerate(
            sorted(
                zip(names, [formal_values[name] for name in names], shap_values),
                key=lambda item: abs(item[2]),
                reverse=True,
            )[:10],
            start=1,
        ):
            ranked.append(
                {
                    "feature": self.feature_mapping.get(name, humanize_feature(name)),
                    "model_feature": name,
                    "value": value,
                    "shap_value": float(shap_value),
                    "absolute_shap_value": float(abs(shap_value)),
                    "rank": rank,
                }
            )

        return {
            "entity_type": "claim",
            "entity_id": str(claim_id),
            "risk_score": float(risk_score) if risk_score is not None else None,
            "shap": {
                "base_value": 0.0,
                "top_features": ranked,
            },
        }

    def explain_claim(self, claim_id: Any, risk_score: float, feature_values: Any, model: Any | None = None, feature_names: Sequence[str] | None = None) -> dict[str, Any]:
        return self.explain(claim_id=claim_id, model=model or self.model, feature_vector=feature_values, risk_score=risk_score, feature_names=feature_names)
