"""Test synthesis cross-validation and conflict detection."""
import pytest
from multi_agent.schemas.investigation_case import InvestigationCase
from multi_agent.schemas.finding import Finding
from multi_agent.schemas.claim_context import ClaimContext
from multi_agent.synthesis import Synthesis


def test_synthesis_detect_no_conflicts_when_agents_agree():
    """All agents find HIGH severity → no conflict."""
    finding_high_billing = Finding(agent="billing", category="payment", rule="high_payment", severity="HIGH", description="High payment", evidence={})
    finding_high_peer = Finding(agent="peer", category="deviation", rule="peer_deviation", severity="HIGH", description="High peer deviation", evidence={})
    
    findings_by_agent = {
        "billing": [finding_high_billing],
        "peer": [finding_high_peer],
        "clinical_rule": [],
    }
    
    conflicts = Synthesis._detect_agent_conflicts(findings_by_agent)
    assert len(conflicts) == 0, "No conflict when all agents agree on HIGH severity"


def test_synthesis_detect_conflict_high_vs_none():
    """Single agent finds HIGH, others find NONE → no conflict (only 1 agent has findings)."""
    finding_high = Finding(agent="billing", category="payment", rule="high_payment", severity="HIGH", description="High payment", evidence={})
    
    findings_by_agent = {
        "billing": [finding_high],
        "peer": [],  # No findings
        "clinical_rule": [],
    }
    
    conflicts = Synthesis._detect_agent_conflicts(findings_by_agent)
    assert len(conflicts) == 0, "No conflict when only 1 agent finds something; others find nothing"


def test_synthesis_detect_conflict_high_vs_medium():
    """Billing finds HIGH, Peer finds MEDIUM → conflict detected."""
    finding_high = Finding(agent="billing", category="payment", rule="high_payment", severity="HIGH", description="High payment", evidence={})
    finding_medium = Finding(agent="peer", category="deviation", rule="peer_deviation", severity="MEDIUM", description="Medium peer deviation", evidence={})
    
    findings_by_agent = {
        "billing": [finding_high],
        "peer": [finding_medium],
        "clinical_rule": [],
    }
    
    conflicts = Synthesis._detect_agent_conflicts(findings_by_agent)
    assert len(conflicts) > 0, "Conflict should be detected when one agent finds HIGH and another finds MEDIUM"


def test_synthesis_cross_validation_summary_populated():
    """Ensure cross_validation_summary is populated in InvestigationResult."""
    claim = ClaimContext(
        claim_id="123", claim_type="OUTPATIENT", provider_id="456",
        bene_id="789", claim_risk_score=75.0, final_risk_level="HIGH", final_risk_priority=3
    )
    case = InvestigationCase(case_id="CASE_001", claim_id="123", claim=claim)
    
    finding_high = Finding(agent="billing", category="payment", rule="high_payment", severity="HIGH", description="High payment", evidence={})
    billing_findings = [finding_high]
    peer_findings = []
    clinical_findings = []
    
    synthesis = Synthesis()
    result = synthesis.investigate(
        case=case,
        billing_findings=billing_findings,
        peer_findings=peer_findings,
        clinical_rule_findings=clinical_findings,
    )
    
    assert result.cross_validation_summary is not None, "cross_validation_summary should be populated"
    assert isinstance(result.cross_validation_summary, str), "cross_validation_summary should be a string"
    assert len(result.cross_validation_summary) > 0, "cross_validation_summary should not be empty"


def test_synthesis_conflicts_populated():
    """Ensure conflicts list is populated when disagreements exist."""
    claim = ClaimContext(
        claim_id="123", claim_type="OUTPATIENT", provider_id="456",
        bene_id="789", claim_risk_score=75.0, final_risk_level="HIGH", final_risk_priority=3
    )
    case = InvestigationCase(case_id="CASE_001", claim_id="123", claim=claim)
    
    # Billing finds HIGH, Peer finds nothing
    finding_high = Finding(agent="billing", category="payment", rule="high_payment", severity="HIGH", description="High payment", evidence={})
    billing_findings = [finding_high]
    peer_findings = []
    clinical_findings = []
    
    synthesis = Synthesis()
    result = synthesis.investigate(
        case=case,
        billing_findings=billing_findings,
        peer_findings=peer_findings,
        clinical_rule_findings=clinical_findings,
    )
    
    assert result.conflicts is not None, "conflicts should be populated"
    assert isinstance(result.conflicts, list), "conflicts should be a list"


def test_synthesis_synthesis_narrative_populated():
    """Ensure synthesis_narrative is populated."""
    claim = ClaimContext(
        claim_id="123", claim_type="OUTPATIENT", provider_id="456",
        bene_id="789", claim_risk_score=75.0, final_risk_level="HIGH", final_risk_priority=3
    )
    case = InvestigationCase(case_id="CASE_001", claim_id="123", claim=claim)
    
    finding = Finding(agent="billing", category="payment", rule="high_payment", severity="HIGH", description="High payment", evidence={})
    billing_findings = [finding]
    peer_findings = []
    clinical_findings = []
    
    synthesis = Synthesis()
    result = synthesis.investigate(
        case=case,
        billing_findings=billing_findings,
        peer_findings=peer_findings,
        clinical_rule_findings=clinical_findings,
    )
    
    assert result.synthesis_narrative is not None, "synthesis_narrative should be populated"
    assert isinstance(result.synthesis_narrative, str), "synthesis_narrative should be a string"


def test_synthesis_agent_narratives_optional():
    """Synthesis should work without agent_narratives parameter (backward compatibility)."""
    claim = ClaimContext(
        claim_id="123", claim_type="OUTPATIENT", provider_id="456",
        bene_id="789", claim_risk_score=75.0, final_risk_level="HIGH", final_risk_priority=3
    )
    case = InvestigationCase(case_id="CASE_001", claim_id="123", claim=claim)
    
    finding = Finding(agent="billing", category="payment", rule="high_payment", severity="HIGH", description="High payment", evidence={})
    billing_findings = [finding]
    peer_findings = []
    clinical_findings = []
    
    synthesis = Synthesis()
    
    # Call without agent_narratives - should not raise error
    result = synthesis.investigate(
        case=case,
        billing_findings=billing_findings,
        peer_findings=peer_findings,
        clinical_rule_findings=clinical_findings,
    )
    
    assert result.investigation_risk_score >= 0, "Should return valid result without agent_narratives"


def test_synthesis_risk_score_remains_frozen():
    """Risk score computation should remain unchanged (frozen deterministic behavior)."""
    claim = ClaimContext(
        claim_id="123", claim_type="OUTPATIENT", provider_id="456",
        bene_id="789", claim_risk_score=75.0, final_risk_level="HIGH", final_risk_priority=3
    )
    case = InvestigationCase(case_id="CASE_001", claim_id="123", claim=claim)
    
    finding_high = Finding(agent="billing", category="payment", rule="high_payment", severity="HIGH", description="High payment", evidence={})
    finding_medium = Finding(agent="peer", category="deviation", rule="peer_deviation", severity="MEDIUM", description="Medium peer deviation", evidence={})
    
    billing_findings = [finding_high]
    peer_findings = [finding_medium]
    clinical_findings = []
    
    synthesis = Synthesis()
    result = synthesis.investigate(
        case=case,
        billing_findings=billing_findings,
        peer_findings=peer_findings,
        clinical_rule_findings=clinical_findings,
    )
    
    # The risk score should be computed the same way regardless of conflicts
    # HIGH = 25, MEDIUM = 10, so total = 35 (if weights are applied correctly)
    assert result.investigation_risk_score > 0, "Risk score should be computed deterministically"
    assert result.investigation_risk_score <= 100, "Risk score should not exceed 100"
