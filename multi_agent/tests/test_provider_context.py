import pytest
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
from multi_agent.schemas.provider_context import ProviderContext


def test_valid_provider():
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
    )
    assert provider.npi == 1003569997
    assert provider.provider_type == "Mass Immunizer Roster Biller"
    assert provider.provider_state == "NY"


def test_optional_peer_evidence_missing():
    provider = ProviderContext(
        npi=1003806670,
        provider_type="Anesthesiology",
        provider_state="PR",
        provider_risk_score=99.08,
        risk_tier="Critical",
        global_anomaly_score=0.99,
        peer_deviation_score=None,
        geo_deviation_score=None,
        is_leie_excluded=False,
    )
    assert provider.peer_deviation_score is None
    assert provider.peer_group is None


def test_provider_risk_fields():
    provider = ProviderContext(
        npi=1003056227,
        provider_type="Certified Registered Nurse Anesthetist (CRNA)",
        provider_state="MN",
        provider_risk_score=98.96,
        risk_tier="Critical",
        global_anomaly_score=0.9846,
        peer_deviation_score=0.9957,
        geo_deviation_score=0.9966,
        is_leie_excluded=False,
    )
    assert provider.provider_risk_score == 98.96
    assert provider.risk_tier == "Critical"
    assert provider.global_anomaly_score == 0.9846


def test_npi_validation():
    provider = ProviderContext(npi="1003569997")
    assert provider.npi == 1003569997
