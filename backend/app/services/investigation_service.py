from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from multi_agent.models.schemas import (
    AgentResult,
    AgentStatus,
    Evidence,
    Finding,
    InvestigationCase,
    ProviderIdType,
    RAGExplanationRequest,
    RiskCategory,
    RiskPriority,
    RiskSynthesis,
    GenAIExplanationContext,
    HandoffMetadata,
)

from backend.app.data.repository import repository
from backend.app.core.config import settings


_orchestrator = None


def _get_orchestrator():
    global _orchestrator
    if _orchestrator is None:
        from multi_agent.orchestrator import Orchestrator

        _orchestrator = Orchestrator()
    return _orchestrator


class InvestigationService:
    """Stable backend contract for running and fetching investigations.

    TODO: swap for real multi_agent.orchestrator.Orchestrator.
    """

    def get_investigation(self, case_id: str) -> InvestigationCase:
        claim = repository.get_claim(case_id)
        if claim is None:
            raise KeyError(f"Claim {case_id} not found")
        if settings.use_real_multi_agent:
            orchestrator = _get_orchestrator()
            result = orchestrator.investigate_claim(case_id)
            if getattr(result, "status", None) == "ERROR":
                raise KeyError(f"Claim {case_id} could not be investigated")
            case = orchestrator.to_investigation_case(result)
            case.case_id = str(case_id)
            if getattr(case, "investigation_context", None) is not None:
                case.investigation_context.case_id = str(case_id)
            return case
        return self._build_investigation_case(claim)

    def run_investigation(self, case_id: str) -> InvestigationCase:
        return self.get_investigation(case_id)

    def _build_investigation_case(self, claim: Dict[str, Any]) -> InvestigationCase:
        claim_id = str(claim["claim_id"])
        provider_row = repository.get_provider(claim.get("provider_id") or "")
        provider_score = float((provider_row or {}).get("provider_risk_score", 0.0)) if provider_row else 0.0
        claim_score = float(claim.get("claim_risk_score", 0.0))
        
        # Fetch ML evidence if available
        ml_evidence = repository.get_claim_evidence(claim_id)
        ml_score = ml_evidence.ensemble_score if ml_evidence else claim_score
        
        overall_risk = min(100.0, max(0.0, (ml_score * 0.7) + (provider_score * 0.3)))
        if overall_risk >= 85:
            risk_category = RiskCategory.CRITICAL
            priority = RiskPriority.P0
        elif overall_risk >= 70:
            risk_category = RiskCategory.HIGH
            priority = RiskPriority.P1
        elif overall_risk >= 40:
            risk_category = RiskCategory.MEDIUM
            priority = RiskPriority.P2
        else:
            risk_category = RiskCategory.LOW
            priority = RiskPriority.P3

        evidence = [
            Evidence(
                evidence_id=f"EV-{claim_id}-risk",
                agent="billing",
                category="claim_risk",
                metric="claim_risk_score",
                provider_value=provider_score,
                claim_value=claim_score,
                baseline_value=50.0,
                deviation=claim_score - 50.0,
                deviation_ratio=max(0.0, (claim_score - 50.0) / 50.0) if 50.0 else 0.0,
                percentile=None,
                threshold=70.0,
                direction="above",
                source="final_unified_claim_risk.csv",
                source_fields=["CLAIM_RISK_SCORE"],
                methodology="deterministic_backend_stub",
                confidence=0.88,
            ),
            Evidence(
                evidence_id=f"EV-{claim_id}-provider",
                agent="peer",
                category="provider_risk",
                metric="provider_risk_score",
                provider_value=provider_score,
                claim_value=claim_score,
                baseline_value=50.0,
                deviation=provider_score - 50.0,
                deviation_ratio=max(0.0, (provider_score - 50.0) / 50.0) if 50.0 else 0.0,
                percentile=None,
                threshold=70.0,
                direction="above",
                source="provider_risk_scores.csv",
                source_fields=["risk_score_0_100"],
                methodology="deterministic_backend_stub",
                confidence=0.82,
            ),
        ]
        
        # Add ML evidence if available
        if ml_evidence:
            evidence.append(
                Evidence(
                    evidence_id=f"EV-{claim_id}-ml",
                    agent="anomaly_detection",
                    category="ml_ensemble_risk",
                    metric="ensemble_anomaly_score",
                    provider_value=None,
                    claim_value=ml_score,
                    baseline_value=50.0,
                    deviation=ml_score - 50.0,
                    deviation_ratio=max(0.0, (ml_score - 50.0) / 50.0) if 50.0 else 0.0,
                    percentile=ml_evidence.risk_percentile,
                    threshold=70.0,
                    direction="above",
                    source=ml_evidence.source_pipeline,
                    source_fields=[f"{ml_evidence.claim_type.lower()}_ensemble_score"],
                    methodology=f"{ml_evidence.claim_type.lower()}_ml_pipeline",
                    confidence=0.90,
                )
            )

        findings = [
            Finding(
                finding_id=f"F-{claim_id}-1",
                agent="billing",
                title="High claim anomaly signal",
                description=f"Claim {claim_id} scored {claim_score:.1f} on the finalized risk signal and exceeds the review threshold.",
                severity="HIGH" if claim_score >= 70 else "MEDIUM",
                category="claim_risk",
                evidence_ids=[evidence[0].evidence_id],
                confidence=0.88,
            ),
            Finding(
                finding_id=f"F-{claim_id}-2",
                agent="peer",
                title="Provider risk concentration",
                description=(
                    f"Provider {claim.get('provider_id','UNKNOWN')} is rated at {provider_score:.1f}, reinforcing the claim-level anomaly."
                    if provider_row
                    else "No linked provider score was available for this claim."
                ),
                severity="HIGH" if provider_score >= 70 else "MEDIUM",
                category="provider_risk",
                evidence_ids=[evidence[1].evidence_id] if len(evidence) > 1 else [],
                confidence=0.82,
            ),
        ]
        
        # Add ML evidence finding if available
        if ml_evidence:
            findings.append(
                Finding(
                    finding_id=f"F-{claim_id}-3",
                    agent="anomaly_detection",
                    title=f"{ml_evidence.claim_type} claim ML ensemble anomaly",
                    description=f"ML pipeline ({ml_evidence.claim_type.lower()}) detected ensemble anomaly score of {ml_evidence.ensemble_score:.1f} (risk band: {ml_evidence.risk_band}). Model consensus: {ml_evidence.model_scores}.",
                    severity="CRITICAL" if ml_evidence.ensemble_score >= 85 else ("HIGH" if ml_evidence.ensemble_score >= 70 else "MEDIUM"),
                    category="ml_anomaly",
                    evidence_ids=[evidence[2].evidence_id] if len(evidence) > 2 else [],
                    confidence=0.90,
                )
            )

        agent_results = [
            AgentResult(
                agent="billing",
                status=AgentStatus.SUCCESS,
                score=int(min(100, max(0, claim_score))),
                risk=RiskCategory.HIGH if claim_score >= 70 else RiskCategory.MEDIUM,
                findings=[findings[0]],
                evidence=[evidence[0]],
                rule_hits=[],
                limitations=[],
                provenance={"source": "final_unified_claim_risk.csv"},
                execution_id=f"agent-billing-{claim_id}",
                execution_time_ms=42,
            ),
            AgentResult(
                agent="peer",
                status=AgentStatus.SUCCESS,
                score=int(min(100, max(0, provider_score))),
                risk=RiskCategory.HIGH if provider_score >= 70 else RiskCategory.MEDIUM,
                findings=[findings[1]],
                evidence=[evidence[1]],
                rule_hits=[],
                limitations=[],
                provenance={"source": "provider_risk_scores.csv"},
                execution_id=f"agent-peer-{claim_id}",
                execution_time_ms=39,
            ),
        ]
        
        # Add ML agent result if evidence available
        if ml_evidence:
            agent_results.append(
                AgentResult(
                    agent="anomaly_detection",
                    status=AgentStatus.SUCCESS,
                    score=int(min(100, max(0, ml_score))),
                    risk=RiskCategory.CRITICAL if ml_score >= 85 else (RiskCategory.HIGH if ml_score >= 70 else RiskCategory.MEDIUM),
                    findings=[findings[2]],
                    evidence=[evidence[2]],
                    rule_hits=[],
                    limitations=[],
                    provenance={"source": ml_evidence.source_pipeline, "claim_type": ml_evidence.claim_type},
                    execution_id=f"agent-anomaly-{claim_id}",
                    execution_time_ms=28,
                )
            )

        risk_synthesis = RiskSynthesis(
            claim_anomaly=claim_score,
            provider_anomaly=provider_score,
            billing_score=claim_score,
            peer_score=provider_score,
            rule_score=min(100.0, claim_score * 0.5),
            weights={"claim_anomaly": 30, "provider_anomaly": 30, "peer_score": 20, "billing_score": 10, "rule_score": 10},
            overall_risk=float(overall_risk),
            risk_category=risk_category,
            priority=priority,
            methodology="backend_stub_investigation_service",
            contributing_agents=["billing", "peer"],
            contract_version="1.0",
            synthesis_version="stub-1.0",
            raw_score=float(overall_risk),
            contributions=[
                {"component_name": "claim_anomaly", "input_score": claim_score, "weight": 0.3, "contribution": claim_score * 0.3},
                {"component_name": "provider_anomaly", "input_score": provider_score, "weight": 0.3, "contribution": provider_score * 0.3},
            ],
            errors=[],
            warnings=[],
            is_complete=True,
            is_usable=True,
        )

        case = InvestigationCase(
            case_id=claim_id,
            claim_id=claim_id,
            provider_id=claim.get("provider_id") or (provider_row.get("npi") if provider_row else None),
            provider_id_type=ProviderIdType.NPI if (claim.get("provider_id") or (provider_row.get("npi") if provider_row else None)) else ProviderIdType.UNKNOWN,
            claim_type=str(claim.get("claim_type") or "UNKNOWN"),
            investigation_context=None,
            agent_results=agent_results,
            findings=findings,
            evidence=evidence,
            risk_synthesis=risk_synthesis,
            provenance={"source": "backend_stub_investigation_service", "claim_csv": "final_unified_claim_risk.csv"},
            created_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            updated_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
        return case


class ExplainabilityService:
    """Stable backend contract for explanation generation.

    TODO: swap for real explainability service.
    """

    def get_explanation(self, case_id: str, investigation: Optional[InvestigationCase] = None) -> RAGExplanationRequest:
        case = investigation or InvestigationService().get_investigation(case_id)
        request_id = f"rag-{case.case_id}"
        context = GenAIExplanationContext.from_case(case)
        explanation_metadata = {"source": "backend_contract"}
        if settings.use_real_explainability:
            from explainability.explanation_service import explain_entity

            claim = repository.get_claim(case.claim_id)
            try:
                real_explanation = explain_entity(
                    entity_type="CLAIM",
                    entity_id=case.claim_id,
                    entity_data=claim,
                    claim_type=case.claim_type,
                    investigation_output=case,
                )
                explanation_metadata = {
                    "source": "explainability.explanation_service",
                    "status": real_explanation.get("genai", {}).get("status", "READY"),
                    "shap_status": real_explanation.get("shap", {}).get("status"),
                    "shap": real_explanation.get("shap") or {},
                    "genai": real_explanation.get("genai") or {},
                }
            except Exception as exc:
                explanation_metadata = {
                    "source": "explainability.explanation_service",
                    "status": "UNAVAILABLE",
                    "error": f"{type(exc).__name__}: {exc}",
                }
        metadata = HandoffMetadata(
            case_id=case.case_id,
            request_id=request_id,
            generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            source=explanation_metadata["source"],
            data_availability={"claim_data": "AVAILABLE", "provider_data": "AVAILABLE"},
            provenance=explanation_metadata,
            limitations=[] if explanation_metadata.get("status") != "UNAVAILABLE" else ["Explainability artifacts were unavailable."],
            contract_version="1.0",
        )
        return RAGExplanationRequest(
            request_id=request_id,
            case=case,
            evidence=case.evidence,
            findings=case.findings,
            risk_synthesis=case.risk_synthesis,
            agent_results=case.agent_results,
            genai_context=context,
            metadata=metadata,
        )


investigation_service = InvestigationService()
explainability_service = ExplainabilityService()
