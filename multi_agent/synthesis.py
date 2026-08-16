from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence

from multi_agent.schemas.finding import Finding
from multi_agent.schemas.investigation_case import InvestigationCase

SEVERITY_WEIGHTS = {
    "INFO": 0,
    "LOW": 10,
    "MEDIUM": 25,
    "HIGH": 50,
    "CRITICAL": 80,
}

SEVERITY_ORDER = ["INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL"]


@dataclass
class InvestigationResult:
    """Aggregated investigation outcome derived from agent findings.

    The synthesized score is an investigation-priority score, not a replacement for the
    upstream ML risk outputs. It is intentionally explainable and capped so the case
    narrative remains grounded in actual evidence.
    """

    case_id: str
    claim_id: Optional[str] = None
    claim_type: Optional[str] = None
    provider_id: Optional[str] = None
    provider_id_type: Optional[str] = None
    claim_risk_score: Optional[float] = None
    final_risk_level: Optional[str] = None
    final_risk_priority: Optional[int] = None
    final_claim_rank: Optional[int] = None
    provider_npi: Optional[int] = None
    provider_type: Optional[str] = None
    provider_state: Optional[str] = None
    provider_risk_score: Optional[float] = None
    risk_tier: Optional[str] = None
    global_anomaly_score: Optional[float] = None
    findings: List[Finding] = field(default_factory=list)
    findings_by_agent: Dict[str, List[Finding]] = field(default_factory=dict)
    findings_by_category: Dict[str, List[Finding]] = field(default_factory=dict)
    routing: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    summary: Dict[str, Any] = field(default_factory=dict)
    investigation_risk_score: float = 0.0
    investigation_priority: str = "LOW"
    strongest_evidence: List[Finding] = field(default_factory=list)
    explanation: str = ""
    status: str = "OPEN"
    agent_errors: Dict[str, str] = field(default_factory=dict)
    evidence_quality: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "case_id": self.case_id,
            "claim_id": self.claim_id,
            "claim_type": self.claim_type,
            "provider_id": self.provider_id,
            "provider_id_type": self.provider_id_type,
            "claim_risk_score": self.claim_risk_score,
            "final_risk_level": self.final_risk_level,
            "final_risk_priority": self.final_risk_priority,
            "final_claim_rank": self.final_claim_rank,
            "provider_npi": self.provider_npi,
            "provider_type": self.provider_type,
            "provider_state": self.provider_state,
            "provider_risk_score": self.provider_risk_score,
            "risk_tier": self.risk_tier,
            "global_anomaly_score": self.global_anomaly_score,
            "findings": [f.__dict__ for f in self.findings],
            "findings_by_agent": {k: [f.__dict__ for f in v] for k, v in self.findings_by_agent.items()},
            "findings_by_category": {k: [f.__dict__ for f in v] for k, v in self.findings_by_category.items()},
            "routing": self.routing,
            "summary": self.summary,
            "investigation_risk_score": self.investigation_risk_score,
            "investigation_priority": self.investigation_priority,
            "strongest_evidence": [f.__dict__ for f in self.strongest_evidence],
            "explanation": self.explanation,
            "status": self.status,
            "agent_errors": self.agent_errors,
            "evidence_quality": self.evidence_quality,
        }


class Synthesis:
    """Deterministic evidence aggregation layer for the multi-agent system.

    Formula:
      investigation_risk_score = min(100, sum(SEVERITY_WEIGHTS[f.severity] for unique findings))

    This is an investigation-priority score, not a replacement for the upstream ML risk
    outputs. It is used to drive review prioritization and explanation generation.
    """

    def investigate(
        self,
        case: InvestigationCase,
        billing_findings: Optional[Sequence[Finding]] = None,
        peer_findings: Optional[Sequence[Finding]] = None,
        clinical_rule_findings: Optional[Sequence[Finding]] = None,
        agent_errors: Optional[Dict[str, str]] = None,
    ) -> InvestigationResult:
        if case is None:
            case = InvestigationCase(case_id="UNKNOWN", claim_id="UNKNOWN")

        billing = self._safe_list(billing_findings)
        peer = self._safe_list(peer_findings)
        clinical = self._safe_list(clinical_rule_findings)

        all_findings = self._deduplicate_findings(billing + peer + clinical)
        findings_by_agent = {
            "billing": self._filter_agent(all_findings, "billing"),
            "peer": self._filter_agent(all_findings, "peer"),
            "clinical_rule": self._filter_agent(all_findings, "clinical_rule"),
        }

        findings_by_category = self._group_by_category(all_findings)
        summary = self._make_summary(findings_by_agent, all_findings)
        severity_counts = self._severity_counts(all_findings)
        summary.update(severity_counts)
        summary.setdefault("total_findings", len(all_findings))

        investigation_risk_score = min(100.0, float(sum(self._weight_for(f) for f in all_findings)))
        investigation_priority = self._priority_for_score(investigation_risk_score)
        status = self._status_for_score(investigation_risk_score)
        strongest_evidence = self._strongest_evidence(all_findings)
        explanation = self._build_explanation(all_findings, findings_by_agent)
        evidence_quality = self._evidence_quality(all_findings)

        result = InvestigationResult(
            case_id=case.case_id,
            claim_id=case.claim_id,
            claim_type=(case.claim.claim_type if case.claim is not None else None),
            provider_id=(case.claim.provider_id if case.claim is not None else None),
            provider_id_type=(case.claim.provider_id_type if case.claim is not None else None),
            claim_risk_score=(case.claim.claim_risk_score if case.claim is not None else None),
            final_risk_level=(case.claim.final_risk_level if case.claim is not None else None),
            final_risk_priority=(case.claim.final_risk_priority if case.claim is not None else None),
            final_claim_rank=(case.claim.final_claim_rank if case.claim is not None else None),
            provider_npi=(case.provider.npi if case.provider is not None else None),
            provider_type=(case.provider.provider_type if case.provider is not None else None),
            provider_state=(case.provider.provider_state if case.provider is not None else None),
            provider_risk_score=(case.provider.provider_risk_score if case.provider is not None else None),
            risk_tier=(case.provider.risk_tier if case.provider is not None else None),
            global_anomaly_score=(case.provider.global_anomaly_score if case.provider is not None else None),
            findings=all_findings,
            findings_by_agent=findings_by_agent,
            findings_by_category=findings_by_category,
            summary=summary,
            investigation_risk_score=investigation_risk_score,
            investigation_priority=investigation_priority,
            strongest_evidence=strongest_evidence,
            explanation=explanation,
            status=status,
            agent_errors=(agent_errors or {}),
            evidence_quality=evidence_quality,
        )
        return result

    @staticmethod
    def _safe_list(items: Optional[Sequence[Finding]]) -> List[Finding]:
        if items is None:
            return []
        return [item for item in items if item is not None]

    @staticmethod
    def _deduplicate_findings(findings: Sequence[Finding]) -> List[Finding]:
        seen = set()
        unique: List[Finding] = []
        for finding in findings:
            key = (
                finding.agent,
                finding.category,
                finding.rule,
                finding.severity,
                Synthesis._stable_json(finding.evidence),
            )
            if key in seen:
                continue
            seen.add(key)
            unique.append(finding)
        return unique

    @staticmethod
    def _filter_agent(findings: Sequence[Finding], agent_name: str) -> List[Finding]:
        if agent_name in {"clinical_rule", "clinical"}:
            return [f for f in findings if f.agent in {"clinical_rule", "clinical"}]
        return [f for f in findings if f.agent == agent_name]

    @staticmethod
    def _group_by_category(findings: Sequence[Finding]) -> Dict[str, List[Finding]]:
        grouped: Dict[str, List[Finding]] = {}
        for finding in findings:
            bucket = finding.category or "general"
            grouped.setdefault(bucket, []).append(finding)
        return grouped

    @staticmethod
    def _make_summary(findings_by_agent: Dict[str, List[Finding]], findings: Sequence[Finding]) -> Dict[str, Any]:
        return {
            "total_findings": len(findings),
            "billing_finding_count": len(findings_by_agent.get("billing", [])),
            "peer_finding_count": len(findings_by_agent.get("peer", [])),
            "clinical_rule_finding_count": len(findings_by_agent.get("clinical_rule", [])),
        }

    @staticmethod
    def _severity_counts(findings: Sequence[Finding]) -> Dict[str, int]:
        counts = {level: 0 for level in SEVERITY_ORDER}
        for finding in findings:
            level = str(finding.severity or "INFO").upper()
            if level not in counts:
                level = "INFO"
            counts[level] += 1
        return counts

    @staticmethod
    def _weight_for(finding: Finding) -> float:
        degree = str(finding.severity or "INFO").upper()
        return float(SEVERITY_WEIGHTS.get(degree, 0))

    @staticmethod
    def _priority_for_score(score: float) -> str:
        if score >= 80:
            return "CRITICAL"
        if score >= 60:
            return "HIGH"
        if score >= 25:
            return "MEDIUM"
        return "LOW"

    @staticmethod
    def _status_for_score(score: float) -> str:
        if score == 0:
            return "OPEN"
        if score >= 80:
            return "CRITICAL_REVIEW"
        if score >= 60:
            return "HIGH_PRIORITY_REVIEW"
        return "REVIEW_REQUIRED"

    @staticmethod
    def _strongest_evidence(findings: Sequence[Finding]) -> List[Finding]:
        if not findings:
            return []
        ranked = sorted(
            findings,
            key=lambda f: (
                SEVERITY_WEIGHTS.get(str(f.severity or "INFO").upper(), 0),
                float(f.confidence or 0.0),
                Synthesis._evidence_quality_score(f.evidence),
            ),
            reverse=True,
        )
        return ranked[:3]

    @staticmethod
    def _evidence_quality_score(evidence: Optional[Dict[str, Any]]) -> int:
        if not evidence:
            return 0
        explicit_numeric = any(
            isinstance(v, (int, float)) for v in evidence.values()
        )
        if explicit_numeric:
            return 2
        if evidence:
            return 1
        return 0

    @staticmethod
    def _evidence_quality(findings: Sequence[Finding]) -> Dict[str, int]:
        quality = {
            "high_quality_evidence_count": 0,
            "medium_quality_evidence_count": 0,
            "summary_score_only_count": 0,
            "unavailable_evidence_count": 0,
        }
        for finding in findings:
            evidence = finding.evidence or {}
            if not evidence:
                quality["unavailable_evidence_count"] += 1
            elif Synthesis._evidence_quality_score(evidence) >= 2:
                quality["high_quality_evidence_count"] += 1
            elif any(k in evidence for k in {"peer_deviation_score", "geo_deviation_score", "risk_tier"}):
                quality["summary_score_only_count"] += 1
            else:
                quality["medium_quality_evidence_count"] += 1
        return quality

    @staticmethod
    def _build_explanation(findings: Sequence[Finding], findings_by_agent: Dict[str, List[Finding]]) -> str:
        if not findings:
            return (
                "No billing, peer, or clinical/rule findings were returned for this case. "
                "The case remains informational only; absence of findings does not prove absence of risk."
            )

        billing_count = len(findings_by_agent.get("billing", []))
        peer_count = len(findings_by_agent.get("peer", []))
        clinical_count = len(findings_by_agent.get("clinical_rule", []))
        primary_rules = [f.rule for f in sorted(findings, key=lambda f: (SEVERITY_WEIGHTS.get(str(f.severity or "INFO").upper(), 0), float(f.confidence or 0.0)), reverse=True)[:3]]

        strong_text = ", ".join(primary_rules) if primary_rules else "supporting evidence"
        return (
            f"The case contains {len(findings)} investigation findings: {billing_count} billing, "
            f"{peer_count} peer, and {clinical_count} clinical/rule findings. "
            f"The strongest evidence is based on: {strong_text}."
        )

    @staticmethod
    def _stable_json(value: Any) -> str:
        try:
            return json.dumps(value, sort_keys=True, default=str)
        except TypeError:
            return str(value)
