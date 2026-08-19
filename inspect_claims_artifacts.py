"""
Comprehensive inspection of Claims ML artifacts.

Goal: Understand the exact structure, features, preprocessing, and model configurations
for Carrier, Inpatient, and Outpatient claim pipelines.
"""
import os
import pickle
import pandas as pd
import numpy as np
from pathlib import Path

CLAIMS_BASE = Path("models/claims")

def inspect_pipeline(claim_type):
    """Inspect a single claim type pipeline."""
    print(f"\n{'='*80}")
    print(f"INSPECTING: {claim_type.upper()}")
    print(f"{'='*80}")
    
    pipeline_path = CLAIMS_BASE / claim_type.lower()
    
    # List all files
    print(f"\nFiles in {pipeline_path}:")
    files = list(pipeline_path.glob("*"))
    for f in sorted(files):
        print(f"  {f.name} ({f.stat().st_size:,} bytes)")
    
    # Load feature columns
    print(f"\n1. FEATURE COLUMNS")
    try:
        with open(pipeline_path / "feature_columns.pkl", "rb") as f:
            features = pickle.load(f)
        
        if isinstance(features, dict):
            print(f"   Type: dict")
            for key, val in features.items():
                if isinstance(val, list):
                    print(f"   '{key}': {len(val)} items - {val[:3]}...")
                else:
                    print(f"   '{key}': {val}")
        elif isinstance(features, list):
            print(f"   Type: list ({len(features)} features)")
            print(f"   First 5: {features[:5]}")
            print(f"   Last 5: {features[-5:]}")
            print(f"   Total count: {len(features)}")
        else:
            print(f"   Type: {type(features)}")
            print(f"   Value: {features}")
    except Exception as e:
        print(f"   ERROR: {e}")
    
    # Load scaler
    print(f"\n2. SCALER")
    try:
        with open(pipeline_path / "scaler.pkl", "rb") as f:
            scaler = pickle.load(f)
        print(f"   Type: {type(scaler).__name__}")
        if hasattr(scaler, 'scale_'):
            print(f"   Scale shape: {scaler.scale_.shape}")
        if hasattr(scaler, 'center_'):
            print(f"   Center shape: {scaler.center_.shape}")
        print(f"   Methods: {[m for m in dir(scaler) if not m.startswith('_')][:10]}")
    except Exception as e:
        print(f"   ERROR: {e}")
    
    # Load Isolation Forest
    print(f"\n3. ISOLATION FOREST")
    try:
        with open(pipeline_path / "isolation_forest.pkl", "rb") as f:
            iso = pickle.load(f)
        print(f"   Type: {type(iso).__name__}")
        print(f"   n_estimators: {iso.n_estimators if hasattr(iso, 'n_estimators') else 'N/A'}")
        print(f"   contamination: {iso.contamination if hasattr(iso, 'contamination') else 'N/A'}")
        print(f"   random_state: {iso.random_state if hasattr(iso, 'random_state') else 'N/A'}")
        print(f"   Methods: score_samples={hasattr(iso, 'score_samples')}, decision_function={hasattr(iso, 'decision_function')}, predict={hasattr(iso, 'predict')}")
    except Exception as e:
        print(f"   ERROR: {e}")
    
    # Load LOF
    print(f"\n4. LOCAL OUTLIER FACTOR")
    try:
        with open(pipeline_path / "lof.pkl", "rb") as f:
            lof = pickle.load(f)
        print(f"   Type: {type(lof).__name__}")
        print(f"   n_neighbors: {lof.n_neighbors if hasattr(lof, 'n_neighbors') else 'N/A'}")
    except Exception as e:
        print(f"   ERROR: {e}")
    
    # Load OCSVM
    print(f"\n5. ONE-CLASS SVM")
    try:
        with open(pipeline_path / "ocsvm.pkl", "rb") as f:
            ocsvm = pickle.load(f)
        print(f"   Type: {type(ocsvm).__name__}")
        print(f"   kernel: {ocsvm.kernel if hasattr(ocsvm, 'kernel') else 'N/A'}")
        print(f"   nu: {ocsvm.nu if hasattr(ocsvm, 'nu') else 'N/A'}")
    except Exception as e:
        print(f"   ERROR: {e}")
    
    # Load model config if it exists
    print(f"\n6. MODEL CONFIG")
    try:
        config_path = pipeline_path / "model_config.pkl"
        if config_path.exists():
            with open(config_path, "rb") as f:
                config = pickle.load(f)
            print(f"   Type: {type(config)}")
            if isinstance(config, dict):
                for key, val in config.items():
                    print(f"   '{key}': {val}")
        else:
            print("   (not available)")
    except Exception as e:
        print(f"   ERROR: {e}")
    
    # Load and inspect CSV
    print(f"\n7. RISK SCORE CSV")
    try:
        csv_path = pipeline_path / f"{claim_type.lower()}_final_risk_scores.csv"
        df = pd.read_csv(csv_path, nrows=5)
        print(f"   Shape: {pd.read_csv(csv_path).shape}")
        print(f"   Columns: {list(df.columns[:10])}")
        print(f"   First row:\n{df.iloc[0]}")
    except Exception as e:
        print(f"   ERROR: {e}")


if __name__ == "__main__":
    for claim_type in ["Carrier", "Inpatient", "Outpatient"]:
        try:
            inspect_pipeline(claim_type)
        except Exception as e:
            print(f"\nERROR inspecting {claim_type}: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\n{'='*80}")
    print("INSPECTION COMPLETE")
    print(f"{'='*80}")
