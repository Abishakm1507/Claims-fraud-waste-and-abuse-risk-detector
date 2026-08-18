"""Check ID matching between carrier features file and unified claim risk."""
import pandas as pd

# Load carrier features
feats = pd.read_csv("data/raw/carrier_claim_features_FINAL.csv", low_memory=False)
print(f"Features file: {len(feats)} rows")
print(f"  CLM_ID dtype: {feats['CLM_ID'].dtype}")
print(f"  CLM_ID range: {feats['CLM_ID'].min()} to {feats['CLM_ID'].max()}")
print(f"  First 5: {feats['CLM_ID'].iloc[:5].tolist()}")
print(f"  Last 5: {feats['CLM_ID'].iloc[-5:].tolist()}")

# Load unified
unified = pd.read_csv("models/claims/unified_claim_risk_with_provider.csv", low_memory=False)
carrier = unified[unified['CLAIM_TYPE'] == 'CARRIER'].copy()
print(f"\nCarrier in unified: {len(carrier)} rows")
print(f"  CLM_ID dtype: {carrier['CLM_ID'].dtype}")
print(f"  CLAIM_ID dtype: {carrier['CLAIM_ID'].dtype}")
print(f"  CLM_ID first 5: {carrier['CLM_ID'].iloc[:5].tolist()}")
print(f"  CLAIM_ID first 5: {carrier['CLAIM_ID'].iloc[:5].tolist()}")

# Compare using CLAIM_ID from unified
feat_ids = set(feats['CLM_ID'].astype(str).str.strip())
unified_ids = set(carrier['CLAIM_ID'].astype(str).str.strip())
overlap = feat_ids & unified_ids
print(f"\n  Features IDs: {len(feat_ids)}")
print(f"  Unified CLAIM_ID: {len(unified_ids)}")
print(f"  Overlap: {len(overlap)}")

# Also check CLM_ID from unified (as string)
unified_clm = set(carrier['CLM_ID'].astype(str).str.strip())
overlap_clm = feat_ids & unified_clm
print(f"  Unified CLM_ID: {len(unified_clm)}")
print(f"  Overlap with CLM_ID: {len(overlap_clm)}")

# Print some example IDs from each
print(f"\n  Sample feature file IDs: {feats['CLM_ID'].iloc[:3].tolist()}")
print(f"  Sample unified CLAIM_ID: {carrier['CLAIM_ID'].iloc[:3].tolist()}")
print(f"  Sample unified CLM_ID: {carrier['CLM_ID'].iloc[:3].tolist()}")

# Check whether unified values look like float-rounded versions
print(f"\n  Check - could CLM_ID floats round to something?")
for i in range(3):
    fv = feats['CLM_ID'].iloc[i]
    uv = carrier['CLAIM_ID'].iloc[i]
    print(f"    feat={fv}, unified_claim_id={uv}, equal={str(fv) == str(uv)}")

# Also check the final_unified_claim_risk.csv if it exists  
try:
    fin = pd.read_csv("models/claims/final_unified_claim_risk.csv", low_memory=False, nrows=5)
    print(f"\n  final_unified_claim_risk columns: {list(fin.columns)}")
except Exception as e:
    print(f"\n  final_unified_claim_risk error: {e}")

# Check if there are any carrier-specific score files elsewhere
import os
for root, dirs, files in os.walk("."):
    for f in files:
        if "carrier" in f.lower() and f.endswith(".csv"):
            path = os.path.join(root, f)
            print(f"\n  Found carrier csv: {path}")