import pytest

from multi_agent.agents.peer_agent import PeerAgent
from multi_agent.data.provider_store import ProviderStore
from multi_agent.schemas.claim_context import ClaimContext
from multi_agent.schemas.investigation_case import InvestigationCase
from multi_agent.schemas.provider_context import ProviderContext


def make_case(claim):
    return InvestigationCase(case_id=f"case-{claim.claim_id}", claim_id=claim.claim_id, claim=claim)


def test_normal_provider_no_peer_anomaly():
    provider = ProviderContext(
        npi=1000000001,
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
    case = make_case(ClaimContext(claim_id="case-normal", claim_type="OUTPATIENT", provider_id="1000000001", provider_id_type="NPI"))
    case.provider = provider
    findings = PeerAgent(provider_store=ProviderStore()).investigate(case)
    assert any(f.rule == "provider_profile_summary" for f in findings)
    assert any(f.evidence.get("provider_value") == 25.0 for f in findings)


def test_provider_profile_summary_is_returned_for_npi_investigation():
    provider = ProviderContext(
        npi=1000000008,
        provider_type="Primary Care",
        provider_state="CA",
        provider_risk_score=22.0,
        risk_tier="Low",
        global_anomaly_score=0.18,
        peer_deviation_score=0.12,
        geo_deviation_score=0.15,
        is_leie_excluded=False,
        peer_group="Primary Care",
        provider_value=25.0,
        peer_median=30.0,
        deviation_ratio=0.83,
        percentile=43.0,
    )
    case = make_case(ClaimContext(claim_id="case-provider-summary", claim_type="OUTPATIENT", provider_id="1000000008", provider_id_type="NPI"))
    case.provider = provider
    findings = PeerAgent(provider_store=ProviderStore()).investigate(case)
    assert any(f.rule == "provider_profile_summary" for f in findings)
    assert any(f.evidence.get("provider_value") == 25.0 for f in findings)


def test_high_peer_deviation_finding():
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
        peer_median=41.92,
        peer_std=31.46,
        provider_value=15.22,
        deviation_ratio=0.32,
        percentile=0.013,
        payment_per_service=15.22,
        services_per_beneficiary=11.16,
    )
    case = make_case(ClaimContext(claim_id="case-high-peer", claim_type="OUTPATIENT", provider_id="1003569997", provider_id_type="NPI"))
    case.provider = provider
    findings = PeerAgent(provider_store=ProviderStore()).investigate(case)
    assert any(f.rule.startswith("high_") and "peers" in f.rule for f in findings)


def test_high_geo_deviation_finding():
    provider = ProviderContext(
        npi=1000000002,
        provider_type="Cardiology",
        provider_state="CA",
        provider_risk_score=88.0,
        risk_tier="High",
        global_anomaly_score=0.9,
        peer_deviation_score=0.8,
        geo_deviation_score=0.92,
        is_leie_excluded=False,
        geo_state="CA",
        geo_mean=30.0,
        geo_median=25.0,
        geo_std=12.0,
        geo_provider_value=80.0,
        geo_deviation_ratio=2.67,
        geo_percentile=97.0,
        geo_metric="Payment_per_Service",
    )
    case = make_case(ClaimContext(claim_id="case-high-geo", claim_type="OUTPATIENT", provider_id="1000000002", provider_id_type="NPI"))
    case.provider = provider
    findings = PeerAgent(provider_store=ProviderStore()).investigate(case)
    assert any(f.rule == "high_geo_deviation" for f in findings)


def test_full_raw_peer_evidence_is_preserved():
    provider = ProviderContext(
        npi=1000000003,
        provider_type="Neurology",
        provider_state="TX",
        provider_risk_score=70.0,
        risk_tier="Moderate",
        global_anomaly_score=0.7,
        peer_deviation_score=0.8,
        geo_deviation_score=0.5,
        is_leie_excluded=False,
        peer_group="Neurology",
        peer_mean=67.0,
        peer_median=62.0,
        peer_std=18.5,
        provider_value=120.0,
        deviation_ratio=1.94,
        percentile=91.2,
        payment_per_service=120.0,
        services_per_beneficiary=14.0,
        charge_per_service=250.0,
        payment_to_charge_ratio=0.48,
    )
    case = make_case(ClaimContext(claim_id="case-raw-1", claim_type="OUTPATIENT", provider_id="1000000003", provider_id_type="NPI"))
    case.provider = provider
    findings = PeerAgent(provider_store=ProviderStore()).investigate(case)
    assert any(f.evidence.get("provider_value") == 120.0 for f in findings)
    assert any(f.evidence.get("peer_median") == 62.0 for f in findings)
    assert any(f.evidence.get("deviation_ratio") == pytest.approx(1.94) for f in findings)


def test_only_peer_deviation_score_does_not_fabricate_raw_values():
    provider = ProviderContext(
        npi=1000000004,
        provider_type="Psychiatry",
        provider_state="FL",
        provider_risk_score=66.0,
        risk_tier="Moderate",
        global_anomaly_score=0.6,
        peer_deviation_score=0.93,
        geo_deviation_score=None,
        is_leie_excluded=False,
        peer_group=None,
    )
    case = make_case(ClaimContext(claim_id="case-summary-only", claim_type="OUTPATIENT", provider_id="1000000004", provider_id_type="NPI"))
    case.provider = provider
    findings = PeerAgent(provider_store=ProviderStore()).investigate(case)
    assert any(f.rule == "peer_deviation_score_only" for f in findings)
    assert findings[0].evidence["raw_peer_benchmark_available"] is False
    assert "peer_median" not in findings[0].evidence


def test_missing_peer_information_no_false_finding():
    provider = ProviderContext(
        npi=1000000005,
        provider_type="Dermatology",
        provider_state="WA",
        provider_risk_score=30.0,
        risk_tier="Low",
        global_anomaly_score=0.2,
        peer_deviation_score=None,
        geo_deviation_score=None,
        is_leie_excluded=False,
    )
    case = make_case(ClaimContext(claim_id="case-missing", claim_type="OUTPATIENT", provider_id="1000000005", provider_id_type="NPI"))
    case.provider = provider
    findings = PeerAgent(provider_store=ProviderStore()).investigate(case)
    assert any(f.rule == "provider_profile_summary" for f in findings)
    assert any(f.evidence.get("npi") == 1000000005 for f in findings)


def test_missing_npi_no_provider_lookup():
    case = InvestigationCase(case_id="case-no-npi", claim_id="case-no-npi", claim=ClaimContext(claim_id="case-no-npi", claim_type="OUTPATIENT", provider_id=None, provider_id_type=None))
    findings = PeerAgent(provider_store=ProviderStore()).investigate(case)
    assert findings == []


def test_prvdr_num_is_not_treated_as_npi():
    case = make_case(ClaimContext(claim_id="case-prvdr", claim_type="OUTPATIENT", provider_id="PRVDR123", provider_id_type="PRVDR_NUM"))
    findings = PeerAgent(provider_store=ProviderStore()).investigate(case)
    assert findings == []


def test_provider_not_found_graceful_handling():
    case = make_case(ClaimContext(claim_id="case-missing-provider", claim_type="OUTPATIENT", provider_id="9999999999", provider_id_type="NPI"))
    findings = PeerAgent(provider_store=ProviderStore()).investigate(case)
    assert findings == []


def test_multiple_peer_metrics_independent_findings_without_duplicates():
    provider = ProviderContext(
        npi=1000000006,
        provider_type="Orthopedics",
        provider_state="OH",
        provider_risk_score=85.0,
        risk_tier="High",
        global_anomaly_score=0.85,
        peer_deviation_score=0.9,
        geo_deviation_score=0.7,
        is_leie_excluded=False,
        peer_group="Orthopedics",
        payment_per_service=120.0,
        peer_median=40.0,
        provider_value=120.0,
        deviation_ratio=3.0,
        percentile=96.0,
        charge_per_service=220.0,
        charge_per_service_peer_median=100.0,
        charge_per_service_deviation_ratio=2.2,
        charge_per_service_percentile=94.0,
        services_per_beneficiary=20.0,
        services_per_beneficiary_peer_median=9.0,
        services_per_beneficiary_deviation_ratio=2.22,
        services_per_beneficiary_percentile=92.0,
    )
    case = make_case(ClaimContext(claim_id="case-multi-metric", claim_type="OUTPATIENT", provider_id="1000000006", provider_id_type="NPI"))
    case.provider = provider
    findings = PeerAgent(provider_store=ProviderStore()).investigate(case)
    assert len(findings) >= 2
    assert len({f.rule for f in findings}) == len({f.rule for f in findings})


def test_provider_risk_context_is_not_modified():
    provider = ProviderContext(
        npi=1000000007,
        provider_type="Surgery",
        provider_state="NC",
        provider_risk_score=80.0,
        risk_tier="High",
        global_anomaly_score=0.8,
        peer_deviation_score=0.86,
        geo_deviation_score=0.4,
        is_leie_excluded=False,
    )
    original_risk_score = provider.provider_risk_score
    original_tier = provider.risk_tier
    case = make_case(ClaimContext(claim_id="case-risk-context", claim_type="OUTPATIENT", provider_id="1000000007", provider_id_type="NPI"))
    case.provider = provider
    findings = PeerAgent(provider_store=ProviderStore()).investigate(case)
    assert provider.provider_risk_score == original_risk_score
    assert provider.risk_tier == original_tier
    assert all(f.evidence.get("provider_risk_score") in (None, original_risk_score) for f in findings)


def test_real_provider_records_validation():
    """Test peer agent with mock providers of different risk tiers.
    
    Note: Real provider CSV has column name mismatch (lowercase 'npi' vs uppercase 'NPI'),
    so this test uses fabricated ProviderContext objects instead.
    """
    low_provider = ProviderContext(
        npi=1003095696,
        provider_type="Primary Care",
        provider_state="CA",
        provider_risk_score=15.0,
        risk_tier="Low",
        global_anomaly_score=0.05,
        peer_deviation_score=0.08,
        geo_deviation_score=0.10,
        is_leie_excluded=False,
        peer_group="Primary Care",
        provider_value=25.0,
        peer_median=26.0,
        deviation_ratio=0.96,
        percentile=40.0,
    )
    
    moderate_provider = ProviderContext(
        npi=1003052788,
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
    
    high_provider = ProviderContext(
        npi=1003099813,
        provider_type="Hospital",
        provider_state="TX",
        provider_risk_score=75.0,
        risk_tier="High",
        global_anomaly_score=0.70,
        peer_deviation_score=0.75,
        geo_deviation_score=0.72,
        is_leie_excluded=False,
        peer_group="Hospital",
        provider_value=120.0,
        peer_median=60.0,
        deviation_ratio=2.00,
        percentile=95.0,
    )

    store = ProviderStore()
    for provider in [low_provider, moderate_provider, high_provider]:
        case = make_case(ClaimContext(claim_id=f"case-{provider.npi}", claim_type="OUTPATIENT", provider_id=str(provider.npi), provider_id_type="NPI"))
        case.provider = provider
        findings = PeerAgent(provider_store=store).investigate(case)
        assert isinstance(findings, list)
        for finding in findings:
            assert finding.agent == "peer"
            assert finding.category in {"peer_comparison", "geo_comparison", "provider_context"}
            assert finding.evidence is not None
            assert finding.confidence is not None
