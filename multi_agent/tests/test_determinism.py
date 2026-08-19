"""Test that investigation_risk_score is deterministic and identical with LLM enabled/disabled."""
import pytest

from multi_agent.orchestrator import Orchestrator
from multi_agent.schemas.claim_context import ClaimContext, EvidenceBundle
from multi_agent.schemas.investigation_case import InvestigationCase
from multi_agent.schemas.provider_context import ProviderContext


def test_investigation_risk_score_is_identical_with_llm_enabled_disabled():
    """Risk score must be identical whether LLM reasoning is enabled or disabled.
    
    This verifies that the risk score is deterministic and not affected by LLM reasoning.
    """
    provider = ProviderContext(
        npi=1000000011,
        provider_type="Primary Care",
        provider_state="CA",
        provider_risk_score=30.0,
        risk_tier="Low",
        global_anomaly_score=0.20,
        peer_deviation_score=0.18,
        geo_deviation_score=0.15,
        is_leie_excluded=False,
        peer_group="Primary Care",
        provider_value=28.0,
        peer_median=30.0,
        deviation_ratio=0.93,
        percentile=40.0,
    )
    
    claim = ClaimContext(
        claim_id="test-determinism-123",
        claim_type="OUTPATIENT",
        provider_id="1000000011",
        provider_id_type="NPI",
        claim_risk_score=60.0,
        final_risk_level="MEDIUM",
        final_risk_priority=3,
        financial_evidence=EvidenceBundle(available=True, values={
            "total_claim_payment": 4500.0,
            "total_claim_charge": 5500.0,
            "payment_to_charge_ratio": 0.818,
        }),
        utilization_evidence=EvidenceBundle(available=True, values={
            "claim_line_count": 12,
            "provider_claim_count": 50,
        }),
    )
    
    case = InvestigationCase(case_id="case-determinism-123", claim_id="test-determinism-123", claim=claim, provider=provider)
    
    # Run with LLM enabled
    orchestrator_with_llm = Orchestrator(enable_llm_agent_reasoning=True)
    result_with_llm = orchestrator_with_llm.investigate(case)
    
    # Run with LLM disabled
    orchestrator_without_llm = Orchestrator(enable_llm_agent_reasoning=False)
    result_without_llm = orchestrator_without_llm.investigate(case)
    
    # Risk scores must be identical
    assert result_with_llm.investigation_risk_score == result_without_llm.investigation_risk_score, \
        f"Risk score differs: with_llm={result_with_llm.investigation_risk_score}, without_llm={result_without_llm.investigation_risk_score}"
    
    # Priority must be identical
    assert result_with_llm.investigation_priority == result_without_llm.investigation_priority, \
        f"Priority differs: with_llm={result_with_llm.investigation_priority}, without_llm={result_without_llm.investigation_priority}"


def test_investigation_risk_score_multiple_cases_deterministic():
    """Multiple cases should have identical risk scores with LLM on/off."""
    test_cases = [
        {
            "provider_score": 15.0,
            "claim_score": 40.0,
            "claim_type": "OUTPATIENT",
        },
        {
            "provider_score": 55.0,
            "claim_score": 75.0,
            "claim_type": "INPATIENT",
        },
        {
            "provider_score": 80.0,
            "claim_score": 95.0,
            "claim_type": "CARRIER",
        },
    ]
    
    for i, test_case in enumerate(test_cases):
        provider = ProviderContext(
            npi=1000000100 + i,
            provider_type="Primary Care",
            provider_state="CA",
            provider_risk_score=test_case["provider_score"],
            risk_tier="Low" if test_case["provider_score"] < 40 else "Medium" if test_case["provider_score"] < 70 else "High",
            global_anomaly_score=0.15 + (i * 0.2),
            peer_deviation_score=0.18 + (i * 0.15),
            geo_deviation_score=0.15 + (i * 0.1),
            is_leie_excluded=False,
            peer_group="Primary Care",
            provider_value=28.0 + (i * 10),
            peer_median=30.0,
            deviation_ratio=0.93,
            percentile=40.0 + (i * 15),
        )
        
        claim = ClaimContext(
            claim_id=f"test-determinism-{i}",
            claim_type=test_case["claim_type"],
            provider_id=str(1000000100 + i),
            provider_id_type="NPI",
            claim_risk_score=test_case["claim_score"],
            final_risk_level="HIGH" if test_case["claim_score"] > 80 else "MEDIUM" if test_case["claim_score"] > 50 else "LOW",
            final_risk_priority=1 if test_case["claim_score"] > 80 else 3 if test_case["claim_score"] > 50 else 5,
        )
        
        case = InvestigationCase(case_id=f"case-det-{i}", claim_id=f"test-determinism-{i}", claim=claim, provider=provider)
        
        # Run with LLM enabled
        orchestrator_with_llm = Orchestrator(enable_llm_agent_reasoning=True)
        result_with_llm = orchestrator_with_llm.investigate(case)
        
        # Run with LLM disabled
        orchestrator_without_llm = Orchestrator(enable_llm_agent_reasoning=False)
        result_without_llm = orchestrator_without_llm.investigate(case)
        
        # Risk scores and priorities must be identical
        assert result_with_llm.investigation_risk_score == result_without_llm.investigation_risk_score, \
            f"Case {i}: Risk score differs: with_llm={result_with_llm.investigation_risk_score}, without_llm={result_without_llm.investigation_risk_score}"
        
        assert result_with_llm.investigation_priority == result_without_llm.investigation_priority, \
            f"Case {i}: Priority differs: with_llm={result_with_llm.investigation_priority}, without_llm={result_without_llm.investigation_priority}"


def test_findings_count_may_differ_but_risk_score_same():
    """LLM may select different tools, resulting in different findings, but risk score must remain identical."""
    provider = ProviderContext(
        npi=1000000012,
        provider_type="Specialist",
        provider_state="NY",
        provider_risk_score=50.0,
        risk_tier="Medium",
        global_anomaly_score=0.40,
        peer_deviation_score=0.42,
        geo_deviation_score=0.38,
        is_leie_excluded=False,
        peer_group="Specialist",
        provider_value=60.0,
        peer_median=50.0,
        deviation_ratio=1.20,
        percentile=60.0,
    )
    
    claim = ClaimContext(
        claim_id="test-findings-123",
        claim_type="OUTPATIENT",
        provider_id="1000000012",
        provider_id_type="NPI",
        claim_risk_score=70.0,
        final_risk_level="HIGH",
        final_risk_priority=2,
    )
    
    case = InvestigationCase(case_id="case-findings-123", claim_id="test-findings-123", claim=claim, provider=provider)
    
    # Run with LLM enabled
    orchestrator_with_llm = Orchestrator(enable_llm_agent_reasoning=True)
    result_with_llm = orchestrator_with_llm.investigate(case)
    
    # Run with LLM disabled
    orchestrator_without_llm = Orchestrator(enable_llm_agent_reasoning=False)
    result_without_llm = orchestrator_without_llm.investigate(case)
    
    # The risk scores must be identical (frozen deterministic synthesis)
    assert result_with_llm.investigation_risk_score == result_without_llm.investigation_risk_score, \
        f"Risk score must be identical. With LLM: {result_with_llm.investigation_risk_score}, Without LLM: {result_without_llm.investigation_risk_score}"
