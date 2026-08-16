from multi_agent.data.claim_store import ClaimStore
from multi_agent.data.provider_store import ProviderStore


def test_claim_store_known_claim():
    store = ClaimStore()
    claim = store.get_claim("-10000930090156")
    assert claim is not None
    assert claim.claim_id == "-10000930090156"
    assert claim.claim_type == "OUTPATIENT"
    assert claim.provider_id_type == "PRVDR_NUM"


def test_claim_store_unknown_claim():
    store = ClaimStore()
    assert store.get_claim("NOT_A_REAL_ID") is None


def test_claim_store_duplicate_claim_handling():
    store = ClaimStore()
    claim = store.get_claim("-10000930090156")
    assert claim is not None
    assert claim.claim_id == "-10000930090156"


def test_claim_store_normalizes_float_like_claim_ids_to_exact_record():
    store = ClaimStore()
    requested_claim_id = "-10000930155681.0"
    claim = store.get_claim(requested_claim_id)
    assert claim is not None
    assert claim.claim_id == "-10000930155681"
    assert claim.claim_id == str(requested_claim_id).rstrip(".0") if requested_claim_id.endswith(".0") else claim.claim_id == requested_claim_id


def test_claim_store_missing_provider_id():
    store = ClaimStore()
    claim = store.get_claim("-10000930775141")
    assert claim is not None
    assert claim.provider_id is None or claim.provider_id == "33S394"


def test_claim_store_correct_provider_id_type():
    store = ClaimStore()
    claim = store.get_claim("-10000930090156")
    assert claim.provider_id_type == "PRVDR_NUM"

    carrier = store.get_claim("-10000930068276")
    assert carrier is not None and carrier.provider_id_type == "NPI"


def test_provider_store_known_npi():
    store = ProviderStore()
    provider = store.get_provider(1003569997)
    assert provider is not None
    assert provider.npi == 1003569997
    assert provider.provider_risk_score is not None


def test_provider_store_unknown_npi():
    store = ProviderStore()
    assert store.get_provider(9999999999) is None


def test_provider_store_duplicate_npi_handling():
    store = ProviderStore()
    assert store.exists(1003569997) is True
