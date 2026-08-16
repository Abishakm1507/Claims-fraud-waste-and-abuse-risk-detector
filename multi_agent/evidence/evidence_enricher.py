from __future__ import annotations

import hashlib
from typing import Any, Dict, Iterable, List, Optional, Sequence

from multi_agent.schemas.finding import Finding
from multi_agent.schemas.investigation_case import InvestigationCase

from .evidence_calculators import deviation, deviation_ratio, percentage_deviation, safe_float, threshold_comparison
from .evidence_normalizer import EvidenceNormalizer
from .provenance import Provenance


class EvidenceEnricher:
    """Attach proof-oriented, traceable evidence to raw agent findings."""

    @staticmethod
    def enrich_findings(findings: Sequence[Finding], case: Optional[InvestigationCase] = None) -> List[Finding]:
        enriched: List[Finding] = []
        for finding in findings:
            enriched.append(EvidenceEnricher.enrich_finding(finding, case=case))
        return enriched

    @staticmethod
    def enrich_finding(finding: Finding, case: Optional[InvestigationCase] = None) -> Finding:
        if finding is None:
            return finding

        evidence = dict(finding.evidence or {})
        evidence.setdefault("agent", finding.agent)
        evidence.setdefault("category", finding.category)
        evidence.setdefault("metric", finding.rule)
        evidence.setdefault("description", finding.description)
        evidence.setdefault("evidence_id", EvidenceEnricher._evidence_id(finding))
        evidence.setdefault("availability", "AVAILABLE")
        evidence.setdefault("source_fields", [])

        if not evidence.get("source"):
            evidence.setdefault("source", EvidenceEnricher._infer_source(finding, case))
        if not evidence.get("provenance"):
            evidence["provenance"] = Provenance.build(
                source=evidence.get("source"),
                source_fields=evidence.get("source_fields") or [],
                record_key=EvidenceEnricher._record_key(case),
                pipeline="multi_agent",
                pipeline_version=None,
                limitation=EvidenceEnricher._limitation_for_finding(finding, evidence),
            )

        evidence = EvidenceEnricher._normalize_numeric_metadata(evidence)

        if evidence.get("availability") in {None, ""}:
            evidence["availability"] = "AVAILABLE" if evidence else "NOT_AVAILABLE"

        if evidence.get("provider_value") is not None and evidence.get("baseline_value") is not None:
            evidence["deviation"] = deviation(evidence["provider_value"], evidence["baseline_value"])
            ratio = deviation_ratio(evidence["provider_value"], evidence["baseline_value"])
            evidence["deviation_ratio"] = ratio
            pct = percentage_deviation(evidence["provider_value"], evidence["baseline_value"])
            if pct is not None:
                evidence["percentage_deviation"] = pct

        if evidence.get("threshold") is not None:
            observed = evidence.get("provider_value") if evidence.get("provider_value") is not None else evidence.get("claim_value")
            comp = threshold_comparison(observed, evidence.get("threshold"), operator= evidence.get("threshold_operator", ">"))
            evidence["threshold_comparison"] = comp
            evidence.setdefault("comparison", evidence.get("threshold_operator", ">"))

        if evidence.get("peer_median") is not None:
            ratio = deviation_ratio(evidence.get("provider_value"), evidence.get("peer_median"))
            if ratio is not None:
                evidence["deviation_ratio"] = ratio
        if evidence.get("peer_mean") is not None and evidence.get("provider_value") is not None:
            evidence["deviation_ratio"] = deviation_ratio(evidence["provider_value"], evidence["peer_mean"])
        if evidence.get("peer_std") is not None and evidence.get("provider_value") is not None:
            evidence["peer_std"] = safe_float(evidence["peer_std"])

        # Allow alternative baseline field names from billing agent
        if evidence.get("provider_avg_claim_payment") is not None and evidence.get("payment") is not None:
            ratio = deviation_ratio(evidence["payment"], evidence["provider_avg_claim_payment"])
            if ratio is not None and evidence.get("deviation_ratio") is None:
                evidence["deviation_ratio"] = ratio

        if evidence.get("peer_group") is None and case is not None and getattr(case.provider, "peer_group", None) is not None:
            evidence["peer_group"] = case.provider.peer_group

        if evidence.get("source_fields") in (None, []):
            evidence["source_fields"] = EvidenceEnricher._infer_source_fields(finding, case)
        if evidence.get("provenance"):
            evidence["provenance"].setdefault("source_fields", evidence.get("source_fields"))

        evidence["calculation"] = EvidenceEnricher._calculate_trace(evidence)

        if evidence.get("provenance") and evidence["provenance"].get("source") is None:
            evidence["provenance"]["source"] = evidence.get("source")

        if not evidence.get("availability"):
            evidence["availability"] = "NOT_AVAILABLE" if any(v is None for v in evidence.values() if isinstance(v, (int, float, str))) else "AVAILABLE"

        finding.evidence = evidence
        return finding

    @staticmethod
    def _normalize_numeric_metadata(evidence: Dict[str, Any]) -> Dict[str, Any]:
        numeric_fields = {
            "provider_value",
            "claim_value",
            "baseline_value",
            "peer_mean",
            "peer_median",
            "peer_std",
            "deviation",
            "deviation_ratio",
            "percentage_deviation",
            "percentile",
            "threshold",
            "observed_value",
        }
        for field in numeric_fields:
            value = evidence.get(field)
            cleaned = safe_float(value)
            if cleaned is None:
                evidence[field] = None
            else:
                evidence[field] = cleaned
        return evidence

    @staticmethod
    def _calculate_trace(evidence: Dict[str, Any]) -> Dict[str, Any]:
        observed = evidence.get("provider_value") if evidence.get("provider_value") is not None else evidence.get("claim_value")
        baseline = evidence.get("baseline_value")
        peer_median = evidence.get("peer_median")
        
        # Allow alternative baseline field names from billing agent evidence
        if baseline is None:
            baseline = evidence.get("provider_avg_claim_payment")
        
        if observed is not None and baseline is not None and baseline != 0:
            return {
                "formula": "observed / baseline",
                "inputs": {"observed": observed, "baseline": baseline},
                "result": deviation_ratio(observed, baseline),
            }
        if observed is not None and peer_median is not None and peer_median != 0:
            return {
                "formula": "provider_value / peer_median",
                "inputs": {"provider_value": observed, "peer_median": peer_median},
                "result": deviation_ratio(observed, peer_median),
            }
        if evidence.get("threshold") is not None and observed is not None:
            return {
                "formula": "observed compared to threshold",
                "inputs": {"observed": observed, "threshold": evidence.get("threshold")},
                "result": threshold_comparison(observed, evidence.get("threshold"), operator=evidence.get("threshold_operator", ">")),
            }
        return {"formula": "not_applicable", "inputs": {}, "result": None}

    @staticmethod
    def _infer_source(finding: Finding, case: Optional[InvestigationCase]) -> str:
        if finding.agent == "peer":
            return "provider_risk_scores.csv"
        if finding.agent == "billing":
            return "final_unified_claim_risk.csv"
        if finding.agent == "clinical_rule":
            return "final_unified_claim_risk.csv"
        return "multi_agent_pipeline"

    @staticmethod
    def _infer_source_fields(finding: Finding, case: Optional[InvestigationCase]) -> List[str]:
        evidence = finding.evidence or {}
        fields = evidence.get("source_fields") or []
        if fields:
            return list(fields)
        if finding.agent == "peer":
            return ["NPI", "Provider_Type", "Prvdr_State", "Provider_Risk_Score", "Payment_per_Service", "Payment_per_Service_Peer_Median"]
        if finding.agent == "billing":
            return ["total_claim_payment", "total_claim_charge", "provider_avg_claim_payment"]
        return ["claim_line_count", "has_multiple_lines", "procedure_code_count", "provider_claim_count"]

    @staticmethod
    def _record_key(case: Optional[InvestigationCase]) -> Optional[str]:
        if case is None:
            return None
        claim = getattr(case, "claim", None)
        provider = getattr(case, "provider", None)
        if claim is not None and getattr(claim, "claim_id", None):
            return f"CLAIM_ID={claim.claim_id}"
        if provider is not None and getattr(provider, "npi", None) is not None:
            return f"NPI={provider.npi}"
        return None

    @staticmethod
    def _limitation_for_finding(finding: Finding, evidence: Dict[str, Any]) -> Optional[str]:
        metric = evidence.get("metric") or finding.rule
        if finding.agent == "peer" and evidence.get("peer_median") is None:
            return "Underlying peer statistics were not exported by the Provider ML pipeline; only blended peer deviation score is available."
        if evidence.get("baseline_value") is None and evidence.get("peer_median") is None:
            return f"No baseline evidence was exported for {metric}; value remains observational only."
        return None

    @staticmethod
    def _evidence_id(finding: Finding) -> str:
        payload = f"{finding.agent}:{finding.rule}:{finding.category}:{finding.description}:{finding.confidence}"
        return "EV-" + hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]
