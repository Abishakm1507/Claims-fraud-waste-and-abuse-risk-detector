from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from multi_agent.data.provider_store import ProviderStore
from multi_agent.schemas.finding import Finding
from multi_agent.schemas.investigation_case import InvestigationCase
from multi_agent.schemas.provider_context import ProviderContext


class PeerAgent:
    """Deterministic peer-comparison agent over ProviderContext data."""

    METRIC_SPECS: Sequence[Tuple[str, str, str]] = (
        ("Payment_per_Service", "payment_per_service", "peer_median"),
        ("Charge_per_Service", "charge_per_service", "charge_per_service_peer_median"),
        ("Services_per_Beneficiary", "services_per_beneficiary", "services_per_beneficiary_peer_median"),
        ("Payment_to_Charge_Ratio", "payment_to_charge_ratio", "payment_to_charge_ratio_peer_median"),
        ("Svc_HHI_Concentration", "svc_hhi_concentration", "svc_hhi_concentration_peer_median"),
    )

    def __init__(self, provider_store: Optional[ProviderStore] = None):
        self.provider_store = provider_store or ProviderStore()

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

        return findings

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
