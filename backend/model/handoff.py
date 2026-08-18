"""
Multi-agent handoff: parsing RAGExplanationRequest.

THE CONTRACT
The multi-agent system emits one canonical artifact per investigated case, built
by `multi_agent.rag.handoff.build_rag_handoff()`. Their integration guide is
explicit about the boundary:

  This module MAY use   case, evidence, findings, risk_synthesis,
                        agent_results, genai_context, metadata, provenance,
                        limitations

  This module MUST NOT  re-run risk scoring, recompute overall risk or risk
                        category, improvise peer baselines or provider
                        statistics, or reinterpret a case while ignoring the
                        stated evidence and limitations

So nothing here computes a score. Everything reported comes from the payload.

WHAT THIS MODULE ADDS
Their pipeline produces findings and a score. It has no domain knowledge base,
so it cannot say what a finding MEANS, what could produce it legitimately, or
what an investigator should examine. That is this system's job, and it is why
their contract lists "retrieve policy/domain knowledge relevant to the evidence"
as a RAG-team responsibility.

MISSING DATA IS NOT LOW RISK
Their guide states it directly: "Missing fields are not equal to normal or low
risk." So skipped agents, unavailable data and stated limitations are surfaced
in the explanation rather than quietly dropped.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def _f(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _fmt(v, unit: str | None = None) -> str | None:
    if v is None:
        return None
    if unit and unit.lower() in ("usd", "dollars", "$"):
        return f"${v:,.2f}"
    return f"{v:,.0f}" if float(v).is_integer() else f"{v:,.2f}"


@dataclass
class AgentFinding:
    """One finding, with its evidence resolved from evidence_ids."""

    finding_id: str = ""
    agent: str = ""
    title: str = ""
    description: str = ""
    severity: str = ""
    category: str = ""
    confidence: float | None = None
    evidence: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.title or self.finding_id,
            "description": self.description,
            "contribution": self.confidence,
            "observed_value": self._headline(),
            "peer_reference": self._peer(),
            "agent": self.agent,
            "severity": self.severity,
            "category": self.category,
            "evidence": self.evidence,
        }

    def _headline(self) -> str | None:
        for e in self.evidence:
            v = e.get("provider_value") or e.get("claim_value")
            if v is not None:
                return _fmt(v, e.get("unit"))
        return None

    def _peer(self) -> str | None:
        for e in self.evidence:
            if e.get("peer_median") is not None:
                return _fmt(e["peer_median"], e.get("unit"))
        return None

    def as_text(self) -> str:
        """Render for the prompt, including quantitative evidence."""
        head = f"- [{self.agent}] {self.title or self.finding_id}"
        if self.severity:
            head += f" (severity {self.severity})"
        lines = [head]
        if self.description:
            lines.append(f"  {self.description}")
        for e in self.evidence:
            bits = [f"metric: {e.get('metric')}"]
            for label, key in (("value", "provider_value"),
                               ("claim value", "claim_value"),
                               ("peer median", "peer_median"),
                               ("peer mean", "peer_mean"),
                               ("baseline", "baseline_value"),
                               ("threshold", "threshold")):
                if e.get(key) is not None:
                    bits.append(f"{label}: {_fmt(e[key], e.get('unit'))}")
            if e.get("percentile") is not None:
                p = e["percentile"]
                bits.append(f"percentile: {p * 100:.0f}" if p <= 1
                            else f"percentile: {p:.0f}")
            if e.get("deviation_ratio") is not None:
                bits.append(f"deviation: {e['deviation_ratio']:.2f}x peer median")
            if e.get("peer_group"):
                bits.append(f"peer group: {e['peer_group']}")
            if e.get("peer_sample_size") is not None:
                bits.append(f"peer sample size: {e['peer_sample_size']}")
            lines.append("    " + "; ".join(bits))
        return "\n".join(lines)


@dataclass
class HandoffCase:
    """A parsed RAGExplanationRequest."""

    available: bool = False
    message: str = ""
    case_id: str = ""
    claim_id: str | None = None
    provider_id: str | None = None
    provider_id_type: str | None = None
    claim_type: str | None = None

    overall_risk: float | None = None
    risk_category: str | None = None
    priority: str | None = None
    methodology: str | None = None
    components: dict[str, Any] = field(default_factory=dict)
    weights: dict[str, Any] = field(default_factory=dict)

    findings: list[AgentFinding] = field(default_factory=list)
    agents_executed: list[str] = field(default_factory=list)
    agents_skipped: list[str] = field(default_factory=list)
    agent_status: dict[str, str] = field(default_factory=dict)
    limitations: list[str] = field(default_factory=list)
    data_availability: dict[str, str] = field(default_factory=dict)
    synthesis_complete: bool | None = None
    synthesis_warnings: list[str] = field(default_factory=list)

    def component_breakdown(self) -> list[dict[str, Any]]:
        """
        The five synthesis components, each with its weight.

        This is what explains why the synthesis score differs from the provider
        model's score: the provider score is ONE component, weighted 0.30. A
        provider extreme at the provider level and ordinary at the claim level
        will show a high provider_anomaly and a lower overall risk.
        """
        labels = {
            "claim anomaly": "Claim anomaly (upstream ML)",
            "provider anomaly": "Provider anomaly (provider risk model)",
            "peer score": "Peer benchmark",
            "billing score": "Billing analysis",
            "rule score": "Rule-based",
        }
        out = []
        for key, value in self.components.items():
            out.append({
                "name": labels.get(key, key),
                "value": value,
                "is_provider_model": key == "provider anomaly",
            })
        return out

    def to_model_information(self) -> dict[str, Any]:
        """Shape the API's model_information field expects."""
        return {
            "entity_type": "claim" if self.claim_id else "provider",
            "entity_id": self.claim_id or self.provider_id,
            "case_id": self.case_id,
            "risk_score": self.overall_risk,
            "risk_level": self.risk_category,
            "priority": self.priority,
            "risk_factors": [f.to_dict() for f in self.findings],
            "detected_anomalies": [],
            "model_prediction": None,
            "detection_reason": self.methodology,
            "model_version": "multi-agent investigation",
            "scored_at": None,
            "score_components": self.components,
            "component_scores": self.component_breakdown(),
            # The synthesis score is the platform's final answer, so it is the
            # headline. The provider model's score appears beneath it as the
            # component it actually is.
            "score_label": "Overall risk (multi-agent synthesis)",
            "score_source": "multi_agent_synthesis",
            "peer_group": None,
            "agents_executed": self.agents_executed,
            "agents_skipped": self.agents_skipped,
            "limitations": self.limitations,
            "data_availability": self.data_availability,
        }

    def as_prompt_block(self) -> str:
        """Render the whole case for the LLM."""
        if not self.available:
            return self.message or "No multi-agent case supplied."

        lines = [f"CASE {self.case_id}"]
        ident = {
            "claim id": self.claim_id,
            "claim type": self.claim_type,
            "provider id": self.provider_id,
            "provider id type": self.provider_id_type,
        }
        for k, v in ident.items():
            if v:
                lines.append(f"- {k}: {v}")

        lines.append("\nRisk synthesis (computed by the multi-agent system, "
                     "not by this assistant):")
        if self.overall_risk is not None:
            lines.append(f"- overall risk: {self.overall_risk}")
        if self.risk_category:
            lines.append(f"- risk category: {self.risk_category}")
        if self.priority:
            lines.append(f"- priority: {self.priority}")
        for k, v in self.components.items():
            lines.append(f"- component {k}: {v}")
        if self.methodology:
            lines.append(f"- methodology: {self.methodology}")

        if self.findings:
            lines.append("\nFindings:")
            for f in self.findings:
                lines.append(f.as_text())

        if self.agents_executed or self.agents_skipped:
            lines.append("\nAgent coverage:")
            if self.agents_executed:
                lines.append(f"- executed: {', '.join(self.agents_executed)}")
            if self.agents_skipped:
                lines.append(f"- SKIPPED: {', '.join(self.agents_skipped)}")

        if self.data_availability:
            missing = [k for k, v in self.data_availability.items()
                       if str(v).upper() not in ("AVAILABLE", "TRUE")]
            if missing:
                lines.append("- data NOT available: " + ", ".join(missing))

        if self.limitations:
            lines.append("\nStated limitations (these must appear in the answer; "
                         "missing data is not the same as low risk):")
            for lim in self.limitations:
                lines.append(f"- {lim}")

        if self.synthesis_complete is False:
            lines.append("\n- NOTE: the synthesis is incomplete; not every "
                         "component was available.")
        return "\n".join(lines)


def parse(payload: str | dict | Path) -> HandoffCase:
    """
    Parse a RAGExplanationRequest from a dict, JSON string, or file path.

    Tolerant by design: the payload may arrive with risk_synthesis at the top
    level or only inside case, and evidence may be attached to findings or held
    separately with evidence_ids as the link. Both shapes appear in their code.
    """
    if isinstance(payload, Path) or (isinstance(payload, str)
                                     and payload.strip().startswith("{") is False
                                     and Path(str(payload)).exists()):
        payload = json.loads(Path(str(payload)).read_text(encoding="utf-8"))
    elif isinstance(payload, str):
        payload = json.loads(payload)

    if not isinstance(payload, dict):
        return HandoffCase(message="Handoff payload could not be parsed.")

    case = payload.get("case") or {}
    ctx = payload.get("genai_context") or {}
    meta = payload.get("metadata") or {}
    synth = payload.get("risk_synthesis") or case.get("risk_synthesis") or {}

    h = HandoffCase(available=True)
    h.case_id = case.get("case_id") or ctx.get("case_id") or meta.get("case_id") or ""
    h.claim_id = case.get("claim_id") or ctx.get("claim_id")
    h.provider_id = case.get("provider_id") or ctx.get("provider_id")
    h.provider_id_type = case.get("provider_id_type")
    h.claim_type = case.get("claim_type") or ctx.get("claim_type")

    h.overall_risk = _f(synth.get("overall_risk")) or _f(ctx.get("overall_risk"))
    h.risk_category = synth.get("risk_category") or ctx.get("risk_category")
    h.priority = synth.get("priority") or ctx.get("priority")
    h.methodology = synth.get("methodology")
    h.weights = synth.get("weights") or {}
    h.synthesis_complete = synth.get("is_complete")
    h.synthesis_warnings = list(synth.get("warnings") or [])

    for key in ("claim_anomaly", "provider_anomaly", "billing_score",
                "peer_score", "rule_score"):
        v = _f(synth.get(key)) if key in synth else _f(ctx.get(key))
        if v is not None:
            # Value only. The synthesis weights are their internal formula and
            # an investigator cannot act on them.
            h.components[key.replace("_", " ")] = f"{v:g}"

    # Evidence is keyed by id so findings can resolve theirs.
    ev_index: dict[str, dict] = {}
    for e in (payload.get("evidence") or []) + (case.get("evidence") or []):
        if isinstance(e, dict) and e.get("evidence_id"):
            ev_index[e["evidence_id"]] = e

    raw_findings = payload.get("findings") or case.get("findings") or []
    for f in raw_findings:
        if not isinstance(f, dict):
            continue
        af = AgentFinding(
            finding_id=f.get("finding_id", ""),
            agent=f.get("agent", ""),
            title=f.get("title", ""),
            description=f.get("description", ""),
            severity=f.get("severity", ""),
            category=f.get("category", ""),
            confidence=_f(f.get("confidence")),
        )
        for eid in f.get("evidence_ids") or []:
            if eid in ev_index:
                af.evidence.append(ev_index[eid])
        if not af.evidence and isinstance(f.get("evidence"), list):
            af.evidence = [e for e in f["evidence"] if isinstance(e, dict)]
        h.findings.append(af)

    # Agent coverage. A skipped agent and its reason matter to an investigator.
    h.agents_executed = list(ctx.get("agents_executed") or [])
    h.agents_skipped = list(ctx.get("agents_skipped") or [])
    for r in payload.get("agent_results") or case.get("agent_results") or []:
        if not isinstance(r, dict):
            continue
        name, status = r.get("agent"), str(r.get("status", "")).upper()
        if name:
            h.agent_status[name] = status
            if status in ("SKIPPED", "NOT_SELECTED") and name not in h.agents_skipped:
                h.agents_skipped.append(name)
            elif status == "SUCCESS" and name not in h.agents_executed:
                h.agents_executed.append(name)
        for lim in r.get("limitations") or []:
            if lim not in h.limitations:
                h.limitations.append(lim)

    for lim in (meta.get("limitations") or []) + (ctx.get("limitations") or []) \
            + h.synthesis_warnings:
        if lim and lim not in h.limitations:
            h.limitations.append(lim)

    avail = meta.get("data_availability") or ctx.get("data_availability") or {}
    h.data_availability = {k: str(v) for k, v in avail.items()
                           if not k.startswith("evidence:")}

    if not h.case_id and not h.findings and h.overall_risk is None:
        return HandoffCase(message="Payload contained no recognisable case data.")
    return h
