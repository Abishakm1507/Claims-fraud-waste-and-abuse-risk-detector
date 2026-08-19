"""
Verify SHAP mathematical reconciliation for IsolationForest.

SHAP TreeExplainer for sklearn IsolationForest should explain the
average negative path length (the internal tree output), not score_samples().

This script validates:
1. base + sum(shap) == mean_tree_output (the internal representation)
2. score_samples is a function of the mean_tree_output
"""
import warnings
warnings.filterwarnings('ignore')

import joblib
import numpy as np
import pandas as pd
import shap
from pathlib import Path

BASE = Path("models/claims")

# Use Outpatient as it's the cleanest pipeline
path = BASE / "outpatient"
feats = joblib.load(path / "feature_columns.pkl")
scaler = joblib.load(path / "scaler.pkl")
iso = joblib.load(path / "isolation_forest.pkl")

df = pd.read_csv(path / "outpatient_final_risk_scores.csv", low_memory=False)

print("=" * 70)
print("SHAP INTERNAL CONSISTENCY VERIFICATION")
print("=" * 70)

for idx in [0, 100, 1000]:
    row = df.iloc[idx]
    features = np.array([float(row[f]) for f in feats]).reshape(1, -1)
    scaled = scaler.transform(features)
    
    # 1. SHAP
    explainer = shap.TreeExplainer(iso)
    sv_raw = explainer.shap_values(scaled)
    sv = np.asarray(sv_raw)
    if sv.ndim == 3:
        sv = sv[0]
    if sv.ndim == 2 and sv.shape[0] == 1:
        sv = sv[0]
    base = explainer.expected_value
    if isinstance(base, (list, np.ndarray)):
        base = float(np.mean(base))
    else:
        base = float(base)
    shap_recon = base + np.sum(sv)
    
    # 2. Direct tree outputs
    tree_preds = np.array([tree.predict(scaled)[0] for tree in iso.estimators_])
    mean_tree_output = tree_preds.mean()
    
    # 3. score_samples
    score_samples = iso.score_samples(scaled)[0]
    
    print(f"\nClaim {row['CLM_ID']}:")
    print(f"  SHAP base + sum(shap) = {shap_recon:.10f}")
    print(f"  Mean tree output      = {mean_tree_output:.10f}")
    print(f"  Difference            = {abs(shap_recon - mean_tree_output):.10f}")
    print(f"  score_samples         = {score_samples:.10f}")
    
    # Check: SHAP explains mean tree output
    if abs(shap_recon - mean_tree_output) < 1e-6:
        print(f"  → SHAP reconciles with mean tree output ✓")
    else:
        print(f"  → SHAP does NOT directly reconcile with mean tree output")
        print(f"  → SHAP explains: {shap_recon:.10f}")
        print(f"  → Tree output: {mean_tree_output:.10f}")

# Also check: what is the SHAP base value?
print(f"\n\nSHAP base values across all claim types:")
explainer = shap.TreeExplainer(iso)
print(f"  Outpatient base: {explainer.expected_value}")

# For carrier
path_car = BASE / "carrier"
scaler_car = joblib.load(path_car / "scaler.pkl")
iso_car = joblib.load(path_car / "isolation_forest.pkl")
explainer_car = shap.TreeExplainer(iso_car)
print(f"  Carrier base: {explainer_car.expected_value}")

# For inpatient
path_inp = BASE / "inpatient"
scaler_inp = joblib.load(path_inp / "scaler.pkl")
iso_inp = joblib.load(path_inp / "isolation_forest.pkl")
explainer_inp = shap.TreeExplainer(iso_inp)
print(f"  Inpatient base: {explainer_inp.expected_value}")

# Check: base value should be mean of expected values of all trees
print(f"\n  Expected base value computation:")
# For each tree, the expected value is the mean of all leaf values
# In sklearn's IsolationForest, leaf values are negative depths
# The expected value is the mean tree output on the training data

# For Outpatient, check what the base value represents
# base = 12.4096 (for outpatient)
# This is the mean negative depth across all trees on background data

# Verify by computing average negative depth for all training claims
print(f"\n  Computing mean negative depth for all outpatient claims:")
X = df[feats].values.astype(float)
X_scaled = scaler.transform(X)
all_tree_preds = np.zeros(len(X_scaled))
for tree in iso.estimators_:
    all_tree_preds += tree.predict(X_scaled)
all_mean = all_tree_preds / len(iso.estimators_)
print(f"  Mean tree output on training data: {all_mean.mean():.10f}")
print(f"  SHAP base value: {explainer.expected_value:.10f}")