"""Verify Inpatient feature derivation against scaler statistics and stored scores."""
import warnings
warnings.filterwarnings('ignore')

import joblib
import numpy as np
import pandas as pd
from pathlib import Path

BASE = Path("models/claims")

# Load artifacts
path = BASE / "inpatient"
feats = joblib.load(path / "feature_columns.pkl")
scaler = joblib.load(path / "scaler.pkl")
iso = joblib.load(path / "isolation_forest.pkl")

# Load raw data
raw = pd.read_csv("data/raw/inpatient_CLEANED_v2.csv", low_memory=False)
print(f"Raw data: {len(raw)} rows, {len(raw.columns)} cols")
print(f"Claims: {raw['clm_id'].nunique()}")

# Load stored scores
scores = pd.read_csv(path / "inpatient_final_risk_scores.csv", low_memory=False)
print(f"Scores: {len(scores)} rows")

# Derive features
def derive_inpatient_features(raw, claim_ids=None):
    """Derive all 49 inpatient features from raw data."""
    
    # Sort raw by clm_id
    raw = raw.sort_values('clm_id').reset_index(drop=True)
    
    # Group by claim
    claim_groups = raw.groupby('clm_id')
    
    features_list = []
    for clm_id, group in claim_groups:
        first = group.iloc[0]
        
        # Claim line count = rows per claim
        claim_line_count = len(group)
        
        # HCPCS codes from hcpcs_cd
        hcpcs_vals = group['hcpcs_cd'].dropna() if 'hcpcs_cd' in group.columns else pd.Series(dtype=str)
        hcpcs_vals = [str(v).strip() for v in hcpcs_vals if str(v).strip() and str(v).strip() != 'nan']
        unique_hcpcs = len(set(hcpcs_vals))
        
        # Diagnosis codes
        diag_cols = [f'icd_dgns_cd{i}' for i in range(1, 26)]
        diag_vals = []
        for col in diag_cols:
            if col in group.columns:
                vals = group[col].dropna()
                for v in vals:
                    s = str(v).strip()
                    if s and s != 'nan':
                        diag_vals.append(s)
        total_diag = len(diag_vals)
        unique_diag = len(set(diag_vals))
        
        # E-codes (external diagnosis)
        e_cols = [f'icd_dgns_e_cd{i}' for i in range(1, 13)]
        e_vals = []
        for col in e_cols:
            if col in group.columns:
                vals = group[col].dropna()
                for v in vals:
                    s = str(v).strip()
                    if s and s != 'nan':
                        e_vals.append(s)
        total_e = len(e_vals)
        unique_e = len(set(e_vals))
        
        # Procedure codes
        proc_cols = [f'icd_prcdr_cd{i}' for i in range(1, 26)]
        proc_vals = []
        for col in proc_cols:
            if col in group.columns:
                vals = group[col].dropna()
                for v in vals:
                    s = str(v).strip()
                    if s and s != 'nan':
                        proc_vals.append(s)
        total_proc = len(proc_vals)
        unique_proc = len(set(proc_vals))
        
        # Procedure dates
        pd_cols = [f'prcdr_dt{i}' for i in range(1, 26)]
        pd_vals = []
        for col in pd_cols:
            if col in group.columns:
                vals = group[col].dropna()
                for v in vals:
                    s = str(v).strip()
                    if s and s != 'nan':
                        pd_vals.append(s)
        unique_pd = len(set(pd_vals))
        
        # Procedure diversity
        proc_diversity = unique_proc / total_proc if total_proc > 0 else 0
        multiple_proc = 1 if unique_proc > 1 else 0
        
        # Financial
        total_charge = pd.to_numeric(first.get('clm_tot_chrg_amt', 0), errors='coerce')
        total_payment = pd.to_numeric(first.get('clm_pmt_amt', 0), errors='coerce')
        if pd.isna(total_charge): total_charge = 0
        if pd.isna(total_payment): total_payment = 0
        
        avg_charge = total_charge / claim_line_count if claim_line_count > 0 else 0
        avg_payment = total_payment / claim_line_count if claim_line_count > 0 else 0
        
        deductible = pd.to_numeric(first.get('nch_bene_ip_ddctbl_amt', 0), errors='coerce')
        coinsurance = pd.to_numeric(first.get('nch_bene_pta_coinsrnc_lblty_am', 0), errors='coerce')
        if pd.isna(deductible): deductible = 0
        if pd.isna(coinsurance): coinsurance = 0
        
        util_days = pd.to_numeric(first.get('clm_utlztn_day_cnt', 0), errors='coerce')
        if pd.isna(util_days): util_days = 0
        
        avg_daily_pmt = total_payment / util_days if util_days > 0 else 0
        
        # Dates
        clm_from = pd.to_datetime(first.get('clm_from_dt'), errors='coerce')
        clm_thru = pd.to_datetime(first.get('clm_thru_dt'), errors='coerce')
        clm_admsn = pd.to_datetime(first.get('clm_admsn_dt'), errors='coerce')
        dschrg = pd.to_datetime(first.get('nch_bene_dschrg_dt'), errors='coerce')
        
        if pd.notna(clm_from) and pd.notna(clm_thru):
            dur = (clm_thru - clm_from).days + 1
        else:
            dur = 1
        
        if pd.notna(clm_admsn) and pd.notna(clm_thru):
            admit_thru = (clm_thru - clm_admsn).days + 1
        else:
            admit_thru = 0
        
        same_day = 1 if (pd.notna(clm_admsn) and pd.notna(clm_thru) and clm_admsn.date() == clm_thru.date()) else 0
        
        admit_month = clm_admsn.month if pd.notna(clm_admsn) else 0
        admit_quarter = (admit_month - 1) // 3 + 1 if admit_month > 0 else 0
        admit_year = clm_admsn.year if pd.notna(clm_admsn) else 0
        
        bene_id = first.get('bene_id')
        prvdr = first.get('prvdr_num')
        
        # High flags (based on thresholds)
        high_line = 1 if claim_line_count > 3 else 0
        high_diag = 1 if unique_diag > 5 else 0
        high_proc = 1 if unique_proc > 3 else 0
        high_util = 1 if util_days > 7 else 0
        high_pmt = 1 if total_payment > 10000 else 0
        long_stay = 1 if util_days > 30 else 0
        
        features_list.append({
            'clm_id': clm_id,
            'bene_id': bene_id,
            'prvdr_num': prvdr,
            'claim_line_count': claim_line_count,
            'unique_hcpcs_count': unique_hcpcs,
            'unique_diagnosis_code_count': unique_diag,
            'total_diagnosis_code_count': total_diag,
            'unique_procedure_code_count': unique_proc,
            'total_procedure_code_count': total_proc,
            'unique_procedure_date_count': unique_pd,
            'procedure_code_diversity_ratio': proc_diversity,
            'multiple_procedures_flag': multiple_proc,
            'total_claim_charge': total_charge,
            'total_claim_payment': total_payment,
            'average_line_charge': avg_charge,
            'average_line_payment': avg_payment,
            'total_deductible_amount': deductible,
            'total_coinsurance_amount': coinsurance,
            'total_utilization_days': util_days,
            'average_daily_payment': avg_daily_pmt,
            'claim_duration_days': dur,
            'admit_to_thru_days': admit_thru,
            'is_same_day_stay': same_day,
            'admit_month': admit_month,
            'admit_quarter': admit_quarter,
            'admit_year': admit_year,
            'high_claim_line_count_flag': high_line,
            'high_diagnosis_count_flag': high_diag,
            'high_procedure_count_flag': high_proc,
            'high_utilization_flag': high_util,
            'high_claim_payment_flag': high_pmt,
            'long_stay_flag': long_stay,
        })
    
    return pd.DataFrame(features_list)

print("\nDeriving inpatient features...")
derived = derive_inpatient_features(raw)
print(f"Derived: {len(derived)} claims, {len(derived.columns)} cols")

# Check the features we derived match the scaler statistics
print("\nFeature statistics comparison (first-order):")
for i in range(min(23, len(feats))):
    feat = feats[i]
    if feat in derived.columns:
        actual_mean = derived[feat].mean()
        actual_std = derived[feat].std()
        sc_mean = scaler.mean_[i]
        sc_scale = scaler.scale_[i]
        match = abs(actual_mean - sc_mean) < 0.1 * abs(sc_mean) if sc_mean != 0 else actual_mean == 0
        print(f"  {feat}: derived_mean={actual_mean:.4f}, scaler_mean={sc_mean:.4f}, derived_std={actual_std:.4f}, scaler_scale={sc_scale:.4f} {'OK' if match else '*** MISMATCH ***'}")

# Merge with scores
merged = derived.merge(scores, on='clm_id', how='inner')
print(f"\nMerged with scores: {len(merged)}")

# Compute model outputs
feature_cols = [f for f in feats if f in merged.columns]
print(f"Features available for model: {len(feature_cols)}/{len(feats)}")

# Check which features are missing
missing_feats = [f for f in feats if f not in merged.columns]
print(f"Missing features: {missing_feats}")

if len(missing_feats) == 0:
    # Compute score_samples for all cases
    X = merged[feats].values.astype(float)
    X_scaled = scaler.transform(X)
    ss = iso.score_samples(X_scaled)
    
    stored_if = merged['isolation_forest_score'].values.astype(float)
    
    # Check correlation with min-max normalized inversion
    from scipy.stats import rankdata
    min_max_inv = (ss.max() - ss) / (ss.max() - ss.min())
    
    corr = np.corrcoef(min_max_inv, stored_if)[0, 1]
    print(f"\ncorr(min_max_inv(ss), stored IF) = {corr:.6f}")
    print(f"ss range: {ss.min():.6f} to {ss.max():.6f}")
    print(f"stored IF range: {stored_if.min():.6f} to {stored_if.max():.6f}")
    
    # Check exact match for a few
    for i in range(5):
        sample = merged.iloc[i]
        print(f"  idx={i}: clm_id={sample['clm_id']}, ss={ss[i]:.6f}, min_max_inv={min_max_inv[i]:.6f}, stored={stored_if[i]:.6f}, diff={abs(min_max_inv[i]-stored_if[i]):.8f}")
    
    # Also check rank-based
    rank_pct = rankdata(ss) / len(ss) * 100
    corr_rank = np.corrcoef(rank_pct / 100, stored_if / 100)[0, 1]
    print(f"\ncorr(rank_pct/100, stored IF/100) = {corr_rank:.6f}")
    
    # Check if stored is actually percentile rank
    diff_rank = np.abs(rank_pct - stored_if)
    print(f"rank_pct vs stored IF: max diff={diff_rank.max():.6f}, mean diff={diff_rank.mean():.6f}")
    
    # Check LOF
    lof = joblib.load(path / "lof.pkl")
    lof_scores = lof.score_samples(X_scaled)
    stored_lof = merged['lof_score'].values.astype(float)
    lof_rank = rankdata(lof_scores) / len(lof_scores) * 100
    diff_lof = np.abs(lof_rank - stored_lof)
    print(f"\nLOF: rank_pct vs stored: max diff={diff_lof.max():.6f}, mean diff={diff_lof.mean():.6f}")
    
    # Check OCSVM
    ocsvm = joblib.load(path / "ocsvm.pkl")
    ocsvm_scores = ocsvm.decision_function(X_scaled)
    stored_ocsvm = merged['one_class_svm_score'].values.astype(float)
    ocsvm_rank = rankdata(ocsvm_scores) / len(ocsvm_scores) * 100
    diff_ocsvm = np.abs(ocsvm_rank - stored_ocsvm)
    print(f"OCSVM: rank_pct vs stored: max diff={diff_ocsvm.max():.6f}, mean diff={diff_ocsvm.mean():.6f}")
    
    # Check ensemble
    # From model_consensus_count we know it's a 3-model ensemble
    stored_ensemble = merged['ensemble_risk_score'].values.astype(float)
    calc_ensemble = 0.2 * (rank_pct / 100) + 0.2 * (lof_rank / 100) + 0.6 * (ocsvm_rank / 100)
    ensemble_corr = np.corrcoef(calc_ensemble, stored_ensemble / 100)[0, 1]
    print(f"\nEnsemble: corr(calc, stored/100) = {ensemble_corr:.6f}")
    print(f"  calc range: {calc_ensemble.min():.6f} to {calc_ensemble.max():.6f}")
    print(f"  stored/100 range: {(stored_ensemble/100).min():.6f} to {(stored_ensemble/100).max():.6f}")