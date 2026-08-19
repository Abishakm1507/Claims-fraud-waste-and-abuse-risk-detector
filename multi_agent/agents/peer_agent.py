from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from multi_agent.config.agent_llm_config import DEFAULT_AGENT_LLM_CONFIG
from multi_agent.data.provider_store import ProviderStore
from multi_agent.schemas.finding import Finding
from multi_agent.schemas.investigation_case import InvestigationCase
from multi_agent.schemas.provider_context import ProviderContext
from multi_agent.services.llm_agent_service import LLMAgentService, ToolDefinition
from multi_agent.services.explanation_service import InvestigationExplanationService
from multi_agent.utils.redaction import redact_for_llm


@dataclass
class PeerAgentResult:
    """Result from peer agent investigation."""

    findings: List[Finding]
    narrative: str
    tools_called: List[str]
    status: str


class PeerAgent:
    """Deterministic peer-comparison agent over ProviderContext data."""

    METRIC_SPECS: Sequence[Tuple[str, str, str]] = (
        ("Payment_per_Service", "payment_per_service", "peer_median"),
        ("Charge_per_Service", "charge_per_service", "charge_per_service_peer_median"),
        ("Services_per_Beneficiary", "services_per_beneficiary", "services_per_beneficiary_peer_median"),
        ("Payment_to_Charge_Ratio", "payment_to_charge_ratio", "payment_to_charge_ratio_peer_median"),
        ("Svc_HHI_Concentration", "svc_hhi_concentration", "svc_hhi_concentration_peer_median"),
    )

    def __init__(self, provider_store: Optional[ProviderStore] = None, llm_service: Optional[InvestigationExplanationService] = None, llm_agent_service: Optional[LLMAgentService] = None, llm_config: Optional[Dict[str, Any]] = None):
        self.provider_store = provider_store or ProviderStore()
        self.llm_service = llm_service or InvestigationExplanationService(enabled=True)
        self.llm_config = llm_config or DEFAULT_AGENT_LLM_CONFIG["peer"].to_dict()
        # Create LLMAgentService with config-driven max_tokens
        self.llm_agent_service = llm_agent_service or LLMAgentService(
            enabled=True,
            max_tokens=self.llm_config.get("max_tokens", 600),
        )

    def investigate_with_llm(
        self,
        case: InvestigationCase,
        provider_risk_score: Optional[float] = None,
        enable_llm: bool = True,
        focus_hint: Optional[str] = None,
    ) -> PeerAgentResult:
        """Investigate provider using LLM-directed tool calling.

        Args:
            case: Investigation case with provider context.
            provider_risk_score: Pre-computed provider risk score for context.
            enable_llm: Whether to use LLM; fall back to deterministic if False.
            focus_hint: Optional LLM guidance for investigation focus (from orchestrator routing rationale).

        Returns:
            PeerAgentResult with findings, narrative, tools called, and status.
        """
        if not enable_llm or not self.llm_agent_service.enabled:
            # Fallback to deterministic investigation
            findings = self.investigate(case)
            return PeerAgentResult(
                findings=findings,
                narrative="Deterministic peer review completed.",
                tools_called=[],
                status="fallback",
            )

        # Build tool registry for this investigation
        tool_registry = {
            "compare_peer_metrics": lambda ctx: self._tool_peer_metrics(ctx),
            "compare_geographic_metrics": lambda ctx: self._tool_geographic_metrics(ctx),
            "get_peer_deviation_score": lambda ctx: self._tool_deviation_score(ctx),
        }

        # Build case context for LLM
        provider_npi = None
        if case.provider is not None:
            provider_npi = case.provider.npi
        elif case.claim is not None and case.claim.provider_id is not None:
            provider_npi = case.claim.provider_id

        case_context = {
            "case_id": case.case_id,
            "provider_npi": provider_npi,
            "provider_risk_score": provider_risk_score or (case.provider.provider_risk_score if case.provider else None),
        }
        # Redact PHI/PII before sending to LLM (HIPAA compliance)
        case_context = redact_for_llm(case_context)

        # Get tool definitions from config
        tool_defs = [ToolDefinition(name=t.name, description=t.description) for t in DEFAULT_AGENT_LLM_CONFIG["peer"].tools]

        # Invoke LLM to reason about which tools to run
        fallback = "Peer investigation complete; deterministic findings remain authoritative."
        reasoning_result = self.llm_agent_service.reason_with_tools(
            agent_name="peer",
            case_context=case_context,
            available_tools=tool_defs,
            tool_registry=tool_registry,
            fallback_narrative=fallback,
            focus_hint=focus_hint,
            case=case,
        )

        # If LLM is unavailable or fell back to deterministic, keep the deterministic path.
        if reasoning_result.status in {"fallback", "disabled", "unavailable"}:
            findings = self.investigate(case)
            return PeerAgentResult(
                findings=findings,
                narrative=reasoning_result.narrative,
                tools_called=[],
                status="fallback",
            )

        # Call selected tools and collect findings
        findings = []
        for tool_name in reasoning_result.selected_tools:
            if tool_name in tool_registry:
                try:
                    tool_result = tool_registry[tool_name](case)
                    if isinstance(tool_result, list):
                        findings.extend(tool_result)
                    elif isinstance(tool_result, Finding):
                        findings.append(tool_result)
                except Exception:  # pragma: no cover
                    pass

        # If no tools returned findings, fall back to deterministic
        if not findings:
            findings = self.investigate(case)

        return PeerAgentResult(
            findings=findings,
            narrative=reasoning_result.narrative,
            tools_called=reasoning_result.selected_tools,
            status="partial" if reasoning_result.tool_failures else "success",
        )

    def _provider_for_tool(self, case: InvestigationCase) -> Optional[ProviderContext]:
        """Resolve a provider for both claim-based and provider-only investigations."""
        if case is None:
            return None
        if case.provider is not None:
            return case.provider

        claim = getattr(case, "claim", None)
        provider_id = getattr(claim, "provider_id", None) if claim is not None else None
        if provider_id is None:
            return None
        return self._resolve_provider(case, provider_id)

    def _tool_peer_metrics(self, case: InvestigationCase) -> List[Finding]:
        """Tool: Compare peer metrics."""
        provider = self._provider_for_tool(case)
        if provider is None:
            return []
        return self._peer_metric_findings(provider)

    def _tool_geographic_metrics(self, case: InvestigationCase) -> List[Finding]:
        """Tool: Compare geographic metrics."""
        provider = self._provider_for_tool(case)
        if provider is None:
            return []
        return self._geo_findings(provider)

    def _tool_deviation_score(self, case: InvestigationCase) -> List[Finding]:
        """Tool: Get peer deviation score summary."""
        provider = self._provider_for_tool(case)
        if provider is None:
            return []

        findings = []
        if provider.peer_deviation_score is not None and provider.peer_deviation_score >= 0.8:
            findings.append(
                self._finding(
                    rule="peer_deviation_score",
                    category="peer_comparison",
                    severity="MEDIUM",
                    description=f"Peer deviation score: {provider.peer_deviation_score:.3f}",
                    evidence={"peer_deviation_score": provider.peer_deviation_score},
                    confidence=0.7,
                )
            )
        return findings

    def investigate(self, case: InvestigationCase) -> List[Finding]:
        if case is None or case.claim is None:
            return []

        claim = case.claim
        if claim.provider_id is None:
            return []

        provider_id_type = str(claim.provider_id_type or "").upper()
        if provider_id_type != "NPI":
            return []

        provider = self._resolve_provider(case, claim.provider_id)
        if provider is None:
            return []

        findings: List[Finding] = []
        findings.extend(self._peer_metric_findings(provider))
        findings.extend(self._geo_findings(provider))

        if not findings and self._is_high_peer_summary(provider):
            if provider.peer_group is not None:
                findings.append(
                    self._finding(
                        rule="high_peer_deviation_vs_peers",
                        category="peer_comparison",
                        severity="HIGH",
                        description=(
                            "Provider peer deviation score is elevated, but the underlying peer "
                            "benchmark values are not available in the Provider ML output."
                        ),
                        evidence={
                            "peer_deviation_score": provider.peer_deviation_score,
                            "raw_peer_benchmark_available": False,
                            "peer_group": provider.peer_group,
                            "provider_risk_score": provider.provider_risk_score,
                            "risk_tier": provider.risk_tier,
                        },
                        confidence=0.82,
                    )
                )
            else:
                findings.append(
                    self._finding(
                        rule="peer_deviation_score_only",
                        category="peer_comparison",
                        severity="MEDIUM",
                        description=(
                            "Normalized peer deviation score is available, but the underlying "
                            "peer benchmark values are not available in the Provider ML output."
                        ),
                        evidence={
                            "peer_deviation_score": provider.peer_deviation_score,
                            "raw_peer_benchmark_available": False,
                            "provider_risk_score": provider.provider_risk_score,
                            "risk_tier": provider.risk_tier,
                        },
                        confidence=0.7,
                    )
                )

        if not findings and self._is_high_geo_summary(provider):
            findings.append(
                self._finding(
                    rule="geo_deviation_score_only",
                    category="geo_comparison",
                    severity="MEDIUM",
                    description=(
                        "Normalized geographic deviation score is available, but the underlying "
                        "state benchmark values are not available in the Provider ML output."
                    ),
                    evidence={
                        "geo_deviation_score": provider.geo_deviation_score,
                        "raw_geo_benchmark_available": False,
                        "provider_state": provider.provider_state,
                    },
                    confidence=0.65,
                )
            )

        if not findings:
            findings.append(
                self._finding(
                    rule="provider_profile_summary",
                    category="provider_context",
                    severity="INFO",
                    description=(
                        "Provider profile review completed. The provider is present in the ML output, "
                        "but no peer or geographic anomaly crossed the investigation thresholds."
                    ),
                    evidence={
                        "npi": provider.npi,
                        "provider_type": provider.provider_type,
                        "provider_state": provider.provider_state,
                        "peer_group": provider.peer_group,
                        "provider_risk_score": provider.provider_risk_score,
                        "risk_tier": provider.risk_tier,
                        "peer_deviation_score": provider.peer_deviation_score,
                        "geo_deviation_score": provider.geo_deviation_score,
                        "provider_value": provider.provider_value,
                        "peer_median": provider.peer_median,
                        "deviation_ratio": provider.deviation_ratio,
                        "percentile": provider.percentile,
                        "raw_peer_benchmark_available": provider.peer_median is not None,
                        "raw_geo_benchmark_available": provider.geo_median is not None,
                    },
                    confidence=0.55,
                )
            )

        return self._complete_with_llm(case, findings)

    def _complete_with_llm(self, case: InvestigationCase, findings: List[Finding]) -> List[Finding]:
        narrative = self._llm_narrative(case, findings)
        for finding in findings:
            finding.agent_narrative = narrative
            finding.tool_results = {"tool": "peer_benchmark_review", "finding_count": len(findings)}
        return findings

    def _llm_narrative(self, case: InvestigationCase, findings: List[Finding]) -> str:
        if not self.llm_service.enabled:
            return "Deterministic peer review remains the source of truth for provider benchmarking."
        context = {
            "case_id": getattr(case, "case_id", "UNKNOWN"),
            "provider_npi": getattr(case.provider, "npi", None) if case.provider else None,
            "provider_risk_score": getattr(case.provider, "provider_risk_score", None) if case.provider else None,
            "findings": [{"rule": f.rule, "severity": f.severity, "description": f.description, "evidence": f.evidence} for f in findings],
        }
        fallback = "Peer comparison is interpreted alongside the provider risk score, but the deterministic peer benchmark findings remain the authoritative basis for this assessment."
        reasoning = self.llm_service.generate_structured_reasoning("peer", context, fallback=fallback)
        return str(reasoning.get("narrative") or fallback)

    def _resolve_provider(self, case: InvestigationCase, provider_id: Any) -> Optional[ProviderContext]:
        if case.provider is not None:
            try:
                if int(case.provider.npi) == int(provider_id):
                    return case.provider
            except (TypeError, ValueError):
                pass

        try:
            return self.provider_store.get_provider(int(provider_id))
        except (TypeError, ValueError):
            return self.provider_store.get_provider(provider_id)

    def _peer_metric_findings(self, provider: ProviderContext) -> List[Finding]:
        findings: List[Finding] = []
        for metric_name, value_field, benchmark_field in self.METRIC_SPECS:
            value = getattr(provider, value_field, None)
            benchmark = getattr(provider, benchmark_field, None)
            ratio = self._get_ratio(provider, value_field)
            percentile = self._get_percentile(provider, value_field)
            if value is None or benchmark is None:
                continue
            if benchmark == 0:
                continue

            if (ratio is not None and ratio >= 2.0) or (percentile is not None and percentile >= 90.0 and ratio is not None and ratio >= 1.5):
                severity = self._severity_for_ratio(ratio or 1.0, percentile)
                findings.append(
                    self._finding(
                        rule=f"high_{self._slug(metric_name)}_vs_peers",
                        category="peer_comparison",
                        severity=severity,
                        description=(
                            f"Provider {metric_name} is {ratio:.2f}x the peer benchmark and "
                            f"falls at the {self._format_percentile(percentile)} percentile within the peer group."
                        ),
                        evidence={
                            "metric": metric_name,
                            "provider_value": value,
                            "peer_median": benchmark,
                            "deviation_ratio": ratio,
                            "percentile": percentile,
                            "peer_group": provider.peer_group,
                            "provider_risk_score": provider.provider_risk_score,
                            "risk_tier": provider.risk_tier,
                        },
                        confidence=0.9,
                    )
                )
        return findings

    def _geo_findings(self, provider: ProviderContext) -> List[Finding]:
        findings: List[Finding] = []
        if provider.geo_deviation_score is None:
            return findings

        geo_metric = provider.geo_metric or "Payment_per_Service"
        provider_value = provider.geo_provider_value
        geo_median = provider.geo_median
        geo_ratio = provider.geo_deviation_ratio

        if provider_value is not None and geo_median is not None and geo_median > 0 and geo_ratio is not None:
            percentile = self._score_to_percentile(provider.geo_deviation_score)
            if geo_ratio >= 2.0 or percentile >= 90:
                findings.append(
                    self._finding(
                        rule="high_geo_deviation",
                        category="geo_comparison",
                        severity=self._severity_for_ratio(geo_ratio, percentile),
                        description=(
                            f"Provider {geo_metric} is {geo_ratio:.2f}x the state benchmark and sits at the "
                            f"{self._format_percentile(percentile)} percentile within the geographic comparison set."
                        ),
                        evidence={
                            "metric": geo_metric,
                            "state": provider.provider_state,
                            "provider_value": provider_value,
                            "geo_median": geo_median,
                            "geo_mean": provider.geo_mean,
                            "geo_std": provider.geo_std,
                            "deviation_ratio": geo_ratio,
                            "percentile": percentile,
                            "geo_deviation_score": provider.geo_deviation_score,
                        },
                        confidence=0.86,
                    )
                )

        return findings

    @staticmethod
    def _has_summary_peer_evidence(provider: ProviderContext) -> bool:
        return provider.peer_deviation_score is not None

    @staticmethod
    def _has_summary_geo_evidence(provider: ProviderContext) -> bool:
        return provider.geo_deviation_score is not None

    @staticmethod
    def _is_high_peer_summary(provider: ProviderContext) -> bool:
        return PeerAgent._has_summary_peer_evidence(provider) and provider.peer_deviation_score is not None and provider.peer_deviation_score >= 0.8

    @staticmethod
    def _is_high_geo_summary(provider: ProviderContext) -> bool:
        return PeerAgent._has_summary_geo_evidence(provider) and provider.geo_deviation_score is not None and provider.geo_deviation_score >= 0.8

    @staticmethod
    def _severity_for_ratio(ratio: float, percentile: Optional[float]) -> str:
        if ratio >= 4.0 or (percentile is not None and percentile >= 98.0):
            return "HIGH"
        if ratio >= 2.0 or (percentile is not None and percentile >= 90.0):
            return "MEDIUM"
        if ratio >= 1.25 or (percentile is not None and percentile >= 75.0):
            return "LOW"
        return "INFO"

    @staticmethod
    def _score_to_percentile(score: Optional[float]) -> float:
        if score is None:
            return 0.0
        return max(0.0, min(100.0, score * 100.0))

    @staticmethod
    def _format_percentile(value: Optional[float]) -> str:
        if value is None:
            return "unknown"
        return f"{value:.1f}"

    @staticmethod
    def _get_ratio(provider: ProviderContext, value_field: str) -> Optional[float]:
        if value_field == "payment_per_service":
            return provider.deviation_ratio
        if value_field == "charge_per_service":
            return provider.charge_per_service_deviation_ratio
        if value_field == "services_per_beneficiary":
            return provider.services_per_beneficiary_deviation_ratio
        if value_field == "payment_to_charge_ratio":
            return provider.payment_to_charge_ratio_deviation_ratio
        if value_field == "svc_hhi_concentration":
            return provider.svc_hhi_concentration_deviation_ratio
        return None

    @staticmethod
    def _get_percentile(provider: ProviderContext, value_field: str) -> Optional[float]:
        if value_field == "payment_per_service":
            return provider.percentile
        if value_field == "charge_per_service":
            return provider.charge_per_service_percentile
        if value_field == "services_per_beneficiary":
            return provider.services_per_beneficiary_percentile
        if value_field == "payment_to_charge_ratio":
            return provider.payment_to_charge_ratio_percentile
        if value_field == "svc_hhi_concentration":
            return provider.svc_hhi_concentration_percentile
        return None

    @staticmethod
    def _slug(value: str) -> str:
        return value.lower().replace("_", "_").replace(" ", "_").replace("/", "_")

    @staticmethod
    def _finding(
        rule: str,
        category: str,
        severity: str,
        description: str,
        evidence: Dict[str, Any],
        confidence: float,
    ) -> Finding:
        return Finding(
            agent="peer",
            category=category,
            rule=rule,
            severity=severity,
            description=description,
            evidence=evidence,
            confidence=confidence,
        )
