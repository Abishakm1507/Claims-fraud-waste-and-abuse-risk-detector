"""
Custom preprocessing transformer used inside provider_risk_pipeline.joblib.

This module MUST be importable (present on sys.path / same folder) whenever
the saved pipeline is unpickled with joblib.load(), because the pipeline
contains a fitted instance of Winsorizer defined here.

Usage in VS Code:
    import joblib
    import provider_preprocessing  # noqa: F401 (registers the class for unpickling)
    pipeline = joblib.load("provider_risk_pipeline.joblib")
"""
import numpy as np
from sklearn.base import BaseEstimator, TransformerMixin


class Winsorizer(BaseEstimator, TransformerMixin):
    """Clips each feature to its [lower_pct, upper_pct] percentile range,
    learned at fit time. Protects the model and the scaler from extreme
    numerical values / long-tailed billing outliers dominating distances
    and split thresholds, without discarding the underlying rows.
    """

    def __init__(self, lower_pct: float = 1.0, upper_pct: float = 99.0):
        self.lower_pct = lower_pct
        self.upper_pct = upper_pct

    def fit(self, X, y=None):
        X = np.asarray(X, dtype=float)
        self.lower_bounds_ = np.nanpercentile(X, self.lower_pct, axis=0)
        self.upper_bounds_ = np.nanpercentile(X, self.upper_pct, axis=0)
        return self

    def transform(self, X):
        X = np.asarray(X, dtype=float).copy()
        X = np.clip(X, self.lower_bounds_, self.upper_bounds_)
        return X

    def get_feature_names_out(self, input_features=None):
        return np.asarray(input_features)
