import pandas as pd
from pathlib import Path

# Location of prediction results
CSV_FILE = Path("check_scores.csv")

# Load risk scores
if not CSV_FILE.exists():
    print("Error: check_scores.csv was not found.")
    print("Run predict_provider.py first.")
    exit()

df = pd.read_csv(CSV_FILE)

# Make NPI comparison reliable
df["npi"] = df["npi"].astype(str).str.strip()

# Get provider NPI
npi = input("Enter Provider NPI: ").strip()

# Find provider
result = df[df["npi"] == npi]

if result.empty:
    print("\nProvider not found.")
    print("Please check the NPI and try again.")
else:
    provider = result.iloc[0]

    print("\n================================")
    print("     PROVIDER RISK ASSESSMENT")
    print("================================")
    print(f"NPI           : {provider['npi']}")
    print(f"Risk Score    : {provider['risk_score_0_100']:.2f} / 100")
    print(f"Risk Category : {provider['risk_category']}")
    print("================================")