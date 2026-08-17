import os
import pandas as pd, numpy as np
from sklearn.preprocessing import StandardScaler, RobustScaler
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.cluster import DBSCAN
from sklearn.decomposition import PCA
path='D:/GitHub/cognizant-hackathon/Claims-fraud-waste-and-abuse-risk-detector'
ART = f'{path}/models/provider/artifacts'
U = pd.read_pickle(f'{ART}/unified_features_logged.pkl').copy()
eps = 1e-9

# =====================================================================
# 1. GLOBAL ANOMALY DETECTION FEATURE SET
#    Log-space utilization/payment + service-pattern + peer-deviation signals.
#    Excludes identifiers, one-hot geography/type columns, and raw (unlogged)
#    heavy-tailed duplicates of the logged versions.
# =====================================================================
model_feats = [
    'log1p_Tot_Benes','log1p_Tot_Srvcs','log1p_Tot_Sbmtd_Chrg','log1p_Tot_Mdcr_Pymt_Amt',
    'log1p_Payment_per_Service','log1p_Charge_per_Service','log1p_Svc_Total_Volume','log1p_Svc_Unique_HCPCS',
    'Payment_to_Charge_Ratio','Services_per_Beneficiary','HCPCS_per_Beneficiary','Drug_Service_Share',
    'Svc_HHI_Concentration','Svc_Top_HCPCS_Share','Svc_Diversity_per_Volume','Svc_Num_Places',
    'Peer_Avg_Pymt_Deviation','Peer_Max_Pymt_Deviation','Peer_Pct_Services_Above_2x_Bench',
    'Dual_Eligible_Ratio','Bene_Avg_Risk_Scre',
]
model_feats = [c for c in model_feats if c in U.columns]

X = U[model_feats].copy()
# providers without service detail (Dataset B) get median-imputed service features + a missingness flag,
# rather than being dropped -- so the "primary" Dataset A population is fully scored.
missing_service = X[['Svc_HHI_Concentration','Peer_Avg_Pymt_Deviation']].isna().any(axis=1)
X = X.fillna(X.median(numeric_only=True))
X = X.replace([np.inf,-np.inf], np.nan).fillna(X.median(numeric_only=True))

scaler = RobustScaler()
Xs = scaler.fit_transform(X)

print(f'Modeling matrix: {Xs.shape[0]} providers x {Xs.shape[1]} features '
      f'({missing_service.sum()} providers imputed for missing service-detail features)')

# =====================================================================
# 2. ISOLATION FOREST (primary)
# =====================================================================
iso = IsolationForest(n_estimators=300, contamination=0.05, random_state=42, n_jobs=-1)
iso.fit(Xs)
iso_raw = -iso.score_samples(Xs)          # higher = more anomalous
U['iso_score_raw'] = iso_raw
U['iso_flag'] = (iso.predict(Xs) == -1).astype(int)

# =====================================================================
# 3. LOCAL OUTLIER FACTOR (comparison)
# =====================================================================
lof = LocalOutlierFactor(n_neighbors=35, contamination=0.05, n_jobs=-1)
lof_pred = lof.fit_predict(Xs)
U['lof_score_raw'] = -lof.negative_outlier_factor_
U['lof_flag'] = (lof_pred == -1).astype(int)

# =====================================================================
# 4. DBSCAN (comparison, density-based; run on a PCA-reduced space for stability)
# =====================================================================
pca = PCA(n_components=10, random_state=42)
Xp = pca.fit_transform(Xs)
db = DBSCAN(eps=1.5, min_samples=15, n_jobs=-1)
db_labels = db.fit_predict(Xp)
U['dbscan_flag'] = (db_labels == -1).astype(int)
print(f'DBSCAN: {(db_labels==-1).sum()} noise points ({(db_labels==-1).mean():.2%}), '
      f'{len(set(db_labels))-(1 if -1 in db_labels else 0)} clusters, '
      f'PCA explained variance retained: {pca.explained_variance_ratio_.sum():.2%}')

# ---- model agreement / comparison report ----
agree = pd.DataFrame({
    'iso_flag': U['iso_flag'], 'lof_flag': U['lof_flag'], 'dbscan_flag': U['dbscan_flag']
})
print('\nFlagged-anomaly counts:\n', agree.sum())
print('\nPairwise agreement (Jaccard overlap of flagged sets):')
for a in ['iso_flag','lof_flag','dbscan_flag']:
    for b in ['iso_flag','lof_flag','dbscan_flag']:
        if a < b:
            sa, sb = set(U.index[U[a]==1]), set(U.index[U[b]==1])
            jac = len(sa & sb) / max(1, len(sa | sb))
            print(f'  {a} vs {b}: {jac:.3f}  (overlap n={len(sa & sb)})')

# =====================================================================
# 5. NORMALIZE EACH MODEL SCORE TO 0-1 VIA PERCENTILE RANK, THEN ENSEMBLE
# =====================================================================
def pct_rank(s):
    return s.rank(pct=True)

U['iso_pctile'] = pct_rank(U['iso_score_raw'])
U['lof_pctile'] = pct_rank(U['lof_score_raw'])
# dbscan has no continuous score -> use flag directly as a 0/1 pctile-like signal
U['dbscan_pctile'] = U['dbscan_flag'].astype(float)

# Global anomaly ensemble: average IsolationForest + LOF percentile (both are full
# continuous rankings and showed reasonable agreement above); DBSCAN's binary flag
# is kept as a separate corroborating signal rather than diluting the continuous score.
U['global_anomaly_score'] = 0.6*U['iso_pctile'] + 0.4*U['lof_pctile']

# =====================================================================
# 6. PEER-GROUP DEVIATION RISK (z-scores within Provider_Type peer group)
# =====================================================================
peer_feats = ['Payment_per_Service','Charge_per_Service','Services_per_Beneficiary',
              'Payment_to_Charge_Ratio','Svc_HHI_Concentration']
peer_feats = [c for c in peer_feats if c in U.columns]

type_counts = U['Provider_Type'].value_counts()
valid_types = type_counts[type_counts >= 20].index  # only group vs peers w/ enough sample size
U['peer_group'] = np.where(U['Provider_Type'].isin(valid_types), U['Provider_Type'], 'Other/Small-Specialty')

z_parts = []
for c in peer_feats:
    grp_mean = U.groupby('peer_group')[c].transform('mean')
    grp_std  = U.groupby('peer_group')[c].transform('std').replace(0, np.nan)
    z = ((U[c] - grp_mean) / grp_std).abs()
    z_parts.append(z.fillna(0))
    # --- additive PEER EVIDENCE for the Multi-Agent layer (descriptive only;
    #     uses the exact same peer_group and groupby statistics as the z-score
    #     above, so it is consistent with peer_deviation_score. Not fed to any
    #     model/score.) ---
    U[f'{c}_Peer_Mean']      = grp_mean
    U[f'{c}_Peer_Median']    = U.groupby('peer_group')[c].transform('median')
    U[f'{c}_Peer_Std']       = grp_std
    U[f'{c}_Peer_Pctile']    = U.groupby('peer_group')[c].rank(pct=True)   # within peer group, 0-1
    U[f'{c}_Deviation_Ratio'] = U[c] / grp_mean.replace(0, np.nan)          # value vs peer mean (x)
U['peer_deviation_zsum'] = np.mean(z_parts, axis=0)
U['peer_deviation_score'] = pct_rank(U['peer_deviation_zsum'])

# =====================================================================
# 7. SERVICE-PATTERN ANOMALY SIGNAL (concentration + diversity, percentile)
# =====================================================================
U['service_pattern_score'] = pct_rank(
    0.5*U['Svc_HHI_Concentration'].fillna(U['Svc_HHI_Concentration'].median())
    + 0.5*U['Svc_Top_HCPCS_Share'].fillna(U['Svc_Top_HCPCS_Share'].median())
)

# =====================================================================
# 8. GEOGRAPHIC/PEER PRICE-BENCHMARK DEVIATION SIGNAL
# =====================================================================
U['geo_deviation_score'] = pct_rank(
    U['Peer_Avg_Pymt_Deviation'].fillna(1.0).clip(upper=U['Peer_Avg_Pymt_Deviation'].quantile(0.99))
)

# =====================================================================
# 8b. MERGE ADDITIVE EVIDENCE ARTIFACTS (geo + temporal)
#     Produced by s2_features.py from the SAME underlying frames used to
#     build the model features. These columns explain the scores above;
#     they are never used as model features or in the risk score.
# =====================================================================
for ev_file in ['D_geo_evidence.pkl', 'D_temporal_evidence.pkl']:
    ev_path = f'{ART}/{ev_file}'
    if os.path.exists(ev_path):
        ev = pd.read_pickle(ev_path)
        U = U.merge(ev, on='NPI', how='left')
        print(f'Merged evidence artifact: {ev_file} ({ev.shape[0]} rows)')
    else:
        print(f'[warn] evidence artifact not found (skipping): {ev_path}')

# =====================================================================
# 9. FINAL 0-100 RISK SCORE
#    Weighting rationale (documented, not arbitrary):
#      - Global anomaly ensemble (IF+LOF)  35%  -> primary multivariate signal, the
#        core deliverable per spec; captures rare overall behavior across all features.
#      - Peer-group deviation              30%  -> grounds the score in a fair
#        same-specialty comparison so high-volume-but-normal specialists aren't
#        penalized just for being high-volume.
#      - Service-pattern anomaly           20%  -> billing-pattern signal (service
#        concentration/diversity) that is a well-established FWA red flag independent
#        of raw dollar magnitude.
#      - Geographic price-benchmark dev.   15%  -> lowest weight because benchmark
#        coverage (Dataset C join) is partial; still contributes when available.
# =====================================================================
weights = {'global_anomaly_score':0.35, 'peer_deviation_score':0.30,
           'service_pattern_score':0.20, 'geo_deviation_score':0.15}
U['Provider_Risk_Score'] = 100 * sum(U[c]*w for c,w in weights.items())

def tier(s):
    if s < 30: return 'Low'
    if s < 60: return 'Moderate'
    if s < 80: return 'High'
    return 'Critical'
U['Risk_Tier'] = U['Provider_Risk_Score'].apply(tier)

print('\nRisk tier distribution:\n', U['Risk_Tier'].value_counts())
print('\nRisk score summary:\n', U['Provider_Risk_Score'].describe())

# =====================================================================
# 10. LEIE SANITY CHECK (validation only -- never used as a feature/label)
# =====================================================================
leie = pd.read_csv(f'{path}/data/provider/LEIE-cleaned.csv', usecols=['NPI','HAS_NPI'])
excluded_npis = set(leie.loc[leie['HAS_NPI']==True,'NPI'].dropna().astype('int64'))
U['is_leie_excluded'] = U['NPI'].astype('int64').isin(excluded_npis).astype(int)
n_match = U['is_leie_excluded'].sum()
if n_match:
    print(f'\nLEIE sanity check: {n_match} providers in our set appear on the exclusion list.')
    print('Their risk score stats vs. population:')
    print(U.groupby('is_leie_excluded')['Provider_Risk_Score'].describe())
else:
    print('\nLEIE sanity check: no overlapping NPIs found -- skipping (dataset overlap is only 15 in the raw files).')

# =====================================================================
# SAVE OUTPUTS
#   Existing columns are preserved verbatim; the evidence columns below are
#   APPENDED so any downstream code reading the old schema keeps working.
# =====================================================================
out_cols = ['NPI','Provider_Type','Prvdr_State','Tot_Benes','Tot_Srvcs','Tot_Sbmtd_Chrg','Tot_Mdcr_Pymt_Amt',
            'Payment_per_Service','Services_per_Beneficiary','has_service_detail',
            'iso_score_raw','iso_flag','lof_score_raw','lof_flag','dbscan_flag',
            'global_anomaly_score','peer_deviation_score','service_pattern_score','geo_deviation_score',
            'Provider_Risk_Score','Risk_Tier','is_leie_excluded']

# --- identification / context ---
extra_cols = [
    'peer_group', 'peer_deviation_zsum',
    # useful provider features (Task 5): actual pipeline variable names
    'Tot_Mdcr_Alowd_Amt',        # Total allowed amount
    'Payment_per_Beneficiary',
    'Tot_HCPCS_Cds',             # unique service count (Dataset A)
    'Svc_Unique_HCPCS',          # unique service count (Dataset B, where available)
    'Svc_HHI_Concentration',     # service concentration
    'Charge_per_Service', 'Payment_to_Charge_Ratio',
    # temporal evidence (Task 4)
    'Year_First','Year_Last','Num_Years_Observed',
    'Svc_First_Year','Svc_Last_Year','Svc_Growth_Pct',
    'Pymt_First_Year','Pymt_Last_Year','Pymt_Growth_Pct',
    'Benes_First_Year','Benes_Last_Year','Benes_Growth_Pct',
]
# per-metric peer evidence (Task 2): mean/median/std/percentile/ratio, same peer_group as the score
for c in peer_feats:
    extra_cols += [f'{c}_Peer_Mean', f'{c}_Peer_Median', f'{c}_Peer_Std', f'{c}_Peer_Pctile', f'{c}_Deviation_Ratio']
# geographic evidence (Task 3): benchmark stats from the same state/national fallback chain
geo_ev_cols = [
    'Peer_Bench_Rows_Matched','Peer_Avg_Pymt_Deviation','Peer_Max_Pymt_Deviation','Peer_Avg_Chrg_Deviation','Peer_Pct_Services_Above_2x_Bench',
    'Geo_Rows_Matched','Geo_Rows_state_year','Geo_Rows_state','Geo_Rows_national',
    'Geo_Provider_Avg_Pymt','Geo_Bench_Pymt_Mean','Geo_Bench_Pymt_Median','Geo_Bench_Pymt_Std',
    'Geo_Provider_Avg_Chrg','Geo_Bench_Chrg_Mean','Geo_Bench_Chrg_Median','Geo_Bench_Chrg_Std',
]
out_cols = out_cols + extra_cols + geo_ev_cols
out_cols = [c for c in out_cols if c in U.columns]
result = U[out_cols].sort_values('Provider_Risk_Score', ascending=False)
result.to_csv(f'{path}/models/provider/output/provider_risk_scores.csv', index=False)
U.to_pickle(f'{ART}/unified_scored.pkl')
print('\nTop 10 highest-risk providers:')
print(result.head(10).to_string(index=False))
print(f'\nSaved: {path}/models/provider/output/provider_risk_scores.csv')
