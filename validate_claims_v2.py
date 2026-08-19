"""
Deep validation: understand score normalization and fix carrier data issues.
"""
import warnings
warnings.filterwarnings('ignore')

import joblib
import numpy as np
import pandas as pd
import shap
from pathlib import Path
from scipy.stats import rankdata

BASE = Path("models/claims")


def load_artifacts(claim_type: str):
    """Load all artifacts for a claim type."""
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


def clean_carrier_features(df, feature_names):
    """Clean carrier feature data - handle spaces, NaN, etc."""
    df_clean = df.copy()
    for col in feature_names:
        # Convert values to numeric, treating empty strings/spaces as NaN
        vals = pd.to_numeric(df_clean[col], errors='coerce')
        # What does the original pipeline do with NaN? Fill with 0
        df_clean[col] = vals.fillna(0)
    return df_clean


def analyze_score_relationship(claim_type, df, feature_names, scaler, iso, score_col, id_col):
    """Analyze relationship between stored scores and model outputs."""
    print(f"\n--- {claim_type} score analysis ---")
    
    # Compute score_samples for all claims
    all_features = df[feature_names].values.astype(float)
    all_scaled = scaler.transform(all_features)
    all_score_samples = iso.score_samples(all_scaled)
    all_decision = iso.decision_function(all_scaled)
    
    stored = df[score_col].values.astype(float)
    
    print(f"  score_samples: min={all_score_samples.min():.6f}, max={all_score_samples.max():.6f}")
    print(f"  decision_function: min={all_decision.min():.6f}, max={all_decision.max():.6f}")
    print(f"  stored {score_col}: min={stored.min():.6f}, max={stored.max():.6f}")
    
    # Check if stored score is rank-based
    rank_pct = rankdata(all_score_samples) / len(all_score_samples) * 100
    rank_pct_norm = rank_pct / 100
    
    # Check if stored is rank of decision
    rank_decision = rankdata(all_decision) / len(all_decision) * 100
    rank_decision_norm = rank_decision / 100
    
    # Check direct correlation
    corr_ss = np.corrcoef(all_score_samples, stored)[0, 1]
    corr_rank = np.corrcoef(rank_pct_norm, stored)[0, 1]
    corr_decision = np.corrcoef(all_decision, stored)[0, 1]
    corr_rank_dec = np.corrcoef(rank_decision_norm, stored)[0, 1]
    
    print(f"  corr(score_samples, stored) = {corr_ss:.6f}")
    print(f"  corr(rank(score_samples), stored) = {corr_rank:.6f}")
    print(f"  corr(decision_function, stored) = {corr_decision:.6f}")
    print(f"  corr(rank(decision), stored) = {corr_rank_dec:.6f}")
    
    # Check min-max
    min_max_ss = (all_score_samples - all_score_samples.min()) / (all_score_samples.max() - all_score_samples.min())
    min_max_dec = (all_decision - all_decision.min()) / (all_decision.max() - all_decision.min())
    
    corr_mm_ss = np.corrcoef(min_max_ss, stored)[0, 1]
    corr_mm_dec = np.corrcoef(min_max_dec, stored)[0, 1]
    
    print(f"  corr(minmax(score_samples), stored) = {corr_mm_ss:.6f}")
    print(f"  corr(minmax(decision), stored) = {corr_mm_dec:.6f}")
    
    # Sample rows to inspect
    sample_idx = [0, len(df)//4, len(df)//2, 3*len(df)//4, len(df)-1]
    print(f"\n  Sample rows:")
    for idx in sample_idx:
        print(f"    idx={idx}, score_samples={all_score_samples[idx]:.6f}, decision={all_decision[idx]:.6f}, stored={stored[idx]:.6f}")
    
    return {
        'corr_ss': corr_ss,
        'corr_rank': corr_rank,
        'corr_decision': corr_decision,
        'corr_rank_dec': corr_rank_dec,
        'corr_mm_ss': corr_mm_ss,
        'corr_mm_dec': corr_mm_dec,
    }


# ============ OUTPATIENT ============
print("=" * 70)
print("OUTPATIENT SCORE ANALYSIS")
print("=" * 70)

artifacts = load_artifacts("OUTPATIENT")
out_feats = artifacts['feature_names']
out_scaler = artifacts['scaler']
out_iso = artifacts['isolation_forest']

out_df = pd.read_csv(BASE / "outpatient" / "outpatient_final_risk_scores.csv", low_memory=False)
print(f"Claims: {len(out_df)}")

# Analyze score relationship
analyze_score_relationship(
    "OUTPATIENT",
    out_df[out_feats + ['IF_score', 'outpatient_ensemble_score']],
    out_feats,
    out_scaler,
    out_iso,
    'IF_score',
    'CLM_ID'
)

# ============ CARRIER ============
print("\n" + "=" * 70)
print("CARRIER SCORE ANALYSIS")
print("=" * 70)

artifacts = load_artifacts("CARRIER")
car_feats = artifacts['feature_names']
car_scaler = artifacts['scaler']
car_iso = artifacts['isolation_forest']

car_df = pd.read_csv("data/raw/carrier_claim_features_FINAL.csv", low_memory=False)
print(f"Claims: {len(car_df)}")

# Clean carrier data
car_clean = clean_carrier_features(car_df[car_feats], car_feats)

# Load unified for stored scores
unified = pd.read_csv(BASE / "unified_claim_risk_with_provider.csv", low_memory=False)
car_unified = unified[unified['CLAIM_TYPE'] == 'CARRIER'].copy()
car_unified['CLAIM_ID_str'] = car_unified['CLAIM_ID'].astype(str).str.strip()
car_df['CLAIM_ID_str'] = car_df['CLM_ID'].astype(str).str.strip()

merged = car_clean.copy()
merged['CLAIM_ID_str'] = car_df['CLAIM_ID_str'].values
merged['IF_score'] = merged['CLAIM_ID_str'].map(
    car_unified.set_index('CLAIM_ID_str')['IF_score']
)
merged['carrier_ensemble_score'] = merged['CLAIM_ID_str'].map(
    car_unified.set_index('CLAIM_ID_str')['carrier_ensemble_score']
)

# Drop claims with no stored score
valid = merged.dropna(subset=['IF_score'])
print(f"Matched with scores: {len(valid)}")

# Analyze
analyze_score_relationship(
    "CARRIER",
    valid[car_feats + ['IF_score', 'carrier_ensemble_score']],
    car_feats,
    car_scaler,
    car_iso,
    'IF_score',
    'CLAIM_ID_str'
)

# Check LOF and OCSVM scores
print(f"\n  LOF/OCSVM check:")
lof = artifacts['lof']
ocsvm = artifacts['ocsvm']

all_scaled = car_scaler.transform(valid[car_feats].values.astype(float))
lof_scores = lof.score_samples(all_scaled)
ocsvm_scores = ocsvm.decision_function(all_scaled)

stored_lof = valid['IF_score'].values.astype(float)  # placeholder - need actual LOF stored
# Actually check stored LOF from unified
stored_lof_actual = valid['CLAIM_ID_str'].map(
    car_unified.set_index('CLAIM_ID_str')['LOF_score']
).values.astype(float)
stored_ocsvm_actual = valid['CLAIM_ID_str'].map(
    car_unified.set_index('CLAIM_ID_str')['OCSVM_score']
).values.astype(float)

# Check LOF normalization
rank_lof = rankdata(lof_scores) / len(lof_scores)
corr_lof = np.corrcoef(rank_lof, stored_lof_actual)[0, 1]
print(f"  corr(rank(lof_score_samples), stored_LOF_score) = {corr_lof:.6f}")
print(f"  LOF score_samples range: {lof_scores.min():.6f} to {lof_scores.max():.6f}")
print(f"  Stored LOF range: {stored_lof_actual.min():.6f} to {stored_lof_actual.max():.6f}")

rank_ocsvm = rankdata(ocsvm_scores) / len(ocsvm_scores)
corr_ocsvm = np.corrcoef(rank_ocsvm, stored_ocsvm_actual)[0, 1]
print(f"  corr(rank(ocsvm_decision), stored_OCSVM_score) = {corr_ocsvm:.6f}")
print(f"  OCSVM decision range: {ocsvm_scores.min():.6f} to {ocsvm_scores.max():.6f}")
print(f"  Stored OCSVM range: {stored_ocsvm_actual.min():.6f} to {stored_ocsvm_actual.max():.6f}")

# Check ensemble calculation
print(f"\n  Ensemble check:")
if_score_norm = rank_lof  # using rank of IF as normalized
lof_score_norm = rank_lof
ocsvm_score_norm = rank_ocsvm

# Check if ensemble is a weighted average of individual scores
# From model_config: IF=0.2, LOF=0.2, OCSVM=0.6
ensemble_calc = 0.2 * rank_lof + 0.2 * rank_lof + 0.6 * rank_ocsvm
stored_ensemble = valid['carrier_ensemble_score'].values.astype(float)
corr_ensemble = np.corrcoef(ensemble_calc, stored_ensemble)[0, 1]
print(f"  corr(calc_ensemble, stored_ensemble) = {corr_ensemble:.6f}")

# Check if carrier_ensemble is in 0-1 or 0-100 scale
print(f"  Stored ensemble range: {stored_ensemble.min():.6f} to {stored_ensemble.max():.6f}")

# ============ INPATIENT FEATURES ============
print("\n" + "=" * 70)
print("INPATIENT FEATURE DERIVATION ANALYSIS")
print("=" * 70)

artifacts = load_artifacts("INPATIENT")
inp_feats = artifacts['feature_names']
inp_scaler = artifacts['scaler']
inp_iso = artifacts['isolation_forest']

print(f"Feature count: {len(inp_feats)}")

# Check if we can derive features from raw data
raw = pd.read_csv("data/raw/inpatient_CLEANED_v2.csv", low_memory=False)
print(f"Raw rows: {len(raw)}")

# Check what raw columns map to features
# Let's look at the feature definitions more carefully
print(f"\nFeatures and what they likely map to:")
feature_mappings = {
    'claim_line_count': 'Number of claim lines',
    'unique_hcpcs_count': 'unique HCPCS codes',
    'unique_diagnosis_code_count': 'unique diagnosis codes',
    'total_diagnosis_code_count': 'total diagnosis codes',
    'unique_procedure_code_count': 'unique procedure codes',
    'total_procedure_code_count': 'total procedure codes',
    'unique_procedure_date_count': 'unique procedure dates',
    'procedure_code_diversity_ratio': 'unique/total procedure ratio',
    'multiple_procedures_flag': 'flag if >1 procedure',
    'total_claim_charge': 'clm_tot_chrg_amt',
    'total_claim_payment': 'clm_pmt_amt',
    'average_line_charge': 'avg line charge',
    'average_line_payment': 'avg line payment',
    'total_deductible_amount': 'nch_bene_ip_ddctbl_amt',
    'total_coinsurance_amount': 'nch_bene_pta_coinsrnc_lblty_am',
    'total_utilization_days': 'clm_utlztn_day_cnt',
    'average_daily_payment': 'avg daily payment',
    'claim_duration_days': 'days from claim_from to claim_thru',
    'admit_to_thru_days': 'days from admit to thru', 
    'is_same_day_stay': 'flag if same day',
    'admit_month': 'month of admission',
    'admit_quarter': 'quarter of admission',
    'admit_year': 'year of admission',
    'bene_total_claims': 'total claims for beneficiary',
    'bene_unique_claims': 'unique claims for beneficiary',
    'bene_avg_line_count': 'avg line count per claim for beneficiary',
    'bene_avg_claim_duration': 'avg claim duration for beneficiary',
    'bene_total_payment': 'total payment for beneficiary',
    'bene_avg_payment': 'avg payment for beneficiary',
    'bene_days_since_first_claim': 'days since first claim',
    'bene_recent_claims_count': 'recent claims for beneficiary',
    'provider_total_claims': 'total claims for provider',
    'provider_unique_beneficiaries': 'unique beneficiaries for provider',
    'provider_total_payment': 'total payment for provider',
    'provider_avg_payment': 'avg payment for provider',
    'provider_total_charge': 'total charge for provider',
    'provider_avg_charge': 'avg charge for provider',
    'provider_avg_utilization_days': 'avg utilization for provider',
    'provider_total_utilization_days': 'total utilization for provider',
    'provider_payment_per_beneficiary': 'payment per beneficiary for provider',
    'provider_claims_per_beneficiary': 'claims per beneficiary',
    'high_claim_line_count_flag': 'flag',
    'high_diagnosis_count_flag': 'flag',
    'high_procedure_count_flag': 'flag',
    'high_utilization_flag': 'flag',
    'high_claim_payment_flag': 'flag',
    'high_provider_claim_volume_flag': 'flag',
    'high_provider_payment_flag': 'flag',
    'long_stay_flag': 'flag',
}

# Check if the 49 features can be derived
raw_cols = set(raw.columns)
print(f"\nRaw columns relevant to features:")
for feat in inp_feats:
    mapped = feature_mappings.get(feat, '')
    print(f"  {feat} -> {mapped}")

# Show raw row for a specific claim
clm_id = raw['clm_id'].iloc[0]
claim_data = raw[raw['clm_id'] == clm_id]
print(f"\nSample claim {clm_id}: {len(claim_data)} rows")
print(f"  clm_from_dt: {claim_data['clm_from_dt'].tolist()}")
print(f"  clm_thru_dt: {claim_data['clm_thru_dt'].tolist()}")
print(f"  clm_admsn_dt: {claim_data.get('clm_admsn_dt', 'N/A').tolist() if 'clm_admsn_dt' in claim_data.columns else 'N/A'}")
print(f"  clm_pmt_amt: {claim_data['clm_pmt_amt'].tolist()}")
print(f"  clm_tot_chrg_amt: {claim_data['clm_tot_chrg_amt'].tolist() if 'clm_tot_chrg_amt' in claim_data.columns else 'N/A'}")
print(f"  clm_utlztn_day_cnt: {claim_data.get('clm_utlztn_day_cnt', 'N/A').tolist() if 'clm_utlztn_day_cnt' in claim_data.columns else 'N/A'}")