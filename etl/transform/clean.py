"""
Per-source cleaning.

Each source gets a function that maps its raw columns onto canonical names,
normalises every identifier, coerces numerics, and records what it changed.

CANONICAL NAMING
Source column names are preserved in a mapping file so nothing is lost, but the
curated output uses one canonical name per concept. That is the point: today
every module invents its own name for "total Medicare payment", so the ML
pipeline and the assistant can compute different answers to the same question.
One name, one definition, one value.
"""

from __future__ import annotations

import pandas as pd

from etl.transform.identifiers import (
    normalise_ccn, normalise_claim_id, normalise_hcpcs, normalise_npi,
    normalise_person_name, normalise_state, npi_checksum_valid,
)


def _num(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Coerce to numeric, stripping $ and , that CMS extracts sometimes carry."""
    for c in cols:
        if c in df.columns:
            s = df[c].astype("string").str.replace(r"[$,]", "", regex=True)
            df[c] = pd.to_numeric(s, errors="coerce")
    return df


def _pick(df: pd.DataFrame, *names: str) -> str | None:
    """First column present, matched case-insensitively."""
    lower = {c.lower(): c for c in df.columns}
    for n in names:
        if n.lower() in lower:
            return lower[n.lower()]
    return None


def clean_provider_service(df: pd.DataFrame, year) -> pd.DataFrame:
    """Medicare Physician & Other Practitioners - by Provider and Service."""
    out = pd.DataFrame(index=df.index)

    out["npi"] = normalise_npi(df[_pick(df, "Rndrng_NPI", "npi")])
    out["npi_checksum_valid"] = npi_checksum_valid(out["npi"])

    for canon, *cands in [
        ("provider_last_or_org", "Rndrng_Prvdr_Last_Org_Name"),
        ("provider_first", "Rndrng_Prvdr_First_Name"),
        ("provider_city", "Rndrng_Prvdr_City"),
        ("provider_specialty", "Rndrng_Prvdr_Type"),
        ("entity_code", "Rndrng_Prvdr_Ent_Cd"),
        ("place_of_service", "Place_Of_Srvc"),
        ("hcpcs_description", "HCPCS_Desc"),
    ]:
        col = _pick(df, *cands)
        if col:
            out[canon] = df[col].astype("string").str.strip()

    st = _pick(df, "Rndrng_Prvdr_State_Abrvtn", "Rndrng_Prvdr_State")
    out["provider_state"] = normalise_state(df[st]) if st else pd.NA

    hc = _pick(df, "HCPCS_Cd", "hcpcs_cd")
    out["hcpcs_code"] = normalise_hcpcs(df[hc]) if hc else pd.NA

    out["year"] = (year.values if hasattr(year, "values") else year)

    numeric = {
        "beneficiaries": ("Tot_Benes",),
        "services": ("Tot_Srvcs",),
        "bene_day_services": ("Tot_Bene_Day_Srvcs",),
        "avg_submitted_charge": ("Avg_Sbmtd_Chrg",),
        "avg_allowed_amount": ("Avg_Mdcr_Alowd_Amt",),
        "avg_payment_amount": ("Avg_Mdcr_Pymt_Amt",),
        "avg_standardised_payment": ("Avg_Mdcr_Stdzd_Amt",),
    }
    for canon, cands in numeric.items():
        col = _pick(df, *cands)
        out[canon] = pd.to_numeric(df[col], errors="coerce") if col else pd.NA

    # Derived totals. CMS publishes per-service averages only; totals are what
    # every downstream question actually needs, so they are computed ONCE here
    # rather than independently (and differently) by each consuming module.
    out["total_submitted_charge"] = out.avg_submitted_charge * out.services
    out["total_allowed_amount"] = out.avg_allowed_amount * out.services
    out["total_payment_amount"] = out.avg_payment_amount * out.services

    return out


def clean_geo_service(df: pd.DataFrame, year) -> pd.DataFrame:
    """Medicare Physician & Other Practitioners - by Geography and Service."""
    out = pd.DataFrame(index=df.index)

    lvl = _pick(df, "Rndrng_Prvdr_Geo_Lvl", "rndrng_prvdr_geo_lvl")
    desc = _pick(df, "Rndrng_Prvdr_Geo_Desc", "rndrng_prvdr_geo_desc")
    out["geo_level"] = df[lvl].astype("string").str.strip() if lvl else pd.NA
    out["geo_description"] = df[desc].astype("string").str.strip() if desc else pd.NA
    # Full state names are mapped to codes so this joins to provider data.
    out["geo_state"] = normalise_state(out["geo_description"])

    hc = _pick(df, "HCPCS_Cd", "hcpcs_cd")
    out["hcpcs_code"] = normalise_hcpcs(df[hc]) if hc else pd.NA
    d = _pick(df, "HCPCS_Desc", "hcpcs_desc")
    out["hcpcs_description"] = df[d].astype("string").str.strip() if d else pd.NA
    pos = _pick(df, "Place_Of_Srvc", "place_of_srvc")
    out["place_of_service"] = df[pos].astype("string").str.strip() if pos else pd.NA

    out["year"] = (year.values if hasattr(year, "values") else year)

    for canon, cand in [
        ("provider_count", "Tot_Rndrng_Prvdrs"),
        ("beneficiaries", "Tot_Benes"),
        ("services", "Tot_Srvcs"),
        ("avg_submitted_charge", "Avg_Sbmtd_Chrg"),
        ("avg_allowed_amount", "Avg_Mdcr_Alowd_Amt"),
        ("avg_payment_amount", "Avg_Mdcr_Pymt_Amt"),
    ]:
        col = _pick(df, cand)
        out[canon] = pd.to_numeric(df[col], errors="coerce") if col else pd.NA

    return out


def clean_leie(df: pd.DataFrame) -> pd.DataFrame:
    """OIG exclusion list."""
    out = pd.DataFrame(index=df.index)

    npi = _pick(df, "NPI")
    out["npi"] = normalise_npi(df[npi]) if npi else pd.NA
    out["has_npi"] = out["npi"].notna()

    for canon, cand in [("last_name", "LASTNAME"), ("first_name", "FIRSTNAME"),
                        ("middle_name", "MIDNAME"), ("business_name", "BUSNAME")]:
        col = _pick(df, cand)
        out[canon] = normalise_person_name(df[col]) if col else pd.NA

    for canon, cand in [("general_category", "GENERAL"), ("specialty", "SPECIALTY"),
                        ("city", "CITY"), ("exclusion_type", "EXCLTYPE"),
                        ("zip_code", "ZIP")]:
        col = _pick(df, cand)
        out[canon] = df[col].astype("string").str.strip().str.upper() if col else pd.NA

    st = _pick(df, "STATE")
    out["state"] = normalise_state(df[st]) if st else pd.NA

    for canon, cand in [("exclusion_date", "EXCLDATE"),
                        ("reinstatement_date", "REINDATE"),
                        ("waiver_date", "WAIVERDATE")]:
        col = _pick(df, cand)
        if col:
            # LEIE dates are YYYYMMDD integers.
            out[canon] = pd.to_datetime(
                df[col].astype("string").str.replace(r"\.0$", "", regex=True),
                format="%Y%m%d", errors="coerce")
        else:
            out[canon] = pd.NaT

    out["is_individual"] = out["last_name"].notna()
    return out


def clean_claims(df: pd.DataFrame, claim_type: str) -> pd.DataFrame:
    """CMS synthetic claims - carrier, inpatient or outpatient."""
    out = pd.DataFrame(index=df.index)

    cid = _pick(df, "CLM_ID", "clm_id")
    out["claim_id"] = normalise_claim_id(df[cid]) if cid else pd.NA
    bid = _pick(df, "BENE_ID", "bene_id", "BENE_ID_first", "DESYNPUF_ID")
    out["beneficiary_id"] = normalise_claim_id(df[bid]) if bid else pd.NA

    ccn = _pick(df, "PRVDR_NUM", "prvdr_num")
    out["provider_ccn"] = normalise_ccn(df[ccn]) if ccn else pd.NA

    for canon, *cands in [
        # Aggregated extracts suffix identifier columns with _first, so both
        # forms are accepted rather than silently yielding no provider link.
        ("organisation_npi", "ORG_NPI_NUM", "org_npi_num", "ORG_NPI_NUM_first"),
        ("attending_npi", "AT_PHYSN_NPI", "at_physn_npi", "AT_PHYSN_NPI_first"),
        ("operating_npi", "OP_PHYSN_NPI", "op_physn_npi", "OP_PHYSN_NPI_first"),
        ("rendering_npi", "RNDRNG_PHYSN_NPI", "rndrng_physn_npi",
         "RNDRNG_PHYSN_NPI_first"),
        ("performing_npi", "PRF_PHYSN_NPI", "prf_physn_npi",
         "PRF_PHYSN_NPI_first"),
        ("billing_npi", "CARR_CLM_BLG_NPI_NUM", "CARR_CLM_BLG_NPI_NUM_first"),
    ]:
        col = _pick(df, *cands)
        if col:
            out[canon] = normalise_npi(df[col])

    st = _pick(df, "PRVDR_STATE_CD", "prvdr_state_cd")
    if st:
        out["provider_state_code"] = df[st].astype("string").str.strip()

    for canon, *cands in [("claim_from_date", "CLM_FROM_DT", "clm_from_dt",
                           "CLM_FROM_DT_min"),
                          ("claim_thru_date", "CLM_THRU_DT", "clm_thru_dt",
                           "CLM_THRU_DT_max")]:
        col = _pick(df, *cands)
        if col:
            out[canon] = pd.to_datetime(df[col], errors="coerce",
                                        format="mixed", dayfirst=False)

    for canon, *cands in [
        ("payment_amount", "CLM_PMT_AMT", "clm_pmt_amt", "CLM_PMT_AMT_first"),
        ("total_charge_amount", "CLM_TOT_CHRG_AMT", "clm_tot_chrg_amt"),
        ("allowed_amount", "NCH_CARR_CLM_ALOWD_AMT",
         "NCH_CARR_CLM_ALOWD_AMT_first"),
        ("submitted_charge_amount", "NCH_CARR_CLM_SBMTD_CHRG_AMT",
         "NCH_CARR_CLM_SBMTD_CHRG_AMT_first"),
        ("length_of_stay", "CLM_UTLZTN_DAY_CNT", "clm_utlztn_day_cnt"),
    ]:
        col = _pick(df, *cands)
        if col:
            out[canon] = pd.to_numeric(df[col], errors="coerce")

    out["claim_type"] = claim_type
    if "claim_from_date" in out.columns:
        out["claim_year"] = out["claim_from_date"].dt.year
    return out
