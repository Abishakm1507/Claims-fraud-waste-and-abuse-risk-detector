"""Inspect claims ML artifacts - concise version."""
import joblib
import pandas as pd
import os

base = "models/claims"

for claim_type in ["carrier", "inpatient", "outpatient"]:
    path = os.path.join(base, claim_type)
    print(f"\n{'='*60}")
    print(f"{claim_type.upper()}: {path}")
    print(f"{'='*60}")
    if not os.path.exists(path):
        print("  MISSING")
        continue
    for f in sorted(os.listdir(path)):
        fpath = os.path.join(path, f)
        print(f"  {f} ({os.path.getsize(fpath):,} bytes)")

    # feature_columns
    fc_path = os.path.join(path, "feature_columns.pkl")
    if os.path.exists(fc_path):
        fc = joblib.load(fc_path)
        print(f"\n  feature_columns: type={type(fc).__name__}, len={len(fc) if hasattr(fc, '__len__') else 'N/A'}")
        if isinstance(fc, list):
            for i, n in enumerate(fc):
                print(f"    [{i}] {n}")

    # scaler
    sc_path = os.path.join(path, "scaler.pkl")
    if os.path.exists(sc_path):
        sc = joblib.load(sc_path)
        print(f"\n  scaler: type={type(sc).__name__}")
        print(f"    n_features_in_: {getattr(sc, 'n_features_in_', 'N/A')}")
        if hasattr(sc, 'feature_names_in_'):
            print(f"    feature_names_in_: {list(sc.feature_names_in_)}")

    # isolation forest
    if_path = os.path.join(path, "isolation_forest.pkl")
    if os.path.exists(if_path):
        m = joblib.load(if_path)
        print(f"\n  isolation_forest: type={type(m).__name__}")
        print(f"    n_features_in_: {getattr(m, 'n_features_in_', 'N/A')}")
        print(f"    n_estimators: {getattr(m, 'n_estimators', 'N/A')}")

    # lof
    lof_path = os.path.join(path, "lof.pkl")
    if not os.path.exists(lof_path):
        lof_path = os.path.join(path, "lof .pkl")
    if os.path.exists(lof_path):
        lm = joblib.load(lof_path)
        print(f"\n  lof: type={type(lm).__name__}")
        print(f"    n_features_in_: {getattr(lm, 'n_features_in_', 'N/A')}")

    # ocsvm
    oc_path = os.path.join(path, "ocsvm.pkl")
    if os.path.exists(oc_path):
        om = joblib.load(oc_path)
        print(f"\n  ocsvm: type={type(om).__name__}")
        print(f"    n_features_in_: {getattr(om, 'n_features_in_', 'N/A')}")

    # model config
    mc_path = os.path.join(path, "model_config.pkl")
    if os.path.exists(mc_path):
        cfg = joblib.load(mc_path)
        print(f"\n  model_config: {cfg}")

    # risk scores csv
    csv_name = f"{claim_type}_final_risk_scores.csv"
    csv_path = os.path.join(path, csv_name)
    if os.path.exists(csv_path):
        df = pd.read_csv(csv_path, low_memory=False)
        print(f"\n  {csv_name}: {len(df)} rows, {len(df.columns)} cols")
        print(f"    Columns: {list(df.columns)}")
    else:
        print(f"\n  {csv_name}: MISSING")

print("\nUnified file check:")
unified_path = os.path.join(base, "unified_claim_risk_with_provider.csv")
if os.path.exists(unified_path):
    df = pd.read_csv(unified_path, low_memory=False)
    print(f"  Rows: {len(df)}, Cols: {len(df.columns)}")
    print(f"  CLAIM_TYPE counts:")
    print(df['CLAIM_TYPE'].value_counts())
    print(f"  Columns: {list(df.columns)}")