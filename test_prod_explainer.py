"""
Test the corrected production claims explainer with real data.
"""
import warnings
warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd
import joblib
from pathlib import Path

from explainability.claims_explainer_prod import (
    explain_claim,
    OutpatientClaimExplainer,
    CarrierClaimExplainer,
    InpatientClaimExplainer,
)

BASE = Path("models/claims")

print("=" * 70)
print("PRODUCTION EXPLAINER VALIDATION")
print("=" * 70)

# ============ OUTPATIENT ============
print("\n" + "=" * 70)
print("OUTPATIENT")
print("=" * 70)

out = OutpatientClaimExplainer()
print(f"Features: {len(out.feature_names)}")

# Load the score CSV
out_df = pd.read_csv(BASE / "outpatient" / "outpatient_final_risk_scores.csv", low_memory=False)

# Pick claims from different risk levels
high_risk_id = out_df.nlargest(1, 'outpatient_ensemble_score')['CLM_ID'].iloc[0]
low_risk_id = out_df.nsmallest(1, 'outpatient_ensemble_score')['CLM_ID'].iloc[0]

for claim_id in [high_risk_id, low_risk_id]:
    result = explain_claim(claim_id, 'OUTPATIENT')
    status = result.get('status')
    print(f"\n  Claim {claim_id}: status={status}")
    if status == 'success':
        shap_info = result['shap']
        print(f"    model_output: {shap_info['model_output']:.6f}")
        print(f"    base_value: {shap_info['base_value']:.6f}")
        print(f"    top_features: {len(shap_info['top_features'])}")
        print(f"    top_feature: {shap_info['top_features'][0]['feature']} = {shap_info['top_features'][0]['shap_value']:.6f}")
        print(f"    model_evidence keys: {list(result['model_evidence'].keys())}")

# ============ CARRIER ============
print("\n" + "=" * 70)
print("CARRIER")
print("=" * 70)

car = CarrierClaimExplainer()
print(f"Features: {len(car.feature_names)}")

# Load carrier data
car_df = pd.read_csv("data/raw/carrier_claim_features_FINAL.csv", low_memory=False)
unified = pd.read_csv(BASE / "unified_claim_risk_with_provider.csv", low_memory=False)
car_unified = unified[unified['CLAIM_TYPE'] == 'CARRIER'].copy()

# Pick claims from different risk levels
merged = car_unified.copy()
high_risk_id = merged.nlargest(1, 'carrier_ensemble_score')['CLAIM_ID'].iloc[0]
low_risk_id = merged.nsmallest(1, 'carrier_ensemble_score')['CLAIM_ID'].iloc[0]

for claim_id in [high_risk_id, low_risk_id]:
    result = explain_claim(claim_id, 'CARRIER')
    status = result.get('status')
    print(f"\n  Claim {claim_id}: status={status}")
    if status == 'success':
        shap_info = result['shap']
        print(f"    model_output: {shap_info['model_output']:.6f}")
        print(f"    base_value: {shap_info['base_value']:.6f}")
        print(f"    top_features: {len(shap_info['top_features'])}")
        print(f"    top_feature: {shap_info['top_features'][0]['feature']} = {shap_info['top_features'][0]['shap_value']:.6f}")
        print(f"    model_evidence: {result['model_evidence']}")

# ============ INPATIENT ============
print("\n" + "=" * 70)
print("INPATIENT")
print("=" * 70)

inp = InpatientClaimExplainer()
print(f"Features: {len(inp.feature_names)}")

# Test without features - should return feature_data_required
result = explain_claim("test-claim", 'INPATIENT')
print(f"\n  Without features: status={result.get('status')}")
print(f"  Reason: {result.get('reason', 'N/A')}")

# Test with explicit features
# Construct a synthetic 49-feature vector (all zeros is fine for testing the SHAP path)
zero_features = {name: 0.0 for name in inp.feature_names}
result = explain_claim("test-claim", 'INPATIENT', features=zero_features)
print(f"\n  With zero features: status={result.get('status')}")
if result.get('status') == 'success':
    shap_info = result['shap']
    print(f"    model_output: {shap_info['model_output']:.6f}")
    print(f"    base_value: {shap_info['base_value']:.6f}")
    print(f"    top_features: {len(shap_info['top_features'])}")

# ============ ERROR HANDLING ============
print("\n" + "=" * 70)
print("ERROR HANDLING")
print("=" * 70)

# Invalid claim type
try:
    result = explain_claim("123", "NONEXISTENT")
    print(f"  Invalid type: {result}")
except ValueError as e:
    print(f"  Invalid type raises ValueError: {e}")

# Claim not found
result = explain_claim("999999999", 'OUTPATIENT')
print(f"  Not found: status={result.get('status')}, reason={result.get('reason', 'N/A')}")

# Wrong feature count for inpatient
bad_features = {name: 0.0 for name in inp.feature_names[:10]}
result = explain_claim("123", 'INPATIENT', features=bad_features)
print(f"  Wrong feature count: status={result.get('status')}, error={result.get('error', 'N/A')[:100]}")

print("\nDone.")