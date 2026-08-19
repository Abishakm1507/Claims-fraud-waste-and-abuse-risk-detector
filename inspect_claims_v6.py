"""Check carrier feature data coverage and inpatient feature derivability."""
import pandas as pd
import os

# 1. Check carrier features file coverage
carrier_path = "data/raw/carrier_claim_features_FINAL.csv"
df = pd.read_csv(carrier_path, low_memory=False)
print(f"carrier_claim_features_FINAL.csv: {len(df)} rows, {len(df.columns)} cols")
print(f"  Columns: {list(df.columns)}")
print(f"\n  CLM_ID dtype: {df['CLM_ID'].dtype}")
print(f"  First 3 CLM_IDs: {df['CLM_ID'].iloc[:3].tolist()}")

# Compare with carrier claims in unified file
unified = pd.read_csv("models/claims/unified_claim_risk_with_provider.csv", low_memory=False)
carrier_unified = unified[unified['CLAIM_TYPE'] == 'CARRIER']
print(f"\n  Carrier unified rows: {len(carrier_unified)}")
print(f"  Carrier unified CLM_IDs sample: {carrier_unified['CLM_ID'].iloc[:3].tolist()}")

# Check overlap
carrier_feats_ids = set(df['CLM_ID'].astype(str).str.strip())
carrier_unified_ids = set(carrier_unified['CLM_ID'].astype(str).str.strip())
overlap = carrier_feats_ids & carrier_unified_ids
print(f"\n  Carrier features file IDs: {len(carrier_feats_ids)}")
print(f"  Carrier unified IDs: {len(carrier_unified_ids)}")
print(f"  Overlap: {len(overlap)}")
print(f"  In features not in unified: {len(carrier_feats_ids - carrier_unified_ids)}")
print(f"  In unified not in features: {len(carrier_unified_ids - carrier_feats_ids)}")

# Check for NaN in carrier features
feature_cols = [
    'num_lines_per_claim', 'min_line_num', 'max_line_num', 'mean_line_num',
    'CLM_PMT_AMT_first', 'CARR_CLM_PRMRY_PYR_PD_AMT_first',
    'NCH_CLM_PRVDR_PMT_AMT_first', 'NCH_CLM_BENE_PMT_AMT_first',
    'NCH_CARR_CLM_SBMTD_CHRG_AMT_first', 'NCH_CARR_CLM_ALOWD_AMT_first',
    'CARR_CLM_CASH_DDCTBL_APLD_AMT_first', 'LINE_NCH_PMT_AMT_sum',
    'LINE_NCH_PMT_AMT_mean', 'LINE_NCH_PMT_AMT_median',
    'LINE_NCH_PMT_AMT_max', 'LINE_NCH_PMT_AMT_std',
    'LINE_BENE_PMT_AMT_sum', 'LINE_PRVDR_PMT_AMT_sum',
    'LINE_BENE_PTB_DDCTBL_AMT_sum', 'LINE_BENE_PRMRY_PYR_PD_AMT_sum',
    'LINE_COINSRNC_AMT_sum', 'LINE_SBMTD_CHRG_AMT_sum',
    'LINE_ALOWD_CHRG_AMT_sum', 'HCPCS_CD_nunique',
    'claim_duration_days', 'num_unique_diagnosis_codes',
    'num_zero_payment_lines', 'claim_year', 'claim_month',
    'line_expense_duration_days', 'avg_payment_per_line',
    'avg_submitted_charge_per_line', 'payment_to_submitted_charge_ratio',
    'allowed_to_submitted_charge_ratio', 'provider_payment_to_allowed_ratio',
    'bene_total_claims_in_dataset', 'PRTCPTNG_IND_CD_first', 'HPSA_SCRCTY_IND_CD_first'
]
print(f"\n  Feature count expected: {len(feature_cols)}")

missing_cols = [c for c in feature_cols if c not in df.columns]
print(f"  Missing feature columns: {missing_cols}")

if len(missing_cols) == 0:
    nan_counts = df[feature_cols].isna().sum()
    non_finite = nan_counts[nan_counts > 0]
    if len(non_finite) > 0:
        print(f"\n  Columns with NaN:")
        for col, count in non_finite.items():
            print(f"    {col}: {count} NaN")
    else:
        print(f"\n  All {len(feature_cols)} features have no NaN values!")
    
    print(f"\n  Sample first row values:")
    row = df.iloc[0]
    for col in feature_cols[:10]:
        print(f"    {col}: {row[col]}")

# 2. Check if inpatient features are derivable from raw file
inp_path = "data/raw/inpatient_CLEANED_v2.csv"
inp = pd.read_csv(inp_path, low_memory=False, nrows=1000)
print(f"\n\ninpatient_CLEANED_v2.csv sample: {len(inp)} rows (of maybe 20k+)")
print(f"  Full count: ", end="")
full_inp = pd.read_csv(inp_path, low_memory=False, usecols=['clm_id'])
print(len(full_inp))
print(f"  clm_id sample: {full_inp['clm_id'].iloc[:3].tolist()}")

# Check if inpatient scores CSV has matching IDs
inp_scores = pd.read_csv("models/claims/inpatient/inpatient_final_risk_scores.csv", low_memory=False)
inp_score_ids = set(inp_scores['clm_id'].astype(str).str.strip())
inp_raw_ids = set(full_inp['clm_id'].astype(str).str.strip())
overlap_inp = inp_score_ids & inp_raw_ids
print(f"  Inpatient score CSV IDs: {len(inp_score_ids)}")
print(f"  Inpatient raw IDs: {len(inp_raw_ids)}")
print(f"  Overlap: {len(overlap_inp)}")