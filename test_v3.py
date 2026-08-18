"""Test Claims SHAP explainers v3"""
from explainability.claims_explainer_v3 import explain_claim
import pandas as pd

unified_df = pd.read_csv('models/claims/unified_claim_risk_with_provider.csv', low_memory=False)

for claim_type in ['CARRIER', 'INPATIENT', 'OUTPATIENT']:
    print(f'\n{"="*80}')
    print(f'{claim_type}')
    print(f'{"="*80}')
    
    type_df = unified_df[unified_df['CLAIM_TYPE'] == claim_type]
    print(f'Total claims: {len(type_df)}')
    
    # Get one high-risk claim
    if claim_type == 'CARRIER':
        claim_id = type_df.nlargest(1, 'carrier_ensemble_score')['CLM_ID'].values[0]
    elif claim_type == 'INPATIENT':
        claim_id = type_df.nlargest(1, 'ensemble_risk_score')['clm_id'].values[0]
    else:
        claim_id = type_df.nlargest(1, 'outpatient_ensemble_score')['CLM_ID'].values[0]
    
    print(f'\nTesting claim: {claim_id}')
    result = explain_claim(claim_id, claim_type)
    
    if result.get('status') == 'success':
        print(f'  Status: SUCCESS')
        print(f'  SHAP model_output: {result["shap"]["model_output"]:.6f}')
        print(f'  SHAP base_value: {result["shap"]["base_value"]:.6f}')
        print(f'  Reconciliation residual: {result["shap"]["reconciliation"]["residual"]:.6f}')
        top_feat = result['shap']['top_features'][0]
        print(f'  Top feature: {top_feat["feature"]} (shap={top_feat["shap_value"]:.6f})')
    else:
        print(f'  Status: {result.get("status")}')
        print(f'  Error: {result.get("error", result.get("reason"))}')
