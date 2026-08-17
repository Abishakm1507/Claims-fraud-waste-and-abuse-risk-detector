# Provider Risk-Detection Model — Methodology & Results

**Model:** Isolation Forest (unsupervised anomaly detection)
**Scope:** Provider-level billing/service anomaly detection for investigation prioritization
**Training data:** Updated ETL dataset (2020–2024), rebuilt from `raw/cms_provider_service_2020.csv` … `cms_provider_service_2024.csv`
**This model does NOT predict confirmed fraud.** It flags providers whose billing/service behavior is statistically unusual relative to their peers, for human investigation.

---

## 1. Dataset Summary

The uploaded ETL package (`data.zip`) contains a `raw/ → interim/ → curated/` pipeline. The provider-service source files (`raw/cms_provider_service_2020.csv` … `2024.csv`) are the standard CMS Medicare Physician & Other Practitioners public-use file format and are the exact source of the package's own `curated/fact_provider_service.parquet` table (row counts match the package's `reports/quality_report.json` exactly). These raw CSVs were used directly for training, since they are the most granular, verifiable form of the data.

| Check | Result |
|---|---|
| Files loaded | 5 (`cms_provider_service_2020.csv` … `2024.csv`) |
| Total rows | 101,739 |
| Unique providers (NPI) | 2,813 |
| Years available | 2020, 2021, 2022, 2023, 2024 |
| Grain | one row per (NPI, HCPCS code, year, place of service) |
| Duplicate full rows | 0 |
| Duplicate grain keys | 0 (grain is clean — safe to aggregate) |
| Data types | all numeric fields (`Tot_Benes`, `Tot_Srvcs`, `Avg_Sbmtd_Chrg`, `Avg_Mdcr_Alowd_Amt`, `Avg_Mdcr_Pymt_Amt`, `Avg_Mdcr_Stdzd_Amt`, etc.) loaded as strings and cast to numeric; no coercion failures |
| Missing values | low overall; highest are non-analytic identity fields — `Rndrng_Prvdr_St2` (70.7% missing, a secondary address line), `Rndrng_Prvdr_MI` (31.6%, middle initial), `Rndrng_Prvdr_Crdntls` (7.0%) — none of the numeric billing fields used in modeling have missing values |
| Negative values | none found in any billing/utilization column |
| NPI format | all 2,813 NPIs are valid 10-digit numeric identifiers |
| Entity type | 98,526 rows = Individual providers ("I"), 3,213 rows = Organizations ("O") |

**Conclusion:** the data is clean at the provider-service grain and can safely be aggregated to one row per provider (NPI).

An LEIE (List of Excluded Individuals/Entities) reference file (`raw/leie_updated_202608.csv`) was also loaded for the external reference check in Step 8 (8,660 unique valid NPIs with exclusions, out of 83,842 total LEIE records — most LEIE records have no NPI on file).

---

## 2. Provider-Level Aggregation Methodology

Provider-service rows were first aggregated to **provider × year**, summing services/payments across HCPCS codes and places of service within each year, and computing that year's derived ratios and HCPCS concentration (HHI). This provider-year table was then collapsed to **one row per provider (NPI)** using three complementary views:

1. **Latest-year snapshot** (`latest_*`): the provider's most recent year of activity in the dataset (2024 for currently active providers).
2. **Multi-year averages** (`avg_*`): mean of each metric across all years the provider has data for.
3. **Temporal/trend features**: year-over-year change (latest year vs. immediately prior year) and overall multi-year trend (latest year vs. first year on record), plus activity-continuity indicators (`n_years_active`, `is_continuous_active`).

**Scored population:** 2,368 of the 2,813 total providers have a 2024 (latest-year) record and were scored. The remaining 445 NPIs appear only in earlier years (2020–2023) and were excluded from current-risk scoring, since "latest year" behavioral features cannot be computed for them. This is a deliberate design choice to prioritize *currently active* providers for investigation; see Limitations.

---

## 3. Feature Engineering

Features were engineered across five categories, following the brief's guidance, using only fields available in the dataset:

- **Utilization:** total services, total beneficiaries, services per beneficiary, unique HCPCS codes used, services per HCPCS code, places of service, beneficiary-day-to-service ratio.
- **Financial:** total submitted charges, total Medicare payment, payment per service, charge per service, payment-to-charge ratio, allowed-to-charge ratio, standardized-amount-to-payment ratio.
- **Service mix:** drug service share, drug payment share, HCPCS concentration (Herfindahl-Hirschman Index).
- **Temporal:** year-over-year payment/service/beneficiary/payment-per-service change; multi-year payment and service trend; years active; activity continuity.
- **Peer features:** deviation from same-specialty (`provider_type`) peer median, using a robust median/MAD normalization (peer groups smaller than 5 providers are excluded from deviation scoring to avoid meaningless comparisons).

*(Beneficiary risk-score and dual-eligible-ratio features from the brief were not available in this dataset and were therefore omitted rather than fabricated. Geographic peer comparison beyond state was limited by the dataset's geographic granularity and was represented via the `state` reference field rather than a full geo-benchmark feature, since `fact_geo_benchmark` required parquet tooling not available in this environment — see Limitations.)*

---

## 4. Preprocessing

A deterministic, reusable `sklearn.pipeline.Pipeline` was built:

1. **`SimpleImputer(strategy="median")`** — fills missing values (only the two sparse peer-deviation features have missingness; explicit `_missing` indicator columns were created for those **before** imputation, per the brief).
2. **`Winsorizer(lower_pct=1, upper_pct=99)`** — a custom transformer (`provider_preprocessing.py`) that clips extreme values to the 1st/99th percentile learned at fit time, protecting the scaler and distance-based comparison models from long-tailed billing outliers without discarding rows.
3. **`RobustScaler()`** — median/IQR-based scaling, robust to the remaining outliers.

The **exact feature order** used in training is saved verbatim in `provider_feature_columns.json` and is enforced at inference time by `predict_provider.py`.

---

## 5. Feature Selection

| Metric | Count |
|---|---|
| Total engineered features (before selection) | 42 |
| Features removed as redundant | 4 |
| **Final ML feature count** | **40** |

Removed features and reason:
- `latest_medical_payment_share` — perfectly collinear with `latest_drug_payment_share` (r = 1.00; algebraic complement)
- `latest_top_hcpcs_share` — near-duplicate of `latest_hcpcs_hhi` (r = 0.98)
- `first_year`, `last_year` — raw calendar identifiers with no standalone behavioral signal (already captured via `n_years_active` / trend features)

NPI, provider name, address, and all other identifiers were excluded from the ML feature matrix from the start (used only as reference/join keys, never as model inputs). The final 40 features are listed in full in `provider_feature_columns.json`.

---

## 6. Isolation Forest Methodology

```python
IsolationForest(
    n_estimators=300,
    contamination=0.05,
    random_state=42,
    n_jobs=-1
)
```

Isolation Forest isolates observations by randomly partitioning the feature space; anomalies require fewer partitions to isolate and receive a higher anomaly score. It requires no fraud labels, scales well, and is robust to irrelevant features — appropriate for this unlabeled billing-behavior dataset.

---

## 7. Risk-Score Methodology

For each provider:

- **`anomaly_score_raw`** = `−pipeline.decision_function(X)` (sign-flipped so higher = more anomalous)
- **`isolation_forest_anomaly_flag`** = 1 if `pipeline.predict(X) == -1` (i.e., flagged anomalous under the 5% contamination threshold), else 0
- **`risk_score_0_100`** = min-max normalization of `anomaly_score_raw` across the scored population, scaled to 0–100
- **`risk_category`**: Low (0–24), Medium (25–49), High (50–74), Critical (75–100)

> **The risk score is not a probability of fraud.** It is a relative measure of how anomalous a provider's billing/service behavior is compared to the rest of the scored population, intended solely to prioritize providers for human investigation.

---

## 8. Results

| Risk Category | Count | % of scored population |
|---|---|---|
| Low | 1,891 | 79.9% |
| Medium | 369 | 15.6% |
| High | 93 | 3.9% |
| Critical | 15 | 0.6% |

Isolation Forest anomaly flags: **119** providers (5.03% — matches the 5% contamination target).

---

## 9. Model Validation

Because no reliable fraud ground-truth label exists, standard supervised metrics (accuracy/precision/recall/F1) were **not** used. Instead:

- **Anomaly-score distribution:** mean −0.133, std 0.060, p50 −0.152, p95 ≈0.00, p99 0.083 — a right-skewed distribution with a distinct high-score tail, consistent with a small anomalous subpopulation.
- **Sensitivity analysis:** retrained with contamination ∈ {0.03, 0.05, 0.10} and n_estimators ∈ {150, 300, 500}; the top-50 highest-risk provider set stayed highly stable (Jaccard overlap 0.92–1.00 vs. the production configuration across all 9 combinations).
- **Stability across random seeds:** retrained with 5 different seeds; mean Spearman rank correlation of anomaly scores vs. the production model = **0.989** — the ranking of providers by risk is highly reproducible.
- **Isolation Forest vs. LOF comparison:** Local Outlier Factor (n_neighbors=20, contamination=0.05) flagged the same count of providers (119) but overlapped with Isolation Forest on only 11 (9.2%), and rank correlation between the two methods' scores was moderate (Spearman 0.48). This is expected — LOF detects local density anomalies while Isolation Forest detects global structural anomalies — and confirms Isolation Forest (global, ensemble-based) is the more appropriate and stable **primary** model, with LOF serving as a supporting cross-check that surfaces a different subset worth secondary review.
- **Top-risk provider inspection:** the 15 highest-risk providers were manually inspected (see `high_critical_providers_explained.csv`); each has a coherent, explainable set of extreme feature values (see Section 9 below and Section 11).

---

## 10. LEIE Reference Analysis

| Metric | Value |
|---|---|
| Total LEIE-excluded NPIs in reference file | 8,660 |
| Scored providers matched to an LEIE exclusion | **1** (0.042% of scored population) |
| LEIE matches within High/Critical risk category | 0 |

**LEIE was used only as a qualitative external reference check, not as a supervised label**, per the brief's instructions. The match count is far too small to compute meaningful precision/recall, and a match/non-match to LEIE is not equivalent to a fraud/non-fraud ground truth — LEIE exclusions reflect a distinct administrative/legal process (program exclusions for reasons ranging from license revocation to healthcare fraud convictions) that may lag, precede, or be entirely unrelated to anomalous *billing* behavior. The single match found was not in the High/Critical category in this run, which is expected given how rare and structurally different LEIE exclusion is from billing-pattern anomaly, and is not evidence against the model.

---

## 11. Explainability

For every High/Critical provider, the top contributing features are surfaced as human-readable reasons, computed as robust (median/MAD) z-scores relative to the full scored population. Example (highest-risk provider, `1003053851`, Internal Medicine, CA):

> unusually high total Medicare payment received; unusually high total submitted charges; unusually high 5-year average total payment; unusually high multi-year payment trend; unusually high total services billed

Full reasons for all 108 High/Critical providers are in `high_critical_providers_explained.csv`; the top 3 reasons per provider are also included in `provider_risk_scores.csv`.

---

## 12. Limitations

- **Scored population excludes providers inactive in 2024** (445 of 2,813 NPIs) because latest-year snapshot features require a 2024 record. These historical-only providers could be scored separately using an "average/trend-only" feature subset if needed.
- **Peer comparison is limited to specialty (`provider_type`)**, not full geographic peer benchmarking, because the environment used for this build had no parquet-reading capability (no network access to install `pyarrow`/`duckdb`) and could not load `fact_geo_benchmark.parquet`; state is retained as a reference field but not used as a full geographic peer-benchmark feature. Re-running the feature engineering with `fact_geo_benchmark` in an environment with parquet support could add this feature.
- **No beneficiary risk-score or dual-eligibility data** was present in the raw provider-service files, so those brief-suggested features were omitted rather than fabricated.
- **LEIE reference check has very low statistical power** — 1 match — and should not be read as validating or invalidating the model.
- **This is an anomaly detector, not a fraud classifier.** A high risk score means "statistically unusual relative to peers," which can also reflect legitimate explanations (unusual but appropriate specialty mix, a genuinely high-acuity patient panel, a practice-size outlier, a coding correction year-over-year, etc.). All High/Critical providers require human investigation before any conclusion is drawn.

---

## 13. How to Use the Trained Model in VS Code

1. Copy these files into one folder: `provider_risk_pipeline.joblib`, `provider_preprocessing.py`, `feature_engineering.py`, `provider_feature_columns.json`.
2. Install once: `pip install pandas numpy scikit-learn joblib`
3. Score new data with the CLI script:
   ```bash
   python predict_provider.py --raw_csv_dir /path/to/csvs --years 2023 2024 2025 --output_csv new_scores.csv
   ```
4. Or programmatically:
   ```python
   import joblib
   import provider_preprocessing  # registers the Winsorizer class for unpickling
   import json

   pipeline = joblib.load("provider_risk_pipeline.joblib")
   with open("provider_feature_columns.json") as f:
       cols = json.load(f)["feature_columns_in_order"]

   # provider_features_df must be a provider-level DataFrame with these 40 columns
   # in this order (use feature_engineering.engineer_provider_features(...) to build it
   # from raw CMS provider-service CSVs)
   preds = pipeline.predict(provider_features_df[cols])            # -1 = anomaly, 1 = normal
   scores = -pipeline.decision_function(provider_features_df[cols])  # higher = more anomalous
   ```

No retraining is required — the pipeline reloads deterministically and reproduces the exact scores shown in `provider_risk_scores.csv` (verified in the reload test).

---

## Files Delivered

| File | Contents |
|---|---|
| `provider_isolation_forest.joblib` | The actual fitted Isolation Forest (trained on preprocessed features) |
| `provider_risk_pipeline.joblib` | Complete reusable pipeline: imputation → winsorization → scaling → Isolation Forest |
| `provider_preprocessing.py` | Custom `Winsorizer` transformer class (required to unpickle the pipeline) |
| `feature_engineering.py` | Raw CSV → provider-level feature engineering functions (reused identically at inference) |
| `provider_feature_columns.json` | Exact 40 feature names, in training order |
| `provider_model_metadata.json` | Parameters, training counts, methodology, full validation results |
| `provider_risk_scores.csv` | Every scored provider: anomaly score, flag, 0–100 risk score, category, top reasons |
| `high_critical_providers_explained.csv` | Full explainability detail for all High/Critical providers |
| `validation_results.json` | Sensitivity, stability, LOF comparison, LEIE reference check detail |
| `predict_provider.py` | Reusable inference script (CLI + importable functions) |
| `METHODOLOGY_AND_RESULTS.md` | This report |

**Final statement:** this model detects statistically anomalous provider billing/service behavior relative to peers and produces a relative risk score for investigation prioritization. It does **not** predict or confirm fraud, and every flagged provider requires independent human review before any action is taken.
