import pytest

from multi_agent.agents.billing_agent import BillingAgent
from multi_agent.agents.clinical_rule_agent import ClinicalRuleAgent
from multi_agent.agents.peer_agent import PeerAgent
from multi_agent.schemas.claim_context import ClaimContext
from multi_agent.schemas.investigation_case import InvestigationCase
from multi_agent.schemas.provider_context import ProviderContext
from multi_agent.synthesis import Synthesis


def make_case(claim, provider=None):
    case = InvestigationCase(case_id=f"case-{claim.claim_id}", claim_id=claim.claim_id, claim=claim)
    if provider is not None:
        case.provider = provider
    return case


def test_no_findings_returns_valid_low_risk_result():
    claim = ClaimContext(
        claim_id="NO-FINDINGS-1",
        claim_type="OUTPATIENT",
        provider_id="100256",
        provider_id_type="PRVDR_NUM",
        claim_risk_score=12.0,
        final_risk_level="LOW",
        final_risk_priority=1,
        final_claim_rank=200,
    )
    case = make_case(claim)
    result = Synthesis().investigate(case, [], [], [])
    assert result.case_id == "case-NO-FINDINGS-1"
    assert result.summary["total_findings"] == 0
    assert result.investigation_priority == "LOW"
    assert result.claim_risk_score == 12.0
    assert result.final_risk_level == "LOW"


def test_billing_findings_are_preserved():
    claim = ClaimContext(
        claim_id="BILL-1",
        claim_type="OUTPATIENT",
        provider_id="100256",
        provider_id_type="PRVDR_NUM",
        claim_risk_score=70.0,
        final_risk_level="HIGH",
        final_risk_priority=2,
        final_claim_rank=15,
        financial_evidence={
            "available": True,
            "values": {"total_claim_payment": 30000.0, "total_claim_charge": 9000.0},
        },
        utilization_evidence={
            "available": True,
            "values": {"provider_avg_claim_payment": 5000.0},
        },
    )
    case = make_case(claim)
    billing_findings = BillingAgent().investigate(case)
    result = Synthesis().investigate(case, billing_findings, [], [])
    assert any(f.rule == "payment_charge_ratio" for f in result.findings)
    assert len(result.findings_by_agent["billing"]) == len(billing_findings)


def test_peer_findings_preserve_raw_evidence():
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
        peer_group="Mass Immunizer Roster Biller",
        peer_mean=47.25,
        peer_median=5.0,
        peer_std=31.46,
        provider_value=15.22,
        deviation_ratio=3.04,
        percentile=96.0,
        payment_per_service=15.22,
        services_per_beneficiary=11.16,
    )
    claim = ClaimContext(
        claim_id="PEER-1",
        claim_type="OUTPATIENT",
        provider_id="1003569997",
        provider_id_type="NPI",
        claim_risk_score=88.0,
        final_risk_level="HIGH",
        final_risk_priority=3,
        final_claim_rank=7,
    )
    case = make_case(claim, provider)
    peer_findings = PeerAgent().investigate(case)
    result = Synthesis().investigate(case, [], peer_findings, [])
    assert any(f.rule.startswith("high_") and "peers" in f.rule for f in result.findings)
    assert any(f.evidence.get("provider_value") == 15.22 for f in result.findings)
    assert result.findings_by_agent["peer"] == peer_findings


def test_clinical_findings_are_preserved():
    claim = ClaimContext(
        claim_id="CLIN-1",
        claim_type="OUTPATIENT",
        provider_id="100256",
        provider_id_type="PRVDR_NUM",
        claim_risk_score=68.0,
        final_risk_level="HIGH",
        final_risk_priority=2,
        final_claim_rank=20,
        utilization_evidence={
            "available": True,
            "values": {"claim_line_count": 9, "has_multiple_lines": True, "has_multiple_diagnoses": True},
        },
        procedure_evidence={
            "available": True,
            "values": {"has_procedure": True, "procedure_code_count": 18},
        },
    )
    case = make_case(claim)
    findings = ClinicalRuleAgent().investigate(case)
    result = Synthesis().investigate(case, [], [], findings)
    assert any(f.rule == "outpatient_multiple_lines_utilization" for f in result.findings)
    assert result.findings_by_agent["clinical_rule"] == findings


def test_all_three_agents_aggregate_findings():
    claim = ClaimContext(
        claim_id="ALL-1",
        claim_type="OUTPATIENT",
        provider_id="100256",
        provider_id_type="PRVDR_NUM",
        claim_risk_score=80.0,
        final_risk_level="HIGH",
        final_risk_priority=3,
        final_claim_rank=10,
        financial_evidence={
            "available": True,
            "values": {"total_claim_payment": 26000.0, "total_claim_charge": 6000.0},
        },
        utilization_evidence={
            "available": True,
            "values": {"claim_line_count": 8, "has_multiple_lines": True, "is_repeat_beneficiary_claim": True},
        },
        procedure_evidence={
            "available": True,
            "values": {"has_procedure": True, "procedure_code_count": 12},
        },
    )
    case = make_case(claim)
    billing = BillingAgent().investigate(case)
    result = Synthesis().investigate(case, billing, [], ClinicalRuleAgent().investigate(case))
    assert len(result.findings) > 1
    assert result.summary["billing_finding_count"] >= 1
    assert result.summary["clinical_rule_finding_count"] >= 1
    assert result.investigation_risk_score > 0


def test_severity_counts_are_calculated():
    billing = [
        type("F", (), {"agent": "billing", "category": "financial", "rule": "r1", "severity": "HIGH", "description": "d1", "evidence": {"x": 1}, "confidence": 0.9})(),
        type("F", (), {"agent": "billing", "category": "financial", "rule": "r2", "severity": "MEDIUM", "description": "d2", "evidence": {"x": 2}, "confidence": 0.8})(),
    ]
    result = Synthesis().investigate(InvestigationCase(case_id="sev", claim_id="sev"), billing, [], [])
    assert result.summary["HIGH"] == 1
    assert result.summary["MEDIUM"] == 1


def test_duplicate_findings_are_not_duplicated():
    duplicate = type("F", (), {"agent": "billing", "category": "financial", "rule": "dup", "severity": "HIGH", "description": "same", "evidence": {"ratio": 4.0}, "confidence": 0.9})()
    result = Synthesis().investigate(InvestigationCase(case_id="dup", claim_id="dup"), [duplicate, duplicate], [], [])
    assert len(result.findings) == 1


def test_different_evidence_is_not_wrongly_merged():
    f1 = type("F", (), {"agent": "billing", "category": "financial", "rule": "high_payment_ratio", "severity": "HIGH", "description": "same", "evidence": {"ratio": 4.0}, "confidence": 0.9})()
    f2 = type("F", (), {"agent": "peer", "category": "peer_comparison", "rule": "high_payment_vs_peers", "severity": "HIGH", "description": "same", "evidence": {"deviation_ratio": 4.0}, "confidence": 0.9})()
    result = Synthesis().investigate(InvestigationCase(case_id="diff", claim_id="diff"), [f1], [f2], [])
    assert len(result.findings) == 2
    assert {f.rule for f in result.findings} == {"high_payment_ratio", "high_payment_vs_peers"}


def test_missing_agent_does_not_break_synthesis():
    claim = ClaimContext(claim_id="MISS-1", claim_type="OUTPATIENT", provider_id="100256", provider_id_type="PRVDR_NUM")
    case = make_case(claim)
    result = Synthesis().investigate(case, [], [], [])
    assert isinstance(result, object)
    assert result.summary["total_findings"] == 0


def test_upstream_risk_fields_are_preserved():
    claim = ClaimContext(
        claim_id="RISK-1",
        claim_type="OUTPATIENT",
        provider_id="100256",
        provider_id_type="PRVDR_NUM",
        claim_risk_score=91.0,
        final_risk_level="CRITICAL",
        final_risk_priority=5,
        final_claim_rank=2,
    )
    case = make_case(claim)
    result = Synthesis().investigate(case, [], [], [])
    assert result.claim_risk_score == 91.0
    assert result.final_risk_level == "CRITICAL"
    assert result.final_risk_priority == 5
    assert result.final_claim_rank == 2


def test_provider_risk_context_is_preserved():
    provider = ProviderContext(
        npi=1000000001,
        provider_type="Surgery",
        provider_state="CA",
        provider_risk_score=80.0,
        risk_tier="High",
        global_anomaly_score=0.8,
    )
    claim = ClaimContext(claim_id="P-1", claim_type="OUTPATIENT", provider_id="1000000001", provider_id_type="NPI")
    case = make_case(claim, provider)
    result = Synthesis().investigate(case, [], [], [])
    assert result.provider_risk_score == 80.0
    assert result.risk_tier == "High"
    assert result.global_anomaly_score == 0.8


def test_synthesis_is_deterministic():
    claim = ClaimContext(claim_id="DET-1", claim_type="OUTPATIENT", provider_id="100256", provider_id_type="PRVDR_NUM")
    case = make_case(claim)
    first = Synthesis().investigate(case, [], [], [])
    second = Synthesis().investigate(case, [], [], [])
    assert first.to_dict() == second.to_dict()


def test_real_data_validation_uses_agent_outputs():
    claim = ClaimContext(claim_id="-10000930090156", claim_type="OUTPATIENT", provider_id="100256", provider_id_type="PRVDR_NUM")
    case = make_case(claim)
    result = Synthesis().investigate(case, BillingAgent().investigate(case), PeerAgent().investigate(case), ClinicalRuleAgent().investigate(case))
    assert isinstance(result.findings, list)
    assert result.summary["total_findings"] >= 0
    assert result.investigation_priority in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
