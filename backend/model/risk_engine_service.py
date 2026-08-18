"""
PHASE 9 - Risk engine service.

Reads the EXISTING output of the platform's provider risk model. It contains no
scoring logic, and none should ever be added: if the assistant could compute a
score it would become a second, unvalidated detection engine and an investigator
could not tell which number came from where.

THE MODEL (per the platform's own metadata)
-------------------------------------------
Isolation Forest over 46 features, trained on 36,108 providers, bundled into a
weighted 0-100 Provider Risk Score:

    global anomaly    0.35    Isolation Forest, percentile-ranked
    peer deviation    0.30    specialty-peer z-scores
    service pattern           service-mix concentration
    geo deviation             state/national price benchmarks

Tiers: Low 0-29, Moderate 30-59, High 60-79, Critical 80-100.

The platform states plainly that no fraud ground-truth label exists or was used,
and that the model flags statistical anomalies rather than confirmed fraud. The
assistant's language reflects that.

RISK FACTORS
------------
The model does not emit named factors. It emits five peer-compared metrics, each
with the provider's value, peer median, percentile and deviation ratio. Those
ARE the factors, and they carry more evidence than a bare label would: a factor
here reads "payment per service is 4.2x the peer median (99th percentile)".

Factors are surfaced only when the metric is genuinely deviant (>=90th or <=10th
percentile). Reporting every metric regardless of deviation would bury the
signal.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.data import warehouse as wh

NOT_CONNECTED = (
    "Risk engine output is not loaded. Place provider_risk_scores.csv in "
    "data_raw/ and run: python scripts/build_data.py"
)

# Metric column groups, with the plain-language name used in explanations.
_METRICS = [
    ("Payment per service", "m_pay_per_svc", "m_pay_per_svc_peer",
     "m_pay_per_svc_pct", "m_pay_per_svc_dev", True),
    ("Charge per service", "m_chrg_per_svc", "m_chrg_per_svc_peer",
     "m_chrg_per_svc_pct", "m_chrg_per_svc_dev", True),
    ("Services per beneficiary", "m_svc_per_bene", "m_svc_per_bene_peer",
     "m_svc_per_bene_pct", "m_svc_per_bene_dev", False),
    ("Payment-to-charge ratio", "m_pay_chrg", "m_pay_chrg_peer",
     "m_pay_chrg_pct", "m_pay_chrg_dev", False),
    ("Service concentration (HHI)", "m_hhi", "m_hhi_peer",
     "m_hhi_pct", "m_hhi_dev", False),
]

# Component values only. The model's internal weights are not shown: an
# investigator acts on which signal fired, not on how it was weighted.
_COMPONENTS = [
    ("Statistical anomaly (Isolation Forest)", "comp_anomaly"),
    ("Peer deviation", "comp_peer_deviation"),
    ("Service pattern concentration", "comp_service_pattern"),
    ("Geographic price deviation", "comp_geo_deviation"),
]


@dataclass
class RiskFactor:
    name: str
    description: str = ""
    contribution: float | None = None
    observed_value: Any = None
    peer_reference: Any = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "contribution": self.contribution,
            "observed_value": self.observed_value,
            "peer_reference": self.peer_reference,
        }


@dataclass
class ModelInformation:
    """
    Model output, with the SOURCE of every score attached.

    WHY THE LABEL MATTERS
    Two different scores exist for the same provider:

      Provider_Risk_Score   from the provider risk model (Isolation Forest)
      overall_risk          from multi-agent synthesis, which BLENDS five
                            components - and the provider score is one of them,
                            weighted 0.30

    They legitimately differ. A provider extreme at the provider level but
    ordinary at the claim level scores high on the first and lower on the
    second. Their tier boundaries differ too, so the same case can read
    Critical under one and High under the other.

    Shown as bare numbers side by side, an investigator cannot tell which is
    which and may act on the wrong one. So every score carries `score_label`
    naming what produced it, and a synthesis score carries its component
    breakdown - because the breakdown is what explains the difference.
    """

    available: bool = False
    message: str = ""
    entity_type: str | None = None
    entity_id: str | None = None
    risk_score: float | None = None
    risk_level: str | None = None
    risk_factors: list[RiskFactor] = field(default_factory=list)
    detected_anomalies: list[str] = field(default_factory=list)
    model_prediction: str | None = None
    detection_reason: str | None = None
    model_version: str | None = None
    scored_at: str | None = None
    score_components: dict[str, Any] = field(default_factory=dict)
    peer_group: str | None = None
    score_label: str = "Provider risk score"
    score_source: str = "provider_model"
    component_scores: list[dict[str, Any]] = field(default_factory=list)
    priority: str | None = None
    agents_executed: list[str] = field(default_factory=list)
    agents_skipped: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    data_availability: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any] | None:
        if not self.available:
            return None
        return {
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "risk_score": self.risk_score,
            "risk_level": self.risk_level,
            "risk_factors": [f.to_dict() for f in self.risk_factors],
            "detected_anomalies": self.detected_anomalies,
            "model_prediction": self.model_prediction,
            "detection_reason": self.detection_reason,
            "model_version": self.model_version,
            "scored_at": self.scored_at,
            "score_components": self.score_components,
            "component_scores": self.component_scores,
            "score_label": self.score_label,
            "score_source": self.score_source,
            "priority": self.priority,
            "agents_executed": self.agents_executed,
            "agents_skipped": self.agents_skipped,
            "limitations": self.limitations,
            "data_availability": self.data_availability,
            "peer_group": self.peer_group,
        }


def _fmt(v, money: bool) -> str | None:
    if v is None:
        return None
    return f"${v:,.2f}" if money else (f"{v:,.0f}" if float(v).is_integer()
                                       else f"{v:,.2f}")


class RiskEngineService:
    """Read-only access to existing risk model output."""

    def is_available(self) -> bool:
        return wh.is_built() and wh.has("provider_risk")

    def status(self) -> dict[str, Any]:
        from backend.model import agent_bridge

        agents = agent_bridge.status()
        if not self.is_available():
            return {"connected": agents["connected"], "phase": 9,
                    "message": NOT_CONNECTED, "model_version": None,
                    "multi_agent": agents}
        n = wh.scalar("SELECT COUNT(*) FROM provider_risk")
        return {
            "connected": True,
            "phase": 9,
            "message": f"Provider risk model output loaded ({n:,} providers).",
            "model_version": "provider_risk_pipeline (IsolationForest ensemble)",
            "multi_agent": agents,
        }

    def get_provider_risk(self, npi: str) -> ModelInformation:
        if not self.is_available():
            return ModelInformation(message=NOT_CONNECTED,
                                    entity_type="provider", entity_id=npi)

        row = wh.one("SELECT * FROM provider_risk WHERE npi = ?", [str(npi)])
        if not row:
            return ModelInformation(
                available=False, entity_type="provider", entity_id=npi,
                message=(
                    f"NPI {npi} was not scored by the provider risk model. The "
                    "model covers 36,108 providers; an NPI outside that "
                    "population has no score."
                ),
            )

        # --- risk factors: only genuinely deviant metrics ---
        factors: list[RiskFactor] = []
        for label, col, peer_col, pct_col, dev_col, money in _METRICS:
            pct, dev = row.get(pct_col), row.get(dev_col)
            if pct is None:
                continue
            pctile = pct * 100 if pct <= 1 else pct
            if not (pctile >= 90 or pctile <= 10):
                continue
            direction = "above" if pctile >= 90 else "below"
            desc = f"{pctile:.0f}th percentile within peer group"
            if dev:
                desc += f", {dev:.2f}x the peer median"
            factors.append(RiskFactor(
                name=f"{label} {direction} peers",
                description=desc,
                contribution=round(abs(pctile - 50) / 50, 3),
                observed_value=_fmt(row.get(col), money),
                peer_reference=_fmt(row.get(peer_col), money),
            ))
        factors.sort(key=lambda f: f.contribution or 0, reverse=True)

        # --- anomalies the model recorded separately ---
        anomalies: list[str] = []
        if row.get("leie_excluded"):
            anomalies.append("Provider appears on the OIG exclusion list (LEIE)")
        for label, key, threshold in [
            ("Rapid growth in services", "growth_services", 200),
            ("Rapid growth in payment", "growth_payment", 200),
        ]:
            v = row.get(key)
            if v is not None and v >= threshold:
                anomalies.append(f"{label}: {v:,.0f}% over the observed period")
        g = row.get("geo_pct_svcs_2x")
        if g is not None and g >= 0.25:
            anomalies.append(
                f"{g * 100:.0f}% of services priced above 2x the geographic benchmark")

        components = {}
        for label, col in _COMPONENTS:
            v = row.get(col)
            if v is not None:
                components[label] = f"{v:.2f}"

        years = None
        if row.get("year_first") and row.get("year_last"):
            years = f"{row['year_first']}-{row['year_last']}"

        return ModelInformation(
            available=True,
            entity_type="provider",
            entity_id=str(npi),
            risk_score=round(row["risk_score"], 1) if row.get("risk_score") else None,
            risk_level=row.get("risk_tier"),
            risk_factors=factors,
            detected_anomalies=anomalies,
            detection_reason=(
                "Unified provider risk score combining a statistical anomaly "
                "component, specialty-peer deviation, service-pattern "
                "concentration and geographic price deviation."
            ),
            model_version="Provider Risk Pipeline (IsolationForest ensemble, 46 features)",
            scored_at=years,
            score_components=components,
            peer_group=row.get("peer_group"),
            score_label="Provider risk score",
            score_source="provider_model",
        )

    def get_claim_risk(self, claim_id: str) -> ModelInformation:
        """Claim-level risk output is not loaded in this build."""
        return ModelInformation(
            available=False, entity_type="claim", entity_id=claim_id,
            message=(
                "Claim-level risk scores are not loaded. The provider risk model "
                "is connected; claim risk output would need to be added to "
                "data_raw/ in the same way."
            ),
        )

    def load_handoff(self, payload) -> Any:
        """
        Parse a multi-agent RAGExplanationRequest.

        Their contract forbids this module from recomputing risk, so nothing is
        derived here - the payload is read and rendered.
        """
        from backend.model.handoff import parse

        return parse(payload)

    def get_risk(self, entities: dict[str, list[str]]) -> ModelInformation:
        """
        Model output for whichever entity the question referenced.

        PRECEDENCE: the multi-agent investigation wins when available, because
        its synthesis score is the platform's final answer and drives triage
        priority. The provider risk model's score is one of its five components
        (weighted 0.30) and is reported inside the component breakdown, so
        nothing is lost by leading with the synthesis.

        When the orchestrator is unavailable - running outside the main repo,
        or the entity is unknown to it - this falls back to the provider risk
        model rather than reporting nothing.
        """
        from backend.model import agent_bridge

        case = agent_bridge.investigate(entities)
        if case is not None and case.available:
            return self._from_handoff(case)

        if entities.get("provider"):
            return self.get_provider_risk(entities["provider"][0])
        if entities.get("claim"):
            return self.get_claim_risk(entities["claim"][0])
        return ModelInformation(
            available=False,
            message=("This question needs a specific provider NPI or claim ID "
                     "to look up model output."),
        )

    @staticmethod
    def _from_handoff(case) -> ModelInformation:
        """Convert a parsed multi-agent case into ModelInformation."""
        d = case.to_model_information()
        factors = [
            RiskFactor(
                name=f.get("name", ""),
                description=f.get("description", ""),
                contribution=f.get("contribution"),
                observed_value=f.get("observed_value"),
                peer_reference=f.get("peer_reference"),
            )
            for f in d.get("risk_factors") or []
        ]
        info = ModelInformation(
            available=True,
            entity_type=d.get("entity_type") or "provider",
            entity_id=d.get("entity_id"),
            risk_score=d.get("risk_score"),
            risk_level=d.get("risk_level"),
            risk_factors=factors,
            detected_anomalies=d.get("detected_anomalies") or [],
            detection_reason=d.get("detection_reason"),
            model_version=d.get("model_version"),
            scored_at=d.get("scored_at"),
            score_components=d.get("score_components") or {},
            peer_group=d.get("peer_group"),
        )
        info.score_label = d.get("score_label", "Overall risk")
        info.score_source = d.get("score_source", "multi_agent_synthesis")
        info.component_scores = d.get("component_scores") or []
        # Agent-reported gaps must survive into the answer: their guide states
        # that missing data is not the same as low risk.
        info.priority = d.get("priority")
        info.agents_executed = d.get("agents_executed") or []
        info.agents_skipped = d.get("agents_skipped") or []
        info.limitations = d.get("limitations") or []
        info.data_availability = d.get("data_availability") or {}
        return info

    def top_risk_providers(self, limit: int = 10,
                           tier: str | None = None) -> list[dict[str, Any]]:
        if not self.is_available():
            return []
        where, params = [], []
        if tier:
            where.append("LOWER(risk_tier) = ?")
            params.append(tier.lower())
        clause = f"WHERE {' AND '.join(where)}" if where else ""
        return wh.query(f"""
            SELECT npi, provider_type, state, risk_score, risk_tier, peer_group
            FROM provider_risk {clause}
            ORDER BY risk_score DESC LIMIT ?
        """, params + [limit])


_service: RiskEngineService | None = None


def get_risk_engine() -> RiskEngineService:
    global _service
    if _service is None:
        _service = RiskEngineService()
    return _service
