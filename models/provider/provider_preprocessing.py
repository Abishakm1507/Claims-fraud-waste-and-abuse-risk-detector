"""
provider_preprocessing.py

Custom scikit-learn compatible transformer that reproduces EXACTLY the feature
engineering used before the Isolation Forest in the Medicare FWA risk pipeline
(originally stage 6, s6_feature_matrix.py):

  1. Select the curated feature columns, in the exact training order.
  2. For service-detail / peer-deviation features (sparse due to partial dataset
     coverage), add a `<col>_missing` indicator BEFORE imputing.
  3. Impute missing values with the PROVIDER-TYPE median learned at fit time
     (falling back to the global median for provider types unseen at fit time,
     and to 0.0 in the pathological case where even the global median is NaN).
  4. Replace +/-inf (can arise from ratio features) with NaN, then re-impute
     using the same fitted medians.

This module must be importable (i.e. present on the Python path) both when the
pipeline is saved with joblib.dump() and when it is later loaded with
joblib.load() -- this is a standard scikit-learn requirement for any custom
transformer bundled inside a Pipeline.

IMPORTANT for VS Code integration: copy this file into your project (or install
it as a local module) alongside provider_risk_pipeline.joblib, and make sure
`from provider_preprocessing import ProviderFeaturePreprocessor` succeeds
BEFORE calling joblib.load() on the pipeline.
"""
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin

# Feature groups exactly as used in the original pipeline (s6_feature_matrix.py)
LOG_FEATS = [
    'Log_Tot_Benes', 'Log_Tot_Srvcs', 'Log_Tot_HCPCS_Cds',
    'Log_Tot_Sbmtd_Chrg', 'Log_Tot_Mdcr_Pymt_Amt',
    'Log_Drug_Tot_Srvcs', 'Log_Drug_Sbmtd_Chrg',
]
RATIO_FEATS = [
    'Payment_to_Charge_Ratio', 'Allowed_to_Charge_Ratio', 'Standardized_to_Payment_Ratio',
    'Services_per_Beneficiary', 'HCPCS_per_Beneficiary',
    'Payment_per_Service', 'Charge_per_Service',
    'Drug_Service_Share', 'Drug_Payment_Share', 'Medical_Payment_Share',
]
BENE_FEATS = [
    'Bene_Avg_Risk_Scre', 'Dual_Eligible_Ratio', 'Overall_Condition_Risk',
]
SERVICE_DETAIL_FEATS = [
    'Svc_N_Unique_HCPCS', 'Svc_Top_Service_Share', 'Svc_HCPCS_Concentration_HHI',
    'Svc_Drug_Service_Share', 'Svc_Avg_Payment_to_Charge_Ratio', 'Svc_Min_Payment_to_Charge_Ratio',
    'Svc_Max_Beneficiary_Service_Ratio', 'Svc_Services_per_HCPCS', 'Svc_Std_Charge_Per_Service',
]
PEER_FEATS = [
    'Peer_Mean_Log_Dev_Charge', 'Peer_Max_Log_Dev_Charge', 'Peer_Mean_Log_Dev_Payment',
    'Peer_Pct_Services_3x_Peer_Charge',
]

# Base (always-present) feature list, in training order
BASE_FEATURES = LOG_FEATS + RATIO_FEATS + BENE_FEATS + SERVICE_DETAIL_FEATS + PEER_FEATS
# Columns that get a missingness indicator (sparse due to partial Dataset B/C coverage)
FLAGGED_FEATS = SERVICE_DETAIL_FEATS + PEER_FEATS
# Final training feature order: base features, then missing-flag columns (in that order)
FULL_FEATURE_ORDER = BASE_FEATURES + [f'{c}_missing' for c in FLAGGED_FEATS]


class ProviderFeaturePreprocessor(BaseEstimator, TransformerMixin):
    """
    Reproduces stage6_feature_matrix.py exactly as a fit/transform sklearn
    transformer, so the whole preprocessing + Isolation Forest chain can be
    bundled into a single persisted sklearn Pipeline.

    Expected input to `transform`: a pandas DataFrame containing at least
    `Provider_Type` plus every column in BASE_FEATURES (missing columns are
    treated as entirely-missing / NaN).

    Output: numpy array, shape (n_rows, len(FULL_FEATURE_ORDER)), columns in
    FULL_FEATURE_ORDER -- identical column order used to fit the RobustScaler
    and Isolation Forest in the original pipeline.
    """

    def __init__(self):
        self.type_medians_ = None
        self.global_medians_ = None

    def fit(self, X: pd.DataFrame, y=None):
        X = X.copy()
        for c in BASE_FEATURES:
            if c not in X.columns:
                X[c] = np.nan
            X[c] = pd.to_numeric(X[c], errors='coerce').replace([np.inf, -np.inf], np.nan)

        self.global_medians_ = X[BASE_FEATURES].median()
        self.type_medians_ = X.groupby('Provider_Type')[FLAGGED_FEATS].median()
        return self

    def transform(self, X: pd.DataFrame) -> np.ndarray:
        X = X.copy()
        for c in BASE_FEATURES:
            if c not in X.columns:
                X[c] = np.nan
            X[c] = pd.to_numeric(X[c], errors='coerce').replace([np.inf, -np.inf], np.nan)

        # Missingness flags computed BEFORE imputation
        for c in FLAGGED_FEATS:
            X[f'{c}_missing'] = X[c].isna().astype(int)

        # Provider-type-conditional median imputation for the sparse feature groups
        type_meds = self.type_medians_.reindex(X['Provider_Type']).reset_index(drop=True)
        type_meds.index = X.index
        for c in FLAGGED_FEATS:
            X[c] = X[c].fillna(type_meds[c])
            X[c] = X[c].fillna(self.global_medians_[c])
            X[c] = X[c].fillna(0.0)

        # Global median imputation for the always-present feature groups
        for c in LOG_FEATS + RATIO_FEATS + BENE_FEATS:
            X[c] = X[c].fillna(self.global_medians_[c])
            X[c] = X[c].fillna(0.0)

        out = X[FULL_FEATURE_ORDER].to_numpy(dtype=float)
        return out

    def get_feature_names_out(self, input_features=None):
        return np.array(FULL_FEATURE_ORDER)


class ClipTransformer(BaseEstimator, TransformerMixin):
    """Clips scaled features to [low, high]. Guards against a handful of pathological
    ratio-feature outliers dominating distance metrics inside Isolation Forest -- exactly
    as done in the original pipeline (np.clip(Xs, -10, 10) in s7_models.py)."""

    def __init__(self, low=-10.0, high=10.0):
        self.low = low
        self.high = high

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        return np.clip(X, self.low, self.high)

