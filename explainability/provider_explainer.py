from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Mapping

import joblib
import numpy as np
import pandas as pd
import shap

from explainability.feature_mapping import humanize_feature


_DEFAULT_MODEL_PATH = Path(__file__).resolve().parents[1] / "models" / "provider" / "provider_risk_pipeline.joblib"

# Provider BASE_FEATURES as defined in provider_preprocessing.py
_BASE_FEATURES = [
    'Log_Tot_Benes', 'Log_Tot_Srvcs', 'Log_Tot_HCPCS_Cds',
    'Log_Tot_Sbmtd_Chrg', 'Log_Tot_Mdcr_Pymt_Amt',
    'Log_Drug_Tot_Srvcs', 'Log_Drug_Sbmtd_Chrg',
    'Payment_to_Charge_Ratio', 'Allowed_to_Charge_Ratio', 'Standardized_to_Payment_Ratio',
    'Services_per_Beneficiary', 'HCPCS_per_Beneficiary',
    'Payment_per_Service', 'Charge_per_Service',
    'Drug_Service_Share', 'Drug_Payment_Share', 'Medical_Payment_Share',
    'Bene_Avg_Risk_Scre', 'Dual_Eligible_Ratio', 'Overall_Condition_Risk',
    'Svc_N_Unique_HCPCS', 'Svc_Top_Service_Share', 'Svc_HCPCS_Concentration_HHI',
    'Svc_Drug_Service_Share', 'Svc_Avg_Payment_to_Charge_Ratio', 'Svc_Min_Payment_to_Charge_Ratio',
    'Svc_Max_Beneficiary_Service_Ratio', 'Svc_Services_per_HCPCS', 'Svc_Std_Charge_Per_Service',
    'Peer_Mean_Log_Dev_Charge', 'Peer_Max_Log_Dev_Charge', 'Peer_Mean_Log_Dev_Payment',
    'Peer_Pct_Services_3x_Peer_Charge',
]

_FLAGGED_FEATS = [
    'Svc_N_Unique_HCPCS', 'Svc_Top_Service_Share', 'Svc_HCPCS_Concentration_HHI',
    'Svc_Drug_Service_Share', 'Svc_Avg_Payment_to_Charge_Ratio', 'Svc_Min_Payment_to_Charge_Ratio',
    'Svc_Max_Beneficiary_Service_Ratio', 'Svc_Services_per_HCPCS', 'Svc_Std_Charge_Per_Service',
    'Peer_Mean_Log_Dev_Charge', 'Peer_Max_Log_Dev_Charge', 'Peer_Mean_Log_Dev_Payment',
    'Peer_Pct_Services_3x_Peer_Charge',
]


class ProviderExplainer:
    """
    SHAP explainer for the persisted provider IsolationForest model.
    
    CRITICAL DESIGN: Uses the EXISTING fitted preprocessing pipeline as the
    SINGLE SOURCE OF TRUTH. Does NOT recreate preprocessing logic.
    
    Input: Raw provider record (dictionary with Provider_Type and BASE_FEATURES)
    Processing: Uses existing ProviderFeaturePreprocessor for all feature engineering
    Output: SHAP explanations for the IsolationForest anomaly detection
    """

    def __init__(self, model_path: str | Path | None = None, model: Any | None = None):
        self.model_path = Path(model_path) if model_path is not None else _DEFAULT_MODEL_PATH
        self.model = model
        if self.model is None:
            self.model = self._load_model()

    def _load_model(self) -> Any:
        provider_dir = self.model_path.parent
        if str(provider_dir) not in sys.path:
            sys.path.insert(0, str(provider_dir))

        try:
            import provider_preprocessing  # noqa: F401
        except ModuleNotFoundError as exc:
            raise ModuleNotFoundError(
                "The provider preprocessing module must be importable before joblib.load(). "
                "Ensure models/provider/provider_preprocessing.py is available on the Python path."
            ) from exc

        if not self.model_path.exists():
            raise FileNotFoundError(f"Provider model not found at {self.model_path}")

        return joblib.load(self.model_path)

    def _feature_names(self) -> list[str]:
        """Get the exact 46 model feature names in training order."""
        if hasattr(self.model, "named_steps") and "preprocess" in self.model.named_steps:
            return list(self.model.named_steps["preprocess"].get_feature_names_out())
        raise ValueError("The provider model does not expose a feature-order list.")

    def _build_raw_provider_frame(self, raw_provider: Any) -> pd.DataFrame:
        """
        Convert raw provider record to DataFrame suitable for preprocessing.
        
        Accepts:
        - Dictionary with Provider_Type and any BASE_FEATURES
        - Missing BASE_FEATURES will be NaN, allowing preprocessor's fitted imputation
        
        Returns:
        - Single-row DataFrame with Provider_Type + BASE_FEATURES (as-is, no imputation here)
        """
        if not isinstance(raw_provider, Mapping):
            raise TypeError(
                "raw_provider must be a mapping (dict) with Provider_Type and provider features. "
                f"Got {type(raw_provider).__name__}."
            )

        # Extract Provider_Type (required)
        provider_type = raw_provider.get("Provider_Type") or raw_provider.get("provider_type")
        if not provider_type:
            raise ValueError("raw_provider must contain 'Provider_Type' field.")

        # Build frame with Provider_Type + all BASE_FEATURES
        # Missing values remain NaN - preprocessor will impute with fitted medians
        row = {"Provider_Type": provider_type}
        for feat in _BASE_FEATURES:
            if feat in raw_provider:
                val = raw_provider[feat]
                row[feat] = float(val) if val is not None else np.nan
            else:
                row[feat] = np.nan

        return pd.DataFrame([row])

    def _apply_preprocessing_pipeline(self, raw_frame: pd.DataFrame) -> tuple[np.ndarray, list[str]]:
        """
        Apply the existing preprocessing pipeline.
        
        Returns:
        - preprocessed array (1 x 46)
        - feature names in exact order
        """
        # Apply each pipeline step
        preprocess = self.model.named_steps["preprocess"]
        scaler = self.model.named_steps["scaler"]
        clipper = self.model.named_steps["clip"]

        # Step 1: Preprocessing (feature engineering, missing indicators, imputation)
        prep_array = preprocess.transform(raw_frame)

        # Step 2: RobustScaler (median/IQR normalization)
        scaled_array = scaler.transform(prep_array)

        # Step 3: Clip to [-10, 10]
        clipped_array = clipper.transform(scaled_array)

        feature_names = list(preprocess.get_feature_names_out())
        return clipped_array, feature_names

    def _compute_shap(self, raw_provider: Any) -> tuple[list[str], np.ndarray, float, float]:
        """
        Compute SHAP explanations.
        
        Returns:
        - feature_names: List of 46 feature names
        - shap_values: Array of 46 SHAP contributions
        - base_value: SHAP base value (model output when all features=0)
        - model_output: Actual model output (score_samples value)
        """
        # Build raw provider frame
        raw_frame = self._build_raw_provider_frame(raw_provider)

        # Apply preprocessing pipeline
        clipped_array, feature_names = self._apply_preprocessing_pipeline(raw_frame)

        # Compute model output
        iforest = self.model.named_steps["iforest"]
        model_output = iforest.score_samples(clipped_array)[0]

        # Compute SHAP
        explainer = shap.TreeExplainer(iforest)
        explanation = explainer(clipped_array)

        # Extract SHAP values
        shap_array = np.asarray(explanation.values)
        if shap_array.ndim == 3:
            shap_array = shap_array[0]
        if shap_array.ndim == 2 and shap_array.shape[0] == 1:
            shap_array = shap_array[0]

        if shap_array.shape[0] != len(feature_names):
            raise ValueError(
                f"SHAP output shape {shap_array.shape} does not match "
                f"feature count {len(feature_names)}"
            )

        base_value = float(np.asarray(explanation.base_values).reshape(-1)[0])

        return feature_names, shap_array.astype(float), base_value, model_output

    def explain_provider(self, provider_id: Any, risk_score: float, raw_provider: Any) -> dict[str, Any]:
        """
        Generate SHAP explanation for a provider.
        
        Args:
            provider_id: Provider identifier (NPI)
            risk_score: Provider risk score (for context only)
            raw_provider: Raw provider record (dict with Provider_Type and BASE_FEATURES)
        
        Returns:
            Dictionary with provider info and SHAP explanation
        """
        names, shap_values, base_value, model_output = self._compute_shap(raw_provider)

        # Get preprocessed features for display
        raw_frame = self._build_raw_provider_frame(raw_provider)
        clipped_array, _ = self._apply_preprocessing_pipeline(raw_frame)

        ranked = []
        for rank, (name, shap_value) in enumerate(
            sorted(
                zip(names, shap_values),
                key=lambda item: abs(item[1]),
                reverse=True,
            )[:10],
            start=1,
        ):
            ranked.append(
                {
                    "feature": humanize_feature(name),
                    "model_feature": name,
                    "shap_value": float(shap_value),
                    "absolute_shap_value": float(abs(shap_value)),
                    "rank": rank,
                }
            )

        return {
            "entity_type": "provider",
            "entity_id": str(provider_id),
            "risk_score": float(risk_score),
            "shap": {
                "base_value": float(base_value),
                "model_output": float(model_output),
                "model_output_method": "IsolationForest.score_samples()",
                "top_features": ranked,
            },
        }

    def explain_with_dataset(self, dataset: pd.DataFrame, sample_size: int = 500) -> dict[str, Any]:
        """
        Compute global SHAP summary on a sampled provider cohort.
        
        Args:
            dataset: DataFrame with provider data (must include Provider_Type + BASE_FEATURES)
            sample_size: Number of providers to sample for analysis
        
        Returns:
            Dictionary with global feature importance based on mean absolute SHAP values
        """
        sample = dataset.sample(n=min(sample_size, len(dataset)), random_state=42)
        if sample.empty:
            raise ValueError("No provider rows available for global SHAP analysis.")

        values = []
        for _, row in sample.iterrows():
            raw_provider = {col: row[col] for col in _BASE_FEATURES + ["Provider_Type"] if col in row.index}
            try:
                _, contribs, _, _ = self._compute_shap(raw_provider)
                values.append(np.abs(contribs))
            except Exception:
                # Skip rows that fail preprocessing
                continue

        if not values:
            raise ValueError("No provider rows could be successfully processed.")

        global_mean = np.mean(np.vstack(values), axis=0)
        order = np.argsort(global_mean)[::-1]
        names = self._feature_names()
        top = [
            {
                "feature": humanize_feature(names[idx]),
                "model_feature": names[idx],
                "mean_absolute_shap": float(global_mean[idx]),
                "rank": rank + 1,
            }
            for rank, idx in enumerate(order[:10])
        ]
        return {"entity_type": "provider", "sample_size": len(sample), "top_features": top}
