from __future__ import annotations

import json

from multi_agent.agents.billing_agent import BillingAgent
from multi_agent.agents.clinical_rule_agent import ClinicalRuleAgent
from multi_agent.agents.peer_agent import PeerAgent
from multi_agent.schemas.claim_context import ClaimContext
from multi_agent.schemas.investigation_case import InvestigationCase
from multi_agent.schemas.provider_context import ProviderContext
from multi_agent.synthesis import Synthesis


class FakeGroqClient:
    def __init__(self, *, response_text=None, exception=None):
        self.response_text = response_text
        self.exception = exception
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
                if self.client.response_text is None:
                    return type("Resp", (), {"choices": [type("Choice", (), {"message": type("Message", (), {"content": "{}"})()})()]})()
                return type("Resp", (), {"choices": [type("Choice", (), {"message": type("Message", (), {"content": self.client.response_text})()})()]})()

    @property
    def chat(self):
        return self.Chat(self)


def make_case(claim, provider=None):
    case = InvestigationCase(case_id=f"case-{claim.claim_id}", claim_id=claim.claim_id, claim=claim)
    if provider is not None:
        case.provider = provider
    return case


def make_result(*, claim=None, findings=None, provider=None):
    claim = claim or ClaimContext(
        claim_id="CASE-1",
        claim_type="OUTPATIENT",
        provider_id="1003569997",
        provider_id_type="NPI",
        claim_risk_score=82.0,
        final_risk_level="HIGH",
        final_risk_priority=3,
        final_claim_rank=11,
    )
    case = make_case(claim, provider)
    findings = findings or []
    result = Synthesis().investigate(case, findings, findings, findings)
    return result


def test_successful_explanation_generation():
    from multi_agent.services.explanation_service import InvestigationExplanationService

    service = InvestigationExplanationService(
        api_key="test-key",
        model="openai/gpt-oss-120b",
        client=FakeGroqClient(
            response_text=json.dumps({
                "executive_summary": "Anomalies remain under review.",
                "key_findings": [{"agent": "BillingAgent", "finding": "High payment ratio", "evidence": "Evidence available"}],
                "risk_reasoning": "The claim shows strong corroborating evidence.",
                "recommended_investigation_actions": ["Review billing documentation."],
                "limitations": ["Evidence unavailable."],
            })
        ),
        enabled=True,
    )
    result = make_result()
    explanation = service.generate_explanation(result)
    assert explanation.status == "generated"
    assert explanation.executive_summary
    assert explanation.key_findings
    assert explanation.generated_by == "Groq"


def test_missing_api_key_returns_unavailable():
    from multi_agent.services.explanation_service import InvestigationExplanationService

    service = InvestigationExplanationService(api_key=None, model="openai/gpt-oss-120b", enabled=True)
    result = make_result()
    explanation = service.generate_explanation(result)
    assert explanation.status == "unavailable"
    assert explanation.error


def test_timeout_is_handled():
    from multi_agent.services.explanation_service import InvestigationExplanationService

    service = InvestigationExplanationService(
        api_key="test-key",
        model="openai/gpt-oss-120b",
        client=FakeGroqClient(exception=TimeoutError("timed out")),
        enabled=True,
    )
    explanation = service.generate_explanation(make_result())
    assert explanation.status == "fallback"
    assert explanation.is_fallback is True
    assert "timeout" in explanation.error.lower()


def test_api_failure_is_handled():
    from multi_agent.services.explanation_service import InvestigationExplanationService

    service = InvestigationExplanationService(
        api_key="test-key",
        model="openai/gpt-oss-120b",
        client=FakeGroqClient(exception=RuntimeError("upstream failure")),
        enabled=True,
    )
    explanation = service.generate_explanation(make_result())
    assert explanation.status == "unavailable"
    assert explanation.error


def test_malformed_model_response_is_safe():
    from multi_agent.services.explanation_service import InvestigationExplanationService

    service = InvestigationExplanationService(
        api_key="test-key",
        model="openai/gpt-oss-120b",
        client=FakeGroqClient(response_text='not-json'),
        enabled=True,
    )
    explanation = service.generate_explanation(make_result())
    assert explanation.status == "unavailable"
    assert "malformed" in explanation.error.lower()


def test_empty_findings_are_handled_without_fabrication():
    from multi_agent.services.explanation_service import InvestigationExplanationService

    service = InvestigationExplanationService(
        api_key="test-key",
        model="openai/gpt-oss-120b",
        client=FakeGroqClient(response_text=json.dumps({
            "executive_summary": "No findings found.",
            "key_findings": [],
            "risk_reasoning": "Evidence unavailable.",
            "recommended_investigation_actions": ["Monitor case."],
            "limitations": ["Evidence unavailable."],
        })),
        enabled=True,
    )
    result = make_result(claim=ClaimContext(
        claim_id="EMPTY-CASE",
        claim_type="OUTPATIENT",
        provider_id="PRVDR-999",
        provider_id_type="PRVDR_NUM",
        claim_risk_score=12.0,
        final_risk_level="LOW",
        final_risk_priority=1,
        final_claim_rank=200,
    ))
    explanation = service.generate_explanation(result)
    assert explanation.status == "generated"
    assert "evidence unavailable" in explanation.risk_reasoning.lower()


def test_missing_peer_evidence_is_explicitly_not_fabricated():
    from multi_agent.services.explanation_service import InvestigationExplanationService

    provider = ProviderContext(
        npi=1003569997,
        provider_type="Surgery",
        provider_state="CA",
        provider_risk_score=60.0,
        risk_tier="Moderate",
        global_anomaly_score=0.6,
        peer_deviation_score=0.8,
        geo_deviation_score=None,
        is_leie_excluded=False,
        peer_group=None,
    )
    claim = ClaimContext(
        claim_id="PEER-MISSING",
        claim_type="OUTPATIENT",
        provider_id="1003569997",
        provider_id_type="NPI",
        claim_risk_score=52.0,
        final_risk_level="MEDIUM",
        final_risk_priority=2,
        final_claim_rank=40,
    )
    result = Synthesis().investigate(make_case(claim, provider), [], PeerAgent().investigate(make_case(claim, provider)), [])

    service = InvestigationExplanationService(
        api_key="test-key",
        model="openai/gpt-oss-120b",
        client=FakeGroqClient(response_text=json.dumps({
            "executive_summary": "Peer median was unavailable.",
            "key_findings": [{"agent": "PeerAgent", "finding": "Peer comparison is limited by missing metrics.", "evidence": "Peer median unavailable"}],
            "risk_reasoning": "The provider shows a summary-only peer deviation score, but the peer benchmark details are unavailable.",
            "recommended_investigation_actions": ["Verify peer median before escalation."],
            "limitations": ["Peer median unavailable."],
        })),
        enabled=True,
    )
    explanation = service.generate_explanation(result)
    assert explanation.status == "generated"
    assert "unavailable" in explanation.executive_summary.lower()


def test_risk_preservation_after_explanation_generation():
    from multi_agent.services.explanation_service import InvestigationExplanationService

    claim = ClaimContext(
        claim_id="RISK-KEEP",
        claim_type="OUTPATIENT",
        provider_id="1003569997",
        provider_id_type="NPI",
        claim_risk_score=91.0,
        final_risk_level="CRITICAL",
        final_risk_priority=5,
        final_claim_rank=2,
    )
    result = Synthesis().investigate(make_case(claim), [], [], [])
    original_score = result.claim_risk_score
    original_level = result.final_risk_level
    original_priority = result.final_risk_priority
    original_rank = result.final_claim_rank

    service = InvestigationExplanationService(
        api_key="test-key",
        model="openai/gpt-oss-120b",
        client=FakeGroqClient(response_text=json.dumps({
            "executive_summary": "Case remains under review.",
            "key_findings": [],
            "risk_reasoning": "The upstream ML score is preserved.",
            "recommended_investigation_actions": ["Investigate further."],
            "limitations": ["No additional evidence."],
        })),
        enabled=True,
    )
    _ = service.generate_explanation(result)
    assert result.claim_risk_score == original_score
    assert result.final_risk_level == original_level
    assert result.final_risk_priority == original_priority
    assert result.final_claim_rank == original_rank


def test_evidence_attribution_is_preserved():
    from multi_agent.services.explanation_service import InvestigationExplanationService

    claim = ClaimContext(
        claim_id="ATTR-1",
        claim_type="OUTPATIENT",
        provider_id="1003569997",
        provider_id_type="NPI",
        claim_risk_score=75.0,
        final_risk_level="HIGH",
        final_risk_priority=2,
        final_claim_rank=12,
        financial_evidence={"available": True, "values": {"total_claim_payment": 30000.0, "total_claim_charge": 7000.0}},
    )
    billing = BillingAgent().investigate(make_case(claim))
    result = Synthesis().investigate(make_case(claim), billing, [], [])
    service = InvestigationExplanationService(
        api_key="test-key",
        model="openai/gpt-oss-120b",
        client=FakeGroqClient(response_text=json.dumps({
            "executive_summary": "The claim has evidence from multiple agents.",
            "key_findings": [{"agent": "BillingAgent", "finding": "High payment-to-charge ratio.", "evidence": "payment 30000 charge 7000 ratio 4.29"}],
            "risk_reasoning": "The billing evidence is strong and corroborated by the upstream risk score.",
            "recommended_investigation_actions": ["Review payment documentation and claim line detail."],
            "limitations": ["No peer benchmark data provided."],
        })),
        enabled=True,
    )
    explanation = service.generate_explanation(result)
    assert explanation.key_findings[0]["agent"] == "BillingAgent"
    assert "payment" in explanation.key_findings[0]["evidence"].lower()
