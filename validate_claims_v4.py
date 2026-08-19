"""
Carrier deep dive: understand why model output doesn't match stored scores.
"""
import warnings
warnings.filterwarnings('ignore')

import joblib
import numpy as np
import pandas as pd
from pathlib import Path
from scipy.stats import rankdata

BASE = Path("models/claims")

def load_artifacts(claim_type: str):
    path = BASE / claim_type.lower()
    artifacts = {}
    fc_path = path / "feature_columns.pkl"
    if fc_path.exists():
        artifacts['feature_names'] = joblib.load(fc_path)
    else:
        artifacts['feature_names'] = None
    sc_path = path / "scaler.pkl"
    if sc_path.exists():
        artifacts['scaler'] = joblib.load(sc_path)
        if artifacts['feature_names'] is None and hasattr(artifacts['scaler'], 'feature_names_in_'):
            artifacts['feature_names'] = list(artifacts['scaler'].feature_names_in_)
    iso_path = path / "isolation_forest.pkl"
    if iso_path.exists():
        artifacts['isolation_forest'] = joblib.load(iso_path)
    lof_paths = list(path.glob("lof*.pkl"))
    if lof_paths:
        artifacts['lof'] = joblib.load(lof_paths[0])
    oc_path = path / "ocsvm.pkl"
    if oc_path.exists():
        artifacts['ocsvm'] = joblib.load(oc_path)
    mc_path = path / "model_config.pkl"
    if mc_path.exists():
        artifacts['config'] = joblib.load(mc_path)
    return artifacts

artifacts = load_artifacts("CARRIER")
car_feats = artifacts['feature_names']
car_scaler = artifacts['scaler']
car_iso = artifacts['isolation_forest']
car_lof = artifacts['lof']
car_ocsvm = artifacts['ocsvm']

car_df = pd.read_csv("data/raw/carrier_claim_features_FINAL.csv", low_memory=False)
print(f"Carrier features file: {len(car_df)} rows")

# Load unified for stored scores
unified = pd.read_csv(BASE / "unified_claim_risk_with_provider.csv", low_memory=False)
car_unified = unified[unified['CLAIM_TYPE'] == 'CARRIER'].copy()
car_unified['CLAIM_ID_str'] = car_unified['CLAIM_ID'].astype(str).str.strip()

# Match features to unified by CLAIM_ID
car_df['CLAIM_ID_str'] = car_df['CLM_ID'].astype(str).str.strip()
id_map = car_unified.set_index('CLAIM_ID_str')

# Get stored scores in feature file order
stored_if = car_df['CLAIM_ID_str'].map(id_map['IF_score']).values.astype(float)
stored_lof = car_df['CLAIM_ID_str'].map(id_map['LOF_score']).values.astype(float)
stored_ocsvm = car_df['CLAIM_ID_str'].map(id_map['OCSVM_score']).values.astype(float)
stored_ensemble = car_df['CLAIM_ID_str'].map(id_map['carrier_ensemble_score']).values.astype(float)

print(f"Stored IF range: {stored_if.min():.6f} to {stored_if.max():.6f}")
print(f"Stored LOF range: {stored_lof.min():.6f} to {stored_lof.max():.6f}")
print(f"Stored OCSVM range: {stored_ocsvm.min():.6f} to {stored_ocsvm.max():.6f}")
print(f"Stored ensemble range: {stored_ensemble.min():.6f} to {stored_ensemble.max():.6f}")

# Check feature data quality
print(f"\nFeature data quality:")
for col in car_feats:
    vals = pd.to_numeric(car_df[col], errors='coerce')
    n_nan = vals.isna().sum()
    n_blank = (car_df[col].astype(str).str.strip() == '').sum()
    if n_nan > 0 or n_blank > 0:
        print(f"  {col}: {n_nan} NaN, {n_blank} blank")

# Check HPSA_SCRCTY_IND_CD_first - all blank
print(f"\nHPSA_SCRCTY_IND_CD_first: all blank = {(car_df['HPSA_SCRCTY_IND_CD_first'].astype(str).str.strip() == '').all()}")

# Try different preprocessing approaches
print(f"\n=== Testing different preprocessing approaches ===")

# Approach 1: Fill NaN with 0, HPSA with 0
car_a1 = car_df.copy()
for col in car_feats:
    vals = pd.to_numeric(car_a1[col], errors='coerce')
    car_a1[col] = vals.fillna(0)

features_a1 = car_a1[car_feats].values.astype(float)
scaled_a1 = car_scaler.transform(features_a1)
ss_a1 = car_iso.score_samples(scaled_a1)
min_max_inv_a1 = (ss_a1.max() - ss_a1) / (ss_a1.max() - ss_a1.min())
corr_a1 = np.corrcoef(min_max_inv_a1, stored_if)[0, 1]
print(f"\nApproach 1 (NaN->0, HPSA->0):")
print(f"  corr(min_max_inv(ss), stored IF) = {corr_a1:.6f}")

# Approach 2: Fill NaN with median, HPSA with 0
car_a2 = car_df.copy()
for col in car_feats:
    vals = pd.to_numeric(car_a2[col], errors='coerce')
    car_a2[col] = vals.fillna(vals.median())

features_a2 = car_a2[car_feats].values.astype(float)
scaled_a2 = car_scaler.transform(features_a2)
ss_a2 = car_iso.score_samples(scaled_a2)
min_max_inv_a2 = (ss_a2.max() - ss_a2) / (ss_a2.max() - ss_a2.min())
corr_a2 = np.corrcoef(min_max_inv_a2, stored_if)[0, 1]
print(f"\nApproach 2 (NaN->median, HPSA->0):")
print(f"  corr(min_max_inv(ss), stored IF) = {corr_a2:.6f}")

# Approach 3: Drop HPSA column (use only 37 features)
# But scaler expects 38 features, so this won't work directly
# Let's check if the scaler was fit with HPSA as a feature

# Approach 4: Check if the scaler was fit on different data
# Look at scaler statistics vs actual data
print(f"\nScaler statistics vs actual data:")
for i, col in enumerate(car_feats):
    vals = pd.to_numeric(car_df[col], errors='coerce')
    actual_mean = vals.mean()
    actual_std = vals.std()
    scaler_mean = car_scaler.mean_[i]
    scaler_scale = car_scaler.scale_[i]
    if abs(actual_mean - scaler_mean) > 0.1 * abs(scaler_mean) or abs(actual_std - scaler_scale) > 0.1 * abs(scaler_scale):
        print(f"  {col}: actual_mean={actual_mean:.4f}, scaler_mean={scaler_mean:.4f}, actual_std={actual_std:.4f}, scaler_scale={scaler_scale:.4f}")

# Approach 5: Maybe the features file is NOT the training data
# Check if the scaler was fit on a different dataset
# The scaler mean for num_lines_per_claim is 12.54
print(f"\nnum_lines_per_claim stats:")
print(f"  Actual: mean={pd.to_numeric(car_df['num_lines_per_claim'], errors='coerce').mean():.4f}, std={pd.to_numeric(car_df['num_lines_per_claim'], errors='coerce').std():.4f}")
print(f"  Scaler: mean={car_scaler.mean_[0]:.4f}, scale={car_scaler.scale_[0]:.4f}")

# Check if the scaler was fit on the same data
# If scaler.mean_ == data.mean_, then the scaler was fit on this data
# If not, the scaler was fit on different data

# Approach 6: Try using the unified file's outpatient features for carrier
# The unified file has outpatient features for ALL claim types
# Maybe carrier was scored using outpatient features?
print(f"\n=== Check if carrier was scored using outpatient features ===")
out_feats = joblib.load(BASE / "outpatient" / "feature_columns.pkl")
out_scaler = joblib.load(BASE / "outpatient" / "scaler.pkl")
out_iso = joblib.load(BASE / "outpatient" / "isolation_forest.pkl")

# Check if carrier rows in unified have outpatient features
carrier_unified = car_unified.copy()
out_feats_present = [c for c in out_feats if c in carrier_unified.columns]
print(f"  Outpatient features present in carrier unified: {len(out_feats_present)}/{len(out_feats)}")

if len(out_feats_present) == len(out_feats):
    # Try scoring carrier with outpatient model
    features = carrier_unified[out_feats].values.astype(float)
    scaled = out_scaler.transform(features)
    ss = out_iso.score_samples(scaled)
    min_max_inv = (ss.max() - ss) / (ss.max() - ss.min())
    corr = np.corrcoef(min_max_inv, stored_if)[0, 1]
    print(f"  corr(outpatient model ss, carrier stored IF) = {corr:.6f}")

# Approach 7: Check if the carrier model was trained on a different feature set
# Maybe the feature file has different column order than what the scaler expects
print(f"\n=== Check feature order ===")
print(f"Scaler feature_names_in_:")
for i, name in enumerate(car_scaler.feature_names_in_):
    print(f"  [{i}] {name}")

print(f"\nFeature file columns:")
for i, name in enumerate(car_df.columns):
    if name in car_feats:
        print(f"  [{car_feats.index(name)}] {name}")

# Check if the order matches
order_match = all(car_df.columns[i] == car_feats[i] for i in range(min(len(car_df.columns), len(car_feats))))
print(f"\n  Column order matches scaler: {order_match}")

# Approach 8: Maybe the stored scores were computed with a different model
# Check if the stored IF scores are actually from a different pipeline
# The unified file has both IF_score and isolation_forest_score columns
print(f"\n=== Check unified file score columns ===")
print(f"  IF_score: {car_unified['IF_score'].describe()}")
print(f"  isolation_forest_score: {car_unified['isolation_forest_score'].describe()}")

# Check if isolation_forest_score is the same as IF_score
if 'isolation_forest_score' in car_unified.columns:
    same = np.allclose(car_unified['IF_score'].fillna(-1), car_unified['isolation_forest_score'].fillna(-1), equal_nan=True)
    print(f"  IF_score == isolation_forest_score: {same}")

# Approach 9: Check if the carrier model was trained on a different dataset
# The scaler mean for CLM_PMT_AMT_first is 1323.62
# But the actual data has mean of ~42062.86 for the first row
# Let's check the actual mean
pmt_vals = pd.to_numeric(car_df['CLM_PMT_AMT_first'], errors='coerce')
print(f"\nCLM_PMT_AMT_first stats:")
print(f"  Actual: mean={pmt_vals.mean():.4f}, std={pmt_vals.std():.4f}")
print(f"  Scaler: mean={car_scaler.mean_[4]:.4f}, scale={car_scaler.scale_[4]:.4f}")

# Check if the scaler was fit on log-transformed data
log_pmt = np.log1p(pmt_vals)
print(f"  log1p(CLM_PMT_AMT): mean={log_pmt.mean():.4f}, std={log_pmt.std():.4f}")

# Check if the scaler was fit on the raw data
# If scaler.mean_[4] == pmt_vals.mean(), then raw
# If scaler.mean_[4] == log_pmt.mean(), then log-transformed
print(f"  Scaler mean[4] = {car_scaler.mean_[4]:.4f}")
print(f"  Raw mean = {pmt_vals.mean():.4f}")
print(f"  Log mean = {log_pmt.mean():.4f}")

# Check all features for log transformation
print(f"\n=== Check if features are log-transformed ===")
for i, col in enumerate(car_feats[:10]):
    vals = pd.to_numeric(car_df[col], errors='coerce').fillna(0)
    raw_mean = vals.mean()
    log_mean = np.log1p(vals).mean()
    scaler_mean = car_scaler.mean_[i]
    raw_diff = abs(raw_mean - scaler_mean)
    log_diff = abs(log_mean - scaler_mean)
    print(f"  {col}: raw_mean={raw_mean:.4f}, log_mean={log_mean:.4f}, scaler_mean={scaler_mean:.4f}, raw_diff={raw_diff:.4f}, log_diff={log_diff:.4f}")