"""Test production claims explainer"""
from explainability.claims_explainer_prod import explain_claim
import pandas as pd

print("Testing Claims SHAP Explainers - Production Version")
print("="*80)

unified_df = pd.read_csv('models/claims/unified_claim_risk_with_provider.csv', low_memory=False)

# Test Outpatient
print("\n1. OUTPATIENT CLAIM")
print("-"*80)
out_df = unified_df[unified_df['CLAIM_TYPE'] == 'OUTPATIENT']
claim_id = out_df.nlargest(1, 'outpatient_ensemble_score')['CLM_ID'].values[0]
result = explain_claim(claim_id, 'OUTPATIENT')

print(f"Status: {result['status']}")
if result['status'] == 'success':
    print(f"Claim ID: {result['claim_id']}")
    shap = result['shap']
    print(f"Model output: {shap['model_output']:.6f}")
    print(f"Base value: {shap['base_value']:.6f}")
    reconciliation = shap['reconciliation']
    print(f"SHAP reconciliation: {reconciliation['base_value_plus_sum_shap']:.6f} vs {reconciliation['model_output']:.6f}")
    print(f"Residual: {reconciliation['residual']:.6f}")
    print(f"Top 3 features:")
    for feat in shap['top_features'][:3]:
        print(f"  {feat['rank']}. {feat['feature']}: value={feat['value']:.2f}, shap={feat['shap_value']:.6f}")
else:
    print(f"Error: {result.get('error', result.get('message'))}")

# Test Inpatient - should indicate data not available
print("\n2. INPATIENT CLAIM")
print("-"*80)
inp_df = unified_df[unified_df['CLAIM_TYPE'] == 'INPATIENT']
claim_id = inp_df.nlargest(1, 'ensemble_risk_score')['clm_id'].values[0]
result = explain_claim(claim_id, 'INPATIENT')

print(f"Status: {result['status']}")
if result['status'] == 'not_found':
    print("Data not available in embedded source")
    evidence = result.get('model_evidence', {})
    print(f"Model info: {evidence.get('note', 'N/A')}")
else:
    print(f"Error: {result.get('error')}")

# Test Carrier - should indicate data not available
print("\n3. CARRIER CLAIM")
print("-"*80)
carr_df = unified_df[unified_df['CLAIM_TYPE'] == 'CARRIER']
claim_id = carr_df.nlargest(1, 'carrier_ensemble_score')['CLM_ID'].values[0]
result = explain_claim(claim_id, 'CARRIER')

print(f"Status: {result['status']}")
if result['status'] == 'not_found':
    print("Data not available in embedded source")
    evidence = result.get('model_evidence', {})
    print(f"Model info: {evidence.get('note', 'N/A')}")
else:
    print(f"Error: {result.get('error')}")

print("\n" + "="*80)
print("Test complete")
