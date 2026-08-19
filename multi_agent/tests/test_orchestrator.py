import pytest

from multi_agent.agents.billing_agent import BillingAgent
from multi_agent.agents.clinical_rule_agent import ClinicalRuleAgent
from multi_agent.agents.peer_agent import PeerAgent
from multi_agent.orchestrator import Orchestrator
from multi_agent.schemas.claim_context import ClaimContext
from multi_agent.schemas.investigation_case import InvestigationCase
from multi_agent.schemas.provider_context import ProviderContext


def make_case(claim, provider=None):
    case = InvestigationCase(case_id=f"case-{claim.claim_id}", claim_id=claim.claim_id, claim=claim)
    if provider is not None:
        case.provider = provider
    return case


def test_claim_investigation_routes_all_supported_agents():
    claim = ClaimContext(
        claim_id="ORCH-1",
        claim_type="OUTPATIENT",
        provider_id="1003569997",
        provider_id_type="NPI",
        claim_risk_score=82.0,
        final_risk_level="HIGH",
        final_risk_priority=3,
        final_claim_rank=10,
        financial_evidence={"available": True, "values": {"total_claim_payment": 25000.0, "total_claim_charge": 7000.0}},
        utilization_evidence={"available": True, "values": {"claim_line_count": 8, "has_multiple_lines": True}},
    )
    provider = ProviderContext(
        npi=1003569997,
        provider_type="Mass Immunizer Roster Biller",
        provider_state="NY",
        provider_risk_score=99.45,
        risk_tier="Critical",
        global_anomaly_score=0.994,
        peer_deviation_score=0.995,
        geo_deviation_score=0.995,
        is_leie_excluded=False,
    )
    case = make_case(claim, provider)

    result = Orchestrator().investigate(case)

    assert result.findings_by_agent["billing"]
    assert result.findings_by_agent["peer"]
    assert result.findings_by_agent["clinical_rule"]
    assert result.routing["billing"]["selected"] is True
    assert result.routing["peer"]["selected"] is True
    assert result.routing["clinical_rule"]["selected"] is True


def test_claim_with_prvdr_num_skips_peer_agent():
    claim = ClaimContext(
        claim_id="ORCH-PRVDR-1",
        claim_type="INPATIENT",
        provider_id="331234",
        provider_id_type="PRVDR_NUM",
        claim_risk_score=76.0,
        final_risk_level="HIGH",
        final_risk_priority=2,
        final_claim_rank=8,
        model_evidence={"available": True, "values": {"model_consensus": "3_MODEL_CONSENSUS", "model_consensus_count": 3}},
    )
    case = make_case(claim)

    result = Orchestrator().investigate(case)

    assert result.routing["billing"]["selected"] is True
    assert result.routing["clinical_rule"]["selected"] is True
    assert result.routing["peer"]["selected"] is False
    assert "PRVDR_NUM" in result.routing["peer"]["reason"]
    assert result.findings_by_agent["peer"] == []


def test_peer_agent_failure_is_isolated_from_other_agents():
    class ExplodingPeerAgent(PeerAgent):
        def investigate(self, case):
            raise RuntimeError("Provider not found")

    claim = ClaimContext(
        claim_id="ORCH-FAIL-1",
        claim_type="OUTPATIENT",
        provider_id="1003569997",
        provider_id_type="NPI",
        claim_risk_score=68.0,
        final_risk_level="HIGH",
        final_risk_priority=2,
        final_claim_rank=12,
        financial_evidence={"available": True, "values": {"total_claim_payment": 30000.0, "total_claim_charge": 10000.0}},
    )
    case = make_case(claim)

    result = Orchestrator(
        billing_agent=BillingAgent(),
        peer_agent=ExplodingPeerAgent(),
        clinical_rule_agent=ClinicalRuleAgent(),
    ).investigate(case)

    assert result.agent_errors["peer"] == "Provider not found"
    assert result.findings_by_agent["billing"]
    assert "clinical_rule" in result.findings_by_agent
    assert result.summary["total_findings"] >= 1
    assert result.status in {"REVIEW_REQUIRED", "HIGH_PRIORITY_REVIEW", "CRITICAL_REVIEW", "OPEN"}


def test_provider_only_case_runs_peer_only():
    provider = ProviderContext(
        npi=1001111111,
        provider_type="Cardiology",
        provider_state="CA",
        provider_risk_score=65.0,
        risk_tier="Moderate",
        global_anomaly_score=0.62,
        peer_deviation_score=0.96,
        geo_deviation_score=0.4,
        is_leie_excluded=False,
        peer_group="Cardiology",
    )

    result = Orchestrator().investigate_provider(1001111111, provider=provider)

    assert result.routing["peer"]["selected"] is True
    assert result.routing["billing"]["selected"] is False
    assert result.routing["clinical_rule"]["selected"] is False
    assert "peer" in result.findings_by_agent
    assert result.findings_by_agent["peer"]


def test_investigate_claim_missing_claim_returns_structured_error_result():
    result = Orchestrator().investigate_claim("DOES-NOT-EXIST")

    assert result.status == "ERROR"
    assert result.agent_errors == {}
    assert "not found" in result.summary["error"].lower()
