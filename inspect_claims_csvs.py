import pandas as pd

paths = {
    "carrier": "models/claims/carrier/carrier_final_risk_scores.csv",
    "inpatient": "models/claims/inpatient/inpatient_final_risk_scores.csv",
    "outpatient": "models/claims/outpatient/outpatient_final_risk_scores.csv",
}

for claim_type, path in paths.items():
    df = pd.read_csv(path, low_memory=False)
    print(f"\n{'='*60}")
    print(f"{claim_type.upper()} — {path}")
    print(f"{'='*60}")
    print(f"Shape: {len(df)} rows, {len(df.columns)} columns")
    print(f"\nColumns:\n{sorted(df.columns.tolist())}")
    print(f"\nFirst row:")
    print(df.iloc[0].to_dict() if len(df) > 0 else "NO ROWS")
