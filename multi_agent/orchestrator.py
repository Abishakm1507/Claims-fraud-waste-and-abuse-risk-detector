from __future__ import annotations

from typing import Any, Dict, Optional

from multi_agent.agents.billing_agent import BillingAgent
from multi_agent.agents.clinical_rule_agent import ClinicalRuleAgent
from multi_agent.agents.peer_agent import PeerAgent
from multi_agent.data.claim_store import ClaimStore
from multi_agent.data.provider_store import ProviderStore
from multi_agent.models.schemas import InvestigationCase as ContractInvestigationCase
from multi_agent.schemas.claim_context import ClaimContext
from multi_agent.schemas.investigation_case import InvestigationCase
from multi_agent.schemas.provider_context import ProviderContext
from multi_agent.services.explanation_service import InvestigationExplanationService
from multi_agent.synthesis import InvestigationResult, Synthesis


class Orchestrator:
    """Thin, deterministic coordinator for the multi-agent fraud investigation layer."""

    AGENT_ORDER = ("billing", "peer", "clinical_rule")

    def __init__(
        self,
        claim_store: Optional[ClaimStore] = None,
        provider_store: Optional[ProviderStore] = None,
        billing_agent: Optional[BillingAgent] = None,
        peer_agent: Optional[PeerAgent] = None,
        clinical_rule_agent: Optional[ClinicalRuleAgent] = None,
        synthesis: Optional[Synthesis] = None,
        explanation_service: Optional[InvestigationExplanationService] = None,
        enable_genai_explanation: Optional[bool] = None,
    ):
        self.claim_store = claim_store or ClaimStore()
        self.provider_store = provider_store or ProviderStore()
        self.billing_agent = billing_agent or BillingAgent()
        self.peer_agent = peer_agent or PeerAgent(provider_store=self.provider_store)
        self.clinical_rule_agent = clinical_rule_agent or ClinicalRuleAgent()
        self.synthesis = synthesis or Synthesis()
        self.enable_genai_explanation = enable_genai_explanation if enable_genai_explanation is not None else True
        self.explanation_service = explanation_service or InvestigationExplanationService(enabled=self.enable_genai_explanation)

    def investigate(self, case: InvestigationCase) -> InvestigationResult:
        if case is None:
            return self._error_result("UNKNOWN", "UNKNOWN", "No investigation case provided.")

        if case.claim is not None and case.claim.claim_id:
            case.claim = self.claim_store.get_claim(case.claim.claim_id) or case.claim

        if case.provider is not None and case.provider.npi is not None:
            provider = self.provider_store.get_provider(case.provider.npi)
            if provider is not None:
                case.provider = provider

        routing = self._select_agents(case)
        billing_findings = []
        peer_findings = []
        clinical_findings = []
        agent_errors: Dict[str, str] = {}

        for agent_name in self.AGENT_ORDER:
            route = routing[agent_name]
            if not route["selected"]:
                route["status"] = "NOT_SELECTED"
                continue

            route["status"] = "RUNNING"
            try:
                if agent_name == "billing":
                    findings = self.billing_agent.investigate(case)
                    billing_findings = findings
                elif agent_name == "peer":
                    findings = self.peer_agent.investigate(case)
                    peer_findings = findings
                else:
                    findings = self.clinical_rule_agent.investigate(case)
                    clinical_findings = findings

                route["status"] = "SUCCESS" if findings else "EMPTY"
            except Exception as exc:  # pragma: no cover - defensive isolation
                route["status"] = "FAILED"
                agent_errors[agent_name] = str(exc)
                route["error"] = str(exc)

        result = self.synthesis.investigate(
            case=case,
            billing_findings=billing_findings,
            peer_findings=peer_findings,
            clinical_rule_findings=clinical_findings,
            agent_errors=agent_errors,
        )
        result.routing = routing
        result.summary["routing"] = routing
        result.summary["agent_errors"] = agent_errors
        result.summary["selected_agents"] = [name for name, route in routing.items() if route["selected"]]
        result.summary["skipped_agents"] = [name for name, route in routing.items() if not route["selected"]]
        result.summary["failed_agents"] = [name for name, route in routing.items() if route["status"] == "FAILED"]

        if self.enable_genai_explanation:
            try:
                explanation = self.explanation_service.generate_explanation(result)
                result.explanation = explanation.executive_summary or result.explanation
                result.summary["explanation_status"] = explanation.status
                result.summary["explanation_error"] = explanation.error or ""
                result.summary["genai_model"] = explanation.model
                result.summary["genai_generated_by"] = explanation.generated_by
                result.summary["genai_explanation"] = explanation.to_dict()
            except Exception as exc:  # pragma: no cover - safe fallback
                result.summary["explanation_status"] = "fallback"
                result.summary["explanation_error"] = f"GenAI service unavailable: {exc}"
                result.summary["genai_model"] = self.explanation_service.model
                result.summary["genai_generated_by"] = "Groq"

        return result

    def to_investigation_case(self, result: InvestigationResult) -> ContractInvestigationCase:
        """Adapt the deterministic investigation result to the typed InvestigationCase v1 contract."""
        case = ContractInvestigationCase.from_result(result, case_id=result.case_id)
        case.agent_results = []
        case.agent_executions = []
        case.provenance = {
            "source": "deterministic_case",
            "agent_errors": getattr(result, "agent_errors", {}),
            "summary": getattr(result, "summary", {}),
        }
        return case

    def investigate_claim(self, claim_id: str) -> InvestigationResult:
        claim_id = str(claim_id).strip() if claim_id is not None else ""
        if not claim_id:
            return self._error_result("UNKNOWN", "UNKNOWN", "Claim ID is required.")

        claim = self.claim_store.get_claim(claim_id)
        if claim is None:
            return self._error_result(f"claim-{claim_id}", claim_id, f"Claim not found: {claim_id}")

        case = InvestigationCase(case_id=f"case-{claim.claim_id}", claim_id=claim.claim_id, claim=claim)
        return self.investigate(case)

    def investigate_provider(self, npi: int | str, provider: Optional[ProviderContext] = None) -> InvestigationResult:
        normalized_npi = self._coerce_npi(npi)
        if normalized_npi is None:
            return self._error_result("UNKNOWN", "UNKNOWN", "Provider NPI is required.")

        resolved_provider = provider or self.provider_store.get_provider(normalized_npi)
        if resolved_provider is None:
            return self._error_result(f"provider-{normalized_npi}", None, f"Provider not found: {normalized_npi}")

        synthetic_claim = ClaimContext(
            claim_id=f"provider-{resolved_provider.npi}",
            claim_type=None,
            provider_id=str(resolved_provider.npi),
            provider_id_type="NPI",
        )
        case = InvestigationCase(
            case_id=f"provider-{resolved_provider.npi}",
            claim_id=synthetic_claim.claim_id,
            claim=synthetic_claim,
            provider=resolved_provider,
        )
        return self.investigate(case)

    def _select_agents(self, case: InvestigationCase) -> Dict[str, Dict[str, Any]]:
        routing: Dict[str, Dict[str, Any]] = {
            "billing": {"selected": False, "status": "NOT_SELECTED", "reason": ""},
            "peer": {"selected": False, "status": "NOT_SELECTED", "reason": ""},
            "clinical_rule": {"selected": False, "status": "NOT_SELECTED", "reason": ""},
        }

        if case is None:
            return routing

        if case.provider is not None and case.provider.npi is not None and (case.claim is None or case.claim.claim_type in {None, "PROVIDER"}):
            routing["peer"] = {
                "selected": True,
                "status": "NOT_SELECTED",
                "reason": "Provider-only investigation using valid NPI.",
            }
            return routing

        claim = case.claim
        if claim is None:
            return routing

        if claim.provider_id is None:
            billing_reason = "Claim has no provider identifier; billing review still uses claim-level evidence when available."
            routing["billing"] = {"selected": True, "status": "NOT_SELECTED", "reason": billing_reason}
            routing["peer"] = {"selected": False, "status": "NOT_SELECTED", "reason": "Claim provider information is missing; peer review requires valid provider NPI."}
            routing["clinical_rule"] = {"selected": claim.claim_type not in {None, "CARRIER"}, "status": "NOT_SELECTED", "reason": "Clinical/rule review is supported for non-carrier claim types when evidence is present." if claim.claim_type not in {None, "CARRIER"} else "Carrier claims do not have a supported clinical-only rule layer."}
            return routing

        provider_id_type = str(claim.provider_id_type or "").upper()
        if provider_id_type == "NPI":
            routing["billing"] = {"selected": True, "status": "NOT_SELECTED", "reason": "Valid provider NPI available for billing and claim review."}
            routing["peer"] = {"selected": True, "status": "NOT_SELECTED", "reason": "Valid provider NPI available for peer comparison."}
            routing["clinical_rule"] = {"selected": claim.claim_type not in {None, "CARRIER"}, "status": "NOT_SELECTED", "reason": "Clinical/rule review is supported for non-carrier claim types when evidence is present." if claim.claim_type not in {None, "CARRIER"} else "Carrier claims do not have a supported clinical-only rule layer."}
            return routing

        if provider_id_type == "PRVDR_NUM":
            routing["billing"] = {"selected": True, "status": "NOT_SELECTED", "reason": "Claim supplies PRVDR_NUM; billing review runs using claim evidence."}
            routing["peer"] = {"selected": False, "status": "NOT_SELECTED", "reason": "Provider NPI unavailable; claim contains PRVDR_NUM only so PeerAgent is skipped to avoid an invalid NPI lookup."}
            routing["clinical_rule"] = {"selected": claim.claim_type not in {None, "CARRIER"}, "status": "NOT_SELECTED", "reason": "Clinical/rule review is supported for non-carrier claim types when evidence is present." if claim.claim_type not in {None, "CARRIER"} else "Carrier claims do not have a supported clinical-only rule layer."}
            return routing

        routing["billing"] = {"selected": True, "status": "NOT_SELECTED", "reason": "Claim exists and billing review can proceed using available billing evidence."}
        routing["peer"] = {"selected": False, "status": "NOT_SELECTED", "reason": "Provider identifier is not a valid NPI; peer review is skipped."}
        routing["clinical_rule"] = {"selected": claim.claim_type not in {None, "CARRIER"}, "status": "NOT_SELECTED", "reason": "Clinical/rule review is supported for non-carrier claim types when evidence is present." if claim.claim_type not in {None, "CARRIER"} else "Carrier claims do not have a supported clinical-only rule layer."}
        return routing

    def _error_result(self, case_id: str, claim_id: Optional[str], message: str) -> InvestigationResult:
        result = InvestigationResult(
            case_id=case_id,
            claim_id=claim_id,
            findings=[],
            findings_by_agent={"billing": [], "peer": [], "clinical_rule": []},
            findings_by_category={},
            routing={
                "billing": {"selected": False, "status": "FAILED", "reason": "Not executed because the claim or provider lookup failed."},
                "peer": {"selected": False, "status": "NOT_SELECTED", "reason": "PeerAgent skipped because the required provider lookup was unavailable."},
                "clinical_rule": {"selected": False, "status": "NOT_SELECTED", "reason": "Clinical/RuleAgent skipped because the investigation could not be created."},
            },
            summary={"error": message, "total_findings": 0},
            investigation_risk_score=0.0,
            investigation_priority="LOW",
            explanation="The investigation could not be created because the required claim or provider context was unavailable.",
            status="ERROR",
            agent_errors={},
        )
        return result

    @staticmethod
    def _coerce_npi(value: Any) -> Optional[int]:
        if value is None:
            return None
        try:
            return int(str(value).strip())
        except (TypeError, ValueError):
            return None
