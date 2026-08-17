"""
predict_provider.py
--------------------
Reusable inference script for the provider-level anomaly-detection risk model.
Run this from VS Code (or any local Python environment) to score providers
using the ALREADY-TRAINED pipeline saved in provider_risk_pipeline.joblib.
No retraining happens here.

Requirements (same major versions as training):
    pandas, numpy, scikit-learn, joblib

Folder layout expected (all in the same directory as this script, or adjust paths below):
    provider_risk_pipeline.joblib      <- trained preprocessing + Isolation Forest pipeline
    provider_feature_columns.json      <- exact feature order used in training
    provider_preprocessing.py          <- custom Winsorizer transformer class (required for unpickling)
    feature_engineering.py             <- feature engineering functions (raw CSVs -> provider-level features)

USAGE
-----
1) Score brand-new raw CMS provider-service CSVs (same format as cms_provider_service_YYYY.csv):

    python predict_provider.py --raw_csv_dir /path/to/csvs --years 2021 2022 2023 2024 2025

2) Or, from your own Python code, once you already have a provider-level
   feature DataFrame with the 40 columns in provider_feature_columns.json:

    import joblib
    import provider_preprocessing  # noqa: F401  (registers Winsorizer for unpickling)

    pipeline = joblib.load("provider_risk_pipeline.joblib")
    anomaly_flags = pipeline.predict(provider_features_df)          # -1 = anomaly, 1 = normal
    raw_scores    = -pipeline.decision_function(provider_features_df)  # higher = more anomalous
"""
import argparse
import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import provider_preprocessing  # noqa: F401  (registers Winsorizer class for joblib unpickling)
from feature_engineering import engineer_provider_features, FINAL_FEATURE_COLUMNS


def risk_category(score: float) -> str:
    if score < 25:
        return "Low"
    if score < 50:
        return "Medium"
    if score < 75:
        return "High"
    return "Critical"


def score_providers(feature_df: pd.DataFrame, pipeline, feature_columns: list[str]) -> pd.DataFrame:
    """Given a provider-level feature DataFrame (must include 'npi' and all
    feature_columns), return a DataFrame of anomaly scores and risk scores."""
    missing = [c for c in feature_columns if c not in feature_df.columns]
    if missing:
        raise ValueError(f"Input data is missing required feature columns: {missing}")

    X = feature_df[feature_columns].replace([np.inf, -np.inf], np.nan)

    raw_score = -pipeline.decision_function(X)              # higher = more anomalous
    anomaly_flag = (pipeline.predict(X) == -1).astype(int)  # 1 = flagged anomaly

    # Note: for a NEW inference batch, min-max normalize against this batch's own score
    # range to get an interpretable 0-100 scale for THIS run. For scores that need to be
    # directly comparable to the original training population's scale, load
    # provider_model_metadata.json -> validation_summary.anomaly_score_distribution
    # (min/max) and normalize against those training-time bounds instead.
    rmin, rmax = raw_score.min(), raw_score.max()
    if rmax > rmin:
        risk_score = (raw_score - rmin) / (rmax - rmin) * 100
    else:
        risk_score = np.zeros_like(raw_score)

    out = feature_df[["npi"]].copy()
    out["anomaly_score_raw"] = raw_score
    out["isolation_forest_anomaly_flag"] = anomaly_flag
    out["risk_score_0_100"] = np.round(risk_score, 2)
    out["risk_category"] = [risk_category(s) for s in risk_score]
    return out.sort_values("risk_score_0_100", ascending=False).reset_index(drop=True)


def main():
    parser = argparse.ArgumentParser(description="Score providers with the trained risk pipeline.")
    parser.add_argument("--raw_csv_dir", type=str, required=True,
                         help="Directory containing cms_provider_service_YYYY.csv files")
    parser.add_argument("--years", type=int, nargs="+", required=True,
                         help="Years to include, e.g. --years 2021 2022 2023 2024")
    parser.add_argument("--pipeline_path", type=str, default="provider_risk_pipeline.joblib")
    parser.add_argument("--feature_columns_path", type=str, default="provider_feature_columns.json")
    parser.add_argument("--output_csv", type=str, default="new_provider_risk_scores.csv")
    args = parser.parse_args()

    with open(args.feature_columns_path) as f:
        feature_columns = json.load(f)["feature_columns_in_order"]

    pipeline = joblib.load(args.pipeline_path)

    paths_by_year = {y: str(Path(args.raw_csv_dir) / f"cms_provider_service_{y}.csv") for y in args.years}
    feat = engineer_provider_features(paths_by_year)

    scored = score_providers(feat, pipeline, feature_columns)
    scored.to_csv(args.output_csv, index=False)
    print(f"Scored {len(scored)} providers -> {args.output_csv}")
    print(scored.head(10).to_string())


if __name__ == "__main__":
    main()
