"""
Deep dive: Understand carrier score mismatch and outpatient score normalization.
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

# ============ OUTPATIENT: Verify exact normalization ============
print("=" * 70)
print("OUTPATIENT: Verify exact score normalization")
print("=" * 70)

artifacts = load_artifacts("OUTPATIENT")
out_feats = artifacts['feature_names']
out_scaler = artifacts['scaler']
out_iso = artifacts['isolation_forest']

out_df = pd.read_csv(BASE / "outpatient" / "outpatient_final_risk_scores.csv", low_memory=False)

# Compute score_samples for all claims
all_features = out_df[out_feats].values.astype(float)
all_scaled = out_scaler.transform(all_features)
all_ss = out_iso.score_samples(all_scaled)
all_dec = out_iso.decision_function(all_scaled)

stored_if = out_df['IF_score'].values.astype(float)

# Hypothesis: stored = (max_ss - ss) / (max_ss - min_ss)
min_max_inv = (all_ss.max() - all_ss) / (all_ss.max() - all_ss.min())
diff1 = np.abs(min_max_inv - stored_if)
print(f"Hypothesis 1: (max_ss - ss)/(max_ss - min_ss)")
print(f"  Max diff: {diff1.max():.10f}")
print(f"  Mean diff: {diff1.mean():.10f}")

# Hypothesis 2: (ss - min_ss) / (max_ss - min_ss) inverted
min_max = (all_ss - all_ss.min()) / (all_ss.max() - all_ss.min())
diff2 = np.abs(1 - min_max - stored_if)
print(f"\nHypothesis 2: 1 - (ss - min_ss)/(max_ss - min_ss)")
print(f"  Max diff: {diff2.max():.10f}")
print(f"  Mean diff: {diff2.mean():.10f}")

# Hypothesis 3: rank-based
rank_ss = rankdata(all_ss) / len(all_ss)
diff3 = np.abs(1 - rank_ss - stored_if)
print(f"\nHypothesis 3: 1 - rank(ss)/N")
print(f"  Max diff: {diff3.max():.10f}")
print(f"  Mean diff: {diff3.mean():.10f}")

# Also test decision_function normalization
min_max_dec_inv = (all_dec.max() - all_dec) / (all_dec.max() - all_dec.min())
diff4 = np.abs(min_max_dec_inv - stored_if)
print(f"\nHypothesis 4: (max_dec - dec)/(max_dec - min_dec)")
print(f"  Max diff: {diff4.max():.10f}")
print(f"  Mean diff: {diff4.mean():.10f}")

# Test if IF_score relates to score_samples as: exp(ss) or 1/(1+exp(-ss)) or similar
# sklearn IsolationForest score_samples returns -score (lower = more anomalous)
# The stored IF_score is inverted relative to score_samples
print(f"\nSample data:")
for i in range(5):
    print(f"  idx={i}, ss={all_ss[i]:.6f}, min_max_inv={min_max_inv[i]:.6f}, stored={stored_if[i]:.6f}, exact_match={abs(min_max_inv[i]-stored_if[i])<1e-8}")

# ============ CARRIER DEEP DIVE ============
print("\n" + "=" * 70)
print("CARRIER DEEP DIVE")
print("=" * 70)

artifacts = load_artifacts("CARRIER")
car_feats = artifacts['feature_names']
car_scaler = artifacts['scaler']
car_iso = artifacts['isolation_forest']
car_lof = artifacts['lof']
car_ocsvm = artifacts['ocsvm']

car_df = pd.read_csv("data/raw/carrier_claim_features_FINAL.csv", low_memory=False)
print(f"Carrier features file: {len(car_df)} rows")

# Check column types - HPSA_SCRCTY_IND_CD_first may have strings
print(f"\nHPSA_SCRCTY_IND_CD_first unique values: {car_df['HPSA_SCRCTY_IND_CD_first'].unique()[:10]}")
print(f"PRTCPTNG_IND_CD_first unique values: {car_df['PRTCPTNG_IND_CD_first'].unique()[:10]}")

# Load unified for carrier data
unified = pd.read_csv(BASE / "unified_claim_risk_with_provider.csv", low_memory=False)
car_unified = unified[unified['CLAIM_TYPE'] == 'CARRIER'].copy()
car_unified['CLAIM_ID_str'] = car_unified['CLAIM_ID'].astype(str).str.strip()

# Check what's in the unified carrier rows - do they have the features?
print(f"\nCarrier unified columns available:")
carrier_cols = [c for c in car_unified.columns if c not in ['CLAIM_TYPE', 'CLAIM_ID', 'CLM_ID', 'PROVIDER_ID', 'clm_id', 'provider_id', 'MODEL_SCORE', 'CLAIM_RISK_SCORE', 'CLAIM_RISK_RANK']]
print(f"  Non-identifier columns: {carrier_cols}")

# The features file and unified file have different claim IDs
# Features file uses CLM_ID (raw claim IDs), unified uses CLAIM_ID
# But they matched ALL 6665 when using CLAIM_ID from unified!
# That means there's a DIFFERENT claim ID mapping
print(f"\nCheck claim ID mapping:")
car_feat_ids = car_df['CLM_ID'].astype(str).str.strip()
car_unified_ids = car_unified['CLAIM_ID'].astype(str).str.strip()
print(f"  Features CLM_ID sample: {car_feat_ids.iloc[:3].tolist()}")
print(f"  Unified CLAIM_ID sample: {car_unified_ids.iloc[:3].tolist()}")

# Match on CLAIM_ID (correct column from unified)
merged = car_unified.merge(
    car_df[['CLM_ID'] + car_feats],
    left_on='CLAIM_ID',
    right_on='CLM_ID',
    how='inner'
)
print(f"  Merged on CLAIM_ID=CLM_ID: {len(merged)} rows")

# Actually wait - earlier we said overlap=6665 when comparing features CLM_ID with unified CLAIM_ID
# So CLAIM_ID in unified == CLM_ID in features file
# But the unified CLM_ID column doesn't match features CLM_ID
# Let's verify
print(f"\n  Check: is unified.CLAIM_ID == features.CLM_ID for all?")
feature_ids_set = set(car_df['CLM_ID'].astype(str).str.strip())
unified_ids_set = set(car_unified['CLAIM_ID'].astype(str).str.strip())
print(f"  Same set: {feature_ids_set == unified_ids_set}")

# Now check if the features in unified are the same as in features file
# Look at CLM_PMT_AMT_first values
sample_car_df = car_df[['CLM_ID', 'CLM_PMT_AMT_first']].iloc[0]
sample_unified = car_unified[['CLAIM_ID', 'CLM_PMT_AMT_first']].iloc[0]
print(f"\n  Feature file row 0: CLM_ID={sample_car_df['CLM_ID']}, CLM_PMT_AMT={sample_car_df['CLM_PMT_AMT_first']}")
print(f"  Unified row 0: CLAIM_ID={sample_unified['CLAIM_ID']}, CLM_PMT_AMT={sample_unified['CLM_PMT_AMT_first']}")

# Check if the CLM_PMT_AMT values match between the two files
merged_check = car_unified.merge(
    car_df[['CLM_ID', 'CLM_PMT_AMT_first', 'NCH_CARR_CLM_SBMTD_CHRG_AMT_first', 'NCH_CARR_CLM_ALOWD_AMT_first']],
    left_on='CLAIM_ID',
    right_on='CLM_ID',
    how='inner',
    suffixes=('_unified', '_feat')
)
print(f"\n  Merged check: {len(merged_check)} rows")
if len(merged_check) > 0:
    # Compare CLM_PMT_AMT values
    merged_check['pmt_match'] = np.isclose(
        pd.to_numeric(merged_check['CLM_PMT_AMT_first_unified'], errors='coerce'),
        pd.to_numeric(merged_check['CLM_PMT_AMT_first_feat'], errors='coerce'),
        rtol=1e-6, equal_nan=True
    )
    print(f"  CLM_PMT_AMT matches: {merged_check['pmt_match'].sum()}/{len(merged_check)}")
    
    if merged_check['pmt_match'].sum() < len(merged_check):
        # Show mismatches
        mismatch = merged_check[~merged_check['pmt_match']].head(3)
        for _, row in mismatch.iterrows():
            print(f"    Unified CLAIM_ID={row['CLAIM_ID']}, unified_pmt={row['CLM_PMT_AMT_first_unified']}, feat_pmt={row['CLM_PMT_AMT_first_feat']}")

# Check if there's a different source for carrier features
# Maybe carrier features were computed differently
print(f"\n--- Understanding carrier pipeline ---")
print(f"  Scaler feature count: {len(car_feats)}")
print(f"  Scaler type: {type(car_scaler).__name__}")
print(f"  Scaler mean_ shape: {car_scaler.mean_.shape if hasattr(car_scaler, 'mean_') else 'N/A'}")
print(f"  Scaler scale_ shape: {car_scaler.scale_.shape if hasattr(car_scaler, 'scale_') else 'N/A'}")

# Load the scaler parameters to check
print(f"\n  Scaler mean_ (first 5): {car_scaler.mean_[:5]}")
print(f"  Scaler scale_ (first 5): {car_scaler.scale_[:5]}")

# Compute with different preprocessing to see which matches
# Try: NaN imputation with median instead of 0
print(f"\n  Test different imputation strategies:")
for col in car_feats:
    vals = pd.to_numeric(car_df[col], errors='coerce')
    n_nan = vals.isna().sum()
    if n_nan > 0:
        print(f"    {col}: {n_nan} NaN/blank values")

# Test: maybe the original data had no NaN because it was already computed differently
# Let's check what the original pipeline probably did
# Approach: check if the carrier IF scores match if we use all non-NaN values
print(f"\n  Testing with median imputation:")
car_median = car_df.copy()
for col in car_feats:
    vals = pd.to_numeric(car_median[col], errors='coerce')
    car_median[col] = vals.fillna(vals.median())

all_features = car_median[car_feats].values.astype(float)
all_scaled = car_scaler.transform(all_features)
all_ss = car_iso.score_samples(all_scaled)

stored_if = car_unified.set_index('CLAIM_ID').loc[car_median['CLM_ID'].astype(str).str.strip()]['IF_score'].values.astype(float)
# Wait, need to re-align
# Get the stored IF scores in the same order as car_median
id_map = car_unified.set_index('CLAIM_ID')['IF_score']
stored_if = car_median['CLM_ID'].map(id_map).values.astype(float)

corr = np.corrcoef(all_ss, stored_if)[0, 1]
print(f"  corr(ss with median imputation, stored IF) = {corr:.6f}")

min_max_inv = (all_ss.max() - all_ss) / (all_ss.max() - all_ss.min())
corr2 = np.corrcoef(min_max_inv, stored_if)[0, 1]
diff = np.abs(min_max_inv - stored_if)
print(f"  corr(min_max_inv, stored IF) = {corr2:.6f}")
print(f"  Max diff: {diff.max():.6f}, Mean diff: {diff.mean():.6f}")

# Try with zeros (our original)
car_zero = car_df.copy()
for col in car_feats:
    vals = pd.to_numeric(car_zero[col], errors='coerce')
    car_zero[col] = vals.fillna(0)

all_features = car_zero[car_feats].values.astype(float)
all_scaled = car_scaler.transform(all_features)
all_ss = car_iso.score_samples(all_scaled)
min_max_inv = (all_ss.max() - all_ss) / (all_ss.max() - all_ss.min())

corr = np.corrcoef(all_ss, stored_if)[0, 1]
print(f"\n  corr(ss with zero imputation, stored IF) = {corr:.6f}")
corr2 = np.corrcoef(min_max_inv, stored_if)[0, 1]
print(f"  corr(min_max_inv, stored IF) = {corr2:.6f}")

# Check - maybe the feature values in unified should be used instead
print(f"\n  Using unified file features for carrier...")
# But unified only has 3-6 carrier features
unified_feats = ['CLM_PMT_AMT_first', 'NCH_CARR_CLM_SBMTD_CHRG_AMT_first', 'NCH_CARR_CLM_ALOWD_AMT_first']
print(f"  Unified has only: {[c for c in unified_feats if c in car_unified.columns]}")

# ============ INPATIENT FEATURE DERIVATION ============
print("\n" + "=" * 70)
print("INPATIENT FEATURE DERIVATION ATTEMPT")
print("=" * 70)

artifacts = load_artifacts("INPATIENT")
inp_feats = artifacts['feature_names']
inp_scaler = artifacts['scaler']
inp_iso = artifacts['isolation_forest']

raw = pd.read_csv("data/raw/inpatient_CLEANED_v2.csv", low_memory=False)
print(f"Raw data: {len(raw)} rows, {len(raw.columns)} cols")

# Group by clm_id to derive claim-level features
print(f"\nGrouping by clm_id...")
grouped = raw.groupby('clm_id')
print(f"  Unique claims: {len(grouped)}")

# Derive features
from datetime import datetime

def derive_features(claim_rows):
    """Derive claim-level features from raw inpatient rows."""
    first = claim_rows.iloc[0]
    
    # Claim line count
    claim_line_count = len(claim_rows)
    
    # Diagnoses - columns icd_dgns_cd1 to icd_dgns_cd25
    diag_cols = [f'icd_dgns_cd{i}' for i in range(1, 26)]
    diag_vals = []
    for col in diag_cols:
        if col in claim_rows.columns:
            vals = claim_rows[col].dropna().values
            diag_vals.extend(vals)
    diag_vals = [str(v).strip() for v in diag_vals if str(v).strip() and str(v).strip() != 'nan']
    unique_diag = set(diag_vals)
    
    # Procedures - columns icd_prcdr_cd1 to icd_prcdr_cd25
    proc_cols = [f'icd_prcdr_cd{i}' for i in range(1, 26)]
    proc_vals = []
    for col in proc_cols:
        if col in claim_rows.columns:
            vals = claim_rows[col].dropna().values
            proc_vals.extend(vals)
    proc_vals = [str(v).strip() for v in proc_vals if str(v).strip() and str(v).strip() != 'nan']
    unique_proc = set(proc_vals)
    
    # Procedure dates
    proc_date_cols = [f'prcdr_dt{i}' for i in range(1, 26)]
    proc_dates = []
    for col in proc_date_cols:
        if col in claim_rows.columns:
            vals = claim_rows[col].dropna().values
            proc_dates.extend(vals)
    proc_dates = [str(v).strip() for v in proc_dates if str(v).strip() and str(v).strip() != 'nan']
    unique_proc_dates = set(proc_dates)
    
    # Financial
    total_claim_charge = pd.to_numeric(first.get('clm_tot_chrg_amt', 0), errors='coerce')
    total_claim_payment = pd.to_numeric(first.get('clm_pmt_amt', 0), errors='coerce')
    
    # Dates
    clm_from = pd.to_datetime(first.get('clm_from_dt'), errors='coerce')
    clm_thru = pd.to_datetime(first.get('clm_thru_dt'), errors='coerce')
    clm_admsn = pd.to_datetime(first.get('clm_admsn_dt'), errors='coerce')
    nch_bene_dschrg = pd.to_datetime(first.get('nch_bene_dschrg_dt'), errors='coerce')
    
    # Claim duration
    if pd.notna(clm_from) and pd.notna(clm_thru):
        claim_duration = (clm_thru - clm_from).days + 1
    else:
        claim_duration = 1
    
    # Admit to thru
    if pd.notna(clm_admsn) and pd.notna(clm_thru):
        admit_to_thru = (clm_thru - clm_admsn).days + 1
    else:
        admit_to_thru = 0
    
    # Same day stay
    is_same_day = 1 if (pd.notna(clm_admsn) and pd.notna(clm_thru) and clm_admsn.date() == clm_thru.date()) else 0
    
    # Admit month/quarter/year
    admit_month = clm_admsn.month if pd.notna(clm_admsn) else 0
    admit_quarter = (admit_month - 1) // 3 + 1 if admit_month > 0 else 0
    admit_year = clm_admsn.year if pd.notna(clm_admsn) else 0
    
    # Utilization days
    total_utilization_days = pd.to_numeric(first.get('clm_utlztn_day_cnt', 0), errors='coerce')
    
    features = {
        'claim_line_count': claim_line_count,
        'unique_hcpcs_count': 0,  # Not available in inpatient raw
        'unique_diagnosis_code_count': len(unique_diag),
        'total_diagnosis_code_count': len(diag_vals),
        'unique_procedure_code_count': len(unique_proc),
        'total_procedure_code_count': len(proc_vals),
        'unique_procedure_date_count': len(unique_proc_dates),
        'procedure_code_diversity_ratio': len(unique_proc) / len(proc_vals) if proc_vals else 0,
        'multiple_procedures_flag': 1 if len(unique_proc) > 1 else 0,
        'total_claim_charge': total_claim_charge if pd.notna(total_claim_charge) else 0,
        'total_claim_payment': total_claim_payment if pd.notna(total_claim_payment) else 0,
        'average_line_charge': total_claim_charge / claim_line_count if pd.notna(total_claim_charge) and claim_line_count > 0 else 0,
        'average_line_payment': total_claim_payment / claim_line_count if pd.notna(total_claim_payment) and claim_line_count > 0 else 0,
        'total_deductible_amount': pd.to_numeric(first.get('nch_bene_ip_ddctbl_amt', 0), errors='coerce'),
        'total_coinsurance_amount': pd.to_numeric(first.get('nch_bene_pta_coinsrnc_lblty_am', 0), errors='coerce'),
        'total_utilization_days': total_utilization_days if pd.notna(total_utilization_days) else 0,
        'average_daily_payment': total_claim_payment / total_utilization_days if pd.notna(total_claim_payment) and pd.notna(total_utilization_days) and total_utilization_days > 0 else 0,
        'claim_duration_days': claim_duration,
        'admit_to_thru_days': admit_to_thru,
        'is_same_day_stay': is_same_day,
        'admit_month': admit_month,
        'admit_quarter': admit_quarter,
        'admit_year': admit_year,
        'bene_total_claims': 0,  # Need aggregation
        'bene_unique_claims': 0,
        'bene_avg_line_count': 0,
        'bene_avg_claim_duration': 0,
        'bene_total_payment': 0,
        'bene_avg_payment': 0,
        'bene_days_since_first_claim': 0,
        'bene_recent_claims_count': 0,
        'provider_total_claims': 0,
        'provider_unique_beneficiaries': 0,
        'provider_total_payment': 0,
        'provider_avg_payment': 0,
        'provider_total_charge': 0,
        'provider_avg_charge': 0,
        'provider_avg_utilization_days': 0,
        'provider_total_utilization_days': 0,
        'provider_payment_per_beneficiary': 0,
        'provider_claims_per_beneficiary': 0,
        'high_claim_line_count_flag': 1 if claim_line_count > 3 else 0,
        'high_diagnosis_count_flag': 1 if len(unique_diag) > 5 else 0,
        'high_procedure_count_flag': 1 if len(unique_proc) > 3 else 0,
        'high_utilization_flag': 1 if total_utilization_days > 7 else 0,
        'high_claim_payment_flag': 1 if total_claim_payment > 10000 else 0,
        'high_provider_claim_volume_flag': 0,
        'high_provider_payment_flag': 0,
        'long_stay_flag': 1 if total_utilization_days > 30 else 0,
    }
    return features

print(f"\nDeriving features for sample claims...")
# Test on first few claims
sample_claims = list(grouped.groups.keys())[:5]
for clm in sample_claims:
    claim_rows = raw[raw['clm_id'] == clm]
    feats = derive_features(claim_rows)
    print(f"  Claim {clm}: {len(claim_rows)} rows")
    print(f"    line_count={feats['claim_line_count']}, diag={feats['unique_diagnosis_code_count']}, proc={feats['unique_procedure_code_count']}")
    print(f"    charge={feats['total_claim_charge']}, pmt={feats['total_claim_payment']}")