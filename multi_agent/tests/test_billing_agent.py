import pytest

from multi_agent.agents.billing_agent import BillingAgent
from multi_agent.data.claim_store import ClaimStore
from multi_agent.schemas.claim_context import ClaimContext
from multi_agent.schemas.investigation_case import InvestigationCase


def make_case(claim):
    return InvestigationCase(case_id=f"case-{claim.claim_id}", claim_id=claim.claim_id, claim=claim)


def test_normal_claim_no_suspicious_billing_evidence():
    claim = ClaimContext(
        claim_id="NORMAL-1",
        claim_type="OUTPATIENT",
        provider_id="100256",
        provider_id_type="PRVDR_NUM",
        claim_risk_score=10.0,
        final_risk_level="LOW",
        final_risk_priority=1,
        final_claim_rank=100,
        financial_evidence={
            "available": True,
            "values": {
                "total_claim_payment": 600.0,
                "total_claim_charge": 700.0,
                "payment_to_charge_ratio": 0.86,
            },
        },
        utilization_evidence={
            "available": True,
            "values": {
                "claim_line_count": 1,
                "has_multiple_lines": False,
                "is_high_volume_provider": False,
            },
        },
    )
    findings = BillingAgent().investigate(make_case(claim))
    assert findings == []


def test_high_payment_rule():
    claim = ClaimContext(
        claim_id="HIGH-PAYMENT-1",
        claim_type="OUTPATIENT",
        provider_id="100256",
        provider_id_type="PRVDR_NUM",
        claim_risk_score=81.0,
        final_risk_level="HIGH",
        final_risk_priority=2,
        final_claim_rank=9,
        financial_evidence={
            "available": True,
            "values": {
                "total_claim_payment": 30000.0,
                "total_claim_charge": 28000.0,
                "payment_to_charge_ratio": 1.07,
            },
        },
        utilization_evidence={
            "available": True,
            "values": {
                "claim_line_count": 3,
                "has_multiple_lines": False,
                "provider_avg_claim_payment": 9000.0,
                "provider_total_payment": 150000.0,
                "provider_payment_std": 3000.0,
                "is_high_volume_provider": False,
            },
        },
    )
    findings = BillingAgent().investigate(make_case(claim))
    assert any(f.rule == "provider_payment_deviation" for f in findings)


def test_high_payment_charge_ratio_rule():
    claim = ClaimContext(
        claim_id="RATIO-1",
        claim_type="OUTPATIENT",
        provider_id="040085",
        provider_id_type="PRVDR_NUM",
        financial_evidence={
            "available": True,
            "values": {
                "total_claim_payment": 10000.0,
                "total_claim_charge": 2500.0,
                "payment_to_charge_ratio": 4.0,
            },
        },
    )
    findings = BillingAgent().investigate(make_case(claim))
    assert any(f.rule == "payment_charge_ratio" for f in findings)
    assert findings[0].evidence["ratio"] == pytest.approx(4.0)


def test_missing_charge_no_division_by_zero():
    claim = ClaimContext(
        claim_id="NO-CHARGE-1",
        claim_type="OUTPATIENT",
        provider_id="100256",
        provider_id_type="PRVDR_NUM",
        financial_evidence={
            "available": True,
            "values": {
                "total_claim_payment": 5000.0,
                "total_claim_charge": None,
            },
        },
    )
    findings = BillingAgent().investigate(make_case(claim))
    assert findings == []


def test_zero_charge_no_invalid_ratio():
    claim = ClaimContext(
        claim_id="ZERO-CHARGE-1",
        claim_type="OUTPATIENT",
        provider_id="100256",
        provider_id_type="PRVDR_NUM",
        financial_evidence={
            "available": True,
            "values": {
                "total_claim_payment": 5000.0,
                "total_claim_charge": 0.0,
            },
        },
    )
    findings = BillingAgent().investigate(make_case(claim))
    assert all(f.rule != "payment_charge_ratio" for f in findings)


def test_payment_reconciliation_issue():
    claim = ClaimContext(
        claim_id="RECON-1",
        claim_type="OUTPATIENT",
        provider_id="100256",
        provider_id_type="PRVDR_NUM",
        financial_evidence={
            "available": True,
            "values": {
                "has_payment_reconciliation_issue": True,
                "total_claim_payment": 12000.0,
            },
        },
    )
    findings = BillingAgent().investigate(make_case(claim))
    assert any(f.rule == "payment_reconciliation_issue" for f in findings)


def test_provider_payment_deviation():
    claim = ClaimContext(
        claim_id="DEVIATION-1",
        claim_type="OUTPATIENT",
        provider_id="100256",
        provider_id_type="PRVDR_NUM",
        financial_evidence={
            "available": True,
            "values": {
                "total_claim_payment": 24000.0,
            },
        },
        utilization_evidence={
            "available": True,
            "values": {
                "provider_avg_claim_payment": 7500.0,
            },
        },
    )
    findings = BillingAgent().investigate(make_case(claim))
    assert any(f.rule == "provider_payment_deviation" for f in findings)
    assert findings[0].evidence["ratio"] == pytest.approx(3.2)


def test_missing_provider_benchmark_skips_deviation():
    claim = ClaimContext(
        claim_id="DEVIATION-MISSING-1",
        claim_type="OUTPATIENT",
        provider_id="100256",
        provider_id_type="PRVDR_NUM",
        financial_evidence={
            "available": True,
            "values": {
                "total_claim_payment": 24000.0,
            },
        },
        utilization_evidence={
            "available": True,
            "values": {},
        },
    )
    findings = BillingAgent().investigate(make_case(claim))
    assert not any(f.rule == "provider_payment_deviation" for f in findings)


def test_high_volume_provider_rule():
    claim = ClaimContext(
        claim_id="HIGH-VOL-1",
        claim_type="OUTPATIENT",
        provider_id="100256",
        provider_id_type="PRVDR_NUM",
        financial_evidence={
            "available": True,
            "values": {
                "total_claim_payment": 5000.0,
            },
        },
        utilization_evidence={
            "available": True,
            "values": {
                "is_high_volume_provider": True,
            },
        },
    )
    findings = BillingAgent().investigate(make_case(claim))
    assert any(f.rule == "high_volume_provider" for f in findings)


def test_multiple_claim_lines_supporting_evidence():
    claim = ClaimContext(
        claim_id="MULTI-LINES-1",
        claim_type="OUTPATIENT",
        provider_id="100256",
        provider_id_type="PRVDR_NUM",
        financial_evidence={
            "available": True,
            "values": {
                "total_claim_payment": 5000.0,
            },
        },
        utilization_evidence={
            "available": True,
            "values": {
                "claim_line_count": 7,
                "has_multiple_lines": True,
            },
        },
    )
    findings = BillingAgent().investigate(make_case(claim))
    assert any(f.rule == "multiple_claim_lines" for f in findings)


def test_inpatient_limited_export_no_invented_facts():
    claim = ClaimContext(
        claim_id="INP-1",
        claim_type="INPATIENT",
        provider_id="33S394",
        provider_id_type="PRVDR_NUM",
        financial_evidence=None,
        utilization_evidence=None,
    )
    findings = BillingAgent().investigate(make_case(claim))
    assert findings == []


def test_carrier_first_line_values_described_precisely():
    claim = ClaimContext(
        claim_id="CARRIER-1",
        claim_type="CARRIER",
        provider_id="1558308825",
        provider_id_type="NPI",
        financial_evidence={
            "available": True,
            "values": {
                "claim_payment": 42062.86,
                "submitted_charge": 52578.57,
            },
        },
    )
    findings = BillingAgent().investigate(make_case(claim))
    assert any("first claim line" in f.description.lower() for f in findings)


def test_outpatient_complete_financial_evidence():
    claim = ClaimContext(
        claim_id="OUT-1",
        claim_type="OUTPATIENT",
        provider_id="040085",
        provider_id_type="PRVDR_NUM",
        financial_evidence={
            "available": True,
            "values": {
                "total_claim_payment": 8682.43,
                "total_claim_charge": 8682.43,
                "payment_to_charge_ratio": 1.0,
            },
        },
        utilization_evidence={
            "available": True,
            "values": {
                "has_payment_reconciliation_issue": 1,
            },
        },
    )
    findings = BillingAgent().investigate(make_case(claim))
    assert any(f.rule == "payment_reconciliation_issue" for f in findings)


def test_no_billing_evidence_returns_empty():
    claim = ClaimContext(claim_id="NONE-1", claim_type="OUTPATIENT", provider_id="100256", provider_id_type="PRVDR_NUM")
    findings = BillingAgent().investigate(make_case(claim))
    assert findings == []


def test_real_claim_data_validation():
    store = ClaimStore()
    carrier = store.get_claim("-10000930068276")
    outpatient = store.get_claim("-10000930090156")
    inpatient = store.get_claim("-10000930775141")

    assert carrier is not None and carrier.claim_type == "CARRIER"
    assert outpatient is not None and outpatient.claim_type == "OUTPATIENT"
    assert inpatient is not None and inpatient.claim_type == "INPATIENT"

    for claim in [carrier, outpatient, inpatient]:
        findings = BillingAgent().investigate(make_case(claim))
        assert isinstance(findings, list)
        for finding in findings:
            assert finding.agent == "billing"
            assert finding.category in {"financial", "utilization"}
            assert finding.confidence is not None
            assert finding.evidence is not None
