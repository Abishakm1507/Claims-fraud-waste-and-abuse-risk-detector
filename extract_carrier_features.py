"""
Extract Carrier feature columns from unified claim file.
"""
import pandas as pd
from pathlib import Path

unified_path = Path("models/claims/unified_claim_risk_with_provider.csv")

if unified_path.exists():
    # Read a few Carrier claims to identify feature columns
    df = pd.read_csv(unified_path, low_memory=False)
    carrier_df = df[df['CLAIM_TYPE'] == 'CARRIER']
    
    print(f"Total Carrier claims: {len(carrier_df)}")
    print(f"Total columns in unified file: {len(df.columns)}")
    
    # All columns that are numeric and not in the output/model score columns
    exclude_cols = {
        # Identifiers
        'CLM_ID', 'CARR_CLM_BLG_NPI_NUM_first', 'CLAIM_ID', 'PROVIDER_ID', 
        'provider_id', 'clm_id',
        # Financial columns (can vary by claim type)
        'CLM_PMT_AMT_first', 'NCH_CARR_CLM_SBMTD_CHRG_AMT_first', 
        'NCH_CARR_CLM_ALOWD_AMT_first',
        # Output/score columns
        'IF_score', 'LOF_score', 'OCSVM_score', 
        'carrier_ensemble_score', 'carrier_risk_rank', 'carrier_risk_band',
        'CLAIM_RISK_SCORE', 'MODEL_SCORE',
        'isolation_forest_score', 'lof_score', 'one_class_svm_score',
        'ensemble_risk_score', 'isolation_forest_flag', 'lof_flag', 
        'one_class_svm_flag', 'model_consensus_count', 'model_consensus',
        'risk_percentile', 'risk_rank', 'risk_band',
        'outpatient_ensemble_score', 'outpatient_risk_rank', 'outpatient_risk_band',
        'CLAIM_TYPE', 'CLAIM_RISK_RANK',
        # Temporal
        'claim_year', 'claim_month', 'claim_quarter', 'claim_day_of_week',
    }
    
    # Extract potential features
    carrier_sample = carrier_df.iloc[0]
    feature_cols = []
    
    for col in df.columns:
        if col not in exclude_cols:
            try:
                val = carrier_sample[col]
                if pd.notna(val):
                    # Check if it's numeric
                    float(val)
                    feature_cols.append(col)
            except (ValueError, TypeError, KeyError):
                pass
    
    print(f"\nExtracted {len(feature_cols)} features:")
    for i, col in enumerate(sorted(feature_cols), 1):
        print(f"  {i}. {col}")
    
    # Verify we have 38 features for Carrier
    if len(feature_cols) >= 38:
        print(f"\n[GOOD] Found >= 38 features")
        feature_cols_sorted = sorted(feature_cols)
        print(f"\nFirst 10: {feature_cols_sorted[:10]}")
        print(f"Last 10: {feature_cols_sorted[-10:]}")
    else:
        print(f"\n[WARNING] Only found {len(feature_cols)} features, need 38")
else:
    print(f"File not found: {unified_path}")
