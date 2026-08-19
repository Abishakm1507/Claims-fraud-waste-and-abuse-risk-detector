"""
Final validation: Check SHAP consistency for carrier, and inpatient feature derivation.
"""
import warnings
warnings.filterwarnings('ignore')

import joblib
import numpy as np
import pandas as pd
import shap
from pathlib import Path

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

# ============ CARRIER SHAP CONSISTENCY ============
print("=" * 70)
print("CARRIER SHAP CONSISTENCY")
print("=" * 70)

artifacts = load_artifacts("CARRIER")
car_feats = artifacts['feature_names']
car_scaler = artifacts['scaler']
car_iso = artifacts['isolation_forest']

car_df = pd.read_csv("data/raw/carrier_claim_features_FINAL.csv", low_memory=False)

# Clean features: fill NaN with 0, HPSA with 0
for col in car_feats:
    vals = pd.to_numeric(car_df[col], errors='coerce')
    car_df[col] = vals.fillna(0)

# Test SHAP on 2 claims
print(f"\nSHAP reconciliation for carrier:")
for idx in [0, 1000]:
    row = car_df.iloc[idx]
    features = np.array([float(row[f]) for f in car_feats]).reshape(1, -1)
    scaled = car_scaler.transform(features)
    model_output = car_iso.score_samples(scaled)[0]
    
    explainer = shap.TreeExplainer(car_iso)
    shap_values = explainer.shap_values(scaled)
    sv = np.asarray(shap_values)
    if sv.ndim == 3:
        sv = sv[0]
    if sv.ndim == 2 and sv.shape[0] == 1:
        sv = sv[0]
    
    base = explainer.expected_value
    if isinstance(base, (list, np.ndarray)):
        base = float(np.mean(base))
    else:
        base = float(base)
    
    recon = base + np.sum(sv)
    print(f"  Claim {row['CLM_ID']}:")
    print(f"    base_value       = {base:.6f}")
    print(f"    sum(shap)        = {np.sum(sv):.6f}")
    print(f"    base + sum       = {recon:.6f}")
    print(f"    score_samples    = {model_output:.6f}")
    print(f"    residual         = {abs(recon - model_output):.6f}")
    print(f"    decision_function= {car_iso.decision_function(scaled)[0]:.6f}")
    print(f"    SHAP shape       = {sv.shape}")

# ============ INPATIENT FEATURE DERIVATION ============
print("\n" + "=" * 70)
print("INPATIENT FEATURE DERIVATION")
print("=" * 70)

artifacts = load_artifacts("INPATIENT")
inp_feats = artifacts['feature_names']
inp_scaler = artifacts['scaler']
inp_iso = artifacts['isolation_forest']

raw = pd.read_csv("data/raw/inpatient_CLEANED_v2.csv", low_memory=False)
print(f"Raw data: {len(raw)} rows, {len(raw.columns)} cols")

# Check what columns are available for feature derivation
print(f"\nKey columns for feature derivation:")
key_cols = ['clm_id', 'bene_id', 'prvdr_num', 'org_npi_num', 'clm_from_dt', 'clm_thru_dt',
            'clm_admsn_dt', 'clm_pmt_amt', 'clm_tot_chrg_amt', 'clm_utlztn_day_cnt',
            'nch_bene_ip_ddctbl_amt', 'nch_bene_pta_coinsrnc_lblty_am']
for col in key_cols:
    if col in raw.columns:
        print(f"  {col}: present")
    else:
        print(f"  {col}: MISSING")

# Check diagnosis columns
diag_cols = [f'icd_dgns_cd{i}' for i in range(1, 26)]
present_diag = [c for c in diag_cols if c in raw.columns]
print(f"\n  Diagnosis columns present: {len(present_diag)}/{len(diag_cols)}")

# Check procedure columns
proc_cols = [f'icd_prcdr_cd{i}' for i in range(1, 26)]
present_proc = [c for c in proc_cols if c in raw.columns]
print(f"  Procedure columns present: {len(present_proc)}/{len(proc_cols)}")

# Check procedure date columns
proc_date_cols = [f'prcdr_dt{i}' for i in range(1, 26)]
present_proc_date = [c for c in proc_date_cols if c in raw.columns]
print(f"  Procedure date columns present: {len(present_proc_date)}/{len(proc_date_cols)}")

# Check if there's a HCPCS column
hcpcs_cols = [c for c in raw.columns if 'hcpcs' in c.lower()]
print(f"  HCPCS columns: {hcpcs_cols}")

# Check if there's a revenue center column
rev_cols = [c for c in raw.columns if 'rev' in c.lower()]
print(f"  Revenue center columns: {rev_cols}")

# Check if there's a line-level table
print(f"\n  Unique claims: {raw['clm_id'].nunique()}")
print(f"  Rows per claim: {raw.groupby('clm_id').size().describe()}")

# Check if the raw data has line-level detail
print(f"\n  Sample claim rows:")
clm = raw['clm_id'].iloc[0]
claim_rows = raw[raw['clm_id'] == clm]
print(f"  Claim {clm}: {len(claim_rows)} rows")
for _, row in claim_rows.iterrows():
    print(f"    clm_pmt_amt={row.get('clm_pmt_amt')}, clm_tot_chrg_amt={row.get('clm_tot_chrg_amt')}")

# Check if there are multiple rows per claim (line-level)
multi_row_claims = raw.groupby('clm_id').size()
print(f"\n  Claims with >1 row: {(multi_row_claims > 1).sum()}")
print(f"  Claims with 1 row: {(multi_row_claims == 1).sum()}")

# Check if the raw data is actually claim-level (not line-level)
# If each claim has 1 row, then claim_line_count would be 1 for all
# But the feature 'claim_line_count' suggests line-level data
print(f"\n  Check: is raw data line-level or claim-level?")
print(f"  If claim_line_count > 1 for some claims, data is line-level")
print(f"  Max rows per claim: {multi_row_claims.max()}")

# Check if there are HCPCS codes in the data
# Inpatient data typically doesn't have HCPCS codes
# The feature 'unique_hcpcs_count' might be 0 for all inpatient claims
print(f"\n  Feature 'unique_hcpcs_count' - likely 0 for inpatient (no HCPCS in raw)")

# Check if the scaler was fit on data with unique_hcpcs_count = 0
hcpcs_idx = inp_feats.index('unique_hcpcs_count')
print(f"  Scaler mean for unique_hcpcs_count: {inp_scaler.mean_[hcpcs_idx]:.6f}")
print(f"  Scaler scale for unique_hcpcs_count: {inp_scaler.scale_[hcpcs_idx]:.6f}")

# Check if the scaler was fit on data where unique_hcpcs_count is always 0
# If mean=0 and scale=1, then all values were 0
if abs(inp_scaler.mean_[hcpcs_idx]) < 1e-10 and abs(inp_scaler.scale_[hcpcs_idx] - 1) < 1e-10:
    print(f"  -> unique_hcpcs_count was always 0 in training data")
else:
    print(f"  -> unique_hcpcs_count had non-zero values in training data")

# Check the scaler statistics for all features
print(f"\n  Scaler statistics for all features:")
for i, feat in enumerate(inp_feats):
    mean = inp_scaler.mean_[i]
    scale = inp_scaler.scale_[i]
    print(f"    [{i}] {feat}: mean={mean:.4f}, scale={scale:.4f}")

# Check if the scaler was fit on the raw data
# We can check by computing means of derived features
# But first, let's see if the raw data can produce the features

# Check the first few claims
print(f"\n  Sample claims from raw data:")
for clm in list(raw['clm_id'].unique())[:3]:
    claim_rows = raw[raw['clm_id'] == clm]
    first = claim_rows.iloc[0]
    print(f"    Claim {clm}:")
    print(f"      rows={len(claim_rows)}, pmt={first.get('clm_pmt_amt')}, charge={first.get('clm_tot_chrg_amt')}")
    print(f"      from={first.get('clm_from_dt')}, thru={first.get('clm_thru_dt')}, admit={first.get('clm_admsn_dt')}")
    print(f"      util_days={first.get('clm_utlztn_day_cnt')}, bene={first.get('bene_id')}, prvdr={first.get('prvdr_num')}")