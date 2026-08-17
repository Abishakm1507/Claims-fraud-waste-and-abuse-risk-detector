import pandas as pd, numpy as np, json

pd.set_option('display.width', 140)
path='D:/GitHub/cognizant-hackathon/Claims-fraud-waste-and-abuse-risk-detector'
OUT = f'{path}/models/provider/artifacts'

def profile(df, name):
    rep = {
        'rows': len(df), 'cols': df.shape[1],
        'dupe_rows': int(df.duplicated().sum()),
        'n_numeric': int(df.select_dtypes(include=np.number).shape[1]),
        'n_object': int(df.select_dtypes(include='object').shape[1]),
    }
    miss = df.isna().mean().sort_values(ascending=False)
    rep['top_missing'] = {k: round(float(v),4) for k,v in miss[miss>0].head(15).items()}
    print(f"--- {name} ---")
    print(rep)
    return rep

report = {}

prov = pd.read_csv(f'{path}/data/provider/provider-cleaned.csv')
report['provider'] = profile(prov, 'Dataset A: provider-cleaned (By Provider)')
print('unique NPI:', prov['Rndrng_NPI'].nunique(), '| rows with dup NPI (multi-year):', (prov.groupby('Rndrng_NPI').size()>1).sum())
print('Year range:', prov['Year'].min(), prov['Year'].max())

psvc = pd.read_csv(f'{path}/data/provider/provider_service__cleaned.csv')
report['provider_service'] = profile(psvc, 'Dataset B: provider_service (By Provider & Service)')
print('unique NPI:', psvc['Rndrng_NPI'].nunique(), '| unique HCPCS:', psvc['HCPCS_Cd'].nunique())
print('Year range:', psvc['Year'].min(), psvc['Year'].max())

geo = pd.read_csv(f'{path}/data/provider/provider_geography_cleaned.csv')
report['geo'] = profile(geo, 'Dataset C: geography_service (By Geography & Service)')
print('geo levels:', geo['rndrng_prvdr_geo_lvl'].unique(), '| unique states:', geo.loc[geo.rndrng_prvdr_geo_lvl=='State','rndrng_prvdr_geo_desc'].nunique())
print('Year range:', geo['year'].min(), geo['year'].max())

leie = pd.read_csv(f'{path}/data/provider/LEIE-cleaned.csv')
report['leie'] = profile(leie, 'LEIE Exclusion list (validation only, NOT a training label)')

# ---- Identifier / granularity compatibility notes ----
notes = []
notes.append("Dataset A (provider-cleaned) granularity = NPI x Year, NOT one row per NPI as originally assumed. "
              f"{int((prov.groupby('Rndrng_NPI').size()>1).sum())} of {prov['Rndrng_NPI'].nunique()} NPIs have multiple year rows. "
              "MUST aggregate across years before use as the primary provider table.")
notes.append("Dataset A is already heavily pre-engineered (367 cols): includes log-transforms, ratios, and one-hot encoded "
              "State/RUCA/Provider-Type/Participation/Suppression indicators. Raw counts must be re-summed across years and "
              "ratios/logs recomputed post-aggregation rather than averaged, to keep them mathematically valid.")
notes.append(f"Dataset B (provider_service) covers only {psvc['Rndrng_NPI'].nunique()} unique NPIs (row-level = NPI x HCPCS x Year), "
              f"of which only {len(set(prov['Rndrng_NPI']).intersection(set(psvc['Rndrng_NPI'])))} overlap with Dataset A's NPI set. "
              "Coverage is partial -- providers without Dataset B rows will get NaN/0-filled service features plus a "
              "has_service_detail=0 flag; they are not dropped.")
notes.append("Dataset C (geography_service) is at (State or National) x HCPCS x Year granularity, with tot_rndrng_prvdrs "
              "letting us derive a *per-provider* peer benchmark (tot_srvcs/tot_rndrng_prvdrs, tot_benes/tot_rndrng_prvdrs) "
              "for volume, plus avg_mdcr_pymt_amt / avg_sbmtd_chrg as price benchmarks. Provider-level rows in Dataset B carry "
              "Rndrng_Prvdr_State_Abrvtn (postal code, e.g. 'MD') while Dataset C carries full state names (e.g. 'Maryland') -- "
              "these are NOT directly joinable and require a state abbreviation<->name crosswalk before merging.")
notes.append("Dataset A's Year values (2021-2024) and Dataset B/C's Year values (2020-2023) only partially overlap. "
              "Benchmarks are computed per (State, HCPCS, Year) where possible, falling back to (State, HCPCS) pooled across "
              "years, and finally to the National row for that HCPCS, when a state/year cell is unavailable -- documented, not silently forced.")
notes.append("LEIE has only 15 NPIs overlapping the provider set. It is used ONLY as a post-hoc sanity check on the final "
              "risk score distribution (do excluded providers skew toward higher scores?) and is never used as a label, "
              "feature, or target for the unsupervised models.")

with open(f'{OUT}/validation_notes.json','w') as f:
    json.dump({'report':report,'notes':notes}, f, indent=2, default=str)

print("\n=== COMPATIBILITY NOTES ===")
for n in notes: print('-', n)
