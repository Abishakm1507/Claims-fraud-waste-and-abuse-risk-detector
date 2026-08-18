import json

import pytest
from pydantic import ValidationError

from multi_agent.models.schemas import (
    CONTRACT_VERSION,
    AgentExecution,
    AgentResult,
    DataAvailability,
    Evidence,
    Finding,
    GenAIExplanation,
    InvestigationCase,
    InvestigationContext,
    RiskSynthesis,
    RuleHit,
    RiskCategory,
    AgentStatus,
    RiskPriority,
)


def make_evidence():
    return Evidence(
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


def test_valid_agent_result():
    finding = Finding(
        finding_id="F-001",
        agent="peer",
        title="High service utilization",
        description="Provider services are significantly above the peer baseline.",
        severity="HIGH",
        category="utilization",
        evidence_ids=["EV-001"],
        confidence=0.94,
    )
    evidence = make_evidence()
    result = AgentResult(
        agent="peer",
        status="success",
        score=91,
        risk="HIGH",
        findings=[finding],
        evidence=[evidence],
        rule_hits=[],
        limitations=["Peer median unavailable in current Provider ML export."],
        provenance={"source": "provider_risk_scores.csv"},
        execution_id="exec-1",
        execution_time_ms=122,
        contract_version=CONTRACT_VERSION,
    )
    assert result.score == 91
    assert result.risk == "HIGH"
    assert result.contract_version == CONTRACT_VERSION


def test_invalid_agent_result_score_rejected():
    with pytest.raises(ValidationError):
        AgentResult(
            agent="billing",
            status="success",
            score=101,
            risk="HIGH",
            findings=[],
            evidence=[],
            rule_hits=[],
            limitations=[],
            provenance={},
            execution_id="exec-2",
            execution_time_ms=5,
            contract_version=CONTRACT_VERSION,
        )


def test_invalid_risk_rejected():
    with pytest.raises(ValidationError):
        AgentResult(
            agent="clinical_rule",
            status="success",
            score=50,
            risk="SEVERE",
            findings=[],
            evidence=[],
            rule_hits=[],
            limitations=[],
            provenance={},
            execution_id="exec-3",
            execution_time_ms=2,
            contract_version=CONTRACT_VERSION,
        )


def test_invalid_status_rejected():
    with pytest.raises(ValidationError):
        AgentResult(
            agent="peer",
            status="unknown",
            score=20,
            risk="LOW",
            findings=[],
            evidence=[],
            rule_hits=[],
            limitations=[],
            provenance={},
            execution_id="exec-4",
            execution_time_ms=4,
            contract_version=CONTRACT_VERSION,
        )


def test_valid_evidence_and_missing_optional_baseline():
    evidence = Evidence(
        evidence_id="EV-002",
        agent="billing",
        category="financial",
        metric="payment_to_charge_ratio",
        provider_value=30000,
        claim_value=7000,
        baseline_value=None,
        deviation_ratio=4.29,
        source="claims.csv",
        source_fields=["total_claim_payment", "total_claim_charge"],
        methodology="billing_ratio",
        confidence=0.9,
    )
    assert evidence.provider_value == 30000
    assert evidence.baseline_value is None


def test_finding_references_evidence_by_id():
    finding = Finding(
        finding_id="F-002",
        agent="peer",
        title="Peer deviation",
        description="Service utilization exceeds peer group.",
        severity="HIGH",
        category="utilization",
        evidence_ids=["EV-001"],
        confidence=0.9,
    )
    assert finding.evidence_ids == ["EV-001"]


def test_rule_hit_schema():
    rule = RuleHit(
        rule_id="R03",
        rule_name="Extreme utilization",
        status="TRIGGERED",
        severity="HIGH",
        description="Utilization exceeds configured threshold.",
        evidence_ids=["EV-009"],
        threshold=3.0,
        observed_value=4.8,
        source="clinical_rule_agent",
        confidence=0.85,
    )
    assert rule.status == "TRIGGERED"


def test_agent_execution_schema():
    execution = AgentExecution(
        execution_id="ae-1",
        case_id="CASE-1",
        agent="billing",
        status="success",
        started_at="2026-08-16T00:00:00Z",
        completed_at="2026-08-16T00:00:01Z",
        execution_time_ms=1000,
        input_summary="claim-level inputs",
        output_evidence_count=1,
        output_finding_count=1,
        agent_version="1.0",
        contract_version=CONTRACT_VERSION,
    )
    assert execution.execution_time_ms == 1000


def test_risk_synthesis_schema():
    synthesis = RiskSynthesis(
        claim_anomaly=91,
        provider_anomaly=88,
        billing_score=20,
        peer_score=30,
        rule_score=10,
        weights={"claim_anomaly": 30, "provider_anomaly": 30, "peer_score": 20, "billing_score": 10, "rule_score": 10},
        overall_risk=84,
        risk_category="HIGH",
        priority="P1",
        methodology="weights_applied_to_deterministic_scores",
        contributing_agents=["billing", "peer", "clinical_rule"],
        contract_version=CONTRACT_VERSION,
    )
    assert synthesis.risk_category == "HIGH"
    assert synthesis.priority == "P1"


def test_investigation_case_serialization():
    evidence = make_evidence()
    case = InvestigationCase(
        contract_version=CONTRACT_VERSION,
        case_id="CASE-10231",
        claim_id="CLM10231",
        provider_id="P10023",
        provider_id_type="NPI",
        claim_type="OUTPATIENT",
        investigation_context=InvestigationContext(
            case_id="CASE-10231",
            claim_id="CLM10231",
            provider_id="P10023",
            provider_id_type="NPI",
            claim_type="OUTPATIENT",
            claim_anomaly=91,
            provider_anomaly=88,
            data_availability={"financial": DataAvailability.AVAILABLE, "peer": DataAvailability.NOT_AVAILABLE},
        ),
        agent_results=[
            AgentResult(
                agent="billing",
                status="success",
                score=81,
                risk="HIGH",
                findings=[],
                evidence=[evidence],
                rule_hits=[],
                limitations=[],
                provenance={},
                execution_id="exec-5",
                execution_time_ms=20,
                contract_version=CONTRACT_VERSION,
            )
        ],
        findings=[
            Finding(
                finding_id="F-003",
                agent="billing",
                title="Payment-to-charge ratio",
                description="Claim has a high payment-to-charge ratio.",
                severity="HIGH",
                category="financial",
                evidence_ids=["EV-001"],
                confidence=0.92,
            )
        ],
        evidence=[evidence],
        risk_synthesis=RiskSynthesis(
            claim_anomaly=91,
            provider_anomaly=88,
            billing_score=81,
            peer_score=0,
            rule_score=0,
            weights={"claim_anomaly": 30, "provider_anomaly": 30, "peer_score": 20, "billing_score": 10, "rule_score": 10},
            overall_risk=81,
            risk_category="HIGH",
            priority="P1",
            methodology="weighted_deterministic_synthesis",
            contributing_agents=["billing"],
            contract_version=CONTRACT_VERSION,
        ),
        created_at="2026-08-16T00:00:00Z",
        updated_at="2026-08-16T00:00:00Z",
    )
    payload = case.model_dump(mode="json")
    json_payload = case.model_dump_json()
    assert payload["case_id"] == "CASE-10231"
    assert isinstance(json.loads(json_payload), dict)


def test_genai_explanation_schema():
    explanation = GenAIExplanation(
        explanation_id="GE-1",
        model_provider="Groq",
<<<<<<< HEAD
        model_name="openai/gpt-oss-120b",
=======
        model_name="llama-3.3-70b-versatile",
>>>>>>> b166e40 (removed old data)
        summary="The claim is elevated by billing evidence.",
        key_findings=[{"agent": "billing", "finding": "High payment-to-charge ratio."}],
        evidence_references=["EV-001"],
        investigation_narrative="The billing evidence is the strongest signal.",
        limitations=["Peer benchmark data is unavailable."],
        generated_at="2026-08-16T00:00:00Z",
        prompt_version="1.0",
        explanation_version="1.0",
        source_case_id="CASE-10231",
        contract_version=CONTRACT_VERSION,
    )
    assert explanation.model_provider == "Groq"


def test_unknown_fields_rejected():
    with pytest.raises(ValidationError):
        AgentResult(
            agent="peer",
            status="success",
            score=60,
            risk="MEDIUM",
            findings=[],
            evidence=[],
            rule_hits=[],
            limitations=[],
            provenance={},
            execution_id="exec-6",
            execution_time_ms=5,
            contract_version=CONTRACT_VERSION,
            random_internal_field="nope",
        )


def test_missing_provider_evidence_is_explicitly_not_fabricated():
    context = InvestigationContext(
        case_id="CASE-PEER-MISSING",
        claim_id="CLM-PEER-MISSING",
        provider_id="1003569997",
        provider_id_type="NPI",
        claim_type="OUTPATIENT",
        claim_anomaly=52,
        provider_anomaly=60,
        data_availability={
            "peer_benchmark": DataAvailability.NOT_AVAILABLE,
            "provider_geo": DataAvailability.NOT_APPLICABLE,
        },
    )
    assert context.data_availability["peer_benchmark"] == DataAvailability.NOT_AVAILABLE


def test_carrier_context_and_inpatient_and_outpatient_contexts():
    carrier = InvestigationContext(
        case_id="CASE-1",
        claim_id="CLM-1",
        provider_id="1003569997",
        provider_id_type="NPI",
        claim_type="CARRIER",
        claim_anomaly=70,
        provider_anomaly=65,
    )
    inpatient = InvestigationContext(
        case_id="CASE-2",
        claim_id="CLM-2",
        provider_id="PRVDR-123",
        provider_id_type="PRVDR_NUM",
        claim_type="INPATIENT",
        claim_anomaly=72,
        provider_anomaly=72,
    )
    outpatient = InvestigationContext(
        case_id="CASE-3",
        claim_id="CLM-3",
        provider_id="PRVDR-456",
        provider_id_type="PRVDR_NUM",
        claim_type="OUTPATIENT",
        claim_anomaly=77,
        provider_anomaly=75,
    )
    assert carrier.provider_id_type == "NPI"
    assert inpatient.provider_id_type == "PRVDR_NUM"
    assert outpatient.claim_type == "OUTPATIENT"


def test_agent_failure_and_skip_status_are_supported():
    error_result = AgentResult(
        agent="peer",
        status="error",
        score=0,
        risk="UNKNOWN",
        findings=[],
        evidence=[],
        rule_hits=[],
        limitations=["Peer agent failed to resolve provider metadata."],
        provenance={},
        execution_id="exec-7",
        execution_time_ms=75,
        contract_version=CONTRACT_VERSION,
    )
    skipped_result = AgentResult(
        agent="clinical_rule",
        status="skipped",
        score=0,
        risk="UNKNOWN",
        findings=[],
        evidence=[],
        rule_hits=[],
        limitations=["Carrier claims do not support the clinical-only rule layer."],
        provenance={},
        execution_id="exec-8",
        execution_time_ms=0,
        contract_version=CONTRACT_VERSION,
    )
    assert error_result.status == "error"
    assert skipped_result.status == "skipped"
