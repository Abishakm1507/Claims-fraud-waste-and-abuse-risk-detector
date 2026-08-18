"""
Test Claims SHAP explainers with real data.
"""
import pandas as pd
from explainability.claims_explainer_v2 import explain_claim

# Load unified file to get sample claim IDs
unified_path = "models/claims/unified_claim_risk_with_provider.csv"
df = pd.read_csv(unified_path, low_memory=False)

print("="*80)
print("TESTING CLAIMS SHAP EXPLAINERS")
print("="*80)

# Test each claim type
for claim_type in ["CARRIER", "INPATIENT", "OUTPATIENT"]:
    print(f"\n{'='*80}")
    print(f"{claim_type}")
    print(f"{'='*80}")
    
    # Get sample claims
    type_df = df[df['CLAIM_TYPE'] == claim_type]
    print(f"Total {claim_type} claims: {len(type_df)}")
    
    # Get claim IDs for different risk levels
    sample_claims = []
    if claim_type == "CARRIER":
        # Get high and low risk Carrier claims
        sample_claims = [
            type_df.nlargest(1, 'carrier_ensemble_score')['CLM_ID'].values[0],
            type_df.nsmallest(1, 'carrier_ensemble_score')['CLM_ID'].values[0],
        ]
    elif claim_type == "INPATIENT":
        # Get high and low risk Inpatient claims
        sample_claims = [
            type_df.nlargest(1, 'ensemble_risk_score')['clm_id'].values[0],
            type_df.nsmallest(1, 'ensemble_risk_score')['clm_id'].values[0],
        ]
    else:  # OUTPATIENT
        # Get high and low risk Outpatient claims
        sample_claims = [
            type_df.nlargest(1, 'outpatient_ensemble_score')['CLM_ID'].values[0],
            type_df.nsmallest(1, 'outpatient_ensemble_score')['CLM_ID'].values[0],
        ]
    
    for idx, claim_id in enumerate(sample_claims, 1):
        print(f"\n  Sample {idx}: Claim ID = {claim_id}")
        try:
            result = explain_claim(claim_id, claim_type)
            
            if result.get("status") == "success":
                print(f"    [OK] Status: {result['status']}")
                print(f"    [OK] Claim type: {result['claim_type']}")
                
                # Model evidence
                evidence = result.get("model_evidence", {})
                print(f"\n    Model Evidence:")
                if claim_type == "CARRIER":
                    print(f"      IF score: {evidence.get('if_score'):.4f}")
                    print(f"      LOF score: {evidence.get('lof_score'):.4f}")
                    print(f"      OCSVM score: {evidence.get('ocsvm_score'):.4f}")
                    print(f"      Ensemble score: {evidence.get('ensemble_score'):.4f}")
                    print(f"      Risk band: {evidence.get('risk_band')}")
                elif claim_type == "INPATIENT":
                    print(f"      IF score: {evidence.get('isolation_forest_score'):.4f}")
                    print(f"      LOF score: {evidence.get('lof_score'):.4f}")
                    print(f"      OCSVM score: {evidence.get('ocsvm_score'):.4f}")
                    print(f"      Ensemble score: {evidence.get('ensemble_score'):.4f}")
                    print(f"      Model consensus: {evidence.get('model_consensus')}")
                    print(f"      Risk band: {evidence.get('risk_band')}")
                else:  # OUTPATIENT
                    print(f"      IF score: {evidence.get('if_score'):.4f}")
                    print(f"      LOF score: {evidence.get('lof_score'):.4f}")
                    print(f"      OCSVM score: {evidence.get('ocsvm_score'):.4f}")
                    print(f"      Ensemble score: {evidence.get('ensemble_score'):.4f}")
                    print(f"      Ensemble weights: {evidence.get('ensemble_weights')}")
                    print(f"      Risk band: {evidence.get('risk_band')}")
                
                # SHAP
                shap_info = result.get("shap", {})
                print(f"\n    SHAP Explanation:")
                print(f"      Explained model: {shap_info.get('explained_model')}")
                print(f"      Model output: {shap_info.get('model_output'):.6f}")
                print(f"      Base value: {shap_info.get('base_value'):.6f}")
                
                # Reconciliation
                reconciliation = shap_info.get('reconciliation', {})
                print(f"\n    SHAP Reconciliation:")
                print(f"      base_value + sum(SHAP): {reconciliation.get('base_value_plus_sum'):.6f}")
                print(f"      Model output:          {reconciliation.get('model_output'):.6f}")
                print(f"      Residual:              {reconciliation.get('residual'):.6f}")
                
                # Top features
                top_features = shap_info.get('top_features', [])
                print(f"\n    Top 5 Contributing Features:")
                for feat in top_features[:5]:
                    print(f"      {feat['rank']}. {feat['feature']}")
                    print(f"         value: {feat['value']:.4f}, shap: {feat['shap_value']:.6f}")
            else:
                print(f"    [ERROR] Status: {result.get('status')}")
                print(f"    [ERROR] Reason: {result.get('reason', result.get('error', 'Unknown'))}")
        except Exception as e:
            print(f"    [ERROR] Exception: {e}")
            import traceback
            traceback.print_exc()

print(f"\n{'='*80}")
print("TEST COMPLETE")
print(f"{'='*80}")
