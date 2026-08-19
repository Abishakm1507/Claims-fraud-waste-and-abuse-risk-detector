"""
Load Claims ML artifacts using joblib for better sklearn compatibility.
"""
import joblib
import pandas as pd
import warnings
from pathlib import Path

warnings.filterwarnings('ignore')

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
        try:
            features = joblib.load(fc_path)
            print(f"[OK] feature_columns.pkl loaded: {len(features)} features")
            print(f"  First 3: {features[:3]}")
            print(f"  Last 3: {features[-3:]}")
        except Exception as e:
            print(f"[ERROR] feature_columns: {e}")
            features = None
    else:
        print(f"[MISSING] feature_columns.pkl")
        features = None
    
    # Load scaler
    scaler_path = pipeline_path / "scaler.pkl"
    try:
        scaler = joblib.load(scaler_path)
        print(f"[OK] scaler.pkl loaded: {type(scaler).__name__}")
        if hasattr(scaler, 'scale_'):
            print(f"  scale_ shape: {scaler.scale_.shape}")
        if hasattr(scaler, 'mean_'):
            print(f"  mean_ shape: {scaler.mean_.shape}")
    except Exception as e:
        print(f"[ERROR] scaler.pkl: {e}")
        scaler = None
    
    # Load Isolation Forest
    iso_path = pipeline_path / "isolation_forest.pkl"
    try:
        iso = joblib.load(iso_path)
        print(f"[OK] isolation_forest.pkl: {type(iso).__name__}")
        if hasattr(iso, 'contamination'):
            print(f"  contamination: {iso.contamination}")
        if hasattr(iso, 'n_estimators'):
            print(f"  n_estimators: {iso.n_estimators}")
    except Exception as e:
        print(f"[ERROR] isolation_forest.pkl: {e}")
        iso = None
    
    # Load LOF
    lof_paths = list(pipeline_path.glob("lof*.pkl"))
    if lof_paths:
        try:
            lof = joblib.load(lof_paths[0])
            print(f"[OK] lof.pkl: {type(lof).__name__}")
            if hasattr(lof, 'n_neighbors'):
                print(f"  n_neighbors: {lof.n_neighbors}")
        except Exception as e:
            print(f"[ERROR] lof.pkl: {e}")
            lof = None
    else:
        print(f"[MISSING] lof.pkl")
        lof = None
    
    # Load OCSVM
    ocsvm_path = pipeline_path / "ocsvm.pkl"
    try:
        ocsvm = joblib.load(ocsvm_path)
        print(f"[OK] ocsvm.pkl: {type(ocsvm).__name__}")
        if hasattr(ocsvm, 'kernel'):
            print(f"  kernel: {ocsvm.kernel}")
        if hasattr(ocsvm, 'nu'):
            print(f"  nu: {ocsvm.nu}")
    except Exception as e:
        print(f"[ERROR] ocsvm.pkl: {e}")
        ocsvm = None
    
    # Load model config if exists
    config_path = pipeline_path / "model_config.pkl"
    if config_path.exists():
        try:
            config = joblib.load(config_path)
            print(f"[OK] model_config.pkl")
            if isinstance(config, dict):
                for key in sorted(list(config.keys())[:10]):
                    val = config[key]
                    if isinstance(val, (dict, list)):
                        print(f"  {key}: {type(val).__name__} (len={len(val)})")
                    else:
                        print(f"  {key}: {val}")
        except Exception as e:
            print(f"[ERROR] model_config.pkl: {e}")
    
    # Load and inspect CSV
    csv_name = f"{claim_type.lower()}_final_risk_scores.csv"
    csv_path = pipeline_path / csv_name
    if csv_path.exists():
        try:
            df = pd.read_csv(csv_path)
            print(f"[OK] {csv_name}: {df.shape}")
            print(f"  Columns: {list(df.columns)}")
        except Exception as e:
            print(f"[ERROR] {csv_name}: {e}")
    else:
        print(f"[MISSING] {csv_name}")
    
    return features, scaler, iso, lof, ocsvm

if __name__ == "__main__":
    print("LOADING CLAIMS ML ARTIFACTS WITH JOBLIB")
    print(f"Base path: {CLAIMS_BASE.absolute()}")
    
    for claim_type in ["Carrier", "Inpatient", "Outpatient"]:
        try:
            features, scaler, iso, lof, ocsvm = load_pipeline_artifacts(claim_type)
        except Exception as e:
            print(f"\nUNCOMPLIED ERROR in {claim_type}:")
            import traceback
            traceback.print_exc()
    
    # Also inspect unified file for Carrier data
    print(f"\n{'='*80}")
    print("UNIFIED CLAIM RISK FILE INSPECTION")
    print(f"{'='*80}")
    
    unified_path = CLAIMS_BASE / "unified_claim_risk_with_provider.csv"
    if unified_path.exists():
        df = pd.read_csv(unified_path, low_memory=False)
        print(f"[OK] Shape: {df.shape}")
        print(f"[OK] Total columns: {len(df.columns)}")
        
        # Check claim type distribution
        print(f"\nClaim type distribution:")
        for ct, count in df['CLAIM_TYPE'].value_counts().items():
            print(f"  {ct}: {count}")
        
        # Sample claims
        print(f"\nSample Carrier claim:")
        carrier_data = df[df['CLAIM_TYPE'] == 'CARRIER'].iloc[0]
        print(f"  CLM_ID: {carrier_data['CLM_ID']}")
        print(f"  IF_score: {carrier_data['IF_score']}")
        print(f"  LOF_score: {carrier_data['LOF_score']}")
        print(f"  OCSVM_score: {carrier_data['OCSVM_score']}")
        print(f"  carrier_ensemble_score: {carrier_data['carrier_ensemble_score']}")
        print(f"  carrier_risk_band: {carrier_data['carrier_risk_band']}")
        
        print(f"\nSample Inpatient claim:")
        inpatient_data = df[df['CLAIM_TYPE'] == 'INPATIENT'].iloc[0]
        print(f"  clm_id: {inpatient_data['clm_id']}")
        print(f"  isolation_forest_score: {inpatient_data['isolation_forest_score']}")
        print(f"  ensemble_risk_score: {inpatient_data['ensemble_risk_score']}")
        print(f"  risk_band: {inpatient_data['risk_band']}")
        
        print(f"\nSample Outpatient claim:")
        outpatient_data = df[df['CLAIM_TYPE'] == 'OUTPATIENT'].iloc[0]
        print(f"  CLM_ID: {outpatient_data['CLM_ID']}")
        print(f"  IF_score: {outpatient_data['IF_score']}")
        print(f"  outpatient_ensemble_score: {outpatient_data['outpatient_ensemble_score']}")
        print(f"  outpatient_risk_band: {outpatient_data['outpatient_risk_band']}")
