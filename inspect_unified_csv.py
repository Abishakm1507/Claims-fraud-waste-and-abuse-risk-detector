import pandas as pd
df = pd.read_csv("models/claims/final_unified_claim_risk.csv", low_memory=False)
print(f"Unified CSV shape: {len(df)} rows, {len(df.columns)} columns")
print(f"\nFirst 20 columns: {df.columns[:20].tolist()}")
if "CLAIM_TYPE" in df.columns:
    print(f"\nCLAIM_TYPE values: {df['CLAIM_TYPE'].value_counts().to_dict()}")
else:
    print("\nCLAIM_TYPE not in columns. Checking for similar:")
    similar = [c for c in df.columns if 'type' in c.lower()]
    print(f"Similar columns: {similar}")
print(f"\nFirst 5 claim IDs and any claim-type related column:")
cols = ["CLAIM_ID"] + [c for c in df.columns if 'type' in c.lower()]
print(df[cols[:min(len(cols), 2)]].head())
