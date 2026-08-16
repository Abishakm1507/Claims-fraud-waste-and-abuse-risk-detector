import json

import pytest
from pydantic import ValidationError

from multi_agent.models.schemas import (
    AgentResult,
    AgentStatus,
    Evidence,
    Finding,
    GenAIExplanation,
    InvestigationCase,
    RiskCategory,
    RiskPriority,
    RiskSynthesis,
    RAGExplanationRequest,
)
from multi_agent.rag.handoff import build_rag_handoff


def _make_case():
    evidence = Evidence(
        evidence_id="EV-001",
        agent="peer",
        category="utilization",
        metric="services",
        provider_value=20000,
        peer_mean=6200,
        peer_median=5000,
        peer_std=2100,
        deviation_ratio=4.0,
        percentile=98.7,
        peer_group="Cardiology-TX",
        peer_sample_size=184,
        source="provider_risk_scores.csv",
        source_fields=["Tot_Srvcs", "Provider_Type", "Prvdr_State"],
        methodology="provider_benchmark",
        confidence=0.94,
    )
    finding = Finding(
        finding_id="F-001",
        agent="peer",
        title="High service utilization",
        description="Provider services are significantly above the peer median.",
        severity="HIGH",
        category="utilization",
        evidence_ids=["EV-001"],
        confidence=0.94,
    )
    agent_result = AgentResult(
        agent="peer",
        status=AgentStatus.SUCCESS,
        score=92,
        risk="HIGH",
        findings=[finding],
        evidence=[evidence],
        rule_hits=[],
        limitations=["Peer median unavailable in current Provider ML export."],
        provenance={"source": "provider_risk_scores.csv"},
        execution_id="exec-peer-1",
        execution_time_ms=142,
    )
    risk = RiskSynthesis(
        claim_anomaly=91.0,
        provider_anomaly=88.0,
        billing_score=70.0,
        peer_score=92.0,
        rule_score=74.0,
        weights={"claim_anomaly": 30, "provider_anomaly": 30, "peer_score": 20, "billing_score": 10, "rule_score": 10},
        overall_risk=84.0,
        risk_category=RiskCategory.HIGH,
        priority=RiskPriority.P1,
        methodology="deterministic_weighted_component_synthesis",
        contributing_agents=["billing", "peer", "clinical_rule"],
        contract_version="1.0",
        synthesis_version="1.0.0",
        raw_score=84.2,
        contributions=[],
        warnings=[],
        errors=[],
        is_complete=True,
        is_usable=True,
    )
    explanation = GenAIExplanation(
        explanation_id="GEX-1",
        model_name="llama-3.3-70b-versatile",
        summary="Deterministic evidence shows elevated utilization and peer deviation.",
        key_findings=[{"agent": "peer", "finding": "High service utilization", "evidence": "Peer median exceeded."}],
        evidence_references=["EV-001"],
        investigation_narrative="The claim shows elevated utilization and peer deviation.",
        limitations=["Temporal evidence unavailable."],
        generated_at="2026-08-16T00:00:00Z",
        source_case_id="CASE-10231",
    )
    case = InvestigationCase(
        case_id="CASE-10231",
        claim_id="CLAIM-10231",
        provider_id="NPI-1234567890",
        provider_id_type="NPI",
        claim_type="CARRIER",
        findings=[finding],
        evidence=[evidence],
        risk_synthesis=risk,
        genai_explanation=explanation,
        agent_results=[agent_result],
    )
    return case


def test_valid_case_generates_valid_rag_request():
    case = _make_case()
    request = build_rag_handoff(case)
    assert request.contract_version == "1.0"
    assert request.request_id == "rag-CASE-10231"
    assert request.case.case_id == case.case_id
    assert request.risk_synthesis.overall_risk == 84.0
    assert request.genai_context.case_id == "CASE-10231"


def test_missing_case_id_fails_validation():
    case = _make_case()
    case.case_id = ""
    with pytest.raises(ValueError):
        build_rag_handoff(case)


def test_missing_risk_synthesis_fails_validation():
    case = _make_case()
    case.risk_synthesis = None
    with pytest.raises(ValueError):
        build_rag_handoff(case)


def test_invalid_agent_result_fails_validation():
    case = _make_case()
    case.agent_results[0].score = 101
    with pytest.raises(ValueError):
        build_rag_handoff(case)


def test_duplicate_evidence_id_fails_validation():
    case = _make_case()
    case.evidence.append(case.evidence[0].model_copy())
    with pytest.raises(ValueError):
        build_rag_handoff(case)


def test_invalid_score_fails_validation():
    case = _make_case()
    case.risk_synthesis.overall_risk = 200
    with pytest.raises(ValueError):
        build_rag_handoff(case)


def test_nan_and_infinity_fail_validation():
    case = _make_case()
    case.evidence[0].provider_value = float("nan")
    with pytest.raises(ValueError):
        build_rag_handoff(case)

    case = _make_case()
    case.evidence[0].provider_value = float("inf")
    with pytest.raises(ValueError):
        build_rag_handoff(case)


def test_agent_error_status_is_preserved():
    case = _make_case()
    case.agent_results[0].status = "error"
    request = build_rag_handoff(case)
    assert request.agent_results[0].status == "error"


def test_agent_skipped_status_is_preserved():
    case = _make_case()
    case.agent_results[0].status = "skipped"
    request = build_rag_handoff(case)
    assert request.agent_results[0].status == "skipped"


def test_missing_peer_data_is_not_fabricated():
    case = _make_case()
    case.evidence = []
    request = build_rag_handoff(case)
    assert request.evidence == []


def test_missing_temporal_data_is_preserved_as_limitation():
    case = _make_case()
    case.risk_synthesis.warnings.append("Temporal data unavailable")
    request = build_rag_handoff(case)
    assert any("Temporal" in item for item in request.metadata.limitations)


def test_provenance_is_preserved():
    case = _make_case()
    case.provenance = {"source": "provider_risk_scores.csv", "case_id": case.case_id}
    request = build_rag_handoff(case)
    assert request.metadata.provenance["case_id"] == case.case_id


def test_evidence_is_preserved():
    case = _make_case()
    request = build_rag_handoff(case)
    assert request.evidence[0].evidence_id == "EV-001"
    assert request.evidence[0].provider_value == 20000


def test_contract_version_present():
    case = _make_case()
    request = build_rag_handoff(case)
    assert request.contract_version


def test_json_serialization_succeeds():
    case = _make_case()
    request = build_rag_handoff(case)
    payload = json.dumps(request.model_dump(mode="json", exclude_none=True))
    assert "CASE-10231" in payload
    assert "provider_risk_scores.csv" in payload


def test_round_trip_serialization_deserialization():
    case = _make_case()
    request = build_rag_handoff(case)
    serialized = request.model_dump(mode="json", exclude_none=True)
    round_trip = RAGExplanationRequest.model_validate(serialized)
    assert round_trip.request_id == request.request_id
    assert round_trip.risk_synthesis.overall_risk == request.risk_synthesis.overall_risk


def test_genai_context_preserved():
    case = _make_case()
    request = build_rag_handoff(case)
    assert request.genai_context.priority == RiskPriority.P1
    assert request.genai_context.risk_category == RiskCategory.HIGH


def test_internal_implementation_details_not_leaked():
    case = _make_case()
    request = build_rag_handoff(case)
    payload = request.model_dump(mode="json", exclude_none=True)
    assert "joblib" not in json.dumps(payload)
    assert "provider_repository" not in json.dumps(payload)
    assert "csv_path" not in json.dumps(payload)
