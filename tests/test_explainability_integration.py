import json

import pytest

from explainability import explain_entity
from explainability.multi_agent_adapter import normalize_investigation_output


class FakeGroqClient:
    def __init__(self, usage=None, content=None, error=None):
        self.usage = usage or {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}
        self.content = content or {
            "summary": "This claim shows elevated risk based on billing patterns and the model's top features.",
            "key_findings": [
                {"finding": "Payment anomaly", "evidence_ids": ["billing_1"]},
            ],
            "supporting_evidence": ["billing_1", "peer_1"],
            "recommended_review_actions": ["Review payment pattern."],
            "limitations": ["Model evidence was available; no claim-specific peer benchmark was supplied."],
        }
        self.error = error

    class chat:
        class completions:
            @staticmethod
            def create(*args, **kwargs):
                return FakeResponse()


class FakeResponse:
    class choices:
        class message:
            content = json.dumps({
                "summary": "This claim shows elevated risk based on billing patterns and the model's top features.",
                "key_findings": [{"finding": "Payment anomaly", "evidence_ids": ["billing_1"]}],
                "supporting_evidence": ["billing_1", "peer_1"],
                "recommended_review_actions": ["Review payment pattern."],
                "limitations": ["Model evidence was available; no claim-specific peer benchmark was supplied."],
            })

    usage = {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}


class FakeInvestigationResult:
    def __init__(self):
        self.case_id = "case-123"
        self.claim_id = "CLM-123"
        self.claim_type = "OUTPATIENT"
        self.provider_id = "1234567890"
        self.final_risk_level = "HIGH"
        self.final_risk_priority = 80
        self.investigation_risk_score = 72
        self.investigation_priority = "HIGH"
        self.agent_errors = {}
        self.findings = []
        self.summary = {"total_findings": 1, "billing_finding_count": 1, "peer_finding_count": 0, "clinical_rule_finding_count": 0}
        self.explanation = "The case shows elevated payment pattern risk."


@pytest.fixture
def fake_investigation_result():
    return FakeInvestigationResult()


def test_normalize_investigation_output_contract(fake_investigation_result):
    normalized = normalize_investigation_output(fake_investigation_result)

    assert normalized["status"] == "READY"
    assert "findings" in normalized
    assert "peer_comparison" in normalized
    assert "recommendations" in normalized
    assert "narrative" in normalized


def test_explain_entity_claim_ready_uses_structured_generation(monkeypatch, fake_investigation_result):
    from explainability.genai_explainer import StructuredGroqExplainer

    captured = {}

    def fake_generate(self, payload):
        captured.update(payload)
        return {
            "status": "READY",
            "model": "llama-3.3-70b-versatile",
            "summary": "This claim shows elevated risk based on the model and investigative evidence.",
            "key_reasons": ["High payment pattern.", "Abnormal service intensity."],
            "supporting_evidence": ["billing pattern"],
            "recommended_action": "Review with the payment team.",
            "input_tokens": 100,
            "output_tokens": 50,
            "total_tokens": 150,
        }

    monkeypatch.setattr(StructuredGroqExplainer, "generate", fake_generate)

    result = explain_entity(
        entity_type="CLAIM",
        entity_id="CLM-123",
        entity_data={"claim_type": "OUTPATIENT"},
        claim_type="OUTPATIENT",
        investigation_output=fake_investigation_result,
        groq_explainer=StructuredGroqExplainer(api_key="x")
    )

    assert result["entity_type"] == "CLAIM"
    assert result["genai"]["status"] == "READY"
    assert result["genai"]["total_tokens"] == 150


def test_explain_entity_claim_blocked_shap_is_not_fabricated():
    result = explain_entity(
        entity_type="CLAIM",
        entity_id="CLM-999",
        entity_data={"claim_type": "CARRIER"},
        claim_type="CARRIER",
        investigation_output=None,
    )

    assert result["shap"]["status"] == "BLOCKED_MISSING_FEATURE_ARTIFACT"
    assert result["genai"]["status"] in {"NOT_AVAILABLE", "UNAVAILABLE"}
    assert "reason" in result["shap"]


def test_explain_entity_provider_ready_uses_provider_shap(monkeypatch):
    from explainability.provider_explainer import ProviderExplainer

    monkeypatch.setattr(ProviderExplainer, "explain_provider", lambda self, provider_id, risk_score, raw_provider: {
        "status": "success",
        "provider_id": provider_id,
        "risk_score": risk_score,
        "top_features": [{"feature": "Payment per Service", "shap_value": 0.25, "value": 125.0, "rank": 1}],
    })

    result = explain_entity(
        entity_type="PROVIDER",
        entity_id="1234567890",
        entity_data={
            "Provider_Type": "HOSPITAL",
            "Payment_per_Service": 125.0,
            "Charge_per_Service": 110.0,
        },
        risk_score=0.76,
        investigation_output=None,
    )

    assert result["entity_type"] == "PROVIDER"
    assert result["shap"]["status"] == "READY"
    assert result["risk"]["score"] == 0.76


def test_missing_multi_agent_output_sets_investigation_not_available():
    result = explain_entity(
        entity_type="CLAIM",
        entity_id="CLM-100",
        entity_data={"claim_type": "OUTPATIENT"},
        claim_type="OUTPATIENT",
        investigation_output=None,
        groq_explainer=None,
    )

    assert result["investigation"]["status"] == "NOT_AVAILABLE"


def test_groq_failure_reports_unavailable(monkeypatch):
    from explainability.genai_explainer import StructuredGroqExplainer

    class FailingExplainer:
        def __init__(self, *args, **kwargs):
            pass

        def generate(self, payload):
            raise RuntimeError("Groq failure")

    result = explain_entity(
        entity_type="CLAIM",
        entity_id="CLM-200",
        entity_data={"claim_type": "OUTPATIENT"},
        claim_type="OUTPATIENT",
        investigation_output=None,
        groq_explainer=FailingExplainer(),
    )

    assert result["genai"]["status"] in {"UNAVAILABLE", "ERROR"}
