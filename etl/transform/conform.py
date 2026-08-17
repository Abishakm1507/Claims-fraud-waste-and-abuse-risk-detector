"""
Conforming: build the canonical tables every module reads.

WHY THIS STAGE EXISTS
Right now the ML pipeline, the agents and the assistant each parse the raw CSVs
themselves. They will compute "total payment" three slightly different ways and
then disagree in front of an investigator. Conforming computes each fact ONCE,
at one grain, with one definition, and every module reads the result.

OUTPUTS
  dim_provider            one row per NPI - identity, specialty, location
  fact_provider_year      one row per NPI x year - volumes and money
  fact_provider_service   one row per NPI x HCPCS x year - billing detail
  dim_hcpcs               one row per procedure code
  fact_geo_benchmark      one row per geography x HCPCS x year - peer reference
  dim_exclusion           OIG exclusions, normalised
  fact_claim              one row per claim, all claim types unioned
  xwalk_identifier        measured linkage between every dataset pair
"""

from __future__ import annotations

import pandas as pd


def build_dim_provider(ps: pd.DataFrame) -> pd.DataFrame:
    """
    One row per NPI. Attributes are taken from the provider's MOST RECENT year,
    because specialty and location change and the current value is the one an
    investigator needs.
    """
    if ps.empty:
        return pd.DataFrame()

    ordered = ps.sort_values("year")
    agg = ordered.groupby("npi", as_index=False).agg(
        provider_last_or_org=("provider_last_or_org", "last"),
        provider_first=("provider_first", "last"),
        provider_city=("provider_city", "last"),
        provider_state=("provider_state", "last"),
        provider_specialty=("provider_specialty", "last"),
        entity_code=("entity_code", "last"),
        npi_checksum_valid=("npi_checksum_valid", "last"),
        first_year=("year", "min"),
        last_year=("year", "max"),
        years_observed=("year", "nunique"),
    )
    agg["provider_name"] = (
        agg["provider_first"].fillna("").str.strip() + " " +
        agg["provider_last_or_org"].fillna("").str.strip()
    ).str.strip()
    agg["is_organisation"] = agg["entity_code"].astype("string").str.upper().eq("O")
    return agg


def build_fact_provider_year(ps: pd.DataFrame) -> pd.DataFrame:
    """One row per NPI x year. The grain most provider questions need."""
    if ps.empty:
        return pd.DataFrame()

    g = ps.groupby(["npi", "year"], as_index=False).agg(
        service_lines=("hcpcs_code", "size"),
        distinct_procedures=("hcpcs_code", "nunique"),
        total_services=("services", "sum"),
        total_beneficiaries=("beneficiaries", "sum"),
        total_payment=("total_payment_amount", "sum"),
        total_allowed=("total_allowed_amount", "sum"),
        total_submitted=("total_submitted_charge", "sum"),
    )
    # Ratios computed once, here, so no module derives them differently.
    g["payment_per_service"] = g.total_payment.div(g.total_services).where(g.total_services > 0)
    g["payment_per_beneficiary"] = g.total_payment.div(g.total_beneficiaries).where(g.total_beneficiaries > 0)
    g["services_per_beneficiary"] = g.total_services.div(g.total_beneficiaries).where(g.total_beneficiaries > 0)
    g["charge_per_service"] = g.total_submitted.div(g.total_services).where(g.total_services > 0)
    g["payment_to_charge_ratio"] = g.total_payment.div(g.total_submitted).where(g.total_submitted > 0)

    # Herfindahl-Hirschman index of service concentration: sum of squared
    # payment shares across procedure codes. Near 1 = revenue from one code.
    shares = ps.groupby(["npi", "year", "hcpcs_code"], as_index=False)[
        "total_payment_amount"].sum()
    totals = shares.groupby(["npi", "year"])["total_payment_amount"].transform("sum")
    shares["sq"] = (shares.total_payment_amount.div(totals).where(totals > 0)) ** 2
    hhi = shares.groupby(["npi", "year"], as_index=False)["sq"].sum().rename(
        columns={"sq": "service_concentration_hhi"})
    return g.merge(hhi, on=["npi", "year"], how="left")


def build_dim_hcpcs(ps: pd.DataFrame, geo: pd.DataFrame) -> pd.DataFrame:
    """One row per procedure code, description taken from either source."""
    frames = []
    for df in (ps, geo):
        if df is not None and not df.empty and "hcpcs_code" in df.columns:
            frames.append(df[["hcpcs_code", "hcpcs_description"]].dropna(
                subset=["hcpcs_code"]))
    if not frames:
        return pd.DataFrame()
    all_codes = pd.concat(frames, ignore_index=True)
    return (all_codes.dropna(subset=["hcpcs_description"])
            .drop_duplicates("hcpcs_code")
            .sort_values("hcpcs_code")
            .reset_index(drop=True))


def build_xwalk(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    Measured linkage between datasets.

    This is the table that answers "can these two files actually be joined?"
    with a number rather than an assumption. Overlap is computed, not asserted.
    """
    def ids(name: str, col: str) -> set:
        df = tables.get(name)
        if df is None or df.empty or col not in df.columns:
            return set()
        return set(df[col].dropna().astype(str))

    pairs = [
        ("provider_service", "npi", "leie", "npi", "Provider billed vs excluded"),
        ("provider_service", "npi", "claims", "organisation_npi",
         "Medicare provider vs claims org NPI"),
        ("provider_service", "npi", "claims", "attending_npi",
         "Medicare provider vs claims attending NPI"),
        ("claims", "organisation_npi", "leie", "npi", "Claims org NPI vs excluded"),
        ("provider_service", "hcpcs_code", "geo_benchmark", "hcpcs_code",
         "Provider procedures vs benchmark coverage"),
        ("provider_service", "provider_state", "geo_benchmark", "geo_state",
         "Provider states vs benchmark geographies"),
    ]

    rows = []
    for lt, lc, rt, rc, note in pairs:
        left, right = ids(lt, lc), ids(rt, rc)
        if not left or not right:
            continue
        overlap = left & right
        rows.append({
            "left_table": lt, "left_key": lc,
            "right_table": rt, "right_key": rc,
            "left_distinct": len(left),
            "right_distinct": len(right),
            "overlap": len(overlap),
            "pct_of_left": round(len(overlap) / len(left) * 100, 2),
            "pct_of_right": round(len(overlap) / len(right) * 100, 2),
            "joinable": len(overlap) / max(len(left), 1) >= 0.05,
            "note": note,
        })
    return pd.DataFrame(rows)


def link_exclusions(dim_provider: pd.DataFrame,
                    leie: pd.DataFrame) -> pd.DataFrame:
    """
    Exclusion screening results, with match confidence stated.

    Exact NPI match is 'confirmed'. Name+state is 'possible' and NOT treated as
    a match: testing showed most such matches are different people who share a
    name and state, and asserting an exclusion on that basis would be exactly
    the kind of unfounded accusation this platform must avoid.
    """
    if dim_provider.empty or leie.empty:
        return pd.DataFrame()

    exact = dim_provider.merge(
        leie[leie.npi.notna()][["npi", "exclusion_type", "exclusion_date",
                                "specialty", "state", "city"]],
        on="npi", how="inner", suffixes=("", "_leie"))
    exact["match_type"] = "npi_exact"
    exact["match_confidence"] = "confirmed"

    ind = leie[leie.is_individual & leie.npi.isna()]
    possible = pd.DataFrame()
    if not ind.empty and "provider_last_or_org" in dim_provider.columns:
        left = dim_provider.assign(
            _ln=dim_provider.provider_last_or_org.astype("string").str.upper().str.strip(),
            _fn=dim_provider.provider_first.astype("string").str.upper().str.strip())
        right = ind.assign(_ln=ind.last_name, _fn=ind.first_name)
        possible = left.merge(
            right[["_ln", "_fn", "state", "specialty", "exclusion_type",
                   "exclusion_date", "city"]],
            left_on=["_ln", "_fn", "provider_state"],
            right_on=["_ln", "_fn", "state"],
            how="inner", suffixes=("", "_leie"))
        if not possible.empty:
            possible["match_type"] = "name_state"
            possible["match_confidence"] = "possible_requires_verification"
            possible["city_agrees"] = (
                possible.provider_city.astype("string").str.upper()
                == possible.city.astype("string").str.upper())
            possible = possible.drop(columns=["_ln", "_fn"], errors="ignore")

    keep = ["npi", "provider_name", "provider_specialty", "provider_state",
            "provider_city", "exclusion_type", "exclusion_date", "specialty",
            "match_type", "match_confidence"]
    frames = [d for d in (exact, possible) if not d.empty]
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True)
    return out[[c for c in keep if c in out.columns]
               + [c for c in ("city_agrees",) if c in out.columns]]
