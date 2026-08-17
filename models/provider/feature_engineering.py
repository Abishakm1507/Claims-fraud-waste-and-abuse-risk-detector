"""
Provider-level feature engineering for the CMS provider-service anomaly detection model.
Converts provider-service (npi x hcpcs x year x place-of-service) grain data
into ONE ROW PER PROVIDER (NPI) with behavioral, financial, service-mix,
temporal, and peer-comparison features.

This module is imported both by the training script and by predict_provider.py
at inference time, so feature engineering logic used in training is exactly
reproduced at inference.
"""
import numpy as np
import pandas as pd

NUM_COLS = ['Tot_Benes', 'Tot_Srvcs', 'Tot_Bene_Day_Srvcs',
            'Avg_Sbmtd_Chrg', 'Avg_Mdcr_Alowd_Amt', 'Avg_Mdcr_Pymt_Amt', 'Avg_Mdcr_Stdzd_Amt']


def load_raw_provider_service(paths_by_year: dict) -> pd.DataFrame:
    """Load and concatenate raw CMS provider-service CSVs for multiple years."""
    dfs = []
    for year, path in paths_by_year.items():
        d = pd.read_csv(path, dtype=str, low_memory=False)
        d['year_loaded'] = int(year)
        dfs.append(d)
    df = pd.concat(dfs, ignore_index=True)
    for c in NUM_COLS:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    return df


def _hhi(shares):
    """Herfindahl-Hirschman Index of concentration (0-1 scale, since shares sum to 1)."""
    return float(np.sum(np.square(shares)))


def build_provider_year_table(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate provider-service rows to provider x year grain first
    (sums across HCPCS codes and places of service within a year)."""
    df = df.copy()
    df['submitted_charge_total'] = df['Avg_Sbmtd_Chrg'] * df['Tot_Srvcs']
    df['allowed_amt_total'] = df['Avg_Mdcr_Alowd_Amt'] * df['Tot_Srvcs']
    df['payment_total'] = df['Avg_Mdcr_Pymt_Amt'] * df['Tot_Srvcs']
    df['stdzd_amt_total'] = df['Avg_Mdcr_Stdzd_Amt'] * df['Tot_Srvcs']
    df['is_drug'] = (df['HCPCS_Drug_Ind'] == 'Y').astype(int)
    df['drug_services'] = np.where(df['is_drug'] == 1, df['Tot_Srvcs'], 0)
    df['drug_payment'] = np.where(df['is_drug'] == 1, df['payment_total'], 0)

    grp = df.groupby(['Rndrng_NPI', 'year_loaded'])
    py = grp.agg(
        provider_type=('Rndrng_Prvdr_Type', 'first'),
        entity_code=('Rndrng_Prvdr_Ent_Cd', 'first'),
        state=('Rndrng_Prvdr_State_Abrvtn', 'first'),
        ruca=('Rndrng_Prvdr_RUCA', 'first'),
        n_hcpcs=('HCPCS_Cd', 'nunique'),
        n_service_rows=('HCPCS_Cd', 'count'),
        n_place_of_service=('Place_Of_Srvc', 'nunique'),
        total_services=('Tot_Srvcs', 'sum'),
        total_beneficiaries=('Tot_Benes', 'sum'),
        total_bene_day_services=('Tot_Bene_Day_Srvcs', 'sum'),
        total_submitted_charge=('submitted_charge_total', 'sum'),
        total_allowed_amt=('allowed_amt_total', 'sum'),
        total_payment=('payment_total', 'sum'),
        total_stdzd_amt=('stdzd_amt_total', 'sum'),
        total_drug_services=('drug_services', 'sum'),
        total_drug_payment=('drug_payment', 'sum'),
    ).reset_index().rename(columns={'Rndrng_NPI': 'npi', 'year_loaded': 'year'})

    # HCPCS service-mix concentration (HHI) per provider-year, computed from service shares
    hcpcs_shares = (df.groupby(['Rndrng_NPI', 'year_loaded', 'HCPCS_Cd'])['Tot_Srvcs'].sum()
                     .reset_index())
    tot = hcpcs_shares.groupby(['Rndrng_NPI', 'year_loaded'])['Tot_Srvcs'].transform('sum')
    hcpcs_shares['share'] = hcpcs_shares['Tot_Srvcs'] / tot
    hhi = (hcpcs_shares.groupby(['Rndrng_NPI', 'year_loaded'])['share']
           .apply(lambda s: _hhi(s.values)).reset_index()
           .rename(columns={'share': 'hcpcs_hhi', 'Rndrng_NPI': 'npi', 'year_loaded': 'year'}))
    top_share = (hcpcs_shares.groupby(['Rndrng_NPI', 'year_loaded'])['share'].max()
                 .reset_index().rename(columns={'share': 'top_hcpcs_share', 'Rndrng_NPI': 'npi', 'year_loaded': 'year'}))

    py = py.merge(hhi, on=['npi', 'year'], how='left')
    py = py.merge(top_share, on=['npi', 'year'], how='left')

    # derived ratios (guard div by zero -> NaN, handled later by imputer)
    py['services_per_beneficiary'] = py['total_services'] / py['total_beneficiaries'].replace(0, np.nan)
    py['services_per_hcpcs'] = py['total_services'] / py['n_hcpcs'].replace(0, np.nan)
    py['payment_per_service'] = py['total_payment'] / py['total_services'].replace(0, np.nan)
    py['charge_per_service'] = py['total_submitted_charge'] / py['total_services'].replace(0, np.nan)
    py['payment_to_charge_ratio'] = py['total_payment'] / py['total_submitted_charge'].replace(0, np.nan)
    py['allowed_to_charge_ratio'] = py['total_allowed_amt'] / py['total_submitted_charge'].replace(0, np.nan)
    py['stdzd_to_payment_ratio'] = py['total_stdzd_amt'] / py['total_payment'].replace(0, np.nan)
    py['drug_service_share'] = py['total_drug_services'] / py['total_services'].replace(0, np.nan)
    py['drug_payment_share'] = py['total_drug_payment'] / py['total_payment'].replace(0, np.nan)
    py['medical_payment_share'] = 1 - py['drug_payment_share']
    py['bene_day_to_service_ratio'] = py['total_bene_day_services'] / py['total_services'].replace(0, np.nan)
    return py


def build_provider_level_features(py: pd.DataFrame) -> pd.DataFrame:
    """From the provider x year table, build ONE ROW PER PROVIDER with
    latest-year snapshot, multi-year averages, and year-over-year trend features."""
    py = py.sort_values(['npi', 'year'])
    latest_year = py['year'].max()

    latest = py[py['year'] == latest_year].copy()
    latest_cols = ['npi', 'provider_type', 'entity_code', 'state', 'ruca',
                   'n_hcpcs', 'n_place_of_service',
                   'total_services', 'total_beneficiaries', 'total_bene_day_services',
                   'total_submitted_charge', 'total_allowed_amt', 'total_payment', 'total_stdzd_amt',
                   'services_per_beneficiary', 'services_per_hcpcs',
                   'payment_per_service', 'charge_per_service',
                   'payment_to_charge_ratio', 'allowed_to_charge_ratio', 'stdzd_to_payment_ratio',
                   'drug_service_share', 'drug_payment_share', 'medical_payment_share',
                   'hcpcs_hhi', 'top_hcpcs_share', 'bene_day_to_service_ratio']
    latest = latest[latest_cols].copy()
    latest.columns = ['npi'] + [f'latest_{c}' if c not in
                                 ('provider_type', 'entity_code', 'state', 'ruca') else c
                                 for c in latest_cols[1:]]

    # multi-year averages (across all years present for the provider)
    avg_metrics = ['total_services', 'total_beneficiaries', 'total_payment', 'total_submitted_charge',
                   'services_per_beneficiary', 'payment_per_service', 'payment_to_charge_ratio',
                   'drug_payment_share', 'hcpcs_hhi']
    avg = py.groupby('npi')[avg_metrics].mean().reset_index()
    avg.columns = ['npi'] + [f'avg_{c}' for c in avg_metrics]

    # n years active + span
    activity = py.groupby('npi').agg(
        n_years_active=('year', 'nunique'),
        first_year=('year', 'min'),
        last_year=('year', 'max'),
    ).reset_index()
    activity['years_active_span'] = activity['last_year'] - activity['first_year'] + 1
    activity['is_continuous_active'] = (activity['n_years_active'] == activity['years_active_span']).astype(int)

    # year-over-year growth: compare latest year vs prior year (if present), else vs first year
    def yoy_features(g):
        g = g.sort_values('year')
        out = {}
        if len(g) >= 2:
            prev = g.iloc[-2]
            curr = g.iloc[-1]
            out['yoy_payment_change'] = _pct_change(prev['total_payment'], curr['total_payment'])
            out['yoy_service_change'] = _pct_change(prev['total_services'], curr['total_services'])
            out['yoy_beneficiary_change'] = _pct_change(prev['total_beneficiaries'], curr['total_beneficiaries'])
            out['yoy_payment_per_service_change'] = _pct_change(prev['payment_per_service'], curr['payment_per_service'])
        else:
            out['yoy_payment_change'] = 0.0
            out['yoy_service_change'] = 0.0
            out['yoy_beneficiary_change'] = 0.0
            out['yoy_payment_per_service_change'] = 0.0
        # overall trend: latest vs first year on record (captures multi-year drift even with gaps)
        first, last = g.iloc[0], g.iloc[-1]
        out['trend_payment_change'] = _pct_change(first['total_payment'], last['total_payment'])
        out['trend_service_change'] = _pct_change(first['total_services'], last['total_services'])
        return pd.Series(out)

    yoy = py.groupby('npi').apply(yoy_features, include_groups=False).reset_index()

    feat = latest.merge(avg, on='npi', how='left') \
                 .merge(activity, on='npi', how='left') \
                 .merge(yoy, on='npi', how='left')
    return feat


def _pct_change(prev, curr):
    if pd.isna(prev) or pd.isna(curr):
        return np.nan
    if prev == 0:
        return np.nan if curr == 0 else 1.0  # cap growth-from-zero as +100% flag rather than inf
    return (curr - prev) / abs(prev)


def add_peer_deviation_features(feat: pd.DataFrame) -> pd.DataFrame:
    """Compare each provider to peers of the same provider_type (specialty) on
    key metrics; add deviation-from-peer-median features. Falls back gracefully
    for peer groups too small to be meaningful (min group size = 5)."""
    feat = feat.copy()
    peer_metrics = ['latest_services_per_beneficiary', 'latest_payment_per_service',
                     'latest_charge_per_service', 'latest_payment_to_charge_ratio',
                     'latest_hcpcs_hhi', 'latest_drug_payment_share']

    group_sizes = feat.groupby('provider_type')['npi'].transform('count')
    for m in peer_metrics:
        med = feat.groupby('provider_type')[m].transform('median')
        mad = feat.groupby('provider_type')[m].transform(lambda s: (s - s.median()).abs().median())
        mad_safe = mad.replace(0, np.nan)
        dev = (feat[m] - med) / mad_safe
        # only compute peer deviation where the peer group is large enough (>=5) to be meaningful
        col = np.where(group_sizes >= 5, dev, 0.0)
        feat[f'peer_dev_{m}'] = col
        # sparse feature -> explicit missingness indicator BEFORE imputation, per spec
        feat[f'peer_dev_{m}_missing'] = feat[f'peer_dev_{m}'].isna().astype(int)
    return feat


FINAL_FEATURE_COLUMNS = [
    # utilization
    'latest_total_services', 'latest_total_beneficiaries', 'latest_n_hcpcs',
    'latest_services_per_beneficiary', 'latest_services_per_hcpcs', 'latest_n_place_of_service',
    'latest_bene_day_to_service_ratio',
    # financial
    'latest_total_submitted_charge', 'latest_total_payment',
    'latest_payment_per_service', 'latest_charge_per_service',
    'latest_payment_to_charge_ratio', 'latest_allowed_to_charge_ratio', 'latest_stdzd_to_payment_ratio',
    # service mix
    'latest_drug_service_share', 'latest_drug_payment_share',
    'latest_hcpcs_hhi',
    # multi-year averages
    'avg_total_services', 'avg_total_payment', 'avg_services_per_beneficiary',
    'avg_payment_per_service', 'avg_payment_to_charge_ratio', 'avg_drug_payment_share', 'avg_hcpcs_hhi',
    # temporal / trend
    'n_years_active', 'is_continuous_active',
    'yoy_payment_change', 'yoy_service_change', 'yoy_beneficiary_change', 'yoy_payment_per_service_change',
    'trend_payment_change', 'trend_service_change',
    # peer deviation (+ missingness indicators for the two sparse peer-deviation features,
    # created BEFORE imputation since these features are frequently unavailable when a
    # provider's peer group has zero variation on that metric)
    'peer_dev_latest_services_per_beneficiary', 'peer_dev_latest_payment_per_service',
    'peer_dev_latest_charge_per_service', 'peer_dev_latest_payment_to_charge_ratio',
    'peer_dev_latest_hcpcs_hhi', 'peer_dev_latest_hcpcs_hhi_missing',
    'peer_dev_latest_drug_payment_share', 'peer_dev_latest_drug_payment_share_missing',
]
# Removed as redundant during feature-selection review (Step 5):
#   latest_medical_payment_share  -> perfectly collinear with latest_drug_payment_share (r=1.00; 1-x duplicate)
#   latest_top_hcpcs_share        -> near-duplicate concentration measure of latest_hcpcs_hhi (r=0.98)
#   first_year / last_year        -> raw calendar identifiers, not behavioral signal (redundant with n_years_active/trend feats)


def engineer_provider_features(paths_by_year: dict) -> pd.DataFrame:
    """End-to-end: raw CSVs -> provider-level feature table (with npi, provider_type,
    state kept as reference columns alongside the FINAL_FEATURE_COLUMNS ML matrix)."""
    raw = load_raw_provider_service(paths_by_year)
    py = build_provider_year_table(raw)
    feat = build_provider_level_features(py)
    feat = add_peer_deviation_features(feat)
    return feat
