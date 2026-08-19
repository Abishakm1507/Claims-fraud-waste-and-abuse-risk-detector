"""Inspect which features are actually available for each claim type."""
import pandas as pd
import numpy as np
import joblib
import os

base = "models/claims"

# Load unified file
unified = pd.read_csv(os.path.join(base, "unified_claim_risk_with_provider.csv"), low_memory=False)
print("Unified file loaded")

# Check what columns exist for each type
for claim_type in ["CARRIER", "INPATIENT", "OUTPATIENT"]:
    subset = unified[unified['CLAIM_TYPE'] == claim_type]
    print(f"\n{'='*60}")
    print(f"{claim_type}: {len(subset)} claims")
    print(f"{'='*60}")
    
    # Check if all feature columns are present
    if claim_type == "CARRIER":
        # Load features from scaler's feature_names_in_
        scaler = joblib.load(os.path.join(base, "carrier", "scaler.pkl"))
        feature_cols = list(scaler.feature_names_in_)
    elif claim_type == "INPATIENT":
        feature_cols = joblib.load(os.path.join(base, "inpatient", "feature_columns.pkl"))
    else:
        feature_cols = joblib.load(os.path.join(base, "outpatient", "feature_columns.pkl"))
    
    print(f"  Expected {len(feature_cols)} features")
    
    # Check which features are in the unified file columns
    unified_cols = set(unified.columns)
    present = [c for c in feature_cols if c in unified_cols]
    missing = [c for c in feature_cols if c not in unified_cols]
    
    print(f"  Present in unified: {len(present)}")
    print(f"  Missing from unified: {len(missing)}")
    if missing:
        print(f"  Missing features: {missing[:10]}")
    
    # Check if data rows contain valid values for present features
    if present:
        sample = subset[present].head(2)
        print(f"\n  Sample values (first 2 rows, first 5 features):")
        for i, row in sample.iterrows():
            vals = {c: row[c] for c in present[:5]}
            print(f"    Row {i}: {vals}")

# Check the raw data files
print(f"\n{'='*60}")
print("RAW DATA FILES")
print(f"{'='*60}")

# Check claims_clean.parquet schema
try:
    clean = pd.read_parquet(os.path.join(base, "claims_clean.parquet"))
    print(f"\nclaims_clean.parquet: {len(clean)} rows, {len(clean.columns)} cols")
    print(f"  Columns: {list(clean.columns)[:30]}")
except Exception as e:
    print(f"\nclaims_clean.parquet ERROR: {e}")

try:
    master = pd.read_parquet(os.path.join(base, "claims_master.parquet"))
    print(f"\nclaims_master.parquet: {len(master)} rows, {len(master.columns)} cols")
    print(f"  Columns: {list(master.columns)[:30]}")
except Exception as e:
    print(f"\nclaims_master.parquet ERROR: {e}")

# Check inpatient CSV columns in more detail - does it have features?
print(f"\n{'='*60}")
print("INPATIENT CSV FIRST ROWS")
print(f"{'='*60}")
inp_csv = pd.read_csv(os.path.join(base, "inpatient", "inpatient_final_risk_scores.csv"), low_memory=False, nrows=3)
print(inp_csv.to_string())

# Check carrier data in unified file
print(f"\n{'='*60}")
print("CARRIER UNIFIED FIRST ROWS (key cols)")
print(f"{'='*60}")
carrier = unified[unified['CLAIM_TYPE'] == 'CARRIER']
print(f"Columns available for carrier: {list(carrier.columns)}")
print(f"\nFirst 3 carrier rows (first 20 cols):")
print(carrier.head(3).iloc[:, :20].to_string())