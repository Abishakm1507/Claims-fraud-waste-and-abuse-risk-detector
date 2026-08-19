"""Inspect raw data files for carrier and inpatient features."""
import pandas as pd
import os

# Check carrier features file
carrier_path = "data/raw/carrier_claim_features_FINAL.csv"
if os.path.exists(carrier_path):
    df = pd.read_csv(carrier_path, low_memory=False, nrows=5)
    print(f"carrier_claim_features_FINAL.csv: {len(df)} rows (sample)")
    print(f"  Columns ({len(df.columns)}):")
    for col in df.columns:
        print(f"    {col}")
    print(f"\n  First row:")
    for col in df.columns[:15]:
        print(f"    {col}: {df.iloc[0][col]}")
else:
    print(f"MISSING: {carrier_path}")

# Check inpatient file
inp_path = "data/raw/inpatient_CLEANED_v2.csv"
if os.path.exists(inp_path):
    df = pd.read_csv(inp_path, low_memory=False, nrows=5)
    print(f"\ninpatient_CLEANED_v2.csv: {len(df)} rows (sample)")
    print(f"  Columns ({len(df.columns)}):")
    for col in df.columns:
        print(f"    {col}")
    print(f"\n  First row:")
    for col in df.columns[:15]:
        print(f"    {col}: {df.iloc[0][col]}")
else:
    print(f"MISSING: {inp_path}")

# Check old claims scripts for feature building
print("\n\n=== OLD CLAIMS SCRIPTS ===")
scripts_dir = "models/claims/old_claims_scripts"
for f in os.listdir(scripts_dir):
    print(f"\n--- {f} ---")
    path = os.path.join(scripts_dir, f)
    with open(path, 'r', encoding='utf-8', errors='replace') as fh:
        content = fh.read()
    # Print first 100 lines
    lines = content.split('\n')
    for line in lines[:80]:
        print(f"  {line}")