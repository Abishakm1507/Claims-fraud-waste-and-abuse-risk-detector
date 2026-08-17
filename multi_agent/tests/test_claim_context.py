import pytest

from multi_agent.schemas.claim_context import ClaimContext


def test_valid_claim():
    claim = ClaimContext(
        claim_id="CLM-1",
        claim_type="OUTPATIENT",
        provider_id="100256",
        provider_id_type="PRVDR_NUM",
        claim_risk_score=88.5,
        final_risk_level="HIGH",
        final_risk_priority=2,
        final_claim_rank=10,
        data_availability={"financial": True, "temporal": True},
    )
    assert claim.claim_id == "CLM-1"
    assert claim.bene_id == "CLM-1"
    assert claim.provider_id_type == "PRVDR_NUM"


def test_missing_optional_evidence():
    claim = ClaimContext(
        claim_id="CLM-2",
        claim_type="INPATIENT",
        provider_id="33S394",
        provider_id_type="PRVDR_NUM",
        claim_risk_score=91.0,
        final_risk_level="CRITICAL",
    )
    assert claim.financial_evidence is None
    assert claim.utilization_evidence is None


def test_bene_id_mapping():
    claim = ClaimContext(claim_id="12345", claim_type="CARRIER", provider_id="1234567890", provider_id_type="NPI")
    assert claim.bene_id == "12345"


def test_provider_id_type_npi():
    claim = ClaimContext(claim_id="CLM-3", claim_type="CARRIER", provider_id="1234567890", provider_id_type="NPI")
    assert claim.provider_id_type == "NPI"


def test_provider_id_type_prvdr_num():
    claim = ClaimContext(claim_id="CLM-4", claim_type="OUTPATIENT", provider_id="100256", provider_id_type="PRVDR_NUM")
    assert claim.provider_id_type == "PRVDR_NUM"


def test_invalid_provider_id_type():
    with pytest.raises(ValueError):
        ClaimContext(
            claim_id="CLM-5",
            claim_type="OUTPATIENT",
            provider_id="100256",
            provider_id_type="INVALID",
        )


def test_canonical_risk_fields():
    claim = ClaimContext(
        claim_id="CLM-6",
        claim_type="OUTPATIENT",
        provider_id="100256",
        provider_id_type="PRVDR_NUM",
        claim_risk_score=75.0,
        final_risk_level="HIGH",
        final_risk_priority=3,
        final_claim_rank=7,
    )
    assert claim.claim_risk_score == 75.0
    assert claim.final_risk_level == "HIGH"
    assert claim.final_risk_priority == 3
    assert claim.final_claim_rank == 7
