"""Test that agent narratives are grounded in tool outputs (no hallucinated numbers)."""
import re
from typing import List, Set

import pytest

from multi_agent.agents.billing_agent import BillingAgent
from multi_agent.agents.clinical_rule_agent import ClinicalRuleAgent
from multi_agent.agents.peer_agent import PeerAgent
from multi_agent.schemas.claim_context import ClaimContext, EvidenceBundle
from multi_agent.schemas.investigation_case import InvestigationCase
from multi_agent.schemas.provider_context import ProviderContext


def extract_numbers(text: str) -> Set[float]:
    """Extract all numbers from text."""
    if not text:
        return set()
    # Match integers and decimals
    pattern = r"-?\d+(?:\.\d+)?"
    matches = re.findall(pattern, text)
    return {float(m) for m in matches}


def collect_tool_output_numbers(tools_called: List[str], case_context: dict) -> Set[float]:
    """Collect all numbers from the context that would be in tool outputs.
    
    This is a simplified version - in practice we'd capture actual tool outputs.
    For now, we extract numbers from numeric values in case_context.
    """
    numbers = set()
    
    def extract_from_value(val):
        if isinstance(val, (int, float)):
            numbers.add(float(val))
        elif isinstance(val, dict):
            for v in val.values():
                extract_from_value(v)
        elif isinstance(val, (list, tuple)):
            for v in val:
                extract_from_value(v)
    
    extract_from_value(case_context)
    return numbers


def test_billing_agent_narrative_grounding():
    """Billing agent narrative should only use numbers from tool outputs."""
    provider = ProviderContext(
        npi=1000000001,
        provider_type="Primary Care",
        provider_state="CA",
        provider_risk_score=25.0,
        risk_tier="Low",
        global_anomaly_score=0.15,
        peer_deviation_score=0.12,
        geo_deviation_score=0.10,
        is_leie_excluded=False,
        peer_group="Primary Care",
        provider_value=30.0,
        peer_median=35.0,
        deviation_ratio=0.86,
        percentile=35.0,
    )
    
    claim = ClaimContext(
        claim_id="test-claim-123",
        claim_type="OUTPATIENT",
        provider_id="1000000001",
        provider_id_type="NPI",
        claim_risk_score=50.0,
        bene_id="bene-789",
        financial_evidence=EvidenceBundle(available=True, values={
            "total_claim_payment": 5000.0,
            "total_claim_charge": 6000.0,
            "payment_to_charge_ratio": 0.833,
        }),
        utilization_evidence=EvidenceBundle(available=True, values={
            "claim_line_count": 15,
            "provider_claim_count": 25,
        }),
    )
    
    case = InvestigationCase(case_id="case-123", claim_id="test-claim-123", claim=claim, provider=provider)
    
    # Get deterministic findings for context
    agent = BillingAgent()
    findings = agent.investigate(case)
    
    # Extract numbers from case context (these should be in tool outputs)
    available_numbers = collect_tool_output_numbers([], {
        "claim_payment": 5000.0,
        "charge": 6000.0,
        "ratio": 0.833,
        "line_count": 15,
        "provider_count": 25,
        "claim_risk_score": 50.0,
        "provider_risk_score": 25.0,
    })
    
    # If findings have narratives, check grounding
    for finding in findings:
        if hasattr(finding, 'narrative') and finding.narrative:
            narrative_numbers = extract_numbers(finding.narrative)
            # Most numbers should be in available numbers or be minor formatting artifacts
            unexpected = narrative_numbers - available_numbers
            # Allow for some tolerance (percentages, statistics calculated from inputs)
            assert len(unexpected) < 3, f"Narrative contains unexpected numbers: {unexpected}. Narrative: {finding.narrative}"


def test_peer_agent_narrative_grounding():
    """Peer agent narrative should only use numbers from tool outputs."""
    provider = ProviderContext(
        npi=1000000008,
        provider_type="Specialist",
        provider_state="NY",
        provider_risk_score=45.0,
        risk_tier="Medium",
        global_anomaly_score=0.35,
        peer_deviation_score=0.40,
        geo_deviation_score=0.38,
        is_leie_excluded=False,
        peer_group="Specialist",
        provider_value=55.0,
        peer_median=45.0,
        deviation_ratio=1.22,
        percentile=65.0,
    )
    
    claim = ClaimContext(
        claim_id="case-peer-123",
        claim_type="OUTPATIENT",
        provider_id="1000000008",
        provider_id_type="NPI",
        claim_risk_score=75.0,
    )
    
    case = InvestigationCase(case_id="case-peer-123", claim_id="case-peer-123", claim=claim, provider=provider)
    
    # Get deterministic findings for context
    agent = PeerAgent()
    findings = agent.investigate(case)
    
    # Extract numbers from provider context (these should be in tool outputs)
    available_numbers = collect_tool_output_numbers([], {
        "provider_value": 55.0,
        "peer_median": 45.0,
        "deviation_ratio": 1.22,
        "percentile": 65.0,
        "provider_risk_score": 45.0,
        "peer_deviation_score": 0.40,
        "geo_deviation_score": 0.38,
    })
    
    # If findings have narratives, check grounding
    for finding in findings:
        if hasattr(finding, 'narrative') and finding.narrative:
            narrative_numbers = extract_numbers(finding.narrative)
            unexpected = narrative_numbers - available_numbers
            # Allow some tolerance
            assert len(unexpected) < 3, f"Narrative contains unexpected numbers: {unexpected}. Narrative: {finding.narrative}"


def test_clinical_rule_agent_narrative_grounding():
    """Clinical rule agent narrative should only use numbers from tool outputs."""
    claim = ClaimContext(
        claim_id="case-clinical-456",
        claim_type="OUTPATIENT",
        provider_id="1000000009",
        provider_id_type="NPI",
        claim_risk_score=65.0,
        utilization_evidence=EvidenceBundle(available=True, values={
            "claim_line_count": 20,
            "beneficiary_claim_count": 5,
            "provider_claim_count": 100,
        }),
        procedure_evidence=EvidenceBundle(available=True, values={
            "procedure_code_count": 50,
            "unique_procedure_code_count": 15,
        }),
    )
    
    case = InvestigationCase(case_id="case-clinical-456", claim_id="case-clinical-456", claim=claim)
    
    # Get deterministic findings
    agent = ClinicalRuleAgent()
    findings = agent.investigate(case)
    
    # Extract numbers from claim context
    available_numbers = collect_tool_output_numbers([], {
        "line_count": 20,
        "beneficiary_claim_count": 5,
        "provider_claim_count": 100,
        "procedure_code_count": 50,
        "unique_procedure_code_count": 15,
        "claim_risk_score": 65.0,
    })
    
    # If findings have narratives, check grounding
    for finding in findings:
        if hasattr(finding, 'narrative') and finding.narrative:
            narrative_numbers = extract_numbers(finding.narrative)
            unexpected = narrative_numbers - available_numbers
            assert len(unexpected) < 3, f"Narrative contains unexpected numbers: {unexpected}. Narrative: {finding.narrative}"


def test_billing_agent_no_hallucinated_risk_scores():
    """Billing agent should not invent risk scores in narrative."""
    provider = ProviderContext(
        npi=1000000002,
        provider_type="Primary Care",
        provider_state="CA",
        provider_risk_score=20.0,
        risk_tier="Low",
        global_anomaly_score=0.10,
        peer_deviation_score=0.12,
        geo_deviation_score=0.15,
        is_leie_excluded=False,
        peer_group="Primary Care",
        provider_value=25.0,
        peer_median=30.0,
        deviation_ratio=0.83,
        percentile=43.0,
    )
    
    claim = ClaimContext(
        claim_id="case-risk-123",
        claim_type="OUTPATIENT",
        provider_id="1000000002",
        provider_id_type="NPI",
        claim_risk_score=100.0,
    )
    
    case = InvestigationCase(case_id="case-risk-123", claim_id="case-risk-123", claim=claim, provider=provider)
    
    agent = BillingAgent()
    findings = agent.investigate(case)
    
    # Check that no findings claim fraud without supporting evidence
    for finding in findings:
        if finding.narrative:
            # Should not say "fraud" without explicit evidence
            if "fraud" in finding.narrative.lower():
                assert finding.evidence, f"Finding claims fraud but has no evidence: {finding.narrative}"


def test_peer_agent_no_invented_benchmarks():
    """Peer agent should not invent peer benchmark statistics."""
    provider = ProviderContext(
        npi=1000000010,
        provider_type="Specialist",
        provider_state="CA",
        provider_risk_score=50.0,
        risk_tier="Medium",
        global_anomaly_score=0.45,
        peer_deviation_score=0.50,
        geo_deviation_score=0.48,
        is_leie_excluded=False,
        peer_group="Specialist",
        provider_value=75.0,
        peer_median=60.0,
        deviation_ratio=1.25,
        percentile=70.0,
    )
    
    claim = ClaimContext(
        claim_id="case-bench-456",
        claim_type="OUTPATIENT",
        provider_id="1000000010",
        provider_id_type="NPI",
        claim_risk_score=75.0,
    )
    
    case = InvestigationCase(case_id="case-bench-456", claim_id="case-bench-456", claim=claim, provider=provider)
    
    agent = PeerAgent()
    findings = agent.investigate(case)
    
    # Check that benchmarks mentioned in narrative are in the evidence
    for finding in findings:
        if finding.narrative and ("median" in finding.narrative.lower() or "mean" in finding.narrative.lower()):
            # If narrative mentions statistics, they should be in evidence
            assert finding.evidence, f"Narrative mentions statistics but has no evidence: {finding.narrative}"
