import pytest

from multi_agent.agents.clinical_rule_agent import ClinicalRuleAgent
from multi_agent.schemas.claim_context import ClaimContext
from multi_agent.schemas.investigation_case import InvestigationCase


def make_case(claim):
    return InvestigationCase(case_id=f"case-{claim.claim_id}", claim_id=claim.claim_id, claim=claim)


def test_normal_outpatient_has_no_clinical_rule_flags():
    claim = ClaimContext(
        claim_id="OUT-NORMAL-1",
        claim_type="OUTPATIENT",
        provider_id="100256",
        provider_id_type="PRVDR_NUM",
        claim_risk_score=12.0,
        final_risk_level="LOW",
        final_risk_priority=1,
        final_claim_rank=120,
        utilization_evidence={
            "available": True,
            "values": {
                "claim_line_count": 2,
                "has_multiple_lines": False,
                "has_multiple_diagnoses": False,
                "is_repeat_beneficiary_claim": False,
                "beneficiary_claim_count": 1,
                "provider_claim_count": 1,
                "is_high_volume_provider": False,
            },
        },
        procedure_evidence={
            "available": True,
            "values": {
                "has_procedure": False,
                "procedure_code_count": 1,
                "unique_procedure_code_count": 1,
            },
        },
    )
    findings = ClinicalRuleAgent().investigate(make_case(claim))
    assert findings == []


def test_outpatient_utilization_and_procedure_patterns_trigger_rule_findings():
    claim = ClaimContext(
        claim_id="OUT-UTIL-1",
        claim_type="OUTPATIENT",
        provider_id="100256",
        provider_id_type="PRVDR_NUM",
        claim_risk_score=72.0,
        final_risk_level="HIGH",
        final_risk_priority=2,
        final_claim_rank=13,
        utilization_evidence={
            "available": True,
            "values": {
                "claim_line_count": 9,
                "has_multiple_lines": True,
                "has_multiple_diagnoses": True,
                "is_repeat_beneficiary_claim": True,
                "beneficiary_claim_count": 4,
                "provider_claim_count": 3,
                "is_high_volume_provider": False,
            },
        },
        procedure_evidence={
            "available": True,
            "values": {
                "has_procedure": True,
                "procedure_code_count": 18,
                "unique_procedure_code_count": 6,
            },
        },
    )
    findings = ClinicalRuleAgent().investigate(make_case(claim))
    assert any(f.rule.startswith("outpatient_") for f in findings)
    assert any("utilization" in f.rule.lower() or "procedure" in f.rule.lower() for f in findings)


def test_inpatient_model_consensus_creates_clinical_rule_finding():
    claim = ClaimContext(
        claim_id="INP-RULE-1",
        claim_type="INPATIENT",
        provider_id="331234",
        provider_id_type="PRVDR_NUM",
        claim_risk_score=90.0,
        final_risk_level="CRITICAL",
        final_risk_priority=5,
        final_claim_rank=2,
        model_evidence={
            "available": True,
            "values": {
                "model_consensus": "3_MODEL_CONSENSUS",
                "model_consensus_count": 3,
                "isolation_forest_flag": True,
                "lof_flag": True,
                "one_class_svm_flag": True,
            },
        },
    )
    findings = ClinicalRuleAgent().investigate(make_case(claim))
    assert any(f.rule == "inpatient_model_consensus" for f in findings)


def test_missing_evidence_returns_no_false_clinical_findings():
    claim = ClaimContext(
        claim_id="MISSING-1",
        claim_type="OUTPATIENT",
        provider_id="100256",
        provider_id_type="PRVDR_NUM",
        claim_risk_score=25.0,
        final_risk_level="LOW",
        final_risk_priority=1,
        final_claim_rank=80,
        utilization_evidence={"available": True, "values": {}},
        procedure_evidence={"available": True, "values": {}},
        model_evidence={"available": True, "values": {}},
    )
    findings = ClinicalRuleAgent().investigate(make_case(claim))
    assert findings == []


def test_carrier_claim_does_not_create_clinical_rule_finding():
    claim = ClaimContext(
        claim_id="CARRIER-1",
        claim_type="CARRIER",
        provider_id="1558308825",
        provider_id_type="NPI",
        claim_risk_score=55.0,
        final_risk_level="MEDIUM",
        final_risk_priority=3,
        final_claim_rank=50,
        utilization_evidence={
            "available": True,
            "values": {
                "claim_line_count": 9,
                "has_multiple_lines": True,
                "is_high_volume_provider": True,
            },
        },
    )
    findings = ClinicalRuleAgent().investigate(make_case(claim))
    assert findings == []


def test_clinical_agent_does_not_modify_canonical_risk_fields():
    claim = ClaimContext(
        claim_id="RISK-IMMUTABLE-1",
        claim_type="OUTPATIENT",
        provider_id="100256",
        provider_id_type="PRVDR_NUM",
        claim_risk_score=83.0,
        final_risk_level="HIGH",
        final_risk_priority=2,
        final_claim_rank=7,
        utilization_evidence={
            "available": True,
            "values": {
                "claim_line_count": 5,
                "has_multiple_lines": True,
                "has_multiple_diagnoses": True,
                "is_repeat_beneficiary_claim": True,
                "beneficiary_claim_count": 3,
            },
        },
        procedure_evidence={
            "available": True,
            "values": {
                "has_procedure": True,
                "procedure_code_count": 12,
                "unique_procedure_code_count": 4,
            },
        },
    )
    original_score = claim.claim_risk_score
    original_level = claim.final_risk_level
    original_priority = claim.final_risk_priority
    original_rank = claim.final_claim_rank

    ClinicalRuleAgent().investigate(make_case(claim))

    assert claim.claim_risk_score == original_score
    assert claim.final_risk_level == original_level
    assert claim.final_risk_priority == original_priority
    assert claim.final_claim_rank == original_rank
