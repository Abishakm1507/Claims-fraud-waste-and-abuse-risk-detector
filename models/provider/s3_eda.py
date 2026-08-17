import pandas as pd, numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
path='D:/GitHub/cognizant-hackathon/Claims-fraud-waste-and-abuse-risk-detector'
ART = f'{path}/models/provider/artifacts'
U = pd.read_pickle(f'{ART}/unified_features.pkl')

key_num = ['Tot_Benes','Tot_Srvcs','Tot_Sbmtd_Chrg','Tot_Mdcr_Pymt_Amt','Payment_per_Service',
           'Charge_per_Service','Services_per_Beneficiary','Payment_to_Charge_Ratio',
           'Svc_Unique_HCPCS','Svc_HHI_Concentration','Svc_Top_HCPCS_Share',
           'Peer_Avg_Pymt_Deviation','Peer_Pct_Services_Above_2x_Bench']

desc = U[key_num].describe().T
desc['skew'] = U[key_num].skew()
desc.to_csv(f'{ART}/eda_summary_stats.csv')
print(desc[['mean','std','min','50%','max','skew']])

# extreme value / plausibility checks (NOT dropped, just flagged)
flags = pd.DataFrame({'NPI': U['NPI']})
flags['flag_zero_benes_pos_pymt'] = (U['Tot_Benes']<=0) & (U['Tot_Mdcr_Pymt_Amt']>0)
flags['flag_pymt_gt_charge'] = U['Tot_Mdcr_Pymt_Amt'] > U['Tot_Sbmtd_Chrg']
flags['flag_negative_values'] = (U[['Tot_Benes','Tot_Srvcs','Tot_Sbmtd_Chrg','Tot_Mdcr_Pymt_Amt']] < 0).any(axis=1)
print('\nData-quality flag counts:')
print(flags.drop(columns='NPI').sum())
flags.to_csv(f'{ART}/dq_flags.csv', index=False)

# log-transform highly skewed positive financial/utilization vars (name them explicitly, keep originals)
to_log = ['Tot_Benes','Tot_Srvcs','Tot_Sbmtd_Chrg','Tot_Mdcr_Pymt_Amt','Payment_per_Service',
          'Charge_per_Service','Svc_Total_Volume','Svc_Unique_HCPCS']
for c in to_log:
    if c in U.columns:
        U[f'log1p_{c}'] = np.log1p(U[c].clip(lower=0))

# skew comparison before/after log
skew_report = pd.DataFrame({
    'raw_skew': U[to_log].skew(),
    'log_skew': U[[f'log1p_{c}' for c in to_log]].skew().set_axis(to_log)
})
print('\nSkew reduction from log1p transform:\n', skew_report)
skew_report.to_csv(f'{ART}/eda_skew_reduction.csv')

# distribution plots
fig, axes = plt.subplots(2, 4, figsize=(20,9))
for ax, c in zip(axes.flat, to_log):
    ax.hist(np.log1p(U[c].clip(lower=0)), bins=60, color='#3B6E8F')
    ax.set_title(f'log1p({c})')
plt.tight_layout(); plt.savefig(f'{ART}/eda_distributions.png', dpi=110); plt.close()

# correlation heatmap (log-space, key vars)
corr_cols = [f'log1p_{c}' for c in to_log] + ['Payment_to_Charge_Ratio','Services_per_Beneficiary',
             'Svc_HHI_Concentration','Peer_Avg_Pymt_Deviation']
corr = U[corr_cols].corr()
fig, ax = plt.subplots(figsize=(10,8))
im = ax.imshow(corr, cmap='RdBu_r', vmin=-1, vmax=1)
ax.set_xticks(range(len(corr_cols))); ax.set_xticklabels(corr_cols, rotation=90, fontsize=8)
ax.set_yticks(range(len(corr_cols))); ax.set_yticklabels(corr_cols, fontsize=8)
plt.colorbar(im); plt.title('Feature correlation (log-space)'); plt.tight_layout()
plt.savefig(f'{ART}/eda_correlation.png', dpi=110); plt.close()

# by provider type: median payment per service (top 15 by count)
top_types = U['Provider_Type'].value_counts().head(15).index
byt = U[U['Provider_Type'].isin(top_types)].groupby('Provider_Type')['Payment_per_Service'].median().sort_values()
fig, ax = plt.subplots(figsize=(8,6))
byt.plot.barh(ax=ax, color='#3B6E8F'); ax.set_xlabel('Median Payment per Service ($)')
plt.tight_layout(); plt.savefig(f'{ART}/eda_by_provider_type.png', dpi=110); plt.close()

U.to_pickle(f'{ART}/unified_features_logged.pkl')
print('\nSaved EDA artifacts: eda_summary_stats.csv, eda_skew_reduction.csv, dq_flags.csv, eda_distributions.png, eda_correlation.png, eda_by_provider_type.png')
