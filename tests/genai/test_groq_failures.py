import json

import pytest

from multi_agent.services.explanation_service import InvestigationExplanationService


class DummyResult:
    def __init__(self):
        self.case_id = "CASE-FAIL-1"
        self.claim_id = "CLAIM-FAIL-1"
        self.provider_id = "PRV-FAIL-1"
        self.claim_type = "OUTPATIENT"
        self.final_risk_level = "HIGH"
        self.final_risk_priority = "P1"
        self.investigation_risk_score = 88.0
        self.investigation_priority = "HIGH"
        self.agent_errors = {"billing": "ERROR"}
        self.findings = [type("Finding", (), {"agent": "peer", "category": "utilization", "rule": "R02", "severity": "HIGH", "description": "Peer utilization anomaly", "evidence": {"evidence_id": "EV-001", "provider_value": 20000, "peer_median": 5000, "deviation_ratio": 4.0}})()]


class FakeGroqClient:
    def __init__(self, *, exception=None, response_text="{}"):
        self.exception = exception
        self.response_text = response_text
        self.calls = []

    class Chat:
        def __init__(self, client):
            self.client = client
            self.completions = self.Completions(client)

        class Completions:
            def __init__(self, client):
                self.client = client

            def create(self, **kwargs):
                self.client.calls.append(kwargs)
                if self.client.exception is not None:
                    raise self.client.exception
                return type("Resp", (), {"choices": [type("Choice", (), {"message": type("Message", (), {"content": self.client.response_text})()})()]})()

    @property
    def chat(self):
        return self.Chat(self)


@pytest.mark.parametrize(
    "exception, expected_status",
    [
        (TimeoutError("timed out"), "fallback"),
        (ConnectionError("connection failed"), "fallback"),
        (RuntimeError("401 auth error"), "fallback"),
        (RuntimeError("429 rate limited"), "fallback"),
        (RuntimeError("500 server error"), "fallback"),
    ],
)
def test_groq_failures_are_classified_and_fallback_used(exception, expected_status):
    service = InvestigationExplanationService(
        api_key="test-key",
        model="llama-3.3-70b-versatile",
        client=FakeGroqClient(exception=exception),
        enabled=True,
    )
    explanation = service.generate_explanation(DummyResult())
    assert explanation.status == expected_status
    assert explanation.is_fallback is True
    assert explanation.error


def test_malformed_or_empty_response_uses_fallback():
    service = InvestigationExplanationService(
        api_key="test-key",
        model="llama-3.3-70b-versatile",
        client=FakeGroqClient(response_text="not-json"),
        enabled=True,
    )
    explanation = service.generate_explanation(DummyResult())
    assert explanation.status in {"fallback", "unavailable"}
    assert explanation.error


def test_schema_validation_failure_uses_fallback():
    invalid = {
        "summary": "The provider committed fraud.",
        "risk_interpretation": {"category": "LOW", "priority": "P3"},
        "key_findings": [{"finding": "Fraud confirmation", "evidence_ids": ["EV-001"]}],
    }
    service = InvestigationExplanationService(
        api_key="test-key",
        model="llama-3.3-70b-versatile",
        client=FakeGroqClient(response_text=json.dumps(invalid)),
        enabled=True,
    )
    explanation = service.generate_explanation(DummyResult())
    assert explanation.status in {"fallback", "unavailable"}


def test_deterministic_case_is_preserved_after_failure():
    service = InvestigationExplanationService(
        api_key="test-key",
        model="llama-3.3-70b-versatile",
        client=FakeGroqClient(exception=TimeoutError("timed out")),
        enabled=True,
    )
    result = DummyResult()
    explanation = service.generate_explanation(result)
    assert explanation.status == "fallback"
    assert result.final_risk_level == "HIGH"
    assert result.investigation_risk_score == 88.0
    assert result.agent_errors["billing"] == "ERROR"


def test_retries_are_bounded():
    service = InvestigationExplanationService(
        api_key="test-key",
        model="llama-3.3-70b-versatile",
        client=FakeGroqClient(exception=TimeoutError("timed out")),
        enabled=True,
        max_retries=2,
    )
    explanation = service.generate_explanation(DummyResult())
    assert explanation.status == "fallback"
    assert explanation.is_fallback is True
