from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

CONTRACT_VERSION = "1.0"


class DataAvailability(str, Enum):
    AVAILABLE = "AVAILABLE"
    NOT_AVAILABLE = "NOT_AVAILABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    ERROR = "ERROR"


class AgentStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    ERROR = "error"
    SKIPPED = "skipped"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"


class RiskCategory(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RiskPriority(str, Enum):
    P3 = "P3"
    P2 = "P2"
    P1 = "P1"
    P0 = "P0"


class ProviderIdType(str, Enum):
    NPI = "NPI"
    PRVDR_NUM = "PRVDR_NUM"
    UNKNOWN = "UNKNOWN"


class InvestigationContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    claim_id: str
    provider_id: Optional[str] = None
    provider_id_type: ProviderIdType = ProviderIdType.UNKNOWN
    claim_type: Optional[str] = None

    claim_anomaly: Optional[float] = None
    provider_anomaly: Optional[float] = None

    claim_features: Dict[str, Any] = Field(default_factory=dict)
    provider_features: Dict[str, Any] = Field(default_factory=dict)
    peer_features: Dict[str, Any] = Field(default_factory=dict)

    leie_evidence: Dict[str, Any] = Field(default_factory=dict)

    data_availability: Dict[str, DataAvailability] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    provenance: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("provider_id_type", mode="before")
    @classmethod
    def normalize_provider_id_type(cls, value: Any) -> Any:
        if value is None:
            return ProviderIdType.UNKNOWN
        if isinstance(value, ProviderIdType):
            return value
        normalized = str(value).strip().upper()
        if normalized in {"NPI", "PRVDR_NUM", "UNKNOWN"}:
            return ProviderIdType(normalized)
        return ProviderIdType.UNKNOWN


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    agent: str
    category: str
    metric: str

    provider_value: Optional[float] = None
    claim_value: Optional[float] = None
    baseline_value: Optional[float] = None

    peer_mean: Optional[float] = None
    peer_median: Optional[float] = None
    peer_std: Optional[float] = None

    deviation: Optional[float] = None
    deviation_ratio: Optional[float] = None
    percentile: Optional[float] = None

    peer_group: Optional[str] = None
    peer_sample_size: Optional[int] = None

    geographic_baseline: Optional[str] = None

    threshold: Optional[float] = None
    direction: Optional[str] = None

    unit: Optional[str] = None

    source: Optional[str] = None
    source_fields: List[str] = Field(default_factory=list)
    source_record_id: Optional[str] = None

    methodology: Optional[str] = None
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("agent")
    @classmethod
    def validate_agent(cls, value: str) -> str:
        return value.strip()


class Finding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    finding_id: str
    agent: str
    title: str
    description: str
    severity: str = Field(..., pattern=r"^(INFO|LOW|MEDIUM|HIGH|CRITICAL)$")
    category: str
    evidence_ids: List[str] = Field(default_factory=list)
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    @field_validator("severity", mode="before")
    @classmethod
    def normalize_severity(cls, value: Any) -> Any:
        if value is None:
            return "INFO"
        return str(value).strip().upper()


class RuleHit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_id: str
    rule_name: str
    status: str = Field(..., pattern=r"^(TRIGGERED|NOT_TRIGGERED|NOT_APPLICABLE|INSUFFICIENT_DATA)$")
    severity: str = Field(..., pattern=r"^(INFO|LOW|MEDIUM|HIGH|CRITICAL)$")
    description: str
    evidence_ids: List[str] = Field(default_factory=list)
    threshold: Optional[float] = None
    observed_value: Optional[float] = None
    source: Optional[str] = None
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    @field_validator("severity", mode="before")
    @classmethod
    def normalize_severity(cls, value: Any) -> Any:
        if value is None:
            return "INFO"
        return str(value).strip().upper()


class AgentResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent: str
    status: AgentStatus
    score: int = Field(ge=0, le=100)
    risk: RiskLevel

    findings: List[Finding] = Field(default_factory=list)
    evidence: List[Evidence] = Field(default_factory=list)
    rule_hits: List[RuleHit] = Field(default_factory=list)

    limitations: List[str] = Field(default_factory=list)
    provenance: Dict[str, Any] = Field(default_factory=dict)

    execution_id: str
    execution_time_ms: int = Field(ge=0)

    contract_version: str = CONTRACT_VERSION


class AgentExecution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    execution_id: str
    case_id: str
    agent: str
    status: AgentStatus

    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    execution_time_ms: Optional[int] = Field(default=None, ge=0)

    input_summary: Optional[str] = None
    output_evidence_count: int = Field(default=0, ge=0)
    output_finding_count: int = Field(default=0, ge=0)

    error_code: Optional[str] = None
    error_message: Optional[str] = None

    agent_version: Optional[str] = None
    contract_version: str = CONTRACT_VERSION


class SynthesisContribution(BaseModel):
    """M13: Detailed breakdown of how each component contributed to final risk score."""
    model_config = ConfigDict(extra="forbid")

    component_name: str = Field(description="Name of the risk component (claim_anomaly, provider_anomaly, peer_score, billing_score, rule_score)")
    input_score: Optional[float] = Field(description="Raw input score for this component [0, 100] or None if not available")
    weight: float = Field(description="Weight applied to this component in synthesis (0.0 to 1.0)")
    contribution: Optional[float] = Field(description="This component's contribution to final score (input_score * weight)")


class RiskSynthesis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_anomaly: Optional[float] = None
    provider_anomaly: Optional[float] = None

    billing_score: Optional[float] = None
    peer_score: Optional[float] = None
    rule_score: Optional[float] = None

    weights: Dict[str, int] = Field(default_factory=lambda: {"claim_anomaly": 30, "provider_anomaly": 30, "peer_score": 20, "billing_score": 10, "rule_score": 10})

    overall_risk: float = Field(ge=0, le=100)
    risk_category: RiskCategory
    priority: RiskPriority

    methodology: str
    contributing_agents: List[str] = Field(default_factory=list)

    contract_version: str = CONTRACT_VERSION
    
    # M13: Detailed synthesis breakdown (optional, populated by new RiskSynthesisService)
    synthesis_version: Optional[str] = Field(default=None, description="Version of synthesis logic used (e.g., '1.0.0')")
    raw_score: Optional[float] = Field(default=None, description="Raw score before rounding (may have decimals)")
    contributions: List[SynthesisContribution] = Field(default_factory=list, description="Detailed breakdown of each component's contribution to raw_score")
    errors: List[str] = Field(default_factory=list, description="Errors encountered during synthesis (e.g., invalid component scores)")
    warnings: List[str] = Field(default_factory=list, description="Warnings about synthesis (e.g., missing agents)")
    is_complete: Optional[bool] = Field(default=None, description="True if all 5 components were available, False if any missing")
    is_usable: Optional[bool] = Field(default=None, description="True if synthesis is valid and can be used for risk decisions")

    @model_validator(mode="after")
    def validate_risk_and_category(self) -> "RiskSynthesis":
        risk_value = float(self.overall_risk)
        if risk_value < 40:
            expected = "LOW"
        elif risk_value < 70:
            expected = "MEDIUM"
        elif risk_value < 85:
            expected = "HIGH"
        else:
            expected = "CRITICAL"
        if self.risk_category.value != expected:
            raise ValueError(f"Risk category {self.risk_category.value} does not match overall_risk {risk_value}.")
        return self


class GenAIExplanation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    explanation_id: str
    contract_version: str = CONTRACT_VERSION
    case_id: Optional[str] = None
    model_provider: str = "Groq"
    model_name: str
    summary: str
    risk_interpretation: Dict[str, Any] = Field(default_factory=dict)
    key_findings: List[Dict[str, Any]] = Field(default_factory=list)
    evidence_references: List[str] = Field(default_factory=list)
    investigation_narrative: Optional[str] = None
    limitations: List[str] = Field(default_factory=list)
    recommended_review_actions: List[str] = Field(default_factory=list)
    disclaimer: str = "The deterministic investigation remains the source of truth. This explanation is interpretive only and does not confirm fraud."
    model_metadata: Dict[str, Any] = Field(default_factory=dict)
    generated_at: Optional[str] = None
    prompt_version: str = "1.0"
    explanation_version: str = "1.0"
    source_case_id: Optional[str] = None
    status: str = "generated"

    @field_validator("generated_at", mode="before")
    @classmethod
    def normalize_timestamp(cls, value: Any) -> Any:
        if value is None:
            return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        return value


class GenAIExplanationContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    claim_id: Optional[str] = None
    provider_id: Optional[str] = None
    claim_type: Optional[str] = None
    claim_anomaly: Optional[float] = None
    provider_anomaly: Optional[float] = None
    overall_risk: Optional[float] = None
    risk_category: Optional[RiskCategory] = None
    priority: Optional[RiskPriority] = None
    key_findings: List[Dict[str, str]] = Field(default_factory=list)
    evidence: List[Dict[str, Any]] = Field(default_factory=list)
    rule_hits: List[Dict[str, Any]] = Field(default_factory=list)
    peer_comparisons: List[Dict[str, Any]] = Field(default_factory=list)
    billing_findings: List[Dict[str, Any]] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    provenance: Dict[str, Any] = Field(default_factory=dict)
    agents_executed: List[str] = Field(default_factory=list)
    agents_skipped: List[str] = Field(default_factory=list)
    data_availability: Dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_case(cls, case: "InvestigationCase") -> "GenAIExplanationContext":
        if case is None:
            raise ValueError("InvestigationCase is required for GenAIExplanationContext.")

        risk_synthesis = case.risk_synthesis
        findings_by_agent = {}
        for result in case.agent_results:
            findings_by_agent.setdefault(result.agent, []).extend(result.findings)

        key_findings: List[Dict[str, str]] = []
        for finding in case.findings:
            key_findings.append({
                "agent": finding.agent,
                "finding": finding.title,
                "evidence": finding.description,
            })

        evidence_list: List[Dict[str, Any]] = []
        for evidence in case.evidence:
            evidence_list.append(evidence.model_dump(mode="json", exclude_none=True))

        rule_hits: List[Dict[str, Any]] = []
        for result in case.agent_results:
            for rule in result.rule_hits:
                rule_hits.append(rule.model_dump(mode="json", exclude_none=True))

        peer_comparisons = []
        for ev in case.evidence:
            if ev.agent == "peer":
                peer_comparisons.append({
                    "metric": ev.metric,
                    "provider_value": ev.provider_value,
                    "peer_median": ev.peer_median,
                    "deviation_ratio": ev.deviation_ratio,
                    "percentile": ev.percentile,
                    "peer_group": ev.peer_group,
                    "peer_sample_size": ev.peer_sample_size,
                })

        billing_findings = []
        for result in case.agent_results:
            if result.agent == "billing":
                for finding in result.findings:
                    billing_findings.append({
                        "title": finding.title,
                        "description": finding.description,
                        "severity": finding.severity,
                        "category": finding.category,
                    })

        data_availability = {}
        context = case.investigation_context
        if context is not None and context.data_availability:
            for key, value in context.data_availability.items():
                data_availability[key] = value.value if hasattr(value, "value") else value

        return cls(
            case_id=case.case_id,
            claim_id=case.claim_id,
            provider_id=case.provider_id,
            claim_type=case.claim_type,
            claim_anomaly=(risk_synthesis.claim_anomaly if risk_synthesis else None),
            provider_anomaly=(risk_synthesis.provider_anomaly if risk_synthesis else None),
            overall_risk=(risk_synthesis.overall_risk if risk_synthesis else None),
            risk_category=(risk_synthesis.risk_category if risk_synthesis else None),
            priority=(risk_synthesis.priority if risk_synthesis else None),
            key_findings=key_findings,
            evidence=evidence_list,
            rule_hits=rule_hits,
            peer_comparisons=peer_comparisons,
            billing_findings=billing_findings,
            limitations=[item for result in case.agent_results for item in result.limitations],
            provenance=case.provenance or {},
            agents_executed=[result.agent for result in case.agent_results],
            agents_skipped=[],
            data_availability=data_availability,
        )


class HandoffMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    request_id: str
    generated_at: Optional[str] = None
    source: str = "deterministic_multi_agent"
    data_availability: Dict[str, Any] = Field(default_factory=dict)
    provenance: Dict[str, Any] = Field(default_factory=dict)
    limitations: List[str] = Field(default_factory=list)
    contract_version: str = CONTRACT_VERSION


class RAGExplanationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: str = CONTRACT_VERSION
    request_id: str
    case: "InvestigationCase"
    evidence: List[Evidence]
    findings: List[Finding]
    risk_synthesis: RiskSynthesis
    agent_results: List[AgentResult]
    genai_context: GenAIExplanationContext
    metadata: HandoffMetadata

    @model_validator(mode="after")
    def validate_handoff(self) -> "RAGExplanationRequest":
        if not self.request_id:
            raise ValueError("request_id is required")
        if not self.case or not self.case.case_id:
            raise ValueError("case.case_id is required")
        if self.case.case_id != self.metadata.case_id:
            raise ValueError("metadata.case_id must match case.case_id")
        if not self.risk_synthesis or self.risk_synthesis.overall_risk is None:
            raise ValueError("risk_synthesis is required")
        if not self.case.case_id:
            raise ValueError("case_id is required")

        evidence_ids = [item.evidence_id for item in self.evidence]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("evidence identifiers must be unique")

        for item in self.evidence:
            if item.agent not in {result.agent for result in self.agent_results}:
                if item.agent not in {finding.agent for finding in self.findings}:
                    # allow evidence from the main case that has no explicit agent result record
                    pass

        for result in self.agent_results:
            if result.status not in {"success", "partial", "error", "skipped"}:
                raise ValueError(f"Invalid agent status for {result.agent}: {result.status}")
            if result.score < 0 or result.score > 100:
                raise ValueError(f"Agent result score for {result.agent} is out of range: {result.score}")

        def _finite(value: Any) -> bool:
            if value is None:
                return True
            if isinstance(value, (int, float)):
                return value == value and value not in (float("inf"), float("-inf"))
            return True

        for evidence in self.evidence:
            for field in [
                "provider_value", "claim_value", "baseline_value", "peer_mean", "peer_median",
                "peer_std", "deviation", "deviation_ratio", "percentile", "threshold",
            ]:
                if not _finite(getattr(evidence, field, None)):
                    raise ValueError(f"Evidence field {field} for evidence_id={evidence.evidence_id} is invalid")

        if self.risk_synthesis.overall_risk < 0 or self.risk_synthesis.overall_risk > 100:
            raise ValueError("risk_synthesis.overall_risk must be within [0, 100]")

        return self


class InvestigationCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: str = CONTRACT_VERSION

    case_id: str
    claim_id: str
    provider_id: Optional[str] = None
    provider_id_type: ProviderIdType = ProviderIdType.UNKNOWN
    claim_type: Optional[str] = None

    investigation_context: Optional[InvestigationContext] = None
    agent_results: List[AgentResult] = Field(default_factory=list)
    agent_executions: List[AgentExecution] = Field(default_factory=list)

    findings: List[Finding] = Field(default_factory=list)
    evidence: List[Evidence] = Field(default_factory=list)
    risk_synthesis: Optional[RiskSynthesis] = None
    genai_explanation: Optional[GenAIExplanation] = None

    provenance: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def normalize_datetime(cls, value: Any) -> Any:
        if value is None:
            return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        return value

    @field_validator("provider_id_type", mode="before")
    @classmethod
    def normalize_provider_id_type(cls, value: Any) -> Any:
        if value is None:
            return ProviderIdType.UNKNOWN
        if isinstance(value, ProviderIdType):
            return value
        normalized = str(value).strip().upper()
        if normalized in {"NPI", "PRVDR_NUM", "UNKNOWN"}:
            return ProviderIdType(normalized)
        return ProviderIdType.UNKNOWN

    @classmethod
    def from_result(cls, result: Any, *, case_id: Optional[str] = None, explanation: Optional[GenAIExplanation] = None) -> "InvestigationCase":
        claim_id = str(getattr(result, "claim_id", case_id or "UNKNOWN"))
        case_identifier = str(case_id or getattr(result, "case_id", claim_id or "UNKNOWN"))
        provider_id = getattr(result, "provider_id", None)
        provider_id_type = getattr(result, "provider_id_type", None)

        context = InvestigationContext(
            case_id=case_identifier,
            claim_id=claim_id,
            provider_id=str(provider_id) if provider_id is not None else None,
            provider_id_type=provider_id_type or ProviderIdType.UNKNOWN,
            claim_type=getattr(result, "claim_type", None),
            claim_anomaly=getattr(result, "claim_risk_score", None),
            provider_anomaly=getattr(result, "provider_risk_score", None),
            claim_features=(getattr(result, "summary", {}) or {}).get("claim_features", {}),
            provider_features=(getattr(result, "summary", {}) or {}).get("provider_features", {}),
            peer_features=(getattr(result, "summary", {}) or {}).get("peer_features", {}),
            data_availability={},
            metadata={"status": getattr(result, "status", "OPEN")},
            provenance={"source": "deterministic_investigation"},
        )

        findings = []
        evidence_items = []
        for idx, finding in enumerate(getattr(result, "findings", []) or [], start=1):
            finding_id = f"F-{idx:03d}"
            evidence_ids = []
            evidence_payload = getattr(finding, "evidence", {}) or {}
            if evidence_payload:
                ev_id = f"EV-{idx:03d}"
                evidence_ids.append(ev_id)
                evidence_items.append(Evidence(
                    evidence_id=ev_id,
                    agent=str(getattr(finding, "agent", "unknown")),
                    category=str(getattr(finding, "category", "general")),
                    metric=str((evidence_payload.get("metric") if isinstance(evidence_payload, dict) and evidence_payload.get("metric") else (getattr(finding, "rule", None) or "investigation_metric"))),
                    provider_value=evidence_payload.get("provider_value") if isinstance(evidence_payload, dict) else None,
                    claim_value=evidence_payload.get("claim_value") if isinstance(evidence_payload, dict) else None,
                    baseline_value=evidence_payload.get("baseline_value") if isinstance(evidence_payload, dict) else None,
                    peer_mean=evidence_payload.get("peer_mean") if isinstance(evidence_payload, dict) else None,
                    peer_median=evidence_payload.get("peer_median") if isinstance(evidence_payload, dict) else None,
                    peer_std=evidence_payload.get("peer_std") if isinstance(evidence_payload, dict) else None,
                    deviation=evidence_payload.get("deviation") if isinstance(evidence_payload, dict) else None,
                    deviation_ratio=evidence_payload.get("deviation_ratio") if isinstance(evidence_payload, dict) else None,
                    percentile=evidence_payload.get("percentile") if isinstance(evidence_payload, dict) else None,
                    peer_group=evidence_payload.get("peer_group") if isinstance(evidence_payload, dict) else None,
                    peer_sample_size=evidence_payload.get("peer_sample_size") if isinstance(evidence_payload, dict) else None,
                    threshold=evidence_payload.get("threshold") if isinstance(evidence_payload, dict) else None,
                    direction=evidence_payload.get("direction") if isinstance(evidence_payload, dict) else None,
                    source=evidence_payload.get("source") if isinstance(evidence_payload, dict) else None,
                    source_fields=evidence_payload.get("source_fields", []) if isinstance(evidence_payload, dict) else [],
                    methodology=evidence_payload.get("methodology") if isinstance(evidence_payload, dict) else None,
                    confidence=(float(getattr(finding, "confidence", 0.0)) if getattr(finding, "confidence", None) is not None else None),
                    metadata={
                        "raw_evidence": evidence_payload,
                        "finding_rule": str(getattr(finding, "rule", "investigation_metric")),
                        "finding_description": str(getattr(finding, "description", "")),
                    } if isinstance(evidence_payload, dict) else {},
                ))

            findings.append(Finding(
                finding_id=finding_id,
                agent=str(getattr(finding, "agent", "unknown")),
                title=str(getattr(finding, "rule", "Investigation finding")),
                description=str(getattr(finding, "description", "Deterministic evidence identified by the investigation agent.")),
                severity=str(getattr(finding, "severity", "MEDIUM")).upper(),
                category=str(getattr(finding, "category", "general")),
                evidence_ids=evidence_ids,
                confidence=float(getattr(finding, "confidence", 0.0)) if getattr(finding, "confidence", None) is not None else None,
            ))

        overall_risk = float(getattr(result, "investigation_risk_score", 0.0) or 0.0)
        if overall_risk < 40:
            risk_category = RiskCategory.LOW
            priority = RiskPriority.P3
        elif overall_risk < 70:
            risk_category = RiskCategory.MEDIUM
            priority = RiskPriority.P2
        elif overall_risk < 85:
            risk_category = RiskCategory.HIGH
            priority = RiskPriority.P1
        else:
            risk_category = RiskCategory.CRITICAL
            priority = RiskPriority.P0

        risk_synthesis = RiskSynthesis(
            claim_anomaly=float(getattr(result, "claim_risk_score", 0.0) or 0.0),
            provider_anomaly=float(getattr(result, "provider_risk_score", 0.0) or 0.0),
            billing_score=float(getattr(result, "investigation_risk_score", 0.0) or 0.0),
            peer_score=0.0,
            rule_score=0.0,
            weights={"claim_anomaly": 30, "provider_anomaly": 30, "peer_score": 20, "billing_score": 10, "rule_score": 10},
            overall_risk=overall_risk,
            risk_category=risk_category,
            priority=priority,
            methodology="deterministic_investigation_synthesis",
            contributing_agents=[agent for agent in ["billing", "peer", "clinical_rule"] if agent in (getattr(result, "findings_by_agent", {}) or {})],
            contract_version=CONTRACT_VERSION,
        )

        findings_by_agent = {}
        for finding in findings:
            findings_by_agent.setdefault(finding.agent, []).append(finding)
        agent_results = []
        for agent_name, agent_findings in findings_by_agent.items():
            agent_evidence_ids = {
                evidence_id
                for finding in agent_findings
                for evidence_id in finding.evidence_ids
            }
            agent_evidence = [
                evidence for evidence in evidence_items
                if evidence.evidence_id in agent_evidence_ids
            ]
            score_source = (
                getattr(result, "claim_risk_score", None)
                if agent_name in {"billing", "clinical_rule"}
                else getattr(result, "provider_risk_score", None)
            )
            score = int(max(0, min(100, float(score_source or overall_risk))))
            risk = RiskLevel.CRITICAL if score >= 85 else (
                RiskLevel.HIGH if score >= 70 else (
                    RiskLevel.MEDIUM if score >= 40 else RiskLevel.LOW
                )
            )
            agent_results.append(AgentResult(
                agent=agent_name,
                status=AgentStatus.SUCCESS,
                score=score,
                risk=risk,
                findings=agent_findings,
                evidence=agent_evidence,
                rule_hits=[],
                limitations=[] if agent_evidence else ["No structured evidence was returned by this agent."],
                provenance={"source": "deterministic_investigation"},
                execution_id=f"agent-{agent_name}-{case_identifier}",
                execution_time_ms=0,
            ))

        return cls(
            case_id=case_identifier,
            claim_id=claim_id,
            provider_id=str(provider_id) if provider_id is not None else None,
            provider_id_type=provider_id_type or ProviderIdType.UNKNOWN,
            claim_type=getattr(result, "claim_type", None),
            investigation_context=context,
            agent_results=agent_results,
            findings=findings,
            evidence=evidence_items,
            risk_synthesis=risk_synthesis,
            genai_explanation=explanation,
            provenance={"source": "deterministic_investigation"},
            created_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            updated_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )

    def to_summary_dict(self) -> Dict[str, Any]:
        return self.model_dump(mode="json")
