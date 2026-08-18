"""
Full entity profiles.

Assembles everything known about one provider or claim from every connected
source, in the order an investigator reads it: who they are, what they did, how
that compares to peers, what the model says, and whether they are excluded.

WHY A SEPARATE MODULE
The query dispatcher answers narrow questions ("total payment?"). A profile
answers the broad one ("tell me about this provider"), which needs a different
shape: breadth over precision, and a clear statement of which sources had
nothing rather than silent omission.

MISSING SOURCES ARE NAMED
If a provider is absent from the risk model, or a claim has no NPI so peer
comparison is impossible, the profile says so. An investigator must be able to
tell the difference between "no finding" and "not checked".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.data import warehouse as wh


def _money(v) -> str | None:
    return None if v is None else f"${v:,.2f}"


def _num(v) -> str | None:
    if v is None:
        return None
    return f"{v:,.0f}" if float(v).is_integer() else f"{v:,.2f}"


def _pct(v) -> str | None:
    """Percentiles arrive as either a 0-1 fraction or a 0-100 value."""
    if v is None:
        return None
    p = v * 100 if v <= 1 else v
    return f"{p:.0f}th percentile"


@dataclass
class EntityProfile:
    """Everything known about one entity, plus what could not be checked."""

    found: bool = False
    entity_type: str = "provider"
    entity_id: str = ""
    identity: dict[str, Any] = field(default_factory=dict)
    activity: dict[str, Any] = field(default_factory=dict)
    by_year: list[dict[str, Any]] = field(default_factory=list)
    top_procedures: list[dict[str, Any]] = field(default_factory=list)
    peer_position: dict[str, Any] = field(default_factory=dict)
    risk: dict[str, Any] = field(default_factory=dict)
    exclusion: dict[str, Any] = field(default_factory=dict)
    claims_activity: dict[str, Any] = field(default_factory=dict)
    sources_used: list[str] = field(default_factory=list)
    not_available: list[str] = field(default_factory=list)
    message: str = ""

    def to_dict(self) -> dict[str, Any] | None:
        if not self.found:
            return None
        return {
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "identity": self.identity,
            "activity": self.activity,
            "by_year": self.by_year,
            "top_procedures": self.top_procedures,
            "peer_position": self.peer_position,
            "risk": self.risk,
            "exclusion": self.exclusion,
            "claims_activity": self.claims_activity,
            "sources_used": self.sources_used,
            "not_available": self.not_available,
        }

    def as_prompt_block(self) -> str:
        """Render for the LLM. Only sections with content appear."""
        if not self.found:
            return self.message or "Entity not found in any connected dataset."

        lines: list[str] = [f"{self.entity_type.upper()} {self.entity_id}"]

        def section(title: str, data: dict) -> None:
            if not data:
                return
            lines.append(f"\n{title}:")
            for k, v in data.items():
                if v is not None:
                    lines.append(f"- {k}: {v}")

        section("Identity", self.identity)
        section("Activity", self.activity)
        section("Risk model output", self.risk)
        section("Peer position", self.peer_position)
        section("Claims activity", self.claims_activity)
        section("Exclusion screening", self.exclusion)

        if self.by_year:
            lines.append("\nBy year:")
            for row in self.by_year:
                lines.append("- " + "; ".join(f"{k}: {v}" for k, v in row.items()
                                              if v is not None))
        if self.top_procedures:
            lines.append("\nTop procedures by payment:")
            for row in self.top_procedures:
                lines.append("- " + "; ".join(f"{k}: {v}" for k, v in row.items()
                                              if v is not None))
        if self.not_available:
            lines.append("\nNot available for this entity:")
            for item in self.not_available:
                lines.append(f"- {item}")
        return "\n".join(lines)


# ---------------------------------------------------------------- provider

def provider_profile(npi: str, include_years: bool = True,
                     top_n: int = 5) -> EntityProfile:
    p = EntityProfile(entity_type="provider", entity_id=str(npi))
    npi = str(npi).strip()

    if not wh.is_built():
        p.message = "No data source is connected."
        return p

    # --- identity and totals ---
    if wh.has("provider_summary"):
        row = wh.one("SELECT * FROM provider_summary WHERE npi = ?", [npi])
        if row:
            p.found = True
            p.sources_used.append("Medicare provider data")
            name = " ".join(x for x in [row.get("first_name"),
                                        row.get("last_or_org_name")] if x)
            p.identity = {
                "name": name or None,
                "specialty": row.get("specialty"),
                "location": ", ".join(x for x in [row.get("city"),
                                                  row.get("state")] if x) or None,
                "entity type": ("Organisation"
                                if str(row.get("entity_code", "")).upper() == "O"
                                else "Individual"),
                "years covered": (f"{row.get('first_year')}-{row.get('last_year')}"
                                  if row.get("first_year") else None),
            }
            p.activity = {
                "total Medicare payment": _money(row.get("total_payment")),
                "total allowed amount": _money(row.get("total_allowed")),
                "total submitted charges": _money(row.get("total_submitted")),
                "total services": _num(row.get("total_services")),
                "beneficiary-service count": _num(row.get("total_beneficiaries")),
                "distinct procedures billed": _num(row.get("distinct_procedures")),
                "payment per service": _money(row.get("payment_per_service")),
                "services per beneficiary-service": _num(
                    row.get("services_per_beneficiary")),
                "payment-to-charge ratio": _num(row.get("payment_to_charge_ratio")),
                "service concentration (HHI)": _num(
                    row.get("service_concentration_hhi")),
            }
        else:
            p.not_available.append(
                "Medicare provider data has no record of this NPI")

    # --- year by year ---
    if include_years and wh.has("fact_provider_year"):
        # The beneficiary column was renamed between ETL versions
        # (total_beneficiaries -> beneficiary_service_count, because the value
        # is not an unduplicated patient count). Resolve it from the table so
        # either vintage of curated output works.
        cols = wh.columns("fact_provider_year")
        bene = next((c for c in ("beneficiary_service_count",
                                 "total_beneficiaries") if c in cols), None)
        select = ["year", "total_services", "total_payment",
                  "payment_per_service"]
        if bene:
            select.append(f"{bene} AS beneficiaries")
        select = [c for c in select
                  if c.split(" AS ")[0] in cols or " AS " in c]
        rows = wh.query(f"""
            SELECT {', '.join(select)}
            FROM fact_provider_year WHERE npi = ? ORDER BY year
        """, [npi])
        for r in rows:
            p.by_year.append({
                "year": r.get("year"),
                "services": _num(r.get("total_services")),
                "payment": _money(r.get("total_payment")),
                "payment per service": _money(r.get("payment_per_service")),
            })

    # --- top procedures, benchmarked where possible ---
    if wh.has("provider_service"):
        rows = wh.query("""
            SELECT hcpcs_code, ANY_VALUE(hcpcs_desc) AS description,
                   SUM(services) AS services, SUM(est_payment) AS payment,
                   AVG(avg_payment) AS provider_avg
            FROM provider_service WHERE npi = ?
            GROUP BY hcpcs_code ORDER BY payment DESC LIMIT ?
        """, [npi, top_n])
        state = (p.identity.get("location") or "").split(", ")[-1]
        for r in rows:
            entry = {
                "code": r["hcpcs_code"],
                "description": (r["description"] or "")[:60],
                "services": _num(r["services"]),
                "payment": _money(r["payment"]),
                "provider avg payment": _money(r["provider_avg"]),
            }
            if wh.has("geo_benchmark") and state:
                bench = wh.one("""
                    SELECT AVG(avg_payment) AS b FROM geo_benchmark
                    WHERE hcpcs_code = ? AND geo_state = ?
                """, [r["hcpcs_code"], state])
                if bench and bench.get("b"):
                    entry["state avg payment"] = _money(bench["b"])
                    if r["provider_avg"]:
                        entry["vs state average"] = \
                            f"{r['provider_avg'] / bench['b']:.2f}x"
            p.top_procedures.append(entry)

    # --- risk model output ---
    if wh.has("provider_risk"):
        r = wh.one("SELECT * FROM provider_risk WHERE npi = ?", [npi])
        if r:
            p.found = True
            p.sources_used.append("provider risk model")
            p.risk = {
                "risk score": (f"{r['risk_score']:.1f} / 100"
                               if r.get("risk_score") is not None else None),
                "risk tier": r.get("risk_tier"),
                "peer group used by the model": r.get("peer_group"),
                "period scored": (f"{r.get('year_first')}-{r.get('year_last')}"
                                  if r.get("year_first") else None),
            }
            for label, col in [
                ("Payment per service", "m_pay_per_svc"),
                ("Charge per service", "m_chrg_per_svc"),
                ("Services per beneficiary", "m_svc_per_bene"),
                ("Payment-to-charge ratio", "m_pay_chrg"),
                ("Service concentration", "m_hhi"),
            ]:
                pct, dev = r.get(f"{col}_pct"), r.get(f"{col}_dev")
                if pct is None:
                    continue
                text = _pct(pct)
                if dev:
                    text += f", {dev:.2f}x peer median"
                p.peer_position[label] = text
        else:
            p.not_available.append(
                "This NPI was not scored by the provider risk model")

    # --- claims activity ---
    if wh.has("all_claims"):
        rows = wh.query("""
            SELECT claim_type, COUNT(*) AS n, SUM(payment_amount) AS paid
            FROM all_claims WHERE org_npi = ? GROUP BY claim_type
        """, [npi])
        for r in rows:
            p.claims_activity[f"{r['claim_type']} claims"] = _num(r["n"])
            p.claims_activity[f"{r['claim_type']} payment"] = _money(r["paid"])
        if rows:
            p.sources_used.append("CMS claims data")

    # --- exclusion screening ---
    if wh.has("leie"):
        hit = wh.one("""
            SELECT exclusion_type, exclusion_date, specialty
            FROM leie WHERE npi = ? LIMIT 1
        """, [npi])
        p.exclusion = {
            "OIG exclusion": (
                f"MATCH on NPI - excluded {hit['exclusion_date']} "
                f"under {hit['exclusion_type']}" if hit
                else "No exclusion record matching this NPI")
        }
        p.sources_used.append("OIG exclusion list")

    if not p.found:
        p.message = (
            f"NPI {npi} is not present in any connected dataset. The Medicare "
            "provider data, the CMS claims data and the risk model cover "
            "different provider populations, so an NPI may legitimately appear "
            "in none of them."
        )
    return p


# ------------------------------------------------------------------- claim

def claim_profile(claim_id: str) -> EntityProfile:
    p = EntityProfile(entity_type="claim", entity_id=str(claim_id))
    cid = str(claim_id).strip()

    if not wh.is_built() or not wh.has("all_claims"):
        p.message = "Claims data is not connected."
        return p

    row = wh.one("SELECT * FROM all_claims WHERE claim_id = ?", [cid])
    if not row:
        p.message = (f"Claim {cid} was not found in the outpatient, inpatient "
                     f"or carrier claim datasets.")
        return p

    p.found = True
    p.sources_used.append("CMS claims data")
    p.identity = {
        "claim type": row.get("claim_type"),
        "beneficiary": row.get("beneficiary_id"),
        "service date": row.get("claim_from_date"),
    }
    p.activity = {
        "payment amount": _money(row.get("payment_amount")),
        "charge amount": _money(row.get("charge")),
    }

    org_npi, ccn = row.get("org_npi"), row.get("provider_ccn")
    if org_npi:
        p.identity["billing NPI"] = org_npi
    if ccn:
        p.identity["provider CCN"] = ccn

    # Line detail, where the ETL preserved it.
    if wh.has("fact_claim_line"):
        n = wh.scalar("SELECT COUNT(*) FROM fact_claim_line WHERE claim_id = ?",
                      [cid])
        if n:
            p.activity["claim lines"] = _num(n)

    # The provider link only works through an NPI. A claim carrying only a
    # facility CCN cannot be looked up in NPI-keyed Medicare data, and saying so
    # is more useful than returning nothing.
    if org_npi and wh.has("provider_summary"):
        prov = wh.one("SELECT specialty, state, last_or_org_name "
                      "FROM provider_summary WHERE npi = ?", [org_npi])
        if prov:
            p.identity["billing provider"] = prov.get("last_or_org_name")
            p.identity["provider specialty"] = prov.get("specialty")
        else:
            p.not_available.append(
                f"Billing NPI {org_npi} is not in the Medicare provider data, "
                "so provider context and peer comparison are unavailable")
    elif ccn and not org_npi:
        p.not_available.append(
            f"This claim identifies its provider by facility CCN ({ccn}) only. "
            "Peer comparison requires an NPI, so it cannot be performed for "
            "this claim."
        )

    return p
