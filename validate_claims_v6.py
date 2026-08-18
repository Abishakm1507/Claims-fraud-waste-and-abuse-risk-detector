"""
Verify SHAP reconciliation for IsolationForest - understand what TreeExplainer explains.
"""
import warnings
warnings.filterwarnings('ignore')

import joblib
import numpy as np
import pandas as pd
import shap
from pathlib import Path

BASE = Path("models/claims")

# ============ OUTPATIENT: Verify SHAP explains path length ============
print("=" * 70)
print("OUTPATIENT: SHAP vs score_samples relationship")
print("=" * 70)

# Load artifacts
path = BASE / "outpatient"
feats = joblib.load(path / "feature_columns.pkl")
scaler = joblib.load(path / "scaler.pkl")
iso = joblib.load(path / "isolation_forest.pkl")

print(f"IF: n_estimators={iso.n_estimators}, max_samples_={iso.max_samples_}")
print(f"IF: max_samples = {iso.max_samples}")

# Check the offset
print(f"IF offset_: {iso.offset_}")

# Load data
df = pd.read_csv(path / "outpatient_final_risk_scores.csv", low_memory=False)

# Compute for a sample claim
idx = 0
row = df.iloc[idx]
features = np.array([float(row[f]) for f in feats]).reshape(1, -1)
scaled = scaler.transform(features)

# Model outputs
score_samples = iso.score_samples(scaled)[0]
decision = iso.decision_function(scaled)[0]

# SHAP
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
print(f"\nClaim {row['CLM_ID']}:")
print(f"  base_value           = {base:.10f}")
print(f"  sum(shap)            = {np.sum(sv):.10f}")
print(f"  base + sum           = {recon:.10f}")
print(f"  score_samples        = {score_samples:.10f}")
print(f"  decision_function    = {decision:.10f}")

# Hyp: recon is avg_path_length, score_samples = -2^(-avg_path/c(n))
# c(n) = 2*(ln(n-1)+euler_gamma) - 2*(n-1)/n
from scipy.special import digamma

def c_n(n):
    """Average path length of unsuccessful search in BST."""
    if n <= 1:
        return 1
    if n == 2:
        return 1
    return 2 * (np.log(n - 1) + 0.5772156649) - 2 * (n - 1) / n

cn = c_n(iso.max_samples_)
print(f"  c(max_samples_)      = {cn:.10f}")

# Check if score_samples = 2^(-recon/cn)  with some offset
# sklearn: score_samples = -_compute_chunked_score_samples(X)
# _compute_chunked_score_samples returns 2^(-avg_path/c(n)) - offset_
# Actually, score_samples returns negative of that
# So: score_samples = -(2^(-avg_path/cn) - offset_)

# Let's try to derive avg_path from score_samples
# score_samples = -(2^(-path/cn) - offset)
# -score_samples = 2^(-path/cn) - offset
# -score_samples + offset = 2^(-path/cn)
# log2(-score_samples + offset) = -path/cn
# path = -cn * log2(-score_samples + offset)

offset = iso.offset_
print(f"  offset               = {offset:.10f}")

recon_from_ss = -cn * np.log2(-score_samples + offset)
print(f"\n  path from score_samples = {recon_from_ss:.10f}")
print(f"  SHAP base + sum          = {recon:.10f}")
print(f"  diff                     = {abs(recon_from_ss - recon):.10f}")

# Alternative: directly check if TreeExplainer explains _average_path_length
# In newer sklearn, the IsolationForest has a special structure
# Let's look at the first tree
print(f"\n  First tree structure:")
tree0 = iso.estimators_[0]
print(f"    tree0 type: {type(tree0).__name__}")

# For IsolationForest, the estimators are ExtraTreeRegressors
# TreeExplainer explains the mean of the tree outputs
# Each tree outputs -depth (negative depth) for IsolationForest

# Let's compute what TreeExplainer explains
# For an ExtraTreeRegressor in IsolationForest, TreeExplainer explains the regression output
# which is -depth (the negative path length)

# The mean across all estimators:
# tree_output = -depth for each tree
# mean_output = mean(-depth) = -mean(depth) = -avg_path
# score = 2^(-avg_path/cn) = 2^(mean_output/cn)
# But wait: offset is also involved

# Let me check: what does TreeExplainer explain?
# expected_value should be mean of all tree outputs
# Let's compute it manually
print(f"\n  Manual verification:")
# Get the raw scores from all trees
preds = np.zeros(1)
for tree in iso.estimators_:
    preds += tree.predict(scaled)
mean_pred = preds / len(iso.estimators_)
print(f"  Mean tree output: {mean_pred[0]:.10f}")
print(f"  SHAP expected_value: {base:.10f}")

# score from sklearn formula:
# score = 2^mean_pred / c(n)
# Actually: in sklearn's IsolationForest._compute_chunked_score_samples:
#   scores = 2 ** (-depths / self._average_path_length([self.max_samples_]))
# where depths is the per-tree average path length
# depths[i] = -sum(tree_predictions) / n_estimators
# = -mean_predictions

# So: score = 2^(-(-mean_pred)/cn) = 2^(mean_pred/cn)
# And: score_samples = -(score - offset) = offset - score

# Let me verify:
score_manual = 2 ** (mean_pred[0] / cn)
print(f"  Manual score: {score_manual:.10f}")
print(f"  Actual score (score_samples): {score_samples:.10f}")

# score_samples returns: -2^(-depths/cn) + offset?
# Let me check sklearn source:
# return -self._compute_chunked_score_samples(X)
# _compute_chunked_score_samples returns: 2**(-depths/c(n)) - offset_
# So score_samples = -(2**(-depths/c(n)) - offset_) = offset_ - 2**(-depths/c(n))

score_internal = 2 ** (-(-mean_pred[0]) / cn)
print(f"\n  Internal score (2^(-(-mean_pred)/cn))): {score_internal:.10f}")
print(f"  score_samples should be: offset - internal = {offset - score_internal:.10f}")
print(f"  Actual score_samples: {score_samples:.10f}")

# Now, what does SHAP reconcile with?
# base + sum(shap) = ??? 
# For TreeExplainer on an ensemble of ExtraTreeRegressors:
# The output is the mean of all tree outputs = mean_pred
# So: base + sum(shap) = mean_pred = -avg_path

print(f"\n  SHAP base + sum should equal mean_pred:")
print(f"    SHAP base + sum: {recon:.10f}")
print(f"    Mean tree output: {mean_pred[0]:.10f}")
print(f"    Difference: {abs(recon - mean_pred[0]):.10f}")

# So SHAP explains the mean tree prediction (-avg_path), NOT score_samples
# score_samples = offset - 2^(mean_pred/cn) = offset - 2^(-avg_path/cn)

# Let's verify:
avg_path = -mean_pred[0]
score_verify = offset - 2 ** (-avg_path / cn)
print(f"\n  Verify: offset - 2^(-avg_path/cn):")
print(f"    avg_path = {avg_path:.10f}")
print(f"    computed score = {score_verify:.10f}")
print(f"    actual score_samples = {score_samples:.10f}")
print(f"    diff = {abs(score_verify - score_samples):.10f}")

# ============ Now verify for a few more claims ============
print(f"\n\n  Verifying across multiple outpatient claims:")
for idx in [0, 1000, 5000, 10000, 25000, len(df)-1]:
    row = df.iloc[idx]
    features = np.array([float(row[f]) for f in feats]).reshape(1, -1)
    scaled = scaler.transform(features)
    ss = iso.score_samples(scaled)[0]
    
    # SHAP
    sv = np.asarray(explainer.shap_values(scaled))
    if sv.ndim == 3:
        sv = sv[0]
    if sv.ndim == 2 and sv.shape[0] == 1:
        sv = sv[0]
    recon = base + np.sum(sv)
    
    # Compute expected score from SHAP
    avg_path_from_shap = -recon
    score_from_shap = offset - 2 ** (-avg_path_from_shap / cn)
    diff = abs(score_from_shap - ss)
    
    print(f"  Claim {row['CLM_ID']}: ss={ss:.6f}, recon={recon:.6f}, score_from_shap={score_from_shap:.6f}, diff={diff:.8f}")