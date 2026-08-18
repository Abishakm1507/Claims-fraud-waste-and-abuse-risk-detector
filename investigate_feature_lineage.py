"""
Comprehensive investigation of Carrier and Inpatient feature lineage.
Attempts to recover and reproduce the stored risk scores from persisted artifacts.
"""
import warnings
warnings.filterwarnings('ignore')

import joblib
import numpy as np
import pandas as pd
from pathlib import Path
from scipy.stats import rankdata

BASE = Path("models/claims")

print("=" * 80)
print("FEATURE LINEAGE INVESTIGATION")
print("=" * 80)

# ============================================================================
# CARRIER INVESTIGATION
# ============================================================================
print("\n" + "=" * 80)
print("CARRIER ANALYSIS")
print("=" * 80)

print("\n1. Load persisted Carrier artifacts...")
try:
    carrier_path = BASE / "carrier"
    carrier_feats = joblib.load(carrier_path / "feature_columns.pkl")
    carrier_scaler = joblib.load(carrier_path / "scaler.pkl")
    carrier_iso = joblib.load(carrier_path / "isolation_forest.pkl")
    print(f"   ✓ Feature columns: {len(carrier_feats)} features")
    print(f"   ✓ Scaler shape: {carrier_scaler.mean_.shape}")
    print(f"   ✓ IsolationForest n_features_in_: {carrier_iso.n_features_in_}")
    
    print(f"\nCarrier features ({len(carrier_feats)}):")
    for i, f in enumerate(carrier_feats, 1):
        print(f"   {i:2}. {f}")
except Exception as e:
    print(f"   ✗ Error loading Carrier artifacts: {e}")
    carrier_feats = None

print("\n2. Load Carrier feature matrix from data/raw/carrier_claim_features_FINAL.csv...")
try:
    carrier_data = pd.read_csv("data/raw/carrier_claim_features_FINAL.csv", low_memory=False)
    print(f"   ✓ Loaded: {len(carrier_data)} claims, {len(carrier_data.columns)} columns")
    
    # Check if all carrier features are present in the data file
    present = [f for f in carrier_feats if f in carrier_data.columns]
    missing = [f for f in carrier_feats if f not in carrier_data.columns]
    print(f"   ✓ Features found in data file: {len(present)}/{len(carrier_feats)}")
    if missing:
        print(f"   ✗ Missing features from data file: {missing}")
except Exception as e:
    print(f"   ✗ Error loading Carrier feature data: {e}")
    carrier_data = None

print("\n3. Load stored Carrier risk scores...")
try:
    carrier_scores = pd.read_csv(BASE / "carrier" / "carrier_final_risk_scores.csv", low_memory=False)
    print(f"   ✓ Loaded: {len(carrier_scores)} claims")
    print(f"   Columns: {list(carrier_scores.columns[:5])}...")
except Exception as e:
    print(f"   ✗ Error loading Carrier scores: {e}")
    carrier_scores = None

if carrier_feats and carrier_data is not None and carrier_scores is not None:
    print("\n4. Merge features with stored scores and test reproducibility...")
    try:
        # Match claim IDs
        carrier_data['CLM_ID_STR'] = carrier_data['CLM_ID'].astype(str).str.strip()
        carrier_scores['CLAIM_ID_STR'] = carrier_scores['CLAIM_ID'].astype(str).str.strip()
        
        merged = carrier_data.merge(
            carrier_scores,
            left_on='CLM_ID_STR',
            right_on='CLAIM_ID_STR',
            how='inner'
        )
        print(f"   ✓ Merged: {len(merged)} matched claims")
        
        if len(merged) > 0:
            # Prepare feature matrix
            X = merged[carrier_feats].values.astype(float)
            print(f"   Feature matrix shape: {X.shape}")
            
            # Check for NaN
            nan_count = np.isnan(X).sum()
            if nan_count > 0:
                print(f"   ⚠ NaN values in feature matrix: {nan_count}")
                X = np.nan_to_num(X, nan=0.0)
                print(f"   → Imputed NaN to 0")
            
            # Scale
            X_scaled = carrier_scaler.transform(X)
            print(f"   Scaled features: {X_scaled.shape}")
            
            # Get model outputs
            iso_scores = carrier_iso.score_samples(X_scaled)
            print(f"   IsolationForest score_samples range: [{iso_scores.min():.6f}, {iso_scores.max():.6f}]")
            
            # Get stored scores
            stored_if = merged['IF_score'].values.astype(float)
            print(f"   Stored IF_score range: [{stored_if.min():.6f}, {stored_if.max():.6f}]")
            
            # Try various transformations
            print("\n5. Test different score transformation hypothesis...")
            
            # Hypothesis 1: min-max inversion
            iso_minmax_inv = (iso_scores.max() - iso_scores) / (iso_scores.max() - iso_scores.min())
            corr1 = np.corrcoef(iso_minmax_inv, stored_if)[0, 1]
            print(f"   H1 (min-max inversion):  corr = {corr1:.6f}")
            
            # Hypothesis 2: rank-based percentile
            iso_rank = rankdata(iso_scores) / len(iso_scores)
            corr2 = np.corrcoef(iso_rank, stored_if / 100.0)[0, 1]
            print(f"   H2 (rank percentile):    corr = {corr2:.6f}")
            
            # Hypothesis 3: negative scores
            iso_neg = -iso_scores
            iso_neg_minmax = (iso_neg.max() - iso_neg) / (iso_neg.max() - iso_neg.min())
            corr3 = np.corrcoef(iso_neg_minmax, stored_if)[0, 1]
            print(f"   H3 (-score min-max inv): corr = {corr3:.6f}")
            
            # Hypothesis 4: raw correspondence
            corr4 = np.corrcoef(iso_scores, stored_if)[0, 1]
            print(f"   H4 (raw score):          corr = {corr4:.6f}")
            
            # Check best hypothesis
            best_hyp = max([
                (corr1, "min-max inversion", iso_minmax_inv),
                (corr2, "rank percentile", iso_rank * 100.0),
                (corr3, "-score min-max inv", iso_neg_minmax),
                (corr4, "raw score", iso_scores),
            ], key=lambda x: x[0])
            
            print(f"\n   ✓ Best hypothesis: {best_hyp[1]} (corr={best_hyp[0]:.6f})")
            
            if best_hyp[0] > 0.99:
                print(f"   ✓ Carrier feature lineage REPRODUCIBLE with {best_hyp[1]}")
                print(f"\n   CARRIER STATUS: READY")
                carrier_ready = True
                carrier_transform = best_hyp[1]
            elif best_hyp[0] > 0.90:
                print(f"   ⚠ Good but not perfect match (corr={best_hyp[0]:.6f})")
                print(f"\n   CARRIER STATUS: BLOCKED (insufficient reproducibility)")
                carrier_ready = False
                carrier_transform = None
            else:
                print(f"   ✗ Cannot match stored scores (best corr={best_hyp[0]:.6f})")
                print(f"\n   CARRIER STATUS: BLOCKED (transformation unknown)")
                carrier_ready = False
                carrier_transform = None
            
            # Show sample reproducibility
            print(f"\n6. Sample-level reproducibility (first 5 claims):")
            sample_hyp = best_hyp[2]
            for i in range(min(5, len(merged))):
                claim_id = merged.iloc[i]['CLM_ID_STR']
                actual = stored_if[i]
                recomp = sample_hyp[i]
                diff = abs(actual - recomp)
                pct_diff = 100.0 * diff / actual if actual != 0 else 0
                print(f"   {i+1}. claim_id={claim_id}: stored={actual:.4f}, recomp={recomp:.4f}, diff={diff:.6f} ({pct_diff:.2f}%)")
    
    except Exception as e:
        print(f"   ✗ Error testing reproducibility: {e}")
        import traceback
        traceback.print_exc()
        carrier_ready = False
        carrier_transform = None
else:
    print("\n   ✗ Cannot proceed: missing artifacts or data")
    carrier_ready = False
    carrier_transform = None

# ============================================================================
# INPATIENT INVESTIGATION
# ============================================================================
print("\n\n" + "=" * 80)
print("INPATIENT ANALYSIS")
print("=" * 80)

print("\n1. Load persisted Inpatient artifacts...")
try:
    inpatient_path = BASE / "inpatient"
    inpatient_feats = joblib.load(inpatient_path / "feature_columns.pkl")
    inpatient_scaler = joblib.load(inpatient_path / "scaler.pkl")
    inpatient_iso = joblib.load(inpatient_path / "isolation_forest.pkl")
    print(f"   ✓ Feature columns: {len(inpatient_feats)} features")
    print(f"   ✓ Scaler shape: {inpatient_scaler.mean_.shape}")
    print(f"   ✓ IsolationForest n_features_in_: {inpatient_iso.n_features_in_}")
    
    print(f"\nInpatient features ({len(inpatient_feats)}):")
    for i, f in enumerate(inpatient_feats, 1):
        print(f"   {i:2}. {f}")
except Exception as e:
    print(f"   ✗ Error loading Inpatient artifacts: {e}")
    inpatient_feats = None

print("\n2. Search for Inpatient feature matrix source...")
# Try to find the feature matrix or raw data
potential_sources = [
    "data/raw/inpatient_claim_features.csv",
    "data/raw/inpatient_features.csv",
    "models/claims/inpatient/inpatient_features.csv",
    "data/raw/inpatient_CLEANED_v2.csv",
]

inpatient_features_data = None
inpatient_source = None

for source in potential_sources:
    try:
        p = Path(source)
        if p.exists():
            df = pd.read_csv(source, low_memory=False, nrows=10)
            inpatient_features_data = df
            inpatient_source = source
            print(f"   ✓ Found: {source}")
            print(f"     Columns: {list(df.columns[:10])}...")
            break
    except Exception:
        pass

if inpatient_features_data is None:
    print(f"   ✗ Could not find pre-engineered inpatient feature matrix")
    print(f"   Checked: {potential_sources}")

print("\n3. Load stored Inpatient risk scores...")
try:
    inpatient_scores = pd.read_csv(BASE / "inpatient" / "inpatient_final_risk_scores.csv", low_memory=False)
    print(f"   ✓ Loaded: {len(inpatient_scores)} claims")
    print(f"   Columns: {list(inpatient_scores.columns[:5])}...")
except Exception as e:
    print(f"   ✗ Error loading Inpatient scores: {e}")
    inpatient_scores = None

print("\n4. Attempt to derive Inpatient features from raw data...")
if inpatient_feats is not None:
    try:
        raw = pd.read_csv("data/raw/inpatient_CLEANED_v2.csv", low_memory=False)
        print(f"   ✓ Loaded raw inpatient data: {len(raw)} rows, {len(raw.columns)} columns")
        print(f"   Claims: {raw['clm_id'].nunique()}")
        
        # Try to derive the 49 features
        # Based on verify_inpatient_features.py, let's attempt feature derivation
        
        def try_derive_inpatient_features(raw_data, feature_names):
            """Attempt to derive inpatient features from raw data."""
            
            # Group by claim
            claim_groups = raw_data.groupby('clm_id')
            
            features_list = []
            errors = []
            
            for clm_id, group in claim_groups:
                try:
                    first = group.iloc[0]
                    
                    # Basic counts
                    claim_line_count = len(group)
                    unique_hcpcs = len(set(str(v).strip() for v in group['hcpcs_cd'].dropna() if str(v).strip() and str(v).strip() != 'nan'))
                    
                    # Diagnosis codes
                    diag_cols = [f'icd_dgns_cd{i}' for i in range(1, 26)]
                    diag_vals = []
                    for col in diag_cols:
                        if col in group.columns:
                            vals = group[col].dropna()
                            for v in vals:
                                s = str(v).strip()
                                if s and s != 'nan':
                                    diag_vals.append(s)
                    unique_diag = len(set(diag_vals))
                    total_diag = len(diag_vals)
                    
                    # Financial
                    total_charge = pd.to_numeric(first.get('clm_tot_chrg_amt', 0), errors='coerce') or 0
                    total_payment = pd.to_numeric(first.get('clm_pmt_amt', 0), errors='coerce') or 0
                    util_days = pd.to_numeric(first.get('clm_utlztn_day_cnt', 0), errors='coerce') or 0
                    
                    # Dates and duration
                    clm_from = pd.to_datetime(first.get('clm_from_dt'), errors='coerce')
                    clm_thru = pd.to_datetime(first.get('clm_thru_dt'), errors='coerce')
                    
                    if pd.notna(clm_from) and pd.notna(clm_thru):
                        dur = (clm_thru - clm_from).days + 1
                    else:
                        dur = 1
                    
                    # Build record
                    record = {
                        'clm_id': clm_id,
                        'claim_line_count': claim_line_count,
                        'unique_hcpcs_count': unique_hcpcs,
                        'unique_diagnosis_code_count': unique_diag,
                        'total_diagnosis_code_count': total_diag,
                        'total_claim_charge': total_charge,
                        'total_claim_payment': total_payment,
                        'total_utilization_days': util_days,
                        'claim_duration_days': dur,
                    }
                    
                    features_list.append(record)
                    
                except Exception as e:
                    errors.append((clm_id, str(e)))
            
            if errors:
                print(f"   ⚠ {len(errors)} errors during feature derivation (first 3):")
                for clm_id, err in errors[:3]:
                    print(f"      - clm_id={clm_id}: {err}")
            
            return pd.DataFrame(features_list) if features_list else pd.DataFrame()
        
        derived_feats = try_derive_inpatient_features(raw, inpatient_feats)
        print(f"   Derived {len(derived_feats)} claims, {len(derived_feats.columns)} features (partial)")
        
        if len(derived_feats) > 0 and inpatient_scores is not None:
            print("\n5. Merge derived features with stored scores...")
            
            derived_feats['clm_id_str'] = derived_feats['clm_id'].astype(str).str.strip()
            inpatient_scores['clm_id_str'] = inpatient_scores.get('clm_id', 
                                                                   inpatient_scores.get('CLM_ID', pd.Series())).astype(str).str.strip()
            
            merged_inp = derived_feats.merge(inpatient_scores, on='clm_id_str', how='inner')
            print(f"   ✓ Merged: {len(merged_inp)} matched claims")
            
            if len(merged_inp) > 0:
                print("\n   Key finding: Inpatient feature matrix is NOT persisted in available repository")
                print(f"   We can only derive a subset from raw data, missing {len(inpatient_feats) - len(derived_feats.columns)} features")
                print(f"\n   INPATIENT STATUS: BLOCKED (original feature matrix not stored)")
                inpatient_ready = False
    
    except Exception as e:
        print(f"   ✗ Error with inpatient feature derivation: {e}")
        import traceback
        traceback.print_exc()
        inpatient_ready = False
else:
    inpatient_ready = False

# ============================================================================
# SUMMARY
# ============================================================================
print("\n\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)

print(f"\nCARRIER:   {'READY' if carrier_ready else 'BLOCKED'}")
if carrier_ready:
    print(f"  Feature source: data/raw/carrier_claim_features_FINAL.csv")
    print(f"  Features: {len(carrier_feats)}")
    print(f"  Transformation: {carrier_transform}")
    print(f"  Reproducibility: > 99% correlation with stored IF_score")
else:
    print(f"  Status: Feature lineage cannot be reproduced from available artifacts")
    print(f"  Missing: Exact transformation from persisted IsolationForest to stored IF_score")

print(f"\nINPATIENT: {'READY' if inpatient_ready else 'BLOCKED'}")
if inpatient_ready:
    print(f"  Feature source: [source]")
    print(f"  Features: {len(inpatient_feats)}")
    print(f"  Reproducibility: Verified")
else:
    print(f"  Status: Original {len(inpatient_feats)}-feature matrix NOT persisted in repository")
    print(f"  Missing: Complete feature matrix and feature-generation code")

print("\n" + "=" * 80)
