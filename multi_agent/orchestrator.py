from __future__ import annotations

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, Optional

from multi_agent.agents.billing_agent import BillingAgent
from multi_agent.agents.clinical_rule_agent import ClinicalRuleAgent
from multi_agent.agents.peer_agent import PeerAgent
from multi_agent.config.agent_llm_config import DEFAULT_AGENT_LLM_CONFIG
from multi_agent.utils.redaction import redact_for_llm
from multi_agent.data.claim_store import ClaimStore
from multi_agent.data.provider_store import ProviderStore
from multi_agent.models.schemas import InvestigationCase as ContractInvestigationCase
from multi_agent.schemas.claim_context import ClaimContext
from multi_agent.schemas.investigation_case import InvestigationCase
from multi_agent.schemas.provider_context import ProviderContext
from multi_agent.services.explanation_service import InvestigationExplanationService
from multi_agent.services.llm_agent_service import LLMAgentService
from multi_agent.synthesis import InvestigationResult, Synthesis

logger = logging.getLogger(__name__)


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
        llm_agent_service: Optional[LLMAgentService] = None,
        enable_genai_explanation: Optional[bool] = None,
        enable_llm_agent_reasoning: Optional[bool] = None,
    ):
        self.claim_store = claim_store or ClaimStore()
        self.provider_store = provider_store or ProviderStore()
        self.billing_agent = billing_agent or BillingAgent()
        self.peer_agent = peer_agent or PeerAgent(provider_store=self.provider_store)
        self.clinical_rule_agent = clinical_rule_agent or ClinicalRuleAgent()
        self.synthesis = synthesis or Synthesis()
        self.enable_genai_explanation = enable_genai_explanation if enable_genai_explanation is not None else True
        self.enable_llm_agent_reasoning = enable_llm_agent_reasoning if enable_llm_agent_reasoning is not None else True
        self.explanation_service = explanation_service or InvestigationExplanationService(enabled=self.enable_genai_explanation)
        self.llm_agent_service = llm_agent_service or LLMAgentService(enabled=self.enable_llm_agent_reasoning)

    def investigate(self, case: InvestigationCase) -> InvestigationResult:
        wall_start = time.time()
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
        agent_narratives: Dict[str, str] = {}
        tools_by_agent: Dict[str, list] = {}

        # Parallel execution: run all selected agents concurrently
        selected_agents = [name for name in self.AGENT_ORDER if routing[name]["selected"]]
        
        if selected_agents:
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = {}
                for agent_name in selected_agents:
                    routing[agent_name]["status"] = "RUNNING"
                    futures[executor.submit(self._run_agent, agent_name, case, routing)] = agent_name
                
                # Collect results as agents complete
                for future in as_completed(futures):
                    agent_name = futures[future]
                    try:
                        result_data = future.result()
                        # Unpack results
                        if agent_name == "billing":
                            billing_findings = result_data["findings"]
                            if "narrative" in result_data:
                                agent_narratives["billing"] = result_data["narrative"]
                            if "tools_called" in result_data:
                                tools_by_agent["billing"] = result_data["tools_called"]
                            routing[agent_name]["status"] = "SUCCESS" if result_data["findings"] else "EMPTY"
                        elif agent_name == "peer":
                            peer_findings = result_data["findings"]
                            if "narrative" in result_data:
                                agent_narratives["peer"] = result_data["narrative"]
                            if "tools_called" in result_data:
                                tools_by_agent["peer"] = result_data["tools_called"]
                            routing[agent_name]["status"] = "SUCCESS" if result_data["findings"] else "EMPTY"
                        elif agent_name == "clinical_rule":
                            clinical_findings = result_data["findings"]
                            if "narrative" in result_data:
                                agent_narratives["clinical_rule"] = result_data["narrative"]
                            if "tools_called" in result_data:
                                tools_by_agent["clinical_rule"] = result_data["tools_called"]
                            routing[agent_name]["status"] = "SUCCESS" if result_data["findings"] else "EMPTY"
                    except Exception as exc:  # pragma: no cover - defensive isolation
                        routing[agent_name]["status"] = "FAILED"
                        agent_errors[agent_name] = str(exc)
                        routing[agent_name]["error"] = str(exc)

        result = self.synthesis.investigate(
            case=case,
            billing_findings=billing_findings,
            peer_findings=peer_findings,
            clinical_rule_findings=clinical_findings,
            agent_errors=agent_errors,
            agent_narratives=agent_narratives,
            tools_by_agent=tools_by_agent,
        )
        result.routing = routing
        result.summary["routing"] = routing
        result.summary["agent_errors"] = agent_errors
        result.summary["selected_agents"] = [name for name, route in routing.items() if route["selected"]]
        result.summary["skipped_agents"] = [name for name, route in routing.items() if not route["selected"]]
        result.summary["failed_agents"] = [name for name, route in routing.items() if route["status"] == "FAILED"]
        result.summary["latency_seconds"] = 0.0
        result.summary["claim_features"] = (
            dict(getattr(case.claim, "claim_features", {}) or {})
            if case.claim is not None else {}
        )
        result.summary["provider_features"] = (
            case.provider.to_dict() if case.provider is not None else {}
        )
        result.summary["peer_features"] = (
            dict(getattr(case.claim, "peer_evidence", None).values or {})
            if case.claim is not None and getattr(case.claim, "peer_evidence", None) and getattr(case.claim.peer_evidence, "available", False)
            else {}
        )

        result.diagnostic_timing = {
            "orchestrator_total_seconds": float(time.time() - wall_start),
        }
        logger.info(
            "INVESTIGATION_TIMING case_id=%s orchestrator_total_seconds=%.6f",
            getattr(result, "case_id", "UNKNOWN"),
            result.diagnostic_timing["orchestrator_total_seconds"],
        )

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

    def _run_agent(self, agent_name: str, case: InvestigationCase, routing: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Execute a single agent and return its findings, narrative, and tools.
        
        This method runs in a thread pool worker and handles all agent-specific logic.
        
        Args:
            agent_name: Name of the agent ("billing", "peer", or "clinical_rule")
            case: Investigation case
            routing: Routing dict with per-agent metadata (including focus_hint if LLM enabled)
            
        Returns:
            Dict with "findings", "narrative" (if LLM), and "tools_called" (if LLM)
        """
        route = routing[agent_name]
        
        try:
            if agent_name == "billing":
                if self.enable_llm_agent_reasoning:
                    result = self.billing_agent.investigate_with_llm(
                        case,
                        claim_risk_score=getattr(case.claim, "claim_risk_score", None) if case.claim else None,
                        enable_llm=True,
                        focus_hint=route.get("rationale") or route.get("reason"),
                    )
                    return {
                        "findings": result.findings,
                        "narrative": result.narrative,
                        "tools_called": result.tools_called,
                    }
                else:
                    return {"findings": self.billing_agent.investigate(case)}
            elif agent_name == "peer":
                if self.enable_llm_agent_reasoning:
                    result = self.peer_agent.investigate_with_llm(
                        case,
                        provider_risk_score=case.provider.provider_risk_score if case.provider else None,
                        enable_llm=True,
                        focus_hint=route.get("rationale") or route.get("reason"),
                    )
                    return {
                        "findings": result.findings,
                        "narrative": result.narrative,
                        "tools_called": result.tools_called,
                    }
                else:
                    return {"findings": self.peer_agent.investigate(case)}
            elif agent_name == "clinical_rule":
                if self.enable_llm_agent_reasoning:
                    result = self.clinical_rule_agent.investigate_with_llm(
                        case,
                        claim_risk_score=getattr(case.claim, "claim_risk_score", None) if case.claim else None,
                        enable_llm=True,
                        focus_hint=route.get("rationale") or route.get("reason"),
                    )
                    return {
                        "findings": result.findings,
                        "narrative": result.narrative,
                        "tools_called": result.tools_called,
                    }
                else:
                    return {"findings": self.clinical_rule_agent.investigate(case)}
        except Exception:
            raise  # Let the caller handle exception and mark as FAILED

        return {"findings": []}  # pragma: no cover - unreachable


    def to_investigation_case(self, result: InvestigationResult) -> ContractInvestigationCase:
        """Adapt the deterministic investigation result to the typed InvestigationCase v1 contract."""
        explanation = None
        raw_explanation = (getattr(result, "summary", {}) or {}).get("genai_explanation")
        if isinstance(raw_explanation, dict):
            from multi_agent.models.schemas import GenAIExplanation

            explanation = GenAIExplanation(
                explanation_id=f"GEX-{result.case_id}",
                case_id=result.case_id,
                model_name=str(raw_explanation.get("model") or raw_explanation.get("model_name") or self.explanation_service.model),
                summary=str(raw_explanation.get("summary") or raw_explanation.get("executive_summary") or ""),
                risk_interpretation=raw_explanation.get("risk_interpretation") or {},
                key_findings=raw_explanation.get("key_findings") or raw_explanation.get("key_reasons") or [],
                evidence_references=raw_explanation.get("evidence_references") or raw_explanation.get("supporting_evidence") or [],
                investigation_narrative=raw_explanation.get("investigation_narrative"),
                limitations=raw_explanation.get("limitations") or [],
                recommended_review_actions=raw_explanation.get("recommended_review_actions") or ([raw_explanation["recommended_action"]] if raw_explanation.get("recommended_action") else []),
                model_metadata={"generated_by": raw_explanation.get("generated_by"), "error": raw_explanation.get("error")},
                source_case_id=result.case_id,
                status=str(raw_explanation.get("status") or "unavailable"),
            )
        case = ContractInvestigationCase.from_result(result, case_id=result.case_id, explanation=explanation)
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

        llm_plan = self._llm_plan(case)
        if llm_plan and isinstance(llm_plan, dict):
            for name, route in llm_plan.items():
                if name in routing and isinstance(route, dict):
                    routing[name].update({
                        "selected": bool(route.get("selected", routing[name].get("selected", False))),
                        "reason": route.get("reason") or routing[name].get("reason") or "LLM routing rationale.",
                        "rationale": route.get("rationale") or route.get("reason") or routing[name].get("reason") or "LLM routing rationale.",
                    })

        if case is None:
            return routing

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

    def _llm_plan(self, case: InvestigationCase) -> Dict[str, Dict[str, Any]]:
        if not self.explanation_service.enabled:
            return {}
        try:
            context = {
                "case_id": getattr(case, "case_id", "UNKNOWN"),
                "claim_id": getattr(case, "claim_id", "UNKNOWN"),
                "claim_type": getattr(getattr(case, "claim", None), "claim_type", None),
                "provider_id": getattr(getattr(case, "claim", None), "provider_id", None),
                "provider_id_type": getattr(getattr(case, "claim", None), "provider_id_type", None),
                "claim_risk_score": getattr(getattr(case, "claim", None), "claim_risk_score", None),
                "provider_risk_score": getattr(getattr(case, "provider", None), "provider_risk_score", None),
            }
            # Redact PHI/PII before sending to LLM (HIPAA compliance)
            context = redact_for_llm(context)
            fallback = {"billing": {"selected": True, "reason": "Billing review is required for claims with available billing evidence.", "rationale": "Billing review is required for claims with available billing evidence."}, "peer": {"selected": False, "reason": "Peer review is only required when a valid provider NPI is available.", "rationale": "Peer review is only required when a valid provider NPI is available."}, "clinical_rule": {"selected": False, "reason": "Clinical/rule review is only supported for non-carrier claim types when evidence is present.", "rationale": "Clinical/rule review is only supported for non-carrier claim types when evidence is present."}}
            response = self.explanation_service.generate_structured_reasoning("orchestrator", context, fallback=json.dumps(fallback))
            data = response.get("reasoning") or {}
            if isinstance(data, dict) and isinstance(data.get("routing_plan"), dict):
                return data["routing_plan"]
            return {}
        except Exception:
            return {}

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
