"""
Deep investigation: Search for carrier/inpatient feature engineering scripts and raw feature matrices.
"""
import warnings
warnings.filterwarnings('ignore')

import pandas as pd
import numpy as np
import joblib
import os
from pathlib import Path

BASE = Path("models/claims")

print("=" * 70)
print("INVESTIGATION: CARRIER/INPATIENT FEATURE SOURCES")
print("=" * 70)

# 1. Check curated fact_claim parquet
print("\n--- fact_claim.parquet ---")
try:
    fc = pd.read_parquet("data/curated/fact_claim.parquet")
    print(f"Rows: {len(fc)}, Cols: {len(fc.columns)}")
    print(f"Columns: {list(fc.columns)}")
    print(f"\nClaim type counts:")
    if 'claim_type' in fc.columns:
        print(fc['claim_type'].value_counts())
except Exception as e:
    print(f"ERROR: {e}")

# 2. Check everything in the claims base directory
print("\n--- All files in models/claims (recursive) ---")
for root, dirs, files in os.walk("models/claims"):
    for f in sorted(files):
        path = os.path.join(root, f)
        size = os.path.getsize(path)
        print(f"  {path} ({size:,} bytes)")

# 3. Search for any feature-related files
print("\n--- Feature-related files anywhere ---")
for root, dirs, files in os.walk("."):
    for f in sorted(files):
        fl = f.lower()
        if ('feature' in fl or 'train' in fl or 'score' in fl or 'risk' in fl) and f.endswith(('.csv', '.pkl', '.joblib', '.parquet')):
            path = os.path.join(root, f)
            size = os.path.getsize(path)
            print(f"  {path} ({size:,} bytes)")

# 4. Check if inpatient raw data can be loaded from fact_claim or other sources
print("\n--- Check claims_master.parquet ---")
try:
    master = pd.read_parquet(BASE / "claims_master.parquet")
    print(f"Rows: {len(master)}, Cols: {len(master.columns)}")
    print(f"Columns: {list(master.columns)}")
    print(f"\nClaim type counts:")
    if 'claim_type' in master.columns:
        print(master['claim_type'].value_counts())
except Exception as e:
    print(f"ERROR: {e}")

# 5. Find where the carrier/inpatient feature engineering happened
print("\n--- Search for carrier/inpatient feature engineering scripts ---")
import subprocess
result = subprocess.run(
    ['findstr', '/s', '/i', '/n', 'num_lines_per_claim', '*.py', '*.md', '*.txt', '*.json'],
    capture_output=True, text=True, shell=True
)
if result.stdout:
    print(result.stdout[:5000])
else:
    print("  No matches found")

print("\n--- Search for unique_hcpcs_count ---")
result = subprocess.run(
    ['findstr', '/s', '/i', '/n', 'unique_hcpcs_count', '*.py', '*.md', '*.txt', '*.json'],
    capture_output=True, text=True, shell=True
)
if result.stdout:
    print(result.stdout[:3000])
else:
    print("  No matches found")

# 6. Check if the README references match real files
print("\n--- Check README claims references ---")
unified = pd.read_csv(BASE / "unified_claim_risk_with_provider.csv", low_memory=False)
final = pd.read_csv(BASE / "final_unified_claim_risk.csv", low_memory=False)
print(f"unified: {len(unified)} rows")
print(f"final: {len(final)} rows")

# Check final_unified_claim_risk columns
print(f"\nfinal_unified_claim_risk columns:")
for c in final.columns:
    print(f"  {c}")

# 7. Check if the final risk file has features
carrier_final = final[final['CLAIM_TYPE'] == 'CARRIER']
print(f"\nCarrier in final: {len(carrier_final)} rows")
print(f"Carrier final columns: {list(carrier_final.columns)}")

# 8. Try to understand what IF_score represents in unified vs. what the outpatient model produces
print("\n--- Score normalization comparison across claim types ---")

# For each claim type, check if stored scores could be min-max of something
for ct, score_col in [("CARRIER", "IF_score"), ("INPATIENT", "isolation_forest_score"), ("OUTPATIENT", "IF_score")]:
    subset = unified[unified['CLAIM_TYPE'] == ct]
    print(f"\n{ct}: {score_col}")
    print(f"  Min: {subset[score_col].min():.6f}")
    print(f"  Max: {subset[score_col].max():.6f}")
    print(f"  Mean: {subset[score_col].mean():.6f}")
    print(f"  Std: {subset[score_col].std():.6f}")

# 9. Check if raw carrier data exists somewhere for feature reconstruction
print("\n--- Raw carrier data search ---")
for root, dirs, files in os.walk("data"):
    for f in sorted(files):
        fl = f.lower()
        if 'carrier' in fl and f.endswith(('.csv', '.parquet')):
            path = os.path.join(root, f)
            size = os.path.getsize(path)
            print(f"  {path} ({size:,} bytes)")

# 10. Check the unified data for carrier - are the CLM_PMT_AMT values the same as in carrier features file?
# This would confirm the claims are the same but on different feature sets
print("\n--- Verify carrier data consistency ---")
# We know: feature file CLM_ID == unified CLAIM_ID (not unified CLM_ID)
# Check CLM_PMT_AMT values match
carrier_feat = pd.read_csv("data/raw/carrier_claim_features_FINAL.csv", low_memory=False)
merged_check = unified[unified['CLAIM_TYPE'] == 'CARRIER'].merge(
    carrier_feat[['CLM_ID', 'CLM_PMT_AMT_first', 'NCH_CARR_CLM_SBMTD_CHRG_AMT_first']],
    left_on='CLAIM_ID',
    right_on='CLM_ID',
    how='inner',
    suffixes=('_unified', '_feat')
)
print(f"  Matched: {len(merged_check)}")
if len(merged_check) > 0:
    # Compare payment amounts
    for col in ['CLM_PMT_AMT_first', 'NCH_CARR_CLM_SBMTD_CHRG_AMT_first']:
        u_col = f"{col}_unified"
        f_col = f"{col}_feat"
        uni_vals = pd.to_numeric(merged_check[u_col], errors='coerce')
        feat_vals = pd.to_numeric(merged_check[f_col], errors='coerce')
        match = np.isclose(uni_vals, feat_vals, rtol=1e-6, atol=1e-6, equal_nan=True)
        print(f"  {col}: {match.sum()}/{len(match)} match")

# 11. Try to understand WHERE the IF_score values came from
# Test: check if IF_score in unified correlates with exp(-score_samples) or similar
print("\n--- Check if IF_score can be derived from raw feature values ---")

# For carrier, try computing percentiles of the raw features
carrier_feat = pd.read_csv("data/raw/carrier_claim_features_FINAL.csv", low_memory=False)
car_feats = joblib.load(BASE / "carrier" / "scaler.pkl").feature_names_in_

# Clean
for col in car_feats:
    carrier_feat[col] = pd.to_numeric(carrier_feat[col], errors='coerce').fillna(0)

# Compare first few values with the unified file
carrier_unified = unified[unified['CLAIM_TYPE'] == 'CARRIER'].copy()
carrier_unified['CLAIM_ID_str'] = carrier_unified['CLAIM_ID'].astype(str).str.strip()
print(f"\n  First carrier claim in unified: {carrier_unified.iloc[0]['CLAIM_ID']}")
print(f"  First carrier feature claim: {carrier_feat.iloc[0]['CLM_ID']}")
print(f"  First carrier feature CLM_PMT_AMT: {carrier_feat.iloc[0]['CLM_PMT_AMT_first']}")
print(f"  First carrier unified CLM_PMT_AMT: {carrier_unified.iloc[0]['CLM_PMT_AMT_first']}")

# Check: is the unified CLM_ID a DIFFERENT set of claims than the feature file?
carrier_feat_ids = set(carrier_feat['CLM_ID'].astype(str).str.strip())
carrier_unified_ids = set(carrier_unified['CLAIM_ID'].astype(str).str.strip())
print(f"\n  Carrier feature IDs count: {len(carrier_feat_ids)}")
print(f"  Carrier unified CID count: {len(carrier_unified_ids)}")
print(f"  Overlap: {len(carrier_feat_ids & carrier_unified_ids)}")

# The unified CLM_ID column was float and doesn't match - but CLAIM_ID does
# Let me understand this: is CLAIM_ID == original CLM_ID or transformed?
unified_clm_ids = set(carrier_unified['CLM_ID'].astype(str).str.strip())
print(f"  Unified CLM_ID count: {len(unified_clm_ids)}")
print(f"  Overlap with feature CLM_ID: {len(carrier_feat_ids & unified_clm_ids)}")
print(f"  Sample feature CLM_ID: {carrier_feat['CLM_ID'].iloc[0]}")
print(f"  Sample unified CLAIM_ID: {carrier_unified['CLAIM_ID'].iloc[0]}")
print(f"  Sample unified CLM_ID: {carrier_unified['CLM_ID'].iloc[0]}")