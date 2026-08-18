"""
Comprehensive validation of Claims Explainability pipelines.

Validates:
1. Artifact loading for Carrier, Inpatient, Outpatient
2. Feature contract (feature count and names)
3. Model output reproduction using persisted artifacts
4. SHAP reconciliation
5. Stored score comparison
"""
import warnings
warnings.filterwarnings('ignore')

import joblib
import numpy as np
import pandas as pd
import shap
import os
from pathlib import Path

BASE = Path("models/claims")


def load_artifacts(claim_type: str):
    """Load all artifacts for a claim type."""
    path = BASE / claim_type.lower()
    
    artifacts = {}
    
    # Feature columns
    fc_path = path / "feature_columns.pkl"
    if fc_path.exists():
        artifacts['feature_names'] = joblib.load(fc_path)
    else:
        artifacts['feature_names'] = None
    
    # Scaler (fallback to feature_names_in_)
    sc_path = path / "scaler.pkl"
    if sc_path.exists():
        artifacts['scaler'] = joblib.load(sc_path)
        if artifacts['feature_names'] is None and hasattr(artifacts['scaler'], 'feature_names_in_'):
            artifacts['feature_names'] = list(artifacts['scaler'].feature_names_in_)
    
    # Isolation Forest
    iso_path = path / "isolation_forest.pkl"
    if iso_path.exists():
        artifacts['isolation_forest'] = joblib.load(iso_path)
    
    # LOF (handle space in filename)
    lof_paths = list(path.glob("lof*.pkl"))
    if lof_paths:
        artifacts['lof'] = joblib.load(lof_paths[0])
    
    # OCSVM
    oc_path = path / "ocsvm.pkl"
    if oc_path.exists():
        artifacts['ocsvm'] = joblib.load(oc_path)
    
    # Model config
    mc_path = path / "model_config.pkl"
    if mc_path.exists():
        artifacts['config'] = joblib.load(mc_path)
    
    return artifacts


def validate_outpatient():
    """Validate Outpatient pipeline using CSV features."""
    print("\n" + "=" * 70)
    print("OUTPATIENT VALIDATION")
    print("=" * 70)
    
    artifacts = load_artifacts("OUTPATIENT")
    feature_names = artifacts['feature_names']
    scaler = artifacts['scaler']
    iso = artifacts['isolation_forest']
    
    print(f"  Feature count: {len(feature_names)}")
    print(f"  Scaler type: {type(scaler).__name__}")
    print(f"  IF: {type(iso).__name__}, n_estimators={iso.n_estimators}")
    
    # Load scores CSV (has features)
    csv_path = BASE / "outpatient" / "outpatient_final_risk_scores.csv"
    df = pd.read_csv(csv_path, low_memory=False)
    print(f"  Claims: {len(df)}")
    
    # Check feature availability
    missing = [c for c in feature_names if c not in df.columns]
    print(f"  Missing feature columns in CSV: {missing}")
    
    # Pick 2 claims from different risk levels
    high_risk = df.nlargest(1, 'outpatient_ensemble_score')
    low_risk = df.nsmallest(1, 'outpatient_ensemble_score')
    
    test_claims = pd.concat([high_risk, low_risk])
    
    print(f"\n  Test claims:")
    for _, row in test_claims.iterrows():
        claim_id = row['CLM_ID']
        ensemble = row['outpatient_ensemble_score']
        if_score_stored = row.get('IF_score', np.nan)
        print(f"    CLM_ID={claim_id}, ensemble={ensemble:.4f}, IF_stored={if_score_stored}")
    
    print(f"\n  Model output validation (IF score_samples):")
    results = []
    for _, row in test_claims.iterrows():
        claim_id = row['CLM_ID']
        
        # Build feature vector in exact order
        features = np.array([float(row[f]) for f in feature_names]).reshape(1, -1)
        
        # Scale
        scaled = scaler.transform(features)
        
        # IF score_samples
        score_samples = iso.score_samples(scaled)[0]
        decision_fn = iso.decision_function(scaled)[0]
        
        # Also try negative score (anomaly score: lower = more anomalous)
        results.append({
            'claim_id': claim_id,
            'score_samples': score_samples,
            'decision_function': decision_fn,
            'stored_if': if_score_stored,
        })
        print(f"    Claim {claim_id}:")
        print(f"      score_samples()    = {score_samples:.6f}")
        print(f"      decision_function() = {decision_fn:.6f}")
        print(f"      stored IF_score     = {if_score_stored}")
    
    # Now compute scores for ALL claims to understand normalization
    print(f"\n  Recomputing IF scores for all {len(df)} claims...")
    all_features = df[feature_names].values.astype(float)
    all_scaled = scaler.transform(all_features)
    all_if_scores = iso.score_samples(all_scaled)
    
    print(f"  IF score_samples range: {all_if_scores.min():.6f} to {all_if_scores.max():.6f}")
    
    # Try to understand normalization: stored IF_score vs score_samples
    stored_if = df['IF_score'].values.astype(float)
    print(f"  Stored IF_score range: {stored_if.min():.4f} to {stored_if.max():.4f}")
    
    # Check correlation
    from scipy.stats import rankdata
    rank_samples = rankdata(all_if_scores) / len(all_if_scores) * 100
    diff = np.abs(rank_samples - stored_if)
    print(f"  Percentile rank vs stored IF_score:")
    print(f"    Max diff: {diff.max():.6f}")
    print(f"    Mean diff: {diff.mean():.6f}")
    print(f"    Median diff: {np.median(diff):.6f}")
    
    # Also check min-max normalization
    min_max = (all_if_scores - all_if_scores.min()) / (all_if_scores.max() - all_if_scores.min()) * 100
    diff2 = np.abs(min_max - stored_if)
    print(f"  Min-max vs stored IF_score:")
    print(f"    Max diff: {diff2.max():.6f}")
    print(f"    Mean diff: {diff2.mean():.6f}")
    
    # Test SHAP for sample claims
    print(f"\n  SHAP reconciliation:")
    for _, row in test_claims.iterrows():
        claim_id = row['CLM_ID']
        features = np.array([float(row[f]) for f in feature_names]).reshape(1, -1)
        scaled = scaler.transform(features)
        model_output = iso.score_samples(scaled)[0]
        
        explainer = shap.TreeExplainer(iso)
        shap_values = explainer.shap_values(scaled)
        sv = np.asarray(shap_values)
        if sv.ndim == 3:
            sv = sv[0]
        if sv.ndim == 2 and sv.shape[0] == 1:
            sv = sv[0]
        
        base = explainer.expected_value
        if isinstance(base, (list, np.ndarray)):
            base = float(np.mean(base))
        else:
            base = float(base)
        
        recon = base + np.sum(sv)
        print(f"    Claim {claim_id}:")
        print(f"      base_value       = {base:.6f}")
        print(f"      sum(shap)        = {np.sum(sv):.6f}")
        print(f"      base + sum       = {recon:.6f}")
        print(f"      score_samples    = {model_output:.6f}")
        print(f"      residual         = {abs(recon - model_output):.6f}")
        print(f"      decision_function= {iso.decision_function(scaled)[0]:.6f}")
        print(f"      SHAP shape       = {sv.shape}")
    
    return results


def validate_carrier():
    """Validate Carrier pipeline using feature file."""
    print("\n" + "=" * 70)
    print("CARRIER VALIDATION")
    print("=" * 70)
    
    artifacts = load_artifacts("CARRIER")
    feature_names = artifacts['feature_names']
    scaler = artifacts['scaler']
    iso = artifacts['isolation_forest']
    
    print(f"  Feature count: {len(feature_names)}")
    print(f"  Scaler type: {type(scaler).__name__}")
    print(f"  IF: {type(iso).__name__}, n_estimators={iso.n_estimators}")
    
    # Load features from raw file
    feat_path = "data/raw/carrier_claim_features_FINAL.csv"
    df = pd.read_csv(feat_path, low_memory=False)
    print(f"  Claims in feature file: {len(df)}")
    
    # Check feature availability
    missing = [c for c in feature_names if c not in df.columns]
    print(f"  Missing feature columns: {missing}")
    
    # Fill NaN with 0 for now (we'll see what the original pipeline does)
    df_filled = df.copy()
    for col in feature_names:
        df_filled[col] = pd.to_numeric(df_filled[col], errors='coerce').fillna(0)
    
    # Load unified file for stored scores
    unified = pd.read_csv(BASE / "unified_claim_risk_with_provider.csv", low_memory=False)
    carrier_unified = unified[unified['CLAIM_TYPE'] == 'CARRIER'].copy()
    carrier_unified['CLAIM_ID_str'] = carrier_unified['CLAIM_ID'].astype(str).str.strip()
    
    # Match by CLAIM_ID
    df['CLAIM_ID_str'] = df['CLM_ID'].astype(str).str.strip()
    
    # Pick claims from different risk levels using ensemble score
    merged = df.merge(carrier_unified[['CLAIM_ID_str', 'IF_score', 'LOF_score', 'OCSVM_score', 'carrier_ensemble_score', 'carrier_risk_band']], 
                      on='CLAIM_ID_str', how='left')
    
    print(f"  Matched with unified: {merged['IF_score'].notna().sum()}/{len(merged)}")
    
    high_risk = merged.nlargest(1, 'carrier_ensemble_score')
    low_risk = merged.nsmallest(1, 'carrier_ensemble_score')
    
    test_claims = pd.concat([high_risk, low_risk])
    
    print(f"\n  Test claims:")
    for _, row in test_claims.iterrows():
        print(f"    CLM_ID={row['CLM_ID']}, ensemble={row['carrier_ensemble_score']:.4f}, IF_stored={row['IF_score']}")
    
    print(f"\n  Model output validation (IF score_samples):")
    for _, row in test_claims.iterrows():
        claim_id = row['CLM_ID']
        
        # Build feature vector in exact order
        features = np.array([float(row[f]) for f in feature_names]).reshape(1, -1)
        
        # Scale
        scaled = scaler.transform(features)
        
        # IF score_samples
        score_samples = iso.score_samples(scaled)[0]
        decision_fn = iso.decision_function(scaled)[0]
        
        print(f"    Claim {claim_id}:")
        print(f"      score_samples()    = {score_samples:.6f}")
        print(f"      decision_function() = {decision_fn:.6f}")
        print(f"      stored IF_score     = {row['IF_score']}")
    
    # Compute scores for all claims to understand normalization
    print(f"\n  Recomputing IF scores for all {len(df_filled)} claims...")
    all_features = df_filled[feature_names].values.astype(float)
    all_scaled = scaler.transform(all_features)
    all_if_scores = iso.score_samples(all_scaled)
    
    print(f"  IF score_samples range: {all_if_scores.min():.6f} to {all_if_scores.max():.6f}")
    
    # Compare with stored IF scores
    stored_if = merged['IF_score'].values.astype(float)
    valid = ~np.isnan(stored_if)
    print(f"  Valid stored IF scores: {valid.sum()}/{len(stored_if)}")
    
    if valid.sum() > 0:
        from scipy.stats import rankdata
        rank_samples = rankdata(all_if_scores[valid]) / valid.sum() * 100
        diff = np.abs(rank_samples - stored_if[valid])
        print(f"  Percentile rank vs stored IF_score:")
        print(f"    Max diff: {diff.max():.6f}")
        print(f"    Mean diff: {diff.mean():.6f}")
        
        min_max = (all_if_scores[valid] - all_if_scores[valid].min()) / (all_if_scores[valid].max() - all_if_scores[valid].min()) * 100
        diff2 = np.abs(min_max - stored_if[valid])
        print(f"  Min-max vs stored IF_score:")
        print(f"    Max diff: {diff2.max():.6f}")
        print(f"    Mean diff: {diff2.mean():.6f}")
    
    # SHAP reconciliation for test claims
    print(f"\n  SHAP reconciliation:")
    for _, row in test_claims.iterrows():
        claim_id = row['CLM_ID']
        features = np.array([float(row[f]) for f in feature_names]).reshape(1, -1)
        scaled = scaler.transform(features)
        model_output = iso.score_samples(scaled)[0]
        
        explainer = shap.TreeExplainer(iso)
        shap_values = explainer.shap_values(scaled)
        sv = np.asarray(shap_values)
        if sv.ndim == 3:
            sv = sv[0]
        if sv.ndim == 2 and sv.shape[0] == 1:
            sv = sv[0]
        
        base = explainer.expected_value
        if isinstance(base, (list, np.ndarray)):
            base = float(np.mean(base))
        else:
            base = float(base)
        
        recon = base + np.sum(sv)
        print(f"    Claim {claim_id}:")
        print(f"      base_value       = {base:.6f}")
        print(f"      sum(shap)        = {np.sum(sv):.6f}")
        print(f"      base + sum       = {recon:.6f}")
        print(f"      score_samples    = {model_output:.6f}")
        print(f"      residual         = {abs(recon - model_output):.6f}")
        print(f"      decision_function= {iso.decision_function(scaled)[0]:.6f}")


def validate_inpatient():
    """Validate Inpatient pipeline - need to derive features from raw data."""
    print("\n" + "=" * 70)
    print("INPATIENT VALIDATION")
    print("=" * 70)
    
    artifacts = load_artifacts("INPATIENT")
    feature_names = artifacts['feature_names']
    scaler = artifacts['scaler']
    iso = artifacts['isolation_forest']
    
    print(f"  Feature count: {len(feature_names)}")
    print(f"  Scaler type: {type(scaler).__name__}")
    print(f"  IF: {type(iso).__name__}, n_estimators={iso.n_estimators}")
    
    # Load scores
    scores = pd.read_csv(BASE / "inpatient" / "inpatient_final_risk_scores.csv", low_memory=False)
    print(f"  Claims in scores file: {len(scores)}")
    
    # Load raw data
    raw_path = "data/raw/inpatient_CLEANED_v2.csv"
    print(f"  Loading raw data (this may take a moment)...")
    raw = pd.read_csv(raw_path, low_memory=False)
    print(f"  Raw data rows: {len(raw)}")
    
    # Show what features we need to derive
    print(f"\n  Required features ({len(feature_names)}):")
    for f in feature_names:
        print(f"    {f}")
    
    # Check if any features already exist in raw data
    raw_cols = set(raw.columns)
    present = [f for f in feature_names if f in raw_cols]
    missing = [f for f in feature_names if f not in raw_cols]
    print(f"\n  Features already in raw: {len(present)}")
    print(f"  Features to derive: {len(missing)}")
    if present:
        print(f"  Present: {present}")
    
    # Show raw data sample
    clm = raw['clm_id'].iloc[0]
    claim_rows = raw[raw['clm_id'] == clm]
    print(f"\n  Sample claim {clm}: {len(claim_rows)} rows")
    print(f"  Columns: {list(claim_rows.columns[:30])}")


if __name__ == "__main__":
    print("=" * 70)
    print("CLAIMS EXPLAINABILITY PIPELINE VALIDATION")
    print("=" * 70)
    
    validate_outpatient()
    validate_carrier()
    validate_inpatient()