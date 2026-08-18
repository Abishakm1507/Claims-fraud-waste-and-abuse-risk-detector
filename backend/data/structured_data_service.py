"""
PHASE 8 - Structured data service.

Exact SQL over the real datasets. Nothing here uses semantic similarity: every
number the assistant reports is computed by a query, and when a query returns
nothing the service says so rather than estimating.

PEER COMPARISON IS THE CENTREPIECE.
Three comparison methods, because the data supports three genuinely different
kinds and each answers a different question:

  1. SPECIALTY COHORT  - same specialty, same state (national fallback when the
     state cohort is too small to define a distribution). Gives the provider's
     percentile on each metric. Answers "how does their volume compare?"

  2. PROCEDURE BENCHMARK - the provider's own HCPCS codes compared against the
     state average for those same codes, from geo_benchmark. This compares like
     with like, so it answers "is their reimbursement unusually high?" without
     the distortion of comparing different procedure mixes.

  3. PUBLISHED Z-SCORES - provider_features already carries peer deviation
     scores. Where a provider appears there, those are read, not recomputed.

Every comparison reports its basis (cohort definition and size), because a
wrong peer group is the leading cause of false positives.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.config import MIN_PEER_COHORT
from backend.data import warehouse as wh

NOT_BUILT = (
    "The data warehouse has not been built. Place the dataset CSVs in data_raw/ "
    "and run: python scripts/build_data.py"
)


@dataclass
class DataEvidence:
    """Structured facts retrieved from the real datasets."""

    available: bool = False
    message: str = ""
    entity_type: str | None = None
    entity_id: str | None = None
    facts: dict[str, Any] = field(default_factory=dict)
    peer_comparison: dict[str, Any] = field(default_factory=dict)
    records: list[dict[str, Any]] = field(default_factory=list)
    query_description: str = ""

    def to_dict(self) -> dict[str, Any] | None:
        if not self.available:
            return None
        return {
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "facts": self.facts,
            "peer_comparison": self.peer_comparison,
            "records": self.records,
            "query_description": self.query_description,
        }


def _money(v) -> str | None:
    return None if v is None else f"${v:,.2f}"


def _num(v) -> str | None:
    if v is None:
        return None
    return f"{v:,.0f}" if float(v).is_integer() else f"{v:,.2f}"


def _pct_label(p: float) -> str:
    """Plain-language reading of a percentile, for the LLM to use as given."""
    if p >= 99:
        return "top 1% of peers"
    if p >= 95:
        return "top 5% of peers"
    if p >= 90:
        return "top 10% of peers"
    if p >= 75:
        return "upper quartile"
    if p >= 25:
        return "within the middle range"
    if p >= 10:
        return "lower quartile"
    return "bottom 10% of peers"


class StructuredDataService:
    """Exact queries over the healthcare datasets."""

    # ---------------------------------------------------------------- status

    def is_available(self) -> bool:
        return wh.is_built() and wh.get_connection() is not None

    def status(self) -> dict[str, Any]:
        if not self.is_available():
            return {"connected": False, "phase": 8, "message": NOT_BUILT,
                    "datasets_loaded": []}
        loaded = []
        for t in sorted(wh.tables()):
            n = wh.scalar(f"SELECT COUNT(*) FROM {t}")
            loaded.append({"table": t, "rows": n})
        return {
            "connected": True,
            "phase": 8,
            "message": "Datasets loaded and queryable.",
            "datasets_loaded": loaded,
        }

    # ------------------------------------------------------------- provider

    def get_provider_facts(self, npi: str) -> DataEvidence:
        """Everything known about one provider, across every relevant source."""
        if not self.is_available():
            return DataEvidence(message=NOT_BUILT, entity_type="provider",
                                entity_id=npi)

        facts: dict[str, Any] = {}
        records: list[dict[str, Any]] = []
        found_in: list[str] = []

        # --- Medicare aggregate profile ---
        if wh.has("provider_summary"):
            row = wh.one("SELECT * FROM provider_summary WHERE npi = ?", [npi])
            if row:
                found_in.append("Medicare provider data")
                name = " ".join(x for x in [row.get("first_name"),
                                            row.get("last_or_org_name")] if x)
                facts.update({
                    "provider name": name or None,
                    "specialty": row.get("specialty"),
                    "location": ", ".join(
                        x for x in [row.get("city"), row.get("state")] if x) or None,
                    "years covered": f"{row.get('first_year')}-{row.get('last_year')}",
                    "total Medicare payment": _money(row.get("total_payment")),
                    "total allowed amount": _money(row.get("total_allowed")),
                    "total submitted charges": _money(row.get("total_submitted")),
                    "total services": _num(row.get("total_services")),
                    "total beneficiaries": _num(row.get("total_beneficiaries")),
                    "distinct procedures billed": _num(row.get("distinct_procedures")),
                    "payment per service": _money(row.get("payment_per_service")),
                    "payment per beneficiary": _money(row.get("payment_per_beneficiary")),
                    "services per beneficiary": _num(row.get("services_per_beneficiary")),
                })
                top = wh.query("""
                    SELECT hcpcs_code, ANY_VALUE(hcpcs_desc) AS description,
                           SUM(services) AS services, SUM(est_payment) AS payment
                    FROM provider_service WHERE npi = ?
                    GROUP BY hcpcs_code ORDER BY payment DESC LIMIT 5
                """, [npi])
                for t in top:
                    records.append({
                        "type": "top procedure",
                        "code": t["hcpcs_code"],
                        "description": (t["description"] or "")[:70],
                        "services": _num(t["services"]),
                        "payment": _money(t["payment"]),
                    })

        # --- published peer deviation scores ---
        if wh.has("provider_features"):
            row = wh.one("SELECT * FROM provider_features WHERE npi = ? LIMIT 1",
                         [npi])
            if row:
                found_in.append("provider peer-deviation data")
                for k, v in row.items():
                    if v is None or k == "npi":
                        continue
                    if any(s in k for s in ("score", "zscore", "peer")):
                        facts[k.replace("_", " ")] = _num(v) if isinstance(v, (int, float)) else v

        # --- claims activity ---
        if wh.has("all_claims"):
            row = wh.one("""
                SELECT claim_type, COUNT(*) n, SUM(payment_amount) paid
                FROM all_claims WHERE org_npi = ?
                GROUP BY claim_type ORDER BY n DESC
            """, [npi])
            if row:
                found_in.append("CMS claims data")
                for r in wh.query("""
                    SELECT claim_type, COUNT(*) n, SUM(payment_amount) paid,
                           COUNT(DISTINCT beneficiary_id) benes
                    FROM all_claims WHERE org_npi = ? GROUP BY claim_type
                """, [npi]):
                    facts[f"{r['claim_type']} claims"] = _num(r["n"])
                    facts[f"{r['claim_type']} payment"] = _money(r["paid"])
                    facts[f"{r['claim_type']} beneficiaries"] = _num(r["benes"])

        # --- exclusion screening ---
        excl = self._exclusion_check(npi, facts)
        if excl:
            facts.update(excl)

        if not found_in:
            return DataEvidence(
                available=False, entity_type="provider", entity_id=npi,
                message=(
                    f"No record of NPI {npi} in any loaded dataset. The Medicare "
                    "provider data and the CMS claims data cover different "
                    "provider populations, so an NPI may legitimately appear in "
                    "neither."
                ),
            )

        return DataEvidence(
            available=True, entity_type="provider", entity_id=npi,
            facts={k: v for k, v in facts.items() if v is not None},
            records=records,
            query_description=f"Provider lookup for NPI {npi} in {', '.join(found_in)}",
        )

    def _exclusion_check(self, npi: str, facts: dict) -> dict[str, Any]:
        """OIG exclusion screening. Exact NPI match only - names are unreliable."""
        if not wh.has("leie"):
            return {}
        hit = wh.one("""
            SELECT exclusion_type, exclusion_date, specialty, state, city
            FROM leie WHERE npi = ? LIMIT 1
        """, [npi])
        if hit:
            return {
                "OIG exclusion status": (
                    f"MATCH on NPI - excluded {hit['exclusion_date']} "
                    f"under {hit['exclusion_type']}"
                ),
            }
        return {"OIG exclusion status": "No exclusion record matching this NPI"}

    # ------------------------------------------------------ peer comparison

    def get_peer_comparison(self, npi: str) -> DataEvidence:
        """
        The core comparison. Combines a specialty cohort percentile ranking with
        a procedure-level benchmark, and reports the metrics that deviate most.
        """
        if not self.is_available():
            return DataEvidence(message=NOT_BUILT, entity_type="provider",
                                entity_id=npi)
        if not wh.has("provider_summary"):
            return DataEvidence(
                available=False, entity_type="provider", entity_id=npi,
                message="Provider data is not loaded, so peer comparison is unavailable.",
            )

        me = wh.one("SELECT * FROM provider_summary WHERE npi = ?", [npi])
        if not me:
            return DataEvidence(
                available=False, entity_type="provider", entity_id=npi,
                message=(
                    f"NPI {npi} is not in the Medicare provider dataset, which is "
                    "the source used for peer comparison."
                ),
            )

        specialty, state = me.get("specialty"), me.get("state")

        # Cohort: same specialty + state, falling back to national when small.
        basis = f"{specialty} providers in {state}"
        cohort_sql = "SELECT * FROM provider_summary WHERE specialty = ? AND state = ?"
        params = [specialty, state]
        size = wh.scalar(
            "SELECT COUNT(*) FROM provider_summary WHERE specialty = ? AND state = ?",
            params) or 0
        if size < MIN_PEER_COHORT:
            basis = f"{specialty} providers nationally"
            cohort_sql = "SELECT * FROM provider_summary WHERE specialty = ?"
            params = [specialty]
            size = wh.scalar(
                "SELECT COUNT(*) FROM provider_summary WHERE specialty = ?",
                [specialty]) or 0

        METRICS = [
            ("total_payment", "total Medicare payment", True),
            ("total_services", "total services", False),
            ("total_beneficiaries", "beneficiaries served", False),
            ("payment_per_service", "payment per service", True),
            ("payment_per_beneficiary", "payment per beneficiary", True),
            ("services_per_beneficiary", "services per beneficiary", False),
            ("distinct_procedures", "distinct procedures billed", False),
        ]

        comparison: dict[str, Any] = {
            "peer group": basis,
            "peer group size": f"{size:,} providers",
        }
        deviations: list[tuple[float, str, dict]] = []

        for col, label, money in METRICS:
            if me.get(col) is None:
                continue
            stats = wh.one(f"""
                SELECT
                  MEDIAN({col}) AS med,
                  AVG({col})    AS mean,
                  (SELECT COUNT(*) FROM ({cohort_sql}) c2
                   WHERE c2.{col} IS NOT NULL AND c2.{col} <= ?) * 100.0
                  / NULLIF((SELECT COUNT(*) FROM ({cohort_sql}) c3
                            WHERE c3.{col} IS NOT NULL), 0) AS pct
                FROM ({cohort_sql}) c1
            """, params + [me[col]] + params + params)
            if not stats or stats["pct"] is None:
                continue
            pct = float(stats["pct"])
            fmt = _money if money else _num
            comparison[label] = (
                f"{fmt(me[col])} vs peer median {fmt(stats['med'])} "
                f"({pct:.0f}th percentile, {_pct_label(pct)})"
            )
            deviations.append((abs(pct - 50), label, {
                "percentile": round(pct), "provider": fmt(me[col]),
                "peer_median": fmt(stats["med"]),
            }))

        # Which metrics differ most from peers - answers that question directly.
        deviations.sort(reverse=True, key=lambda x: x[0])
        if deviations:
            comparison["metrics deviating most from peers"] = ", ".join(
                f"{lbl} ({d['percentile']}th pct)" for _, lbl, d in deviations[:3]
            )

        # Procedure-level benchmark: like-for-like on the provider's own codes.
        records: list[dict[str, Any]] = []
        if wh.has("geo_benchmark"):
            rows = wh.query("""
                SELECT ps.hcpcs_code,
                       ANY_VALUE(ps.hcpcs_desc)  AS description,
                       SUM(ps.services)          AS services,
                       AVG(ps.avg_payment)       AS provider_avg_payment,
                       AVG(gb.avg_payment)       AS state_avg_payment
                FROM provider_service ps
                JOIN geo_benchmark gb
                  ON gb.hcpcs_code = ps.hcpcs_code
                 AND gb.geo_level = 'State'
                 AND gb.geo_desc = ?
                WHERE ps.npi = ?
                GROUP BY ps.hcpcs_code
                HAVING AVG(gb.avg_payment) > 0
                ORDER BY SUM(ps.est_payment) DESC
                LIMIT 5
            """, [self._state_name(state), npi])
            for r in rows:
                ratio = (r["provider_avg_payment"] / r["state_avg_payment"]
                         if r["state_avg_payment"] else None)
                records.append({
                    "type": "procedure benchmark",
                    "code": r["hcpcs_code"],
                    "description": (r["description"] or "")[:60],
                    "provider avg payment": _money(r["provider_avg_payment"]),
                    "state avg payment": _money(r["state_avg_payment"]),
                    "ratio to state average": f"{ratio:.2f}x" if ratio else None,
                })

        return DataEvidence(
            available=True, entity_type="provider", entity_id=npi,
            facts={
                "provider name": " ".join(
                    x for x in [me.get("first_name"), me.get("last_or_org_name")] if x),
                "specialty": specialty,
                "state": state,
            },
            peer_comparison=comparison,
            records=records,
            query_description=(
                f"Peer comparison for NPI {npi} against {basis} "
                f"({size:,} providers), plus procedure-level state benchmarks"
            ),
        )

    @staticmethod
    def _state_name(abbr: str | None) -> str:
        """geo_benchmark uses full state names; provider data uses abbreviations."""
        M = {
            "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
            "CA": "California", "CO": "Colorado", "CT": "Connecticut",
            "DE": "Delaware", "DC": "District of Columbia", "FL": "Florida",
            "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois",
            "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky",
            "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
            "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
            "MS": "Mississippi", "MO": "Missouri", "MT": "Montana",
            "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire",
            "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
            "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio",
            "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania",
            "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota",
            "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont",
            "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
            "WI": "Wisconsin", "WY": "Wyoming", "PR": "Puerto Rico",
        }
        return M.get((abbr or "").upper(), abbr or "")

    # ---------------------------------------------------------------- claim

    def get_claim_facts(self, claim_id: str) -> DataEvidence:
        """Look a claim up across all three claim types."""
        if not self.is_available():
            return DataEvidence(message=NOT_BUILT, entity_type="claim",
                                entity_id=claim_id)
        try:
            cid = int(claim_id)
        except (TypeError, ValueError):
            return DataEvidence(available=False, entity_type="claim",
                                entity_id=claim_id,
                                message=f"'{claim_id}' is not a valid claim identifier.")

        for table, label in [("outpatient_claims", "outpatient"),
                             ("inpatient_claims", "inpatient"),
                             ("carrier_claims", "carrier")]:
            if not wh.has(table):
                continue
            row = wh.one(f"SELECT * FROM {table} WHERE claim_id = ?", [cid])
            if not row:
                continue
            facts = {"claim type": label}
            for k, v in row.items():
                if v is None or k == "claim_id":
                    continue
                key = k.replace("_", " ")
                facts[key] = (_money(v) if "amount" in k or "charge" in k
                              else _num(v) if isinstance(v, float) else str(v))
            # anomaly flags, where the pipeline produced them
            if label == "inpatient" and wh.has("inpatient_features"):
                f = wh.one("SELECT * FROM inpatient_features WHERE claim_id = ?", [cid])
                if f:
                    fired = [k.replace("flag_", "").replace("_", " ")
                             for k, v in f.items()
                             if k.startswith("flag_") and v]
                    facts["pipeline anomaly flags"] = ", ".join(fired) if fired else "none"
                    if f.get("anomaly_count") is not None:
                        facts["anomaly flag count"] = _num(f["anomaly_count"])
            return DataEvidence(
                available=True, entity_type="claim", entity_id=str(cid),
                facts=facts,
                query_description=f"Claim lookup for {cid} in {label} claims",
            )

        return DataEvidence(
            available=False, entity_type="claim", entity_id=claim_id,
            message=f"Claim {claim_id} was not found in the outpatient, "
                    f"inpatient or carrier claim datasets.",
        )

    # ------------------------------------------------- rankings / thresholds

    def rank_providers(self, metric: str = "total_payment", limit: int = 10,
                       ascending: bool = False,
                       specialty: str | None = None,
                       state: str | None = None) -> DataEvidence:
        if not self.is_available() or not wh.has("provider_summary"):
            return DataEvidence(message=NOT_BUILT)

        allowed = {
            "total_payment", "total_services", "total_beneficiaries",
            "payment_per_service", "payment_per_beneficiary",
            "services_per_beneficiary", "distinct_procedures", "total_submitted",
        }
        if metric not in allowed:
            metric = "total_payment"

        where, params = [f"{metric} IS NOT NULL"], []
        if specialty:
            where.append("LOWER(specialty) LIKE ?")
            params.append(f"%{specialty.lower()}%")
        if state:
            where.append("UPPER(state) = ?")
            params.append(state.upper())

        rows = wh.query(f"""
            SELECT npi, last_or_org_name, first_name, specialty, state, {metric} AS value
            FROM provider_summary WHERE {' AND '.join(where)}
            ORDER BY {metric} {'ASC' if ascending else 'DESC'} LIMIT ?
        """, params + [limit])

        money = "payment" in metric or "submitted" in metric
        records = [{
            "rank": i,
            "npi": r["npi"],
            "name": " ".join(x for x in [r["first_name"], r["last_or_org_name"]] if x),
            "specialty": r["specialty"],
            "state": r["state"],
            metric.replace("_", " "): _money(r["value"]) if money else _num(r["value"]),
        } for i, r in enumerate(rows, 1)]

        scope = " ".join(x for x in [specialty, f"in {state}" if state else ""] if x)
        return DataEvidence(
            available=bool(records),
            entity_type="ranking",
            facts={"metric": metric.replace("_", " "),
                   "direction": "lowest" if ascending else "highest",
                   "returned": len(records)},
            records=records,
            query_description=(
                f"Top {limit} providers by {metric.replace('_', ' ')}"
                + (f" ({scope})" if scope.strip() else "")
            ),
            message="" if records else "No providers matched that filter.",
        )

    def threshold_filter(self, metric: str = "total_payment",
                         operator: str = ">", value: float = 0,
                         limit: int = 25) -> DataEvidence:
        if not self.is_available() or not wh.has("provider_summary"):
            return DataEvidence(message=NOT_BUILT)
        allowed = {"total_payment", "total_services", "total_beneficiaries",
                   "payment_per_service", "payment_per_beneficiary",
                   "services_per_beneficiary", "total_submitted"}
        if metric not in allowed:
            metric = "total_payment"
        op = operator if operator in (">", ">=", "<", "<=") else ">"

        n = wh.scalar(
            f"SELECT COUNT(*) FROM provider_summary WHERE {metric} {op} ?", [value])
        rows = wh.query(f"""
            SELECT npi, last_or_org_name, first_name, specialty, state,
                   {metric} AS value
            FROM provider_summary WHERE {metric} {op} ?
            ORDER BY {metric} DESC LIMIT ?
        """, [value, limit])
        money = "payment" in metric or "submitted" in metric
        return DataEvidence(
            available=True, entity_type="threshold",
            facts={
                "criterion": f"{metric.replace('_', ' ')} {op} "
                             f"{_money(value) if money else _num(value)}",
                "providers matching": _num(n),
                "showing": len(rows),
            },
            records=[{
                "npi": r["npi"],
                "name": " ".join(x for x in [r["first_name"], r["last_or_org_name"]] if x),
                "specialty": r["specialty"], "state": r["state"],
                metric.replace("_", " "): _money(r["value"]) if money else _num(r["value"]),
            } for r in rows],
            query_description=f"Providers where {metric.replace('_', ' ')} {op} {value:,.0f}",
        )

    # ------------------------------------------------------------- overview

    def dataset_overview(self) -> DataEvidence:
        if not self.is_available():
            return DataEvidence(message=NOT_BUILT)
        facts = {}
        for t in sorted(wh.tables()):
            facts[f"{t} rows"] = _num(wh.scalar(f"SELECT COUNT(*) FROM {t}"))
        return DataEvidence(
            available=True, entity_type="overview", facts=facts,
            query_description="Row counts for every loaded dataset",
        )


_service: StructuredDataService | None = None


def get_data_service() -> StructuredDataService:
    global _service
    if _service is None:
        _service = StructuredDataService()
    return _service


# ---------------------------------------------------------------------------
# Question dispatcher
#
# Maps a DATA question onto the right query. Rule-based on purpose: the spec
# requires that numeric questions never be answered by semantic similarity, and
# a deterministic mapping is auditable - you can point at the rule that fired.
# ---------------------------------------------------------------------------

import re as _re

_METRIC_WORDS = [
    (("payment per service", "per service", "per-service"), "payment_per_service"),
    (("payment per beneficiary", "per beneficiary", "per patient"),
     "payment_per_beneficiary"),
    (("services per beneficiary", "services per patient"), "services_per_beneficiary"),
    (("beneficiar", "patient"), "total_beneficiaries"),
    (("service", "procedure volume"), "total_services"),
    (("submitted", "charge", "billed"), "total_submitted"),
    (("payment", "reimbursement", "paid", "revenue", "money", "amount"),
     "total_payment"),
]


def _metric_from(text: str) -> str:
    for words, col in _METRIC_WORDS:
        if any(w in text for w in words):
            return col
    return "total_payment"


def _amount_from(text: str) -> float | None:
    m = _re.search(r"\$?\s*([\d,]+(?:\.\d+)?)\s*(k|m|million|thousand)?", text)
    if not m:
        return None
    try:
        v = float(m.group(1).replace(",", ""))
    except ValueError:
        return None
    suffix = (m.group(2) or "").lower()
    if suffix in ("k", "thousand"):
        v *= 1_000
    elif suffix in ("m", "million"):
        v *= 1_000_000
    return v


_PROFILE_WORDS = (
    "tell me about", "details", "detail", "profile", "who is", "what do you know",
    "information about", "info on", "summary of", "overview", "background",
    "everything about", "show me", "look up", "lookup",
)

_COMPARE_WORDS = (
    "compare", "comparison", "peer", "similar", "outlier", "unusual",
    "unusually", "deviat", "differ", "benchmark", "versus", " vs ",
    "high", "normal", "typical", "average for", "percentile",
)


def _from_profile(prof) -> DataEvidence:
    """Wrap an EntityProfile as DataEvidence for the pipeline."""
    if not prof.found:
        return DataEvidence(available=False, entity_type=prof.entity_type,
                            entity_id=prof.entity_id, message=prof.message)

    facts = {}
    facts.update(prof.identity)
    facts.update(prof.activity)
    facts.update(prof.risk)
    facts.update(prof.claims_activity)
    facts.update(prof.exclusion)

    records = list(prof.top_procedures)
    for row in prof.by_year:
        records.append({"type": "year", **row})

    note = ""
    if prof.not_available:
        note = " Not available: " + "; ".join(prof.not_available)

    return DataEvidence(
        available=True,
        entity_type=prof.entity_type,
        entity_id=prof.entity_id,
        facts={k: v for k, v in facts.items() if v is not None},
        peer_comparison=prof.peer_position,
        records=records,
        query_description=(
            f"Full profile for {prof.entity_type} {prof.entity_id} from "
            f"{', '.join(prof.sources_used) or 'connected sources'}.{note}"
        ),
    )


def _dispatch(self: StructuredDataService, question: str,
              entities: dict[str, list[str]]) -> DataEvidence:
    if not self.is_available():
        return DataEvidence(message=NOT_BUILT)

    from backend.data.profile import claim_profile, provider_profile

    q = question.lower()
    npi = (entities.get("provider") or [None])[0]
    claim = (entities.get("claim") or [None])[0]

    # 1. Claim lookup - always the full profile, since a claim has few facts
    #    and an investigator asking about one wants all of them.
    if claim:
        return _from_profile(claim_profile(claim))

    # 2. Provider question. A narrow comparison question gets the peer
    #    analysis; anything broader gets the full profile, which already
    #    includes the model's peer percentiles.
    if npi:
        wants_compare = any(w in q for w in _COMPARE_WORDS)
        wants_profile = any(w in q for w in _PROFILE_WORDS)
        if wants_compare and not wants_profile:
            return self.get_peer_comparison(npi)
        return _from_profile(provider_profile(npi))

    # 3. Ranking
    if any(w in q for w in ("highest", "top ", "largest", "most ", "rank",
                            "lowest", "smallest", "bottom")):
        ascending = any(w in q for w in ("lowest", "smallest", "bottom", "least"))
        m = _re.search(r"\b(?:top|bottom|first)\s+(\d{1,3})\b", q)
        limit = int(m.group(1)) if m else 10
        state = None
        sm = _re.search(r"\bin\s+([A-Z]{2})\b", question)
        if sm:
            state = sm.group(1)
        return self.rank_providers(metric=_metric_from(q), limit=min(limit, 50),
                                   ascending=ascending, state=state)

    # 4. Threshold
    if any(w in q for w in ("exceed", "more than", "greater than", "above",
                            "over ", "less than", "below", "under ")):
        value = _amount_from(q)
        if value is not None:
            op = "<" if any(w in q for w in ("less than", "below", "under ")) else ">"
            return self.threshold_filter(metric=_metric_from(q), operator=op,
                                         value=value)

    # 5. Dataset overview
    if any(w in q for w in ("what data", "which dataset", "how many records",
                            "datasets", "what do you have", "data available")):
        return self.dataset_overview()

    # 6. Named but unresolvable
    return DataEvidence(
        available=False,
        message=(
            "This question needs a specific provider NPI, a claim ID, or a "
            "ranking or threshold to query. Provider lookups use a 10-digit "
            "NPI; claim lookups use a claim ID."
        ),
    )


StructuredDataService.query = _dispatch
