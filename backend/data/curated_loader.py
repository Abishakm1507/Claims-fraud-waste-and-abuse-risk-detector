"""
Load the ETL's curated tables into the warehouse.

WHY THIS EXISTS
The assistant used to build its own warehouse straight from raw CSVs. So did
the ML pipeline. Two modules parsing the same files independently compute the
same fact slightly differently - and then contradict each other in front of an
investigator.

The ETL now produces conformed tables where every fact is computed once. This
loader points the assistant at those tables instead, so the assistant and the
ML agents always report identical numbers.

PRECEDENCE
If curated tables exist, they win. Raw CSVs remain as a fallback so the
assistant still runs before the ETL has been executed, but the fallback is
reported rather than silent - a number's provenance should never be ambiguous.
"""

from __future__ import annotations

from pathlib import Path

from backend.config import PROJECT_ROOT

# Curated tables the assistant uses, mapped to the warehouse view it needs.
CURATED_TABLES = {
    "dim_provider": "dim_provider",
    "fact_provider_year": "fact_provider_year",
    "fact_provider_service": "fact_provider_service",
    "fact_geo_benchmark": "fact_geo_benchmark",
    "dim_hcpcs": "dim_hcpcs",
    "dim_exclusion": "dim_exclusion",
    "fact_claim": "fact_claim",
    "fact_claim_line": "fact_claim_line",
    "link_provider_exclusion": "link_provider_exclusion",
    "xwalk_identifier": "xwalk_identifier",
    # Risk model output, if the ETL or the platform publishes it alongside.
    "provider_risk": "provider_risk",
    "provider_risk_scores": "provider_risk",
}


def find_curated_dir() -> Path | None:
    """
    Locate the ETL's curated output, wherever this module ends up living.

    WHY THIS WALKS UPWARDS
    This module is developed standalone but deployed inside the main project
    repo, and its position there is not fixed - it may sit at the root, or under
    rag/, or backend/rag/. A hardcoded relative path breaks on integration, and
    breaks silently: the assistant simply falls back to its own warehouse and
    starts reporting different numbers from the rest of the platform.

    So the search walks up the directory tree from this file looking for a
    data/curated directory, then checks sibling directories at each level. That
    finds the data whether the repo layout is:

        repo/data/curated  +  repo/rag/                (module in a subfolder)
        repo/data/curated  +  repo/                    (module at the root)
        parent/ETL/data/curated  +  parent/RAG/        (separate local projects)

    CURATED_DIR overrides everything, for deployments that place the data
    somewhere unusual.
    """
    import os

    explicit = os.getenv("CURATED_DIR")
    if explicit:
        p = Path(explicit).expanduser()
        if not p.is_absolute():
            p = (PROJECT_ROOT / p).resolve()
        return p if _looks_curated(p) else None

    here = Path(__file__).resolve()

    # Establish a boundary. Without one, the upward walk eventually reaches a
    # shared directory such as /tmp or C:\Users and can match an unrelated
    # folder that happens to contain curated output - which is worse than
    # finding nothing, because the assistant would silently read wrong data.
    repo_root = None
    for level in here.parents:
        if (level / ".git").exists() or (level / "pyproject.toml").exists():
            repo_root = level
            break

    # No repo marker (running from a plain extracted folder): allow a bounded
    # walk instead, but never past the user's home directory.
    ceiling = repo_root or PROJECT_ROOT.parent
    home = Path.home().resolve()

    levels: list[Path] = []
    for level in [here.parent, *here.parents]:
        levels.append(level)
        if level == ceiling:
            break
        if level == home or level.parent == level:
            break

    seen: set[Path] = set()

    # 1. data/curated at or above this module, within the boundary.
    for level in levels:
        for candidate in (level / "data" / "curated", level / "curated"):
            if candidate in seen:
                continue
            seen.add(candidate)
            if _looks_curated(candidate):
                return candidate

    # 2. Sibling projects, checked ONLY at the boundary level. Covers the
    #    development layout where ETL/ and RAG/ sit side by side, without
    #    scanning unrelated directories further up.
    for level in {ceiling, PROJECT_ROOT.parent}:
        try:
            siblings = sorted(d for d in level.iterdir() if d.is_dir())
        except (OSError, PermissionError):
            continue
        for sib in siblings:
            if sib.name.startswith("."):
                continue
            candidate = sib / "data" / "curated"
            if candidate in seen:
                continue
            seen.add(candidate)
            if _looks_curated(candidate):
                return candidate

    return None


def _looks_curated(path: Path) -> bool:
    """
    True if this directory holds ETL output.

    Requires dim_provider specifically rather than any parquet file, so an
    unrelated folder of parquet files is never mistaken for curated output.
    Both extensions are accepted because the ETL falls back to CSV when pyarrow
    is unavailable.
    """
    if not path.is_dir():
        return False
    for ext in (".parquet", ".csv"):
        f = path / f"dim_provider{ext}"
        if f.exists() and f.stat().st_size > 0:
            return True
    return False


def available_tables(curated: Path) -> dict[str, Path]:
    found = {}
    for name in CURATED_TABLES:
        for ext in (".parquet", ".csv"):
            p = curated / f"{name}{ext}"
            if p.exists():
                found[name] = p
                break
    return found


RISK_FILENAMES = ("provider_risk.parquet", "provider_risk_scores.parquet",
                  "provider_risk.csv", "provider_risk_scores.csv")


def find_risk_file(curated: Path) -> Path | None:
    """
    Locate provider risk model output.

    Checked separately from the curated tables because the risk scores are a
    model artifact rather than ETL output, and may sit beside the curated
    directory, in the project's data_raw, or in a models/ directory.
    """
    import os

    explicit = os.getenv("PROVIDER_RISK_FILE")
    if explicit and Path(explicit).exists():
        return Path(explicit)

    roots = [curated, curated.parent, curated.parent.parent,
             PROJECT_ROOT / "data_raw", PROJECT_ROOT / "data"]
    if curated.parent.parent:
        roots.append(curated.parent.parent / "models" / "provider" / "output")

    for root in roots:
        for name in RISK_FILENAMES:
            f = root / name
            if f.exists() and f.stat().st_size > 1000:
                return f
    return None


def register_risk(con, curated: Path) -> bool:
    """Register the risk scores as `provider_risk`, normalising column names."""
    path = find_risk_file(curated)
    if path is None:
        return False

    reader = "read_parquet" if path.suffix == ".parquet" else "read_csv_auto"
    con.execute(f"CREATE OR REPLACE VIEW _risk_raw AS "
                f"SELECT * FROM {reader}('{path.as_posix()}')")
    cols = _columns(con, "_risk_raw")

    # The published file uses the model's own column names; map them onto the
    # names the risk service queries.
    mapping = {
        "npi": ("npi", "NPI"),
        "provider_type": ("provider_type", "Provider_Type"),
        "state": ("state", "Prvdr_State"),
        "peer_group": ("peer_group",),
        "risk_score": ("risk_score", "Provider_Risk_Score"),
        "risk_tier": ("risk_tier", "Risk_Tier"),
        "leie_excluded": ("leie_excluded", "is_leie_excluded"),
        "comp_anomaly": ("comp_anomaly", "global_anomaly_score"),
        "comp_peer_deviation": ("comp_peer_deviation", "peer_deviation_score"),
        "comp_service_pattern": ("comp_service_pattern", "service_pattern_score"),
        "comp_geo_deviation": ("comp_geo_deviation", "geo_deviation_score"),
        "year_first": ("year_first", "Year_First"),
        "year_last": ("year_last", "Year_Last"),
    }
    metric_map = {
        "m_pay_per_svc": "Payment_per_Service",
        "m_chrg_per_svc": "Charge_per_Service",
        "m_svc_per_bene": "Services_per_Beneficiary",
        "m_pay_chrg": "Payment_to_Charge_Ratio",
        "m_hhi": "Svc_HHI_Concentration",
    }
    for short, base in metric_map.items():
        mapping[short] = (short, base)
        mapping[f"{short}_peer"] = (f"{short}_peer", f"{base}_Peer_Median")
        mapping[f"{short}_pct"] = (f"{short}_pct", f"{base}_Peer_Pctile")
        mapping[f"{short}_dev"] = (f"{short}_dev", f"{base}_Deviation_Ratio")

    select = []
    for target, candidates in mapping.items():
        src = next((c for c in candidates if c in cols), None)
        if src is None:
            select.append(f"NULL AS {target}")
        elif target in ("npi", "provider_type", "state", "peer_group",
                        "risk_tier"):
            select.append(f'CAST("{src}" AS VARCHAR) AS {target}')
        else:
            select.append(f'TRY_CAST("{src}" AS DOUBLE) AS {target}')

    con.execute(f"CREATE OR REPLACE VIEW provider_risk AS "
                f"SELECT {', '.join(select)} FROM _risk_raw "
                f"WHERE {'NPI' if 'NPI' in cols else 'npi'} IS NOT NULL")
    return True


def register(con, curated: Path) -> list[str]:
    """
    Register curated files as views in the DuckDB connection.

    Views rather than copies: the files stay the single source of truth, and
    re-running the ETL updates the assistant with no rebuild.
    """
    registered = []
    for name, path in available_tables(curated).items():
        reader = ("read_parquet" if path.suffix == ".parquet"
                  else "read_csv_auto")
        con.execute(
            f"CREATE OR REPLACE VIEW {name} AS "
            f"SELECT * FROM {reader}('{path.as_posix()}')"
        )
        registered.append(name)
    return registered


def build_provider_summary(con) -> bool:
    """
    Provide `provider_summary` from curated tables.

    The service layer queries `provider_summary` for one row per provider. The
    ETL splits that across dim_provider (identity) and fact_provider_year
    (yearly measures), so this view rejoins them at the grain the service
    expects - keeping the ETL's definitions rather than recomputing anything.
    """
    tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    if not {"dim_provider", "fact_provider_year"} <= tables:
        return False

    fy = _columns(con, "fact_provider_year")
    # The ETL renamed the duplicated beneficiary count; accept either name.
    benes = _col(fy, "beneficiary_service_count", "total_beneficiaries",
                 default="NULL")
    hhi = _col(fy, "service_concentration_hhi", default="NULL")

    con.execute(f"""
        CREATE OR REPLACE VIEW provider_summary AS
        SELECT
          d.npi,
          d.provider_last_or_org        AS last_or_org_name,
          d.provider_first              AS first_name,
          d.provider_city               AS city,
          d.provider_state              AS state,
          d.provider_specialty          AS specialty,
          d.entity_code,
          d.first_year,
          d.last_year,
          SUM(f.service_lines)          AS service_line_count,
          MAX(f.distinct_procedures)    AS distinct_procedures,
          SUM(f.total_services)         AS total_services,
          SUM(f.{benes})               AS total_beneficiaries,
          SUM(f.total_payment)          AS total_payment,
          SUM(f.total_allowed)          AS total_allowed,
          SUM(f.total_submitted)        AS total_submitted,
          CASE WHEN SUM(f.total_services) > 0
               THEN SUM(f.total_payment) / SUM(f.total_services) END
                                        AS payment_per_service,
          CASE WHEN SUM(f.{benes}) > 0
               THEN SUM(f.total_payment) / SUM(f.{benes}) END
                                        AS payment_per_beneficiary,
          CASE WHEN SUM(f.{benes}) > 0
               THEN SUM(f.total_services) / SUM(f.{benes}) END
                                        AS services_per_beneficiary,
          CASE WHEN SUM(f.total_submitted) > 0
               THEN SUM(f.total_payment) / SUM(f.total_submitted) END
                                        AS payment_to_charge_ratio,
          AVG(f.{hhi})                 AS service_concentration_hhi
        FROM dim_provider d
        LEFT JOIN fact_provider_year f USING (npi)
        GROUP BY ALL
    """)
    return True


def _columns(con, table: str) -> set[str]:
    try:
        return {r[0] for r in con.execute(f"DESCRIBE {table}").fetchall()}
    except Exception:                                          # noqa: BLE001
        return set()


def _col(present: set[str], *candidates: str, default: str = "NULL") -> str:
    """
    First available column, else a literal default.

    Column availability differs by claim type - carrier extracts carry
    submitted_charge_amount while institutional ones carry
    total_charge_amount - so views are built from what is actually there
    rather than from an assumed schema.
    """
    for c in candidates:
        if c in present:
            return c
    return default


def build_compatibility_views(con) -> list[str]:
    """
    Map curated table names onto the names the service layer already queries.

    Keeps the service code unchanged while the underlying source moves from raw
    CSVs to curated output.
    """
    tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    made = []

    if "fact_provider_service" in tables:
        con.execute("""
            CREATE OR REPLACE VIEW provider_service AS
            SELECT
              npi, provider_last_or_org AS last_or_org_name,
              provider_first AS first_name, provider_city AS city,
              provider_state AS state, provider_specialty AS specialty,
              entity_code, place_of_service, hcpcs_code,
              hcpcs_description AS hcpcs_desc, year,
              beneficiaries, services, bene_day_services,
              avg_submitted_charge, avg_allowed_amount AS avg_allowed,
              avg_payment_amount AS avg_payment,
              total_submitted_charge AS est_submitted,
              total_allowed_amount AS est_allowed,
              total_payment_amount AS est_payment
            FROM fact_provider_service
        """)
        made.append("provider_service")

    if "fact_geo_benchmark" in tables:
        con.execute("""
            CREATE OR REPLACE VIEW geo_benchmark AS
            SELECT
              geo_level, geo_description AS geo_desc, geo_state,
              hcpcs_code, hcpcs_description AS hcpcs_desc, place_of_service,
              provider_count, beneficiaries, services,
              avg_submitted_charge, avg_allowed_amount AS avg_allowed,
              avg_payment_amount AS avg_payment, year
            FROM fact_geo_benchmark
        """)
        made.append("geo_benchmark")

    if "dim_exclusion" in tables:
        con.execute("""
            CREATE OR REPLACE VIEW leie AS
            SELECT
              npi, last_name, first_name, business_name,
              general_category, specialty, city, state,
              exclusion_type, CAST(exclusion_date AS VARCHAR) AS exclusion_date,
              CAST(reinstatement_date AS VARCHAR) AS reinstatement_date
            FROM dim_exclusion
        """)
        made.append("leie")

    if "fact_claim" in tables:
        c = _columns(con, "fact_claim")
        charge_cols = [x for x in ("total_charge_amount",
                                   "submitted_charge_amount") if x in c]
        charge = (f"COALESCE({', '.join(charge_cols)})" if len(charge_cols) > 1
                  else (charge_cols[0] if charge_cols else "NULL"))
        con.execute(f"""
            CREATE OR REPLACE VIEW all_claims AS
            SELECT
              CAST(claim_id AS VARCHAR)                    AS claim_id,
              {_col(c, "claim_type")}                      AS claim_type,
              CAST({_col(c, "beneficiary_id")} AS VARCHAR) AS beneficiary_id,
              {_col(c, "organisation_npi", "org_npi")}     AS org_npi,
              {_col(c, "provider_ccn")}                    AS provider_ccn,
              {_col(c, "payment_amount")}                  AS payment_amount,
              {charge}                                     AS charge,
              CAST({_col(c, "claim_from_date")} AS VARCHAR) AS claim_from_date
            FROM fact_claim
        """)
        made.append("all_claims")

    return made
