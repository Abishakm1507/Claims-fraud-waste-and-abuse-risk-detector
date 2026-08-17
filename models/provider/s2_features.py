import pandas as pd, numpy as np
pd.set_option('display.width', 140)
path='D:/GitHub/cognizant-hackathon/Claims-fraud-waste-and-abuse-risk-detector'
ART = f'{path}/models/provider/artifacts'

# =====================================================================
# A. PROVIDER-LEVEL TABLE (aggregate NPI x Year -> NPI)
# =====================================================================
prov = pd.read_csv(f'{path}/data/provider/provider-cleaned.csv', low_memory=False)
cols = list(prov.columns)

state_cols = [c for c in cols if c.startswith('Rndrng_Prvdr_State_Abrvtn_')]
type_cols  = [c for c in cols if c.startswith('Rndrng_Prvdr_Type_')]
ruca_cols  = [c for c in cols if c.startswith('Rndrng_Prvdr_RUCA_')]
fips_cols  = [c for c in cols if c.startswith('Rndrng_Prvdr_State_FIPS_')]
onehot_cols = state_cols + type_cols + ruca_cols + fips_cols

sum_cols = ['Tot_HCPCS_Cds','Tot_Benes','Tot_Srvcs','Tot_Sbmtd_Chrg','Tot_Mdcr_Alowd_Amt','Tot_Mdcr_Pymt_Amt','Tot_Mdcr_Stdzd_Amt',
            'Drug_Tot_HCPCS_Cds','Drug_Tot_Benes','Drug_Tot_Srvcs','Drug_Sbmtd_Chrg','Drug_Mdcr_Alowd_Amt','Drug_Mdcr_Pymt_Amt','Drug_Mdcr_Stdzd_Amt',
            'Med_Tot_HCPCS_Cds','Med_Tot_Benes','Med_Tot_Srvcs','Med_Sbmtd_Chrg','Med_Mdcr_Alowd_Amt','Med_Mdcr_Pymt_Amt','Med_Mdcr_Stdzd_Amt',
            'Bene_Age_LT_65_Cnt','Bene_Age_65_74_Cnt','Bene_Age_75_84_Cnt','Bene_Age_GT_84_Cnt','Bene_Feml_Cnt','Bene_Male_Cnt',
            'Bene_Race_Wht_Cnt','Bene_Race_Black_Cnt','Bene_Race_API_Cnt','Bene_Race_Hspnc_Cnt','Bene_Race_NatInd_Cnt','Bene_Race_Othr_Cnt',
            'Bene_Dual_Cnt','Bene_Ndual_Cnt']
sum_cols = [c for c in sum_cols if c in cols]

# comorbidity %s and risk score -> beneficiary-weighted average across years
pct_cols = [c for c in cols if c.endswith('_Pct') or c == 'Bene_Avg_Risk_Scre' or c == 'Bene_Avg_Age']

g = prov.groupby('Rndrng_NPI')

agg = {}
for c in sum_cols:
    agg[c] = prov.groupby('Rndrng_NPI')[c].sum()

# weighted average of pct/risk columns by that year's Tot_Benes
w = prov['Tot_Benes'].clip(lower=1)
for c in pct_cols:
    wsum = (prov[c] * w).groupby(prov['Rndrng_NPI']).sum()
    wtot = w.groupby(prov['Rndrng_NPI']).sum()
    agg[c] = wsum / wtot

# one-hot descriptive cols: take the most recent year's row per NPI (identity attrs assumed stable)
last_idx = prov.sort_values('Year').groupby('Rndrng_NPI').tail(1).set_index('Rndrng_NPI')
for c in onehot_cols + ['Rndrng_Prvdr_Ent_Cd_I','Rndrng_Prvdr_Ent_Cd_O',
                         'Rndrng_Prvdr_Mdcr_Prtcptg_Ind_N','Rndrng_Prvdr_Mdcr_Prtcptg_Ind_Y',
                         'Drug_Sprsn_Ind_#','Drug_Sprsn_Ind_*','Drug_Sprsn_Ind_UNKNOWN',
                         'Med_Sprsn_Ind_#','Med_Sprsn_Ind_*','Med_Sprsn_Ind_UNKNOWN']:
    if c in cols:
        agg[c] = last_idx[c]

A = pd.DataFrame(agg)
A['Num_Years_Observed'] = prov.groupby('Rndrng_NPI')['Year'].nunique()
A['Year_First'] = prov.groupby('Rndrng_NPI')['Year'].min()
A['Year_Last'] = prov.groupby('Rndrng_NPI')['Year'].max()
A.index.name = 'NPI'
A = A.reset_index()

# recompute derived ratios from the summed raw totals (do NOT average pre-computed ratios)
eps = 1e-9
A['Payment_to_Charge_Ratio']   = A['Tot_Mdcr_Pymt_Amt'] / (A['Tot_Sbmtd_Chrg'] + eps)
A['Allowed_to_Charge_Ratio']   = A['Tot_Mdcr_Alowd_Amt'] / (A['Tot_Sbmtd_Chrg'] + eps)
A['Standardized_to_Payment_Ratio'] = A['Tot_Mdcr_Stdzd_Amt'] / (A['Tot_Mdcr_Pymt_Amt'] + eps)
A['Payment_per_Beneficiary']   = A['Tot_Mdcr_Pymt_Amt'] / (A['Tot_Benes'] + eps)
A['Charge_per_Beneficiary']    = A['Tot_Sbmtd_Chrg'] / (A['Tot_Benes'] + eps)
A['Payment_per_Service']       = A['Tot_Mdcr_Pymt_Amt'] / (A['Tot_Srvcs'] + eps)
A['Charge_per_Service']        = A['Tot_Sbmtd_Chrg'] / (A['Tot_Srvcs'] + eps)
A['Services_per_Beneficiary']  = A['Tot_Srvcs'] / (A['Tot_Benes'] + eps)
A['HCPCS_per_Beneficiary']     = A['Tot_HCPCS_Cds'] / (A['Tot_Benes'] + eps)
A['Drug_Service_Share']        = A['Drug_Tot_Srvcs'] / (A['Tot_Srvcs'] + eps)
A['Medical_Service_Share']     = A['Med_Tot_Srvcs'] / (A['Tot_Srvcs'] + eps)
A['Drug_Payment_Share']        = A['Drug_Mdcr_Pymt_Amt'] / (A['Tot_Mdcr_Pymt_Amt'] + eps)
A['Dual_Eligible_Ratio']       = A['Bene_Dual_Cnt'] / (A['Tot_Benes'] + eps)
A['Female_Beneficiary_Ratio']  = A['Bene_Feml_Cnt'] / (A['Tot_Benes'] + eps)

# recover categorical Provider Type / State from one-hot for peer grouping
def recover_cat(df, cols_group, prefix):
    sub = df[cols_group]
    out = sub.idxmax(axis=1).str.replace(prefix, '', regex=False)
    out[sub.sum(axis=1) == 0] = 'Unknown'
    return out

A['Provider_Type'] = recover_cat(A, type_cols, 'Rndrng_Prvdr_Type_')
A['Prvdr_State']   = recover_cat(A, state_cols, 'Rndrng_Prvdr_State_Abrvtn_')

print('Dataset A aggregated: ', A.shape, '| unique NPI:', A['NPI'].nunique())
A.to_pickle(f'{ART}/A_provider.pkl')

# =====================================================================
# B. SERVICE-LEVEL FEATURES (aggregate Provider & Service -> NPI)
# =====================================================================
psvc = pd.read_csv(f'{path}/data/provider/provider_service__cleaned.csv', low_memory=False)

def hhi(x):
    s = x.sum()
    if s <= 0: return np.nan
    p = x / s
    return float((p**2).sum())

grp = psvc.groupby('Rndrng_NPI')
Bsvc = pd.DataFrame({
    'Svc_Unique_HCPCS':        grp['HCPCS_Cd'].nunique(),
    'Svc_Total_Volume':        grp['Tot_Srvcs'].sum(),
    'Svc_Total_Benes':         grp['Tot_Benes'].sum(),
    'Svc_Rows':                grp.size(),
    'Svc_Num_Places':          grp['Place_Of_Srvc'].nunique(),
    'Svc_Num_Years':           grp['Year'].nunique(),
    'Svc_Avg_Sbmtd_Chrg':      grp['Avg_Sbmtd_Chrg'].mean(),
    'Svc_Avg_Mdcr_Pymt_Amt':   grp['Avg_Mdcr_Pymt_Amt'].mean(),
    'Svc_Avg_Payment_to_Charge': grp['Payment_to_Charge_Ratio'].mean(),
    'Svc_Drug_Service_Share':  grp.apply(lambda d: (d.loc[d.HCPCS_Drug_Ind=='Y','Tot_Srvcs'].sum()) / (d['Tot_Srvcs'].sum()+eps), include_groups=False),
    'Svc_HHI_Concentration':   grp['Tot_Srvcs'].apply(hhi),
    'Svc_Top_HCPCS_Share':     grp['Tot_Srvcs'].apply(lambda x: x.max()/(x.sum()+eps)),
})
Bsvc['Svc_Diversity_per_Volume'] = Bsvc['Svc_Unique_HCPCS'] / (Bsvc['Svc_Total_Volume'] + eps)
Bsvc.index.name = 'NPI'
Bsvc = Bsvc.reset_index()
Bsvc['has_service_detail'] = 1
print('Dataset B aggregated:', Bsvc.shape)
Bsvc.to_pickle(f'{ART}/B_service.pkl')

# =====================================================================
# C. GEOGRAPHIC / PEER BENCHMARKS from Dataset C, applied to Dataset B rows
# =====================================================================
geo = pd.read_csv(f'{path}/data/provider/provider_geography_cleaned.csv', low_memory=False)

STATE_NAME_TO_ABBR = {
 'Alabama':'AL','Alaska':'AK','Arizona':'AZ','Arkansas':'AR','California':'CA','Colorado':'CO','Connecticut':'CT',
 'Delaware':'DE','District of Columbia':'DC','Florida':'FL','Georgia':'GA','Hawaii':'HI','Idaho':'ID','Illinois':'IL',
 'Indiana':'IN','Iowa':'IA','Kansas':'KS','Kentucky':'KY','Louisiana':'LA','Maine':'ME','Maryland':'MD','Massachusetts':'MA',
 'Michigan':'MI','Minnesota':'MN','Mississippi':'MS','Missouri':'MO','Montana':'MT','Nebraska':'NE','Nevada':'NV',
 'New Hampshire':'NH','New Jersey':'NJ','New Mexico':'NM','New York':'NY','North Carolina':'NC','North Dakota':'ND',
 'Ohio':'OH','Oklahoma':'OK','Oregon':'OR','Pennsylvania':'PA','Rhode Island':'RI','South Carolina':'SC','South Dakota':'SD',
 'Tennessee':'TN','Texas':'TX','Utah':'UT','Vermont':'VT','Virginia':'VA','Washington':'WA','West Virginia':'WV',
 'Wisconsin':'WI','Wyoming':'WY','Puerto Rico':'PR','Virgin Islands':'VI','Guam':'GU','American Samoa':'AS',
 'Northern Mariana Islands':'MP'
}

geo_state = geo[geo['rndrng_prvdr_geo_lvl']=='State'].copy()
geo_state['state_abbr'] = geo_state['rndrng_prvdr_geo_desc'].map(STATE_NAME_TO_ABBR)
geo_state['bench_vol_per_provider']  = geo_state['tot_srvcs'] / geo_state['tot_rndrng_prvdrs'].replace(0,np.nan)
geo_state['bench_benes_per_provider']= geo_state['tot_benes'] / geo_state['tot_rndrng_prvdrs'].replace(0,np.nan)

# state+hcpcs+year benchmark, with (state+hcpcs) and national+hcpcs fallbacks
bench_syh = geo_state.groupby(['state_abbr','hcpcs_cd','year']).agg(
    b_pymt=('avg_mdcr_pymt_amt','mean'), b_chrg=('avg_sbmtd_chrg','mean'),
    b_vol_pp=('bench_vol_per_provider','mean')).reset_index()
bench_sh = geo_state.groupby(['state_abbr','hcpcs_cd']).agg(
    b_pymt=('avg_mdcr_pymt_amt','mean'), b_chrg=('avg_sbmtd_chrg','mean'),
    b_vol_pp=('bench_vol_per_provider','mean')).reset_index()
geo_nat = geo[geo['rndrng_prvdr_geo_lvl']=='National']
bench_nat = geo_nat.groupby('hcpcs_cd').agg(
    b_pymt=('avg_mdcr_pymt_amt','mean'), b_chrg=('avg_sbmtd_chrg','mean')).reset_index()

d = psvc.rename(columns={'Rndrng_Prvdr_State_Abrvtn':'state_abbr','HCPCS_Cd':'hcpcs_cd','Year':'year'})
d = d.merge(bench_syh, on=['state_abbr','hcpcs_cd','year'], how='left')
d['bench_level'] = np.where(d['b_pymt'].notna(), 'state_year', 'unmatched')
missing = d['b_pymt'].isna()
d2 = d.loc[missing, ['state_abbr','hcpcs_cd']].merge(bench_sh, on=['state_abbr','hcpcs_cd'], how='left')
d.loc[missing, ['b_pymt','b_chrg','b_vol_pp']] = d2[['b_pymt','b_chrg','b_vol_pp']].values
d.loc[missing & d['b_pymt'].notna(), 'bench_level'] = 'state'
still_missing = d['b_pymt'].isna()
d3 = d.loc[still_missing, ['hcpcs_cd']].merge(bench_nat, on='hcpcs_cd', how='left')
d.loc[still_missing, ['b_pymt','b_chrg']] = d3[['b_pymt','b_chrg']].values
d.loc[still_missing & d['b_pymt'].notna(), 'bench_level'] = 'national'

d['pymt_deviation'] = d['Avg_Mdcr_Pymt_Amt'] / (d['b_pymt'] + eps)
d['chrg_deviation']  = d['Avg_Sbmtd_Chrg'] / (d['b_chrg'] + eps)

peer = d.groupby('Rndrng_NPI').agg(
    Peer_Bench_Rows_Matched = ('b_pymt','count'),
    Peer_Avg_Pymt_Deviation = ('pymt_deviation','mean'),
    Peer_Max_Pymt_Deviation = ('pymt_deviation','max'),
    Peer_Avg_Chrg_Deviation = ('chrg_deviation','mean'),
    Peer_Pct_Services_Above_2x_Bench = ('pymt_deviation', lambda x: float((x>2).mean())),
).reset_index().rename(columns={'Rndrng_NPI':'NPI'})
print('Dataset C peer-deviation features:', peer.shape, '| matched rows:', d['b_pymt'].notna().sum(), '/', len(d))
peer.to_pickle(f'{ART}/C_peer.pkl')

# =====================================================================
# C2. GEOGRAPHIC EVIDENCE (per-provider, additive investigation evidence)
#     Reuses the SAME joined row-level frame `d` and the same benchmark
#     fallback chain (state+year -> state -> national) as the peer-deviation
#     features above, so the numbers are consistent with the model inputs.
#     This artifact is NOT part of the ML feature table; it exists only to
#     explain geo_deviation_score to the downstream Multi-Agent layer.
# =====================================================================
matched = d[d['b_pymt'].notna()]
geo_ev = matched.groupby('Rndrng_NPI').agg(
    Geo_Rows_Matched        = ('b_pymt','count'),
    Geo_Provider_Avg_Pymt   = ('Avg_Mdcr_Pymt_Amt','mean'),
    Geo_Bench_Pymt_Mean     = ('b_pymt','mean'),
    Geo_Bench_Pymt_Median   = ('b_pymt','median'),
    Geo_Bench_Pymt_Std      = ('b_pymt','std'),
    Geo_Provider_Avg_Chrg   = ('Avg_Sbmtd_Chrg','mean'),
    Geo_Bench_Chrg_Mean     = ('b_chrg','mean'),
    Geo_Bench_Chrg_Median   = ('b_chrg','median'),
    Geo_Bench_Chrg_Std      = ('b_chrg','std'),
).reset_index().rename(columns={'Rndrng_NPI':'NPI'})
# benchmark coverage by fallback level used for each provider row
lvl = pd.crosstab(d['Rndrng_NPI'], d['bench_level']).reset_index().rename(columns={'Rndrng_NPI':'NPI'})
for lv in ['state_year','state','national']:
    lvl[f'Geo_Rows_{lv}'] = lvl.get(lv, 0)
geo_ev = geo_ev.merge(lvl[['NPI','Geo_Rows_state_year','Geo_Rows_state','Geo_Rows_national']], on='NPI', how='left')
print('Dataset C2 geo evidence:', geo_ev.shape, '| providers with >=1 matched geo row:', matched['Rndrng_NPI'].nunique())
geo_ev.to_pickle(f'{ART}/D_geo_evidence.pkl')

# =====================================================================
# D. TEMPORAL EVIDENCE (per-provider year context, additive, NOT model input)
#     Reuses the raw NPI x Year rows of Dataset A (provider-cleaned.csv) that
#     s2 already aggregates. Year_First / Year_Last / Num_Years_Observed are
#     already in A; here we additionally expose first-vs-last year levels and
#     year-over-year growth % for the three core utilization/payment metrics.
# =====================================================================
tm = prov[['Rndrng_NPI','Year','Tot_Srvcs','Tot_Mdcr_Pymt_Amt','Tot_Benes']].copy()
tm = tm.sort_values('Year')
tm_first = tm.groupby('Rndrng_NPI').first().reset_index()
tm_last  = tm.groupby('Rndrng_NPI').last().reset_index()
temporal = pd.DataFrame({'NPI': tm_first['Rndrng_NPI']})
temporal['Svc_First_Year']   = tm_first['Tot_Srvcs'].values
temporal['Svc_Last_Year']    = tm_last['Tot_Srvcs'].values
temporal['Pymt_First_Year']  = tm_first['Tot_Mdcr_Pymt_Amt'].values
temporal['Pymt_Last_Year']   = tm_last['Tot_Mdcr_Pymt_Amt'].values
temporal['Benes_First_Year'] = tm_first['Tot_Benes'].values
temporal['Benes_Last_Year']  = tm_last['Tot_Benes'].values
def _growth(first_col, last_col, out_col):
    f = temporal[first_col]
    l = temporal[last_col]
    temporal[out_col] = np.where(f > 0, (l - f) / f * 100.0, np.nan)
_growth('Svc_First_Year',   'Svc_Last_Year',   'Svc_Growth_Pct')
_growth('Pymt_First_Year',  'Pymt_Last_Year',  'Pymt_Growth_Pct')
_growth('Benes_First_Year', 'Benes_Last_Year', 'Benes_Growth_Pct')
print('Dataset D temporal evidence:', temporal.shape, '| providers with >1 year:', (tm.groupby('Rndrng_NPI').size() > 1).sum())
temporal.to_pickle(f'{ART}/D_temporal_evidence.pkl')

# =====================================================================
# UNIFIED PROVIDER FEATURE TABLE (one row per NPI)
# =====================================================================
unified = A.merge(Bsvc, on='NPI', how='left').merge(peer, on='NPI', how='left')
unified['has_service_detail'] = unified['has_service_detail'].fillna(0)
for c in ['Peer_Bench_Rows_Matched']:
    unified[c] = unified[c].fillna(0)
print('\nUNIFIED provider feature table:', unified.shape, '| one row per NPI:', unified['NPI'].is_unique)
unified.to_pickle(f'{ART}/unified_features.pkl')
unified.to_csv(f'{ART}/unified_features_preview.csv', index=False)
print(unified[['NPI','Provider_Type','Prvdr_State','Tot_Benes','Tot_Srvcs','Payment_per_Service','has_service_detail']].head())
