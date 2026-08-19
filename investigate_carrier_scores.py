"""
Carrier root-cause investigation - determine how stored IF_score was generated.
"""
import warnings
warnings.filterwarnings('ignore')

import joblib
import numpy as np
import pandas as pd
from pathlib import Path
from scipy.stats import rankdata

BASE = Path("models/claims")

unified = pd.read_csv(BASE / "unified_claim_risk_with_provider.csv", low_memory=False)
carrier_unified = unified[unified['CLAIM_TYPE'] == 'CARRIER'].copy()

# 1. Check if carrier rows have POPULATED outpatient feature columns
out_feats = joblib.load(BASE / "outpatient" / "feature_columns.pkl")
print("=== Check outpatient features in carrier unified rows ===")
present = [c for c in out_feats if c in carrier_unified.columns]
populated = [c for c in present if carrier_unified[c].notna().sum() > 0]
print(f"  Outpatient features populated in carrier rows: {len(populated)}/{len(out_feats)}")
for c in present[:10]:
    nn = carrier_unified[c].notna().sum()
    print(f"    {c}: {nn}/{len(carrier_unified)} not-null")

# 2. Try outpatient model on carrier rows
out_scaler = joblib.load(BASE / "outpatient" / "scaler.pkl")
out_iso = joblib.load(BASE / "outpatient" / "isolation_forest.pkl")

print("\n=== Try outpatient model on carrier rows ===")
out_feats_present = [c for c in out_feats if c in carrier_unified.columns]
if all(c in carrier_unified.columns and carrier_unified[c].notna().any() for c in out_feats):
    X = carrier_unified[out_feats].values.astype(float)
    # Check for NaN
    nan_count = np.isnan(X).sum()
    print(f"  NaN count in X: {nan_count}")
    if nan_count == 0:
        scaled = out_scaler.transform(X)
        ss = out_iso.score_samples(scaled)
        stored_if = carrier_unified['IF_score'].values.astype(float)
        
        min_max_inv = (ss.max() - ss) / (ss.max() - ss.min())
        corr = np.corrcoef(min_max_inv, stored_if)[0, 1]
        print(f"  corr(outpatient model minmax_inv, carrier stored IF) = {corr:.6f}")
        
        # Try the CARRIER model on carrier rows with outpatient features?
        # Actually the carrier scaler is 38 features different from outpatient's 38
else:
    print("  Outpatient features NOT fully populated in carrier rows")

# 3. Check the stored IF_score distribution shape
print("\n=== Stored IF_score distribution ===")
stored_if = carrier_unified['IF_score'].values.astype(float)
print(f"  Min: {stored_if.min():.6f}")
print(f"  Max: {stored_if.max():.6f}")
print(f"  Mean: {stored_if.mean():.6f}")
print(f"  Std: {stored_if.std():.6f}")
print(f"  Median: {np.median(stored_if):.6f}")
print(f"  Q25: {np.percentile(stored_if, 25):.6f}")
print(f"  Q75: {np.percentile(stored_if, 75):.6f}")
print(f"  Skewness: {pd.Series(stored_if).skew():.6f}")

# 4. Try to see if IF_score is 1/(1+exp(x)) of score_samples or similar
# Load carrier artifacts
car_scaler = joblib.load(BASE / "carrier" / "scaler.pkl")
car_iso = joblib.load(BASE / "carrier" / "isolation_forest.pkl")
car_feats = list(car_scaler.feature_names_in_)

# Load features
car_feat = pd.read_csv("data/raw/carrier_claim_features_FINAL.csv", low_memory=False)
for col in car_feats:
    car_feat[col] = pd.to_numeric(car_feat[col], errors='coerce').fillna(0)

# Align by ID
car_feat['CLAIM_ID_str'] = car_feat['CLM_ID'].astype(str).str.strip()
carrier_unified['CLAIM_ID_str'] = carrier_unified['CLAIM_ID'].astype(str).str.strip()

# Merge features with unified scores
merged = car_feat.merge(
    carrier_unified[['CLAIM_ID_str', 'IF_score', 'LOF_score', 'OCSVM_score', 'carrier_ensemble_score']],
    on='CLAIM_ID_str',
    how='inner'
)
print(f"\nMerged rows: {len(merged)}")

# Compute model outputs
X = merged[car_feats].values.astype(float)
X_scaled = car_scaler.transform(X)
ss = car_iso.score_samples(X_scaled)
dec = car_iso.decision_function(X_scaled)

stored_if = merged['IF_score'].values.astype(float)

print("\n=== Test various transformations of score_samples ===")

# 1. Min-max inverted
mm_inv = (ss.max() - ss) / (ss.max() - ss.min())
print(f"  minmax_inv vs stored: corr={np.corrcoef(mm_inv, stored_if)[0,1]:.6f}")

# 2. Percentile rank
rank_pct = rankdata(ss) / len(ss)
print(f"  rank(ss)/N vs stored: corr={np.corrcoef(rank_pct, stored_if)[0,1]:.6f}")

# 3. Inverted percentile rank
print(f"  (1-rank(ss)) vs stored: corr={np.corrcoef(1-rank_pct, stored_if)[0,1]:.6f}")

# 4. Softmax / sigmoid of ss
sigmoid = 1 / (1 + np.exp(ss))
print(f"  sigmoid(ss) vs stored: corr={np.corrcoef(sigmoid, stored_if)[0,1]:.6f}")

# 5. exp(-ss) normalized
exp_neg = np.exp(-ss)
exp_norm = (exp_neg - exp_neg.min()) / (exp_neg.max() - exp_neg.min())
print(f"  minmax(exp(-ss)) vs stored: corr={np.corrcoef(exp_norm, stored_if)[0,1]:.6f}")

# 6. exp(-dec)
exp_dec = np.exp(-dec)
exp_dec_norm = (exp_dec - exp_dec.min()) / (exp_dec.max() - exp_dec.min())
print(f"  minmax(exp(-dec)) vs stored: corr={np.corrcoef(exp_dec_norm, stored_if)[0,1]:.6f}")

# 7. -score_samples (isolated score)
neg_ss = -ss
neg_norm = (neg_ss - neg_ss.min()) / (neg_ss.max() - neg_ss.min())
print(f"  minmax(-ss) vs stored: corr={np.corrcoef(neg_norm, stored_if)[0,1]:.6f}")

# 8. Check if the stored IF_score itself has a specific distribution
# Maybe it's a blend of model scores?
print("\n=== Check relationship between stored IF/LOF/OCSVM ===")
stored_lof = merged['LOF_score'].values.astype(float)
stored_ocsvm = merged['OCSVM_score'].values.astype(float)
stored_ens = merged['carrier_ensemble_score'].values.astype(float)

print(f"  corr(stored IF, stored LOF) = {np.corrcoef(stored_if, stored_lof)[0,1]:.6f}")
print(f"  corr(stored IF, stored OCSVM) = {np.corrcoef(stored_if, stored_ocsvm)[0,1]:.6f}")
print(f"  corr(stored LOF, stored OCSVM) = {np.corrcoef(stored_lof, stored_ocsvm)[0,1]:.6f}")

# Try to reconstruct ensemble
for w_if, w_lof, w_oc in [(0.2,0.2,0.6), (0.34,0.33,0.33), (0.6,0.2,0.2), (0.5,0.25,0.25), (0.4,0.3,0.3)]:
    ens = w_if*stored_if + w_lof*stored_lof + w_oc*stored_ocsvm
    print(f"  ens({w_if},{w_lof},{w_oc}) vs stored_ens: corr={np.corrcoef(ens, stored_ens)[0,1]:.6f}")

# 9. Check the score range: ss is very narrow (-0.64 to -0.52)
print(f"\n=== Score range analysis ===")
print(f"  score_samples range: {ss.min():.6f} to {ss.max():.6f} (width={ss.max()-ss.min():.6f})")
print(f"  decision_function range: {dec.min():.6f} to {dec.max():.6f} (width={dec.max()-dec.min():.6f})")
print(f"  Stored IF range: 0 to 1")

# 10. Maybe the stored IF scores came from a DIFFERENT model
# Check if there's a way to tell: the carrier model parameters
print("\n=== Carrier IsolationForest model details ===")
print(f"  n_estimators: {car_iso.n_estimators}")
print(f"  max_samples: {car_iso.max_samples}")
print(f"  contamination: {car_iso.contamination}")
print(f"  max_samples_: {car_iso.max_samples_}")
print(f"  offset_: {car_iso.offset_}")

# 11. Check if the features file is what trained the model
# The scaler stats match the features file exactly - so scaler was FIT on this data
# But model outputs don't match stored scores
# This means: the stored scores were generated by a DIFFERENT pipeline

# Conclusion: check git history for the carrier training script
print("\n=== Search git history for carrier training scripts ===")
import subprocess
try:
    result = subprocess.run(
        ['git', 'log', '--all', '--name-only', '--pretty=format:%H %s', '--', '*.py'],
        capture_output=True, text=True, shell=False
    )
    # Filter for carrier/inpatient/claim related files
    lines = result.stdout.split('\n')
    relevant = [l for l in lines if any(k in l.lower() for k in ['carrier', 'inpatient', 'outpatient', 'claim', 'feature', 'risk'])]
    print('\n'.join(relevant[:100]))
except Exception as e:
    print(f"  Error: {e}")