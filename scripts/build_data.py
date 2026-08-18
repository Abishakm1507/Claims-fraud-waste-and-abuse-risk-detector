"""
PHASE 8 - Build the structured data warehouse.

    python scripts/build_data.py

Reads the CSVs in data_raw/ and writes a single DuckDB file that the backend
opens read-only. Run once, and again whenever the source data changes.

WHY DUCKDB:
~950,000 rows across six sources, with rankings, aggregations and joins. DuckDB
gives real SQL over that in a single portable file, with no server to run. The
alternative (Pandas) would need every groupby hand-written and would reload the
CSVs on every start.

WHY A DERIVED provider_summary TABLE:
provider_service is one row per NPI x HCPCS x year. Nearly every provider
question needs it aggregated to one row per NPI. Computing that once at build
time keeps lookups instant.
"""

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import duckdb  # noqa: E402

from backend.config import DATA_RAW_DIR, WAREHOUSE_PATH  # noqa: E402
from backend.data.schema import SOURCE_FILES  # noqa: E402


def find(table: str) -> Path | None:
    """Locate a source file, accepting the original download names."""
    for candidate in SOURCE_FILES[table]:
        p = DATA_RAW_DIR / candidate
        if p.exists():
            return p
    return None


def csv(path: Path, delim: str = ",") -> str:
    return (
        f"read_csv('{path.as_posix()}', delim='{delim}', header=true, "
        f"all_varchar=true, ignore_errors=true)"
    )


def main() -> int:
    started = time.time()
    print("=" * 66)
    print("BUILDING DATA WAREHOUSE")
    print("=" * 66)
    print(f"source : {DATA_RAW_DIR}")
    print(f"output : {WAREHOUSE_PATH}\n")

    if not DATA_RAW_DIR.exists():
        print(f"ERROR: {DATA_RAW_DIR} does not exist.")
        print("Create it and place the dataset CSVs inside.")
        return 1

    WAREHOUSE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if WAREHOUSE_PATH.exists():
        WAREHOUSE_PATH.unlink()
    con = duckdb.connect(str(WAREHOUSE_PATH))

    built: list[str] = []
    skipped: list[str] = []

    def report(name: str) -> None:
        n = con.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
        print(f"  [ok] {name:<24} {n:>9,} rows")
        built.append(name)

    # ---------------- Group A: Medicare provider analytics ----------------

    p = find("provider_service")
    if p:
        print("provider_service ...")
        con.execute(f"""
            CREATE TABLE provider_service AS
            SELECT
              Rndrng_NPI                              AS npi,
              Rndrng_Prvdr_Last_Org_Name              AS last_or_org_name,
              Rndrng_Prvdr_First_Name                 AS first_name,
              Rndrng_Prvdr_City                       AS city,
              Rndrng_Prvdr_State_Abrvtn               AS state,
              Rndrng_Prvdr_Type                       AS specialty,
              Rndrng_Prvdr_Ent_Cd                     AS entity_code,
              Place_Of_Srvc                           AS place_of_service,
              HCPCS_Cd                                AS hcpcs_code,
              HCPCS_Desc                              AS hcpcs_desc,
              TRY_CAST(Year AS INTEGER)               AS year,
              TRY_CAST(Tot_Benes AS DOUBLE)           AS beneficiaries,
              TRY_CAST(Tot_Srvcs AS DOUBLE)           AS services,
              TRY_CAST(Tot_Bene_Day_Srvcs AS DOUBLE)  AS bene_day_services,
              TRY_CAST(Avg_Sbmtd_Chrg AS DOUBLE)      AS avg_submitted_charge,
              TRY_CAST(Avg_Mdcr_Alowd_Amt AS DOUBLE)  AS avg_allowed,
              TRY_CAST(Avg_Mdcr_Pymt_Amt AS DOUBLE)   AS avg_payment,
              TRY_CAST(Est_Total_Submitted_Charge AS DOUBLE) AS est_submitted,
              TRY_CAST(Est_Total_Allowed_Amount AS DOUBLE)   AS est_allowed,
              TRY_CAST(Est_Total_Medicare_Payment AS DOUBLE)  AS est_payment
            FROM {csv(p)}
            WHERE Rndrng_NPI IS NOT NULL
        """)
        report("provider_service")

        # One row per provider: the grain nearly every question needs.
        con.execute("""
            CREATE TABLE provider_summary AS
            SELECT
              npi,
              ANY_VALUE(last_or_org_name)          AS last_or_org_name,
              ANY_VALUE(first_name)                AS first_name,
              ANY_VALUE(city)                      AS city,
              ANY_VALUE(state)                     AS state,
              ANY_VALUE(specialty)                 AS specialty,
              ANY_VALUE(entity_code)               AS entity_code,
              MIN(year)                            AS first_year,
              MAX(year)                            AS last_year,
              COUNT(*)                             AS service_line_count,
              COUNT(DISTINCT hcpcs_code)           AS distinct_procedures,
              SUM(services)                        AS total_services,
              SUM(beneficiaries)                   AS total_beneficiaries,
              SUM(est_payment)                     AS total_payment,
              SUM(est_allowed)                     AS total_allowed,
              SUM(est_submitted)                   AS total_submitted,
              CASE WHEN SUM(services) > 0
                   THEN SUM(est_payment) / SUM(services) END      AS payment_per_service,
              CASE WHEN SUM(beneficiaries) > 0
                   THEN SUM(est_payment) / SUM(beneficiaries) END AS payment_per_beneficiary,
              CASE WHEN SUM(beneficiaries) > 0
                   THEN SUM(services) / SUM(beneficiaries) END    AS services_per_beneficiary,
              CASE WHEN SUM(est_submitted) > 0
                   THEN SUM(est_payment) / SUM(est_submitted) END AS payment_to_charge_ratio
            FROM provider_service
            GROUP BY npi
        """)
        report("provider_summary")
    else:
        skipped.append("provider_service")

    p = find("provider_features")
    if p:
        print("provider_features ...")
        cols = [c[0] for c in con.execute(f"DESCRIBE SELECT * FROM {csv(p)}").fetchall()]
        keep = [c for c in cols if c != "Rndrng_NPI"]
        sel = ", ".join(f'TRY_CAST("{c}" AS DOUBLE) AS "{c.lower()}"'
                        if any(k in c.lower() for k in
                               ("score", "zscore", "ratio", "per_", "count",
                                "avg", "year", "age", "total"))
                        else f'"{c}" AS "{c.lower()}"'
                        for c in keep)
        con.execute(f"""
            CREATE TABLE provider_features AS
            SELECT Rndrng_NPI AS npi, {sel} FROM {csv(p)}
            WHERE Rndrng_NPI IS NOT NULL
        """)
        report("provider_features")
    else:
        skipped.append("provider_features")

    p = find("geo_benchmark")
    if p:
        print("geo_benchmark ...")
        con.execute(f"""
            CREATE TABLE geo_benchmark AS
            SELECT
              rndrng_prvdr_geo_lvl                    AS geo_level,
              rndrng_prvdr_geo_desc                   AS geo_desc,
              hcpcs_cd                                AS hcpcs_code,
              hcpcs_desc,
              place_of_srvc                           AS place_of_service,
              TRY_CAST(tot_rndrng_prvdrs AS DOUBLE)   AS provider_count,
              TRY_CAST(tot_benes AS DOUBLE)           AS beneficiaries,
              TRY_CAST(tot_srvcs AS DOUBLE)           AS services,
              TRY_CAST(avg_sbmtd_chrg AS DOUBLE)      AS avg_submitted_charge,
              TRY_CAST(avg_mdcr_alowd_amt AS DOUBLE)  AS avg_allowed,
              TRY_CAST(avg_mdcr_pymt_amt AS DOUBLE)   AS avg_payment
            FROM {csv(p)}
            WHERE hcpcs_cd IS NOT NULL
        """)
        report("geo_benchmark")
    else:
        skipped.append("geo_benchmark")

    # ---------------- Group C: OIG exclusions ----------------

    p = find("leie")
    if p:
        print("leie ...")
        con.execute(f"""
            CREATE TABLE leie AS
            SELECT
              NULLIF(TRIM(NPI), '')            AS npi,
              UPPER(TRIM(LASTNAME))            AS last_name,
              UPPER(TRIM(FIRSTNAME))           AS first_name,
              UPPER(TRIM(BUSNAME))             AS business_name,
              UPPER(TRIM(GENERAL))             AS general_category,
              UPPER(TRIM(SPECIALTY))           AS specialty,
              UPPER(TRIM(CITY))                AS city,
              UPPER(TRIM(COALESCE(STATE_CLEAN, STATE))) AS state,
              EXCLTYPE                         AS exclusion_type,
              EXCLDATE                         AS exclusion_date,
              REINDATE                         AS reinstatement_date
            FROM {csv(p)}
        """)
        report("leie")
    else:
        skipped.append("leie")

    # ------------- Risk engine output (Phase 9 source) -------------
    #
    # This table is the platform's provider risk model output. The assistant
    # READS it. It never computes any of these values.

    p = find("provider_risk")
    if p:
        print("provider_risk ...")
        con.execute(f"""
            CREATE TABLE provider_risk AS
            SELECT
              CAST(NPI AS VARCHAR)                       AS npi,
              Provider_Type                              AS provider_type,
              Prvdr_State                                AS state,
              peer_group,
              TRY_CAST(Provider_Risk_Score AS DOUBLE)    AS risk_score,
              Risk_Tier                                  AS risk_tier,
              TRY_CAST(is_leie_excluded AS DOUBLE)       AS leie_excluded,
              TRY_CAST(global_anomaly_score AS DOUBLE)   AS comp_anomaly,
              TRY_CAST(peer_deviation_score AS DOUBLE)   AS comp_peer_deviation,
              TRY_CAST(service_pattern_score AS DOUBLE)  AS comp_service_pattern,
              TRY_CAST(geo_deviation_score AS DOUBLE)    AS comp_geo_deviation,
              TRY_CAST(peer_deviation_zsum AS DOUBLE)    AS peer_zsum,
              TRY_CAST(Payment_per_Service AS DOUBLE)            AS m_pay_per_svc,
              TRY_CAST(Payment_per_Service_Peer_Median AS DOUBLE) AS m_pay_per_svc_peer,
              TRY_CAST(Payment_per_Service_Peer_Pctile AS DOUBLE) AS m_pay_per_svc_pct,
              TRY_CAST(Payment_per_Service_Deviation_Ratio AS DOUBLE) AS m_pay_per_svc_dev,
              TRY_CAST(Charge_per_Service AS DOUBLE)             AS m_chrg_per_svc,
              TRY_CAST(Charge_per_Service_Peer_Median AS DOUBLE) AS m_chrg_per_svc_peer,
              TRY_CAST(Charge_per_Service_Peer_Pctile AS DOUBLE) AS m_chrg_per_svc_pct,
              TRY_CAST(Charge_per_Service_Deviation_Ratio AS DOUBLE) AS m_chrg_per_svc_dev,
              TRY_CAST(Services_per_Beneficiary AS DOUBLE)             AS m_svc_per_bene,
              TRY_CAST(Services_per_Beneficiary_Peer_Median AS DOUBLE) AS m_svc_per_bene_peer,
              TRY_CAST(Services_per_Beneficiary_Peer_Pctile AS DOUBLE) AS m_svc_per_bene_pct,
              TRY_CAST(Services_per_Beneficiary_Deviation_Ratio AS DOUBLE) AS m_svc_per_bene_dev,
              TRY_CAST(Payment_to_Charge_Ratio AS DOUBLE)             AS m_pay_chrg,
              TRY_CAST(Payment_to_Charge_Ratio_Peer_Median AS DOUBLE) AS m_pay_chrg_peer,
              TRY_CAST(Payment_to_Charge_Ratio_Peer_Pctile AS DOUBLE) AS m_pay_chrg_pct,
              TRY_CAST(Payment_to_Charge_Ratio_Deviation_Ratio AS DOUBLE) AS m_pay_chrg_dev,
              TRY_CAST(Svc_HHI_Concentration AS DOUBLE)             AS m_hhi,
              TRY_CAST(Svc_HHI_Concentration_Peer_Median AS DOUBLE) AS m_hhi_peer,
              TRY_CAST(Svc_HHI_Concentration_Peer_Pctile AS DOUBLE) AS m_hhi_pct,
              TRY_CAST(Svc_HHI_Concentration_Deviation_Ratio AS DOUBLE) AS m_hhi_dev,
              TRY_CAST(Svc_Growth_Pct AS DOUBLE)   AS growth_services,
              TRY_CAST(Pymt_Growth_Pct AS DOUBLE)  AS growth_payment,
              TRY_CAST(Benes_Growth_Pct AS DOUBLE) AS growth_beneficiaries,
              TRY_CAST(Year_First AS INTEGER)      AS year_first,
              TRY_CAST(Year_Last AS INTEGER)       AS year_last,
              TRY_CAST(Geo_Provider_Avg_Pymt AS DOUBLE)  AS geo_provider_avg_pymt,
              TRY_CAST(Geo_Bench_Pymt_Median AS DOUBLE)  AS geo_bench_pymt_median,
              TRY_CAST(Peer_Avg_Pymt_Deviation AS DOUBLE) AS geo_avg_pymt_deviation,
              TRY_CAST(Peer_Pct_Services_Above_2x_Bench AS DOUBLE) AS geo_pct_svcs_2x
            FROM {csv(p)}
            WHERE NPI IS NOT NULL
        """)
        report("provider_risk")
    else:
        skipped.append("provider_risk")

    # ---------------- Group B: CMS claims ----------------

    p = find("outpatient_claims")
    if p:
        print("outpatient_claims (large, pipe-delimited) ...")
        con.execute(f"""
            CREATE TABLE outpatient_claims AS
            SELECT
              TRY_CAST(CLM_ID AS BIGINT)   AS claim_id,
              TRY_CAST(BENE_ID AS BIGINT)  AS beneficiary_id,
              PRVDR_NUM                    AS provider_ccn,
              ORG_NPI_NUM                  AS org_npi,
              AT_PHYSN_NPI                 AS attending_npi,
              PRVDR_STATE_CD               AS state_code,
              MIN(CLM_FROM_DT)             AS claim_from_date,
              MAX(CLM_THRU_DT)             AS claim_thru_date,
              MAX(TRY_CAST(CLM_PMT_AMT AS DOUBLE))      AS payment_amount,
              MAX(TRY_CAST(CLM_TOT_CHRG_AMT AS DOUBLE)) AS total_charge,
              COUNT(*)                     AS line_count
            FROM {csv(p, '|')}
            WHERE CLM_ID IS NOT NULL
            GROUP BY 1,2,3,4,5,6
        """)
        report("outpatient_claims")
    else:
        skipped.append("outpatient_claims")

    p = find("inpatient_claims")
    if p:
        print("inpatient_claims ...")
        con.execute(f"""
            CREATE TABLE inpatient_claims AS
            SELECT
              TRY_CAST(clm_id AS BIGINT)   AS claim_id,
              TRY_CAST(bene_id AS BIGINT)  AS beneficiary_id,
              prvdr_num                    AS provider_ccn,
              org_npi_num                  AS org_npi,
              at_physn_npi                 AS attending_npi,
              prvdr_state_cd               AS state_code,
              MIN(clm_from_dt)             AS claim_from_date,
              MAX(clm_thru_dt)             AS claim_thru_date,
              MAX(TRY_CAST(clm_pmt_amt AS DOUBLE))       AS payment_amount,
              MAX(TRY_CAST(clm_tot_chrg_amt AS DOUBLE))  AS total_charge,
              MAX(TRY_CAST(clm_utlztn_day_cnt AS DOUBLE)) AS length_of_stay,
              COUNT(*)                     AS line_count
            FROM {csv(p)}
            WHERE clm_id IS NOT NULL
            GROUP BY 1,2,3,4,5,6
        """)
        report("inpatient_claims")
    else:
        skipped.append("inpatient_claims")

    p = find("inpatient_features")
    if p:
        print("inpatient_features ...")
        con.execute(f"""
            CREATE TABLE inpatient_features AS
            SELECT
              TRY_CAST(clm_id AS BIGINT) AS claim_id,
              prvdr_num                  AS provider_ccn,
              TRY_CAST(claim_anomaly_count AS DOUBLE)            AS anomaly_count,
              TRY_CAST(high_claim_payment_flag AS DOUBLE)        AS flag_high_payment,
              TRY_CAST(high_payment_to_charge_flag AS DOUBLE)    AS flag_high_pay_charge,
              TRY_CAST(long_stay_flag AS DOUBLE)                 AS flag_long_stay,
              TRY_CAST(high_utilization_flag AS DOUBLE)          AS flag_high_utilization,
              TRY_CAST(high_provider_claim_volume_flag AS DOUBLE) AS flag_high_provider_volume,
              TRY_CAST(high_provider_payment_flag AS DOUBLE)     AS flag_high_provider_payment,
              TRY_CAST(high_diagnosis_count_flag AS DOUBLE)      AS flag_high_diagnosis_count,
              TRY_CAST(high_procedure_count_flag AS DOUBLE)      AS flag_high_procedure_count
            FROM {csv(p)}
            WHERE clm_id IS NOT NULL
        """)
        report("inpatient_features")
    else:
        skipped.append("inpatient_features")

    p = find("carrier_claims")
    if p:
        print("carrier_claims ...")
        con.execute(f"""
            CREATE TABLE carrier_claims AS
            SELECT
              TRY_CAST(CLM_ID AS BIGINT)          AS claim_id,
              TRY_CAST(BENE_ID_first AS BIGINT)   AS beneficiary_id,
              ORG_NPI_NUM_first                   AS org_npi,
              PRF_PHYSN_NPI_first                 AS performing_npi,
              CARR_CLM_BLG_NPI_NUM_first          AS billing_npi,
              NULL                                AS claim_from_date,
              NULL                                AS claim_thru_date,
              TRY_CAST(CLM_PMT_AMT_first AS DOUBLE)               AS payment_amount,
              TRY_CAST(NCH_CARR_CLM_SBMTD_CHRG_AMT_first AS DOUBLE) AS submitted_charge,
              TRY_CAST(NCH_CARR_CLM_ALOWD_AMT_first AS DOUBLE)    AS allowed_amount,
              TRY_CAST(LINE_NCH_PMT_AMT_sum AS DOUBLE)            AS line_payment_total,
              TRY_CAST(claim_year AS INTEGER)              AS claim_year
            FROM {csv(p)}
            WHERE CLM_ID IS NOT NULL
        """)
        report("carrier_claims")
    else:
        skipped.append("carrier_claims")

    # ---------- Unified claim view across all three claim types ----------
    parts = []
    if "outpatient_claims" in built:
        parts.append("""SELECT claim_id, 'outpatient' AS claim_type, beneficiary_id,
                        org_npi, provider_ccn, payment_amount, total_charge AS charge,
                        claim_from_date FROM outpatient_claims""")
    if "inpatient_claims" in built:
        parts.append("""SELECT claim_id, 'inpatient', beneficiary_id,
                        org_npi, provider_ccn, payment_amount, total_charge,
                        claim_from_date FROM inpatient_claims""")
    if "carrier_claims" in built:
        parts.append("""SELECT claim_id, 'carrier', beneficiary_id,
                        org_npi, NULL, payment_amount, submitted_charge,
                        NULL FROM carrier_claims""")
    if parts:
        con.execute("CREATE TABLE all_claims AS " + " UNION ALL ".join(parts))
        report("all_claims")

    # ---------- Indexes ----------
    print("\nindexing ...")
    for tbl, col in [
        ("provider_summary", "npi"), ("provider_service", "npi"),
        ("provider_risk", "npi"),
        ("provider_features", "npi"), ("geo_benchmark", "hcpcs_code"),
        ("leie", "npi"), ("leie", "last_name"),
        ("outpatient_claims", "claim_id"), ("outpatient_claims", "org_npi"),
        ("inpatient_claims", "claim_id"), ("inpatient_claims", "org_npi"),
        ("carrier_claims", "claim_id"), ("all_claims", "claim_id"),
        ("all_claims", "org_npi"), ("inpatient_features", "claim_id"),
    ]:
        if tbl in built:
            try:
                con.execute(f"CREATE INDEX idx_{tbl}_{col} ON {tbl}({col})")
            except Exception:
                pass

    con.close()
    size = WAREHOUSE_PATH.stat().st_size / 1e6
    print("\n" + "=" * 66)
    print(f"DONE - {len(built)} tables, {size:.0f} MB, {time.time() - started:.0f}s")
    if skipped:
        print(f"Skipped (file not found in data_raw/): {', '.join(skipped)}")
    print("Test it with:  python scripts/query.py 1003000126")
    print("=" * 66)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
