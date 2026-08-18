"""
Load Claims ML artifacts using joblib for better sklearn compatibility.
"""
import joblib
import pandas as pd
from pathlib import Path

CLAIMS_BASE = Path("models/claims")

def load_pipeline_artifacts(claim_type):
    """Load all artifacts for a claim type using joblib."""
    print(f"\n{'='*80}")
    print(f"{claim_type.upper()}")
    print(f"{'='*80}")
    
    pipeline_path = CLAIMS_BASE / claim_type.lower()
    
    # Load feature columns
    fc_path = pipeline_path / "feature_columns.pkl"
    if fc_path.exists():
        features = joblib.load(fc_path)
        print(f"[OK] feature_columns.pkl loaded: {len(features)} features")
        print(f"  First 3: {features[:3]}")
    else:
        print(f"[MISSING] feature_columns.pkl")
        features = None
    
    # Load scaler
    scaler_path = pipeline_path / "scaler.pkl"
    try:
        scaler = joblib.load(scaler_path)
        print(f"[OK] scaler.pkl loaded: {type(scaler).__name__}")
        if hasattr(scaler, 'scale_'):
            print(f"  Scaler shape: {scaler.scale_.shape}")
    except Exception as e:
        print(f"[ERROR] scaler.pkl failed: {e}")
        scaler = None
    
    # Load Isolation Forest
    iso_path = pipeline_path / "isolation_forest.pkl"
    try:
        iso = joblib.load(iso_path)
        print(f"[OK] isolation_forest.pkl loaded: {type(iso).__name__}")
        if hasattr(iso, 'contamination'):
            print(f"  contamination: {iso.contamination}")
    except Exception as e:
        print(f"[ERROR] isolation_forest.pkl failed: {e}")
        iso = None
    
    # Load LOF (handle space in filename for Outpatient)
    lof_paths = list(pipeline_path.glob("lof*.pkl"))
    try:
        lof = joblib.load(lof_paths[0])
        print(f"[OK] lof.pkl loaded: {type(lof).__name__}")
    except Exception as e:
        print(f"[ERROR] lof.pkl failed: {e}")
        lof = None
    
    # Load OCSVM
    ocsvm_path = pipeline_path / "ocsvm.pkl"
    try:
        ocsvm = joblib.load(ocsvm_path)
        print(f"[OK] ocsvm.pkl loaded: {type(ocsvm).__name__}")
    except Exception as e:
        print(f"[ERROR] ocsvm.pkl failed: {e}")
        ocsvm = None
    
    # Load model config if exists
    config_path = pipeline_path / "model_config.pkl"
    if config_path.exists():
        try:
            config = joblib.load(config_path)
            print(f"[OK] model_config.pkl loaded")
            if isinstance(config, dict) and 'ensemble_weights' in config:
                print(f"  ensemble_weights: {config['ensemble_weights']}")
        except Exception as e:
            print(f"[ERROR] model_config.pkl failed: {e}")
    
    # Load CSV if exists
    csv_name = f"{claim_type.lower()}_final_risk_scores.csv"
    csv_path = pipeline_path / csv_name
    if csv_path.exists():
        df = pd.read_csv(csv_path)
        print(f"✓ {csv_name} loaded: {df.shape}")
        print(f"  Columns sample: {list(df.columns[:5])}")
    else:
        print(f"✗ {csv_name} MISSING")
    
    return {
        'features': features,
        'scaler': scaler,
        'iso': iso,
        'lof': lof,
        'ocsvm': ocsvm,
    }

if __name__ == "__main__":
    print("LOADING CLAIMS ML ARTIFACTS WITH JOBLIB")
    print(f"Base path: {CLAIMS_BASE}")
    
    for claim_type in ["Carrier", "Inpatient", "Outpatient"]:
        try:
            artifacts = load_pipeline_artifacts(claim_type)
        except Exception as e:
            print(f"\nERROR: {e}")
            import traceback
            traceback.print_exc()
    
    # Also check unified file for Carrier data
    print(f"\n{'='*80}")
    print("UNIFIED CLAIM RISK FILE")
    print(f"{'='*80}")
    
    unified_path = CLAIMS_BASE / "unified_claim_risk_with_provider.csv"
    if unified_path.exists():
        df = pd.read_csv(unified_path)
        print(f"Shape: {df.shape}")
        
        # Check for Carrier-specific columns
        carrier_cols = [c for c in df.columns if 'carrier' in c.lower()]
        print(f"Carrier columns: {carrier_cols}")
        
        # Count by claim type
        print(f"\nClaim type distribution:")
        print(df['CLAIM_TYPE'].value_counts())
        
        # Sample a Carrier claim
        carrier_data = df[df['CLAIM_TYPE'] == 'CARRIER'].iloc[0]
        print(f"\nSample Carrier claim:")
        print(f"  CLM_ID: {carrier_data['CLM_ID']}")
        print(f"  IF_score: {carrier_data['IF_score']}")
        print(f"  carrier_ensemble_score: {carrier_data['carrier_ensemble_score']}")
        print(f"  carrier_risk_band: {carrier_data['carrier_risk_band']}")
