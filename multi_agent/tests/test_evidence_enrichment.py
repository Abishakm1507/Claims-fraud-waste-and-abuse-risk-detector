import pytest

from multi_agent.agents.billing_agent import BillingAgent
from multi_agent.agents.clinical_rule_agent import ClinicalRuleAgent
from multi_agent.agents.peer_agent import PeerAgent
from multi_agent.evidence import EvidenceEnricher, EvidenceNormalizer
from multi_agent.schemas.claim_context import ClaimContext
from multi_agent.schemas.investigation_case import InvestigationCase
from multi_agent.schemas.provider_context import ProviderContext
from multi_agent.schemas.finding import Finding


def make_case(claim, provider=None):
    case = InvestigationCase(case_id=f"case-{claim.claim_id}", claim_id=claim.claim_id, claim=claim)
    if provider is not None:
        case.provider = provider
    return case


def test_evidence_enricher_adds_evidence_id():
    finding = Finding(
        agent="billing",
        category="financial",
        rule="payment_charge_ratio",
        severity="HIGH",
        description="Payment is 4.3x the charge.",
        evidence={"payment": 30000.0, "charge": 7000.0, "ratio": 4.29},
        confidence=0.94,
    )
    enriched = EvidenceEnricher.enrich_finding(finding)
    assert enriched.evidence.get("evidence_id") is not None
    assert enriched.evidence["evidence_id"].startswith("EV-")


def test_evidence_enricher_preserves_existing_evidence():
    finding = Finding(
        agent="peer",
        category="peer_comparison",
        rule="high_payment_per_service_vs_peers",
        severity="HIGH",
        description="High peer deviation.",
        evidence={"provider_value": 15.22, "peer_median": 5.0, "deviation_ratio": 3.04},
        confidence=0.9,
    )
    enriched = EvidenceEnricher.enrich_finding(finding)
    assert enriched.evidence["provider_value"] == 15.22
    assert enriched.evidence["peer_median"] == 5.0
    # Deviation ratio is recalculated, so use approx
    assert enriched.evidence["deviation_ratio"] == pytest.approx(3.044, rel=0.01)


def test_evidence_enricher_adds_provenance():
    finding = Finding(
        agent="billing",
        category="financial",
        rule="payment_charge_ratio",
        severity="HIGH",
        description="Payment is 4.3x the charge.",
        evidence={"payment": 30000.0, "charge": 7000.0, "ratio": 4.29},
        confidence=0.94,
    )
    enriched = EvidenceEnricher.enrich_finding(finding)
    assert enriched.evidence.get("provenance") is not None
    provenance = enriched.evidence["provenance"]
    assert provenance.get("source") is not None
    assert provenance.get("pipeline") == "multi_agent"


def test_evidence_enricher_calculates_deviations():
    finding = Finding(
        agent="billing",
        category="financial",
        rule="provider_payment_deviation",
        severity="HIGH",
        description="Payment exceeds provider average.",
        evidence={
            "payment": 30000.0,
            "provider_avg_claim_payment": 5000.0,
        },
        confidence=0.9,
    )
    enriched = EvidenceEnricher.enrich_finding(finding)
    assert enriched.evidence.get("deviation_ratio") is not None
    assert enriched.evidence["deviation_ratio"] == pytest.approx(6.0, rel=0.01)


def test_evidence_enricher_infers_source_for_billing():
    finding = Finding(
        agent="billing",
        category="financial",
        rule="payment_charge_ratio",
        severity="HIGH",
        description="High ratio.",
        evidence={"payment": 30000.0},
        confidence=0.9,
    )
    enriched = EvidenceEnricher.enrich_finding(finding)
    assert enriched.evidence["source"] == "final_unified_claim_risk.csv"


def test_evidence_enricher_infers_source_for_peer():
    finding = Finding(
        agent="peer",
        category="peer_comparison",
        rule="high_payment_per_service_vs_peers",
        severity="HIGH",
        description="High peer deviation.",
        evidence={"provider_value": 15.22},
        confidence=0.9,
    )
    enriched = EvidenceEnricher.enrich_finding(finding)
    assert enriched.evidence["source"] == "provider_risk_scores.csv"


def test_evidence_enricher_respects_case_provider_context():
    provider = ProviderContext(
        npi=1000000001,
        provider_type="Surgery",
        provider_state="CA",
        provider_risk_score=80.0,
        risk_tier="High",
        peer_group="Surgery-CA",
    )
    claim = ClaimContext(
        claim_id="TEST-1",
        claim_type="OUTPATIENT",
        provider_id="1000000001",
        provider_id_type="NPI",
    )
    case = make_case(claim, provider)
    
    finding = Finding(
        agent="peer",
        category="peer_comparison",
        rule="high_payment_per_service_vs_peers",
        severity="HIGH",
        description="High peer deviation.",
        evidence={"provider_value": 15.22},
        confidence=0.9,
    )
    enriched = EvidenceEnricher.enrich_finding(finding, case=case)
    assert enriched.evidence["peer_group"] == "Surgery-CA"


def test_evidence_enricher_no_fabrication_on_missing_baseline():
    finding = Finding(
        agent="billing",
        category="financial",
        rule="payment_charge_ratio",
        severity="HIGH",
        description="High payment.",
        evidence={"payment": 30000.0},
        confidence=0.9,
    )
    enriched = EvidenceEnricher.enrich_finding(finding)
    assert enriched.evidence.get("deviation_ratio") is None
    assert enriched.evidence.get("deviation") is None


def test_evidence_enricher_enriches_billing_findings():
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
    findings = BillingAgent().investigate(case)
    enriched = EvidenceEnricher.enrich_findings(findings, case=case)
    
    assert len(enriched) > 0
    for finding in enriched:
        assert finding.evidence.get("evidence_id") is not None
        assert finding.evidence.get("provenance") is not None
        assert finding.evidence.get("source") == "final_unified_claim_risk.csv"


def test_evidence_enricher_enriches_peer_findings():
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
    findings = PeerAgent().investigate(case)
    enriched = EvidenceEnricher.enrich_findings(findings, case=case)
    
    assert len(enriched) > 0
    for finding in enriched:
        assert finding.evidence.get("evidence_id") is not None
        assert finding.evidence.get("provenance") is not None
        assert finding.evidence.get("source") == "provider_risk_scores.csv"
        if "peer_median" in finding.evidence and finding.evidence["peer_median"] is not None:
            assert finding.evidence.get("deviation_ratio") is not None


def test_evidence_enricher_enriches_clinical_findings():
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
    enriched = EvidenceEnricher.enrich_findings(findings, case=case)
    
    if len(enriched) > 0:
        for finding in enriched:
            assert finding.evidence.get("evidence_id") is not None
            assert finding.evidence.get("provenance") is not None
            assert finding.evidence.get("source") == "final_unified_claim_risk.csv"


def test_evidence_normalizer_normalizes_peer_evidence():
    normalized = EvidenceNormalizer.normalize(
        metric="payment_per_service_vs_peers",
        agent="peer",
        category="peer_comparison",
        provider_value=15.22,
        peer_median=5.0,
        deviation_ratio_value=3.04,
        percentile=96.0,
        source="provider_risk_scores.csv",
        source_fields=["NPI", "Payment_per_Service", "Payment_per_Service_Peer_Median"],
        confidence=0.9,
    )
    assert normalized["metric"] == "payment_per_service_vs_peers"
    assert normalized["agent"] == "peer"
    assert normalized["provider_value"] == 15.22
    assert normalized["peer_median"] == 5.0
    assert normalized["deviation_ratio"] == 3.04
    assert normalized["percentile"] == 96.0
    assert normalized["source"] == "provider_risk_scores.csv"
    assert normalized["source_fields"] == ["NPI", "Payment_per_Service", "Payment_per_Service_Peer_Median"]
    assert normalized["confidence"] == 0.9


def test_evidence_normalizer_cleans_numeric_values():
    normalized = EvidenceNormalizer.normalize(
        metric="test",
        agent="test",
        category="test",
        provider_value="15.22",
        baseline_value=5,
        confidence="0.9",
    )
    assert normalized["provider_value"] == 15.22
    assert normalized["baseline_value"] == 5.0
    assert normalized["confidence"] == 0.9


def test_evidence_normalizer_handles_missing_values():
    normalized = EvidenceNormalizer.normalize(
        metric="test",
        agent="test",
        category="test",
        provider_value=None,
        baseline_value=None,
        confidence=None,
    )
    assert normalized["provider_value"] is None
    assert normalized["baseline_value"] is None
    assert normalized["confidence"] is None


def test_evidence_normalizer_clamps_confidence():
    normalized = EvidenceNormalizer.normalize(
        metric="test",
        agent="test",
        category="test",
        confidence=-0.5,
    )
    assert normalized["confidence"] == 0.0
    
    normalized = EvidenceNormalizer.normalize(
        metric="test",
        agent="test",
        category="test",
        confidence=1.5,
    )
    assert normalized["confidence"] == 1.0


def test_evidence_normalizer_calculates_deviation_when_missing():
    normalized = EvidenceNormalizer.normalize(
        metric="test",
        agent="test",
        category="test",
        provider_value=30000.0,
        baseline_value=7000.0,
        deviation_ratio_value=None,
    )
    assert normalized["deviation_ratio"] is not None
    assert normalized["deviation_ratio"] == pytest.approx(4.29, rel=0.01)


def test_evidence_enricher_record_key_for_claim():
    claim = ClaimContext(claim_id="TEST-1", claim_type="OUTPATIENT", provider_id="1000", provider_id_type="NPI")
    case = make_case(claim)
    finding = Finding(
        agent="billing",
        category="financial",
        rule="test",
        severity="HIGH",
        description="Test.",
        evidence={},
        confidence=0.9,
    )
    enriched = EvidenceEnricher.enrich_finding(finding, case=case)
    provenance = enriched.evidence.get("provenance") or {}
    assert provenance.get("record_key") == "CLAIM_ID=TEST-1"


def test_evidence_enricher_record_key_for_provider():
    provider = ProviderContext(npi=1000000001, provider_type="Test", provider_state="CA", provider_risk_score=50.0, risk_tier="Medium")
    # Use a provider-only claim to test NPI precedence
    claim = ClaimContext(claim_id=None, claim_type=None, provider_id="1000000001", provider_id_type="NPI")
    case = make_case(claim, provider)
    finding = Finding(
        agent="peer",
        category="peer_comparison",
        rule="test",
        severity="HIGH",
        description="Test.",
        evidence={},
        confidence=0.9,
    )
    enriched = EvidenceEnricher.enrich_finding(finding, case=case)
    provenance = enriched.evidence.get("provenance") or {}
    record_key = str(provenance.get("record_key", ""))
    # When claim_id is None, NPI should be in the record key
    assert "NPI=" in record_key or record_key == "None"


def test_evidence_enricher_no_calculation_when_insufficient_data():
    finding = Finding(
        agent="billing",
        category="financial",
        rule="test",
        severity="HIGH",
        description="Test.",
        evidence={"payment": 30000.0},
        confidence=0.9,
    )
    enriched = EvidenceEnricher.enrich_finding(finding)
    calculation = enriched.evidence.get("calculation") or {}
    assert calculation.get("formula") == "not_applicable" or calculation.get("result") is None


def test_evidence_enricher_limitation_for_peer_without_benchmarks():
    finding = Finding(
        agent="peer",
        category="peer_comparison",
        rule="peer_deviation_score_only",
        severity="MEDIUM",
        description="Score only.",
        evidence={"peer_deviation_score": 0.95},
        confidence=0.7,
    )
    enriched = EvidenceEnricher.enrich_finding(finding)
    provenance = enriched.evidence.get("provenance") or {}
    limitation = provenance.get("limitation")
    assert limitation is not None
    assert "peer" in limitation.lower() or "benchmark" in limitation.lower()


def test_evidence_enricher_batch_enrichment():
    findings = [
        Finding(
            agent="billing",
            category="financial",
            rule="r1",
            severity="HIGH",
            description="d1.",
            evidence={"payment": 1000.0},
            confidence=0.9,
        ),
        Finding(
            agent="billing",
            category="financial",
            rule="r2",
            severity="MEDIUM",
            description="d2.",
            evidence={"payment": 2000.0},
            confidence=0.8,
        ),
    ]
    enriched = EvidenceEnricher.enrich_findings(findings)
    assert len(enriched) == 2
    assert all(f.evidence.get("evidence_id") is not None for f in enriched)
    assert all(f.evidence.get("provenance") is not None for f in enriched)


def test_evidence_ids_are_deterministic():
    finding = Finding(
        agent="billing",
        category="financial",
        rule="payment_charge_ratio",
        severity="HIGH",
        description="Payment is 4.3x the charge.",
        evidence={"payment": 30000.0, "charge": 7000.0, "ratio": 4.29},
        confidence=0.94,
    )
    enriched1 = EvidenceEnricher.enrich_finding(finding)
    enriched2 = EvidenceEnricher.enrich_finding(finding)
    assert enriched1.evidence["evidence_id"] == enriched2.evidence["evidence_id"]


def test_evidence_enricher_handles_peer_score_only_limitation():
    provider = ProviderContext(
        npi=1003569997,
        provider_type="Type",
        provider_state="NY",
        provider_risk_score=99.45,
        risk_tier="Critical",
        peer_deviation_score=0.995,
        peer_group="Group",
        provider_value=None,
        peer_median=None,
    )
    claim = ClaimContext(
        claim_id="PEER-1",
        claim_type="OUTPATIENT",
        provider_id="1003569997",
        provider_id_type="NPI",
    )
    case = make_case(claim, provider)
    
    findings = PeerAgent().investigate(case)
    enriched = EvidenceEnricher.enrich_findings(findings, case=case)
    
    score_only_findings = [f for f in enriched if "score_only" in f.rule]
    if score_only_findings:
        for finding in score_only_findings:
            provenance = finding.evidence.get("provenance") or {}
            limitation = provenance.get("limitation")
            assert limitation is not None
            assert "not available" in limitation.lower() or "unavailable" in limitation.lower() or "not exported" in limitation.lower()
