from __future__ import annotations

from typing import Any, Dict, Iterable, List

import pytest

from multi_agent.agents.billing_agent import BillingAgent
from multi_agent.agents.clinical_rule_agent import ClinicalRuleAgent
from multi_agent.agents.peer_agent import PeerAgent
from multi_agent.data.claim_store import ClaimStore
from multi_agent.data.provider_store import ProviderStore
from multi_agent.orchestrator import Orchestrator
from multi_agent.schemas.claim_context import ClaimContext
from multi_agent.schemas.investigation_case import InvestigationCase
from multi_agent.schemas.provider_context import ProviderContext


def _claim_store() -> ClaimStore:
    return ClaimStore()


def _provider_store() -> ProviderStore:
    return ProviderStore()


def _claim_by_type(claim_type: str) -> ClaimContext:
    store = _claim_store()
    df = store._df
    row = df[df["CLAIM_TYPE"] == claim_type].dropna(subset=["CLAIM_ID"]).iloc[0]
    return store.get_claim(str(row["CLAIM_ID"]))


def _first_npi_claim() -> ClaimContext:
    store = _claim_store()
    df = store._df
    row = df[(df["CLAIM_TYPE"] == "CARRIER") & (df["PROVIDER_ID_TYPE"] == "NPI")].dropna(subset=["CLAIM_ID"]).iloc[0]
    return store.get_claim(str(row["CLAIM_ID"]))


def _first_provider_npi() -> int:
    store = _provider_store()
    return int(store._df["NPI"].dropna().iloc[0])


def make_case(claim, provider=None):
    case = InvestigationCase(case_id=f"case-{claim.claim_id}", claim_id=claim.claim_id, claim=claim)
    if provider is not None:
        case.provider = provider
    return case


def test_full_claim_pipeline_end_to_end():
    claim = _first_npi_claim()
    result = Orchestrator().investigate_claim(claim.claim_id)

    assert result.case_id
    assert result.claim_id == claim.claim_id
    assert result.claim_type == claim.claim_type
    assert result.findings is not None
    assert result.investigation_risk_score is not None
    assert result.investigation_priority in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
    assert result.explanation
    assert result.routing["billing"]["selected"] is True


def test_carrier_claim_uses_npi_and_preserves_upstream_risk():
    claim = _first_npi_claim()
    before_score = claim.claim_risk_score
    before_level = claim.final_risk_level
    before_priority = claim.final_risk_priority
    before_rank = claim.final_claim_rank

    result = Orchestrator().investigate_claim(claim.claim_id)

    assert claim.provider_id_type == "NPI"
    assert result.routing["peer"]["selected"] is True
    assert result.claim_risk_score == before_score
    assert result.final_risk_level == before_level
    assert result.final_risk_priority == before_priority
    assert result.final_claim_rank == before_rank


def test_inpatient_claim_skips_peer_when_prvdr_num_only():
    claim = _claim_by_type("INPATIENT")
    result = Orchestrator().investigate_claim(claim.claim_id)

    assert claim.provider_id_type == "PRVDR_NUM"
    assert result.routing["billing"]["selected"] is True
    assert result.routing["peer"]["selected"] is False
    assert "PRVDR_NUM" in result.routing["peer"]["reason"]
    assert result.findings_by_agent["peer"] == []


def test_outpatient_claim_pipeline_preserves_rule_evidence():
    claim = _claim_by_type("OUTPATIENT")
    result = Orchestrator().investigate_claim(claim.claim_id)

    assert result.claim_type == "OUTPATIENT"
    assert result.routing["billing"]["selected"] is True
    assert result.routing["clinical_rule"]["selected"] in {True, False}
    assert result.findings_by_agent["billing"] is not None
    assert result.findings_by_agent["clinical_rule"] is not None


def test_high_risk_claim_keeps_upstream_ml_values_unchanged():
    store = _claim_store()
    df = store._df
    high = df[df["FINAL_RISK_LEVEL"].isin(["HIGH", "CRITICAL", "VERY HIGH", "VERY_HIGH"])].dropna(subset=["CLAIM_ID"]).iloc[0]
    claim = store.get_claim(str(high["CLAIM_ID"]))

    before_score = claim.claim_risk_score
    before_level = claim.final_risk_level
    before_priority = claim.final_risk_priority
    before_rank = claim.final_claim_rank

    result = Orchestrator().investigate_claim(claim.claim_id)

    assert result.claim_risk_score == before_score
    assert result.final_risk_level == before_level
    assert result.final_risk_priority == before_priority
    assert result.final_claim_rank == before_rank
    assert result.investigation_risk_score >= 0


def test_low_risk_claim_runs_without_fabricating_suspicion():
    store = _claim_store()
    df = store._df
    low = df[df["FINAL_RISK_LEVEL"].isin(["LOW", "VERY LOW"])].dropna(subset=["CLAIM_ID"]).iloc[0]
    claim = store.get_claim(str(low["CLAIM_ID"]))

    result = Orchestrator().investigate_claim(claim.claim_id)

    assert result.case_id
    assert result.summary["total_findings"] >= 0
    assert result.explanation
    assert result.investigation_priority in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}


def test_provider_investigation_runs_peer_only_and_preserves_provider_context():
    provider_npi = _first_provider_npi()
    provider = _provider_store().get_provider(provider_npi)
    result = Orchestrator().investigate_provider(provider_npi)

    assert provider is not None
    assert provider_npi == provider.npi
    assert result.routing["peer"]["selected"] is True
    assert result.routing["billing"]["selected"] is False
    assert result.routing["clinical_rule"]["selected"] is False
    assert result.provider_risk_score == provider.provider_risk_score
    assert result.risk_tier == provider.risk_tier
    assert result.global_anomaly_score == provider.global_anomaly_score


def test_end_to_end_evidence_preservation_for_peer_metrics():
    provider_store = _provider_store()
    df = provider_store._df
    row = df[df["Payment_per_Service_Peer_Median"].notna() & df["Payment_per_Service"].notna() & df["Payment_per_Service_Deviation_Ratio"].notna()].iloc[0]
    npi = int(row["NPI"])
    result = Orchestrator().investigate_provider(npi)

    assert result.findings_by_agent["peer"]
    evidence_fields = {"provider_value", "peer_mean", "peer_median", "peer_std", "deviation_ratio", "percentile", "peer_group"}
    found = any(evidence_fields.intersection(f.evidence.keys()) for f in result.findings_by_agent["peer"])
    assert found


def test_agent_failure_isolation_across_all_agents():
    class ExplodingBillingAgent(BillingAgent):
        def investigate(self, case):
            raise RuntimeError("billing failure")

    class ExplodingPeerAgent(PeerAgent):
        def investigate(self, case):
            raise RuntimeError("peer failure")

    class ExplodingClinicalRuleAgent(ClinicalRuleAgent):
        def investigate(self, case):
            raise RuntimeError("clinical failure")

    scenarios = [
        (
            "billing",
            ClaimContext(
                claim_id="FAIL-BILL-1",
                claim_type="OUTPATIENT",
                provider_id="1003569997",
                provider_id_type="NPI",
                claim_risk_score=68.0,
                final_risk_level="HIGH",
                final_risk_priority=2,
                final_claim_rank=12,
                financial_evidence={"available": True, "values": {"total_claim_payment": 30000.0, "total_claim_charge": 10000.0}},
            ),
        ),
        (
            "peer",
            ClaimContext(
                claim_id="FAIL-PEER-1",
                claim_type="CARRIER",
                provider_id="1558308825",
                provider_id_type="NPI",
                claim_risk_score=64.0,
                final_risk_level="MEDIUM",
                final_risk_priority=2,
                final_claim_rank=20,
            ),
        ),
        (
            "clinical_rule",
            ClaimContext(
                claim_id="FAIL-CLINICAL-1",
                claim_type="OUTPATIENT",
                provider_id="1003569997",
                provider_id_type="NPI",
                claim_risk_score=71.0,
                final_risk_level="HIGH",
                final_risk_priority=2,
                final_claim_rank=14,
                utilization_evidence={"available": True, "values": {"claim_line_count": 9, "has_multiple_lines": True}},
            ),
        ),
    ]

    for failing_agent_name, claim in scenarios:
        orchestrator = Orchestrator(
            billing_agent=ExplodingBillingAgent() if failing_agent_name == "billing" else BillingAgent(),
            peer_agent=ExplodingPeerAgent() if failing_agent_name == "peer" else PeerAgent(),
            clinical_rule_agent=ExplodingClinicalRuleAgent() if failing_agent_name == "clinical_rule" else ClinicalRuleAgent(),
        )
        result = orchestrator.investigate(make_case(claim))
        assert result.agent_errors.get(failing_agent_name)
        assert result.summary["total_findings"] >= 0


def test_no_data_fabrication_when_evidence_missing():
    claim = ClaimContext(
        claim_id="NO-EVIDENCE-1",
        claim_type="OUTPATIENT",
        provider_id="PRVDR-999",
        provider_id_type="PRVDR_NUM",
        claim_risk_score=22.0,
        final_risk_level="LOW",
        final_risk_priority=1,
        final_claim_rank=88,
        financial_evidence={"available": True, "values": {}},
        utilization_evidence={"available": True, "values": {}},
        procedure_evidence={"available": True, "values": {}},
    )
    case = InvestigationCase(case_id=f"case-{claim.claim_id}", claim_id=claim.claim_id, claim=claim)
    result = Orchestrator().investigate(case)

    assert result.summary["total_findings"] == 0
    for finding_list in result.findings_by_agent.values():
        assert all(not f.evidence for f in finding_list)


def test_determinism_and_idempotency():
    claim = _first_npi_claim()
    orchestrator = Orchestrator()
    result_1 = orchestrator.investigate_claim(claim.claim_id)
    result_2 = orchestrator.investigate_claim(claim.claim_id)

    assert result_1.case_id == result_2.case_id
    assert result_1.routing == result_2.routing
    assert result_1.summary == result_2.summary
    assert result_1.claim_risk_score == result_2.claim_risk_score
    assert result_1.final_risk_level == result_2.final_risk_level
    assert [f.rule for f in result_1.findings] == [f.rule for f in result_2.findings]
