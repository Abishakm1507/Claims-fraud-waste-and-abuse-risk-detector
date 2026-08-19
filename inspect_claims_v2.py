"""
Robust inspection of Claims ML artifacts with proper pickle handling.
"""
import os
import sys
import pickle
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Any

CLAIMS_BASE = Path("models/claims")

def safe_pickle_load(filepath):
    """Safely load a pickle file with multiple protocols."""
    try:
        with open(filepath, "rb") as f:
            return pickle.load(f)
    except Exception as e1:
        try:
            with open(filepath, "rb") as f:
                # Try with different pickle protocol
                return pickle.Unpickler(f, fix_imports=True, encoding='latin1').load()
        except Exception as e2:
            return f"ERROR: {type(e1).__name__}: {e1}"

def inspect_pipeline(claim_type):
    """Inspect a single claim type pipeline."""
    print(f"\n{'='*80}")
    print(f"{claim_type.upper()}")
    print(f"{'='*80}")
    
    pipeline_path = CLAIMS_BASE / claim_type.lower()
    
    if not pipeline_path.exists():
        print(f"MISSING: {pipeline_path}")
        return
    
    # List all files
    print(f"\nFiles:")
    files = sorted([f for f in pipeline_path.glob("*") if f.is_file()])
    for f in files:
        size_mb = f.stat().st_size / (1024*1024)
        print(f"  {f.name:<40} {size_mb:>8.2f} MB")
    
    # Try to load feature columns
    print(f"\n1. FEATURE COLUMNS")
    fc_path = pipeline_path / "feature_columns.pkl"
    if fc_path.exists():
        features = safe_pickle_load(fc_path)
        if isinstance(features, str):  # Error message
            print(f"   {features}")
        elif isinstance(features, list):
            print(f"   Type: list")
            print(f"   Count: {len(features)}")
            print(f"   First 5: {features[:5]}")
            print(f"   Last 5: {features[-5:]}")
        else:
            print(f"   Type: {type(features)}")
            print(f"   Content: {features}")
    else:
        print(f"   MISSING - {fc_path}")
    
    # Load scaler
    print(f"\n2. SCALER")
    scaler_path = pipeline_path / "scaler.pkl"
    scaler = safe_pickle_load(scaler_path)
    if isinstance(scaler, str):
        print(f"   {scaler}")
    else:
        print(f"   Type: {type(scaler).__name__}")
        if hasattr(scaler, 'scale_'):
            print(f"   scale_ shape: {scaler.scale_.shape}")
        if hasattr(scaler, 'center_'):
            print(f"   center_ shape: {scaler.center_.shape}")
        if hasattr(scaler, 'mean_'):
            print(f"   mean_ shape: {scaler.mean_.shape}")
    
    # Load Isolation Forest
    print(f"\n3. ISOLATION FOREST")
    iso_path = pipeline_path / "isolation_forest.pkl"
    iso = safe_pickle_load(iso_path)
    if isinstance(iso, str):
        print(f"   {iso}")
    else:
        print(f"   Type: {type(iso).__name__}")
        if hasattr(iso, 'n_estimators'):
            print(f"   n_estimators: {iso.n_estimators}")
        if hasattr(iso, 'contamination'):
            print(f"   contamination: {iso.contamination}")
        print(f"   Has score_samples: {hasattr(iso, 'score_samples')}")
        print(f"   Has decision_function: {hasattr(iso, 'decision_function')}")
    
    # Load LOF
    print(f"\n4. LOCAL OUTLIER FACTOR")
    lof_paths = list(pipeline_path.glob("lof*.pkl"))
    if lof_paths:
        lof_path = lof_paths[0]
        lof = safe_pickle_load(lof_path)
        if isinstance(lof, str):
            print(f"   {lof}")
        else:
            print(f"   Type: {type(lof).__name__}")
            if hasattr(lof, 'n_neighbors'):
                print(f"   n_neighbors: {lof.n_neighbors}")
    else:
        print(f"   MISSING")
    
    # Load OCSVM
    print(f"\n5. ONE-CLASS SVM")
    ocsvm_path = pipeline_path / "ocsvm.pkl"
    ocsvm = safe_pickle_load(ocsvm_path)
    if isinstance(ocsvm, str):
        print(f"   {ocsvm}")
    else:
        print(f"   Type: {type(ocsvm).__name__}")
        if hasattr(ocsvm, 'kernel'):
            print(f"   kernel: {ocsvm.kernel}")
        if hasattr(ocsvm, 'nu'):
            print(f"   nu: {ocsvm.nu}")
    
    # Load model config if it exists
    print(f"\n6. MODEL CONFIG")
    config_path = pipeline_path / "model_config.pkl"
    if config_path.exists():
        config = safe_pickle_load(config_path)
        if isinstance(config, str):
            print(f"   {config}")
        else:
            print(f"   Type: {type(config)}")
            if isinstance(config, dict):
                for key in sorted(config.keys())[:15]:
                    val = config[key]
                    if isinstance(val, (dict, list)) and len(str(val)) > 100:
                        print(f"   {key}: {type(val).__name__} (length={len(val)})")
                    else:
                        print(f"   {key}: {val}")
    else:
        print(f"   (not available)")
    
    # Load and inspect CSV
    print(f"\n7. RISK SCORE CSV")
    csv_name = f"{claim_type.lower()}_final_risk_scores.csv"
    csv_path = pipeline_path / csv_name
    if csv_path.exists():
        df = pd.read_csv(csv_path)
        print(f"   Shape: {df.shape}")
        print(f"   Columns: {list(df.columns[:15])}")
        if len(df) > 0:
            print(f"   First row (partial):")
            for col in df.columns[:10]:
                print(f"     {col}: {df.iloc[0][col]}")
    else:
        print(f"   MISSING - {csv_name}")
    
    # Try to load from parent directory
    if not csv_path.exists():
        parent_csv = CLAIMS_BASE / f"{claim_type.lower()}_final_risk_scores.csv"
        if parent_csv.exists():
            print(f"   Found at parent: {parent_csv}")


if __name__ == "__main__":
    print("CLAIMS ML ARTIFACTS INSPECTION")
    print(f"Base path: {CLAIMS_BASE}")
    
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
