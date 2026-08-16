from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List, Optional, Union

from multi_agent.models.schemas import (
    AgentResult,
    Evidence,
    Finding,
    GenAIExplanation,
    GenAIExplanationContext,
    HandoffMetadata,
    InvestigationCase,
    RAGExplanationRequest,
    RiskSynthesis,
)


class RAGHandoffAdapter:
    """Adapter that converts a completed InvestigationCase into the canonical RAG handoff contract."""

    @staticmethod
    def build(case: InvestigationCase) -> RAGExplanationRequest:
        return build_rag_handoff(case)

    @staticmethod
    def serialize(case: InvestigationCase) -> str:
        return serialize_rag_handoff(case)

    @staticmethod
    def deserialize(payload: Union[str, Dict[str, Any]]) -> RAGExplanationRequest:
        if isinstance(payload, str):
            data = json.loads(payload)
        elif isinstance(payload, dict):
            data = payload
        else:
            raise TypeError("payload must be JSON string or dict")
        return RAGExplanationRequest.model_validate(data)


def build_rag_handoff(case: InvestigationCase) -> RAGExplanationRequest:
    if case is None:
        raise ValueError("A completed InvestigationCase is required for RAG handoff.")
    if not getattr(case, "case_id", None):
        raise ValueError("InvestigationCase.case_id is required for RAG handoff.")
    if case.risk_synthesis is None:
        raise ValueError("InvestigationCase.risk_synthesis is required for RAG handoff.")

    evidence = list(case.evidence or [])
    findings = list(case.findings or [])
    agent_results = list(case.agent_results or [])
    request_id = f"rag-{case.case_id}"

    genai_context = GenAIExplanationContext.from_case(case)
    metadata = HandoffMetadata(
        case_id=case.case_id,
        request_id=request_id,
        generated_at=(case.updated_at or case.created_at or ""),
        source="deterministic_multi_agent",
        data_availability=_collect_data_availability(case),
        provenance={
            "source": "multi_agent_investigation_case",
            "case_id": case.case_id,
            "contract_version": case.contract_version,
            "risk_synthesis_version": case.risk_synthesis.synthesis_version or case.risk_synthesis.contract_version,
            "provenance": case.provenance,
        },
        limitations=_collect_limitations(case),
    )

    payload = RAGExplanationRequest(
        contract_version=case.contract_version or "1.0",
        request_id=request_id,
        case=case,
        evidence=evidence,
        findings=findings,
        risk_synthesis=case.risk_synthesis,
        agent_results=agent_results,
        genai_context=genai_context,
        metadata=metadata,
    )
    return payload


def serialize_rag_handoff(case: InvestigationCase) -> str:
    payload = build_rag_handoff(case)
    return json.dumps(payload.model_dump(mode="json", exclude_none=True), separators=(",", ":"), sort_keys=True)


def _collect_data_availability(case: InvestigationCase) -> Dict[str, str]:
    availability: Dict[str, str] = {}
    context = getattr(case, "investigation_context", None)
    if context and getattr(context, "data_availability", None):
        for key, value in context.data_availability.items():
            availability[key] = str(value.value if hasattr(value, "value") else value)
    for evidence in getattr(case, "evidence", []) or []:
        availability.setdefault(f"evidence:{evidence.evidence_id}", "AVAILABLE")
    return availability


def _collect_limitations(case: InvestigationCase) -> List[str]:
    limitations: List[str] = []
    if case.risk_synthesis and case.risk_synthesis.warnings:
        limitations.extend(case.risk_synthesis.warnings)
    for agent in getattr(case, "agent_results", []) or []:
        if agent.limitations:
            limitations.extend(agent.limitations)
    if not limitations:
        limitations.append("No additional limitations captured for this investigation.")
    return limitations
