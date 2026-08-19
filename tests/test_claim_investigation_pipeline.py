from __future__ import annotations

from multi_agent.data.claim_store import ClaimStore
from multi_agent.orchestrator import Orchestrator


TARGET_CLAIM = "-10000930090156"


def test_target_claim_uses_type_specific_model_score_and_features():
    claim = ClaimStore().get_claim(TARGET_CLAIM)

    assert claim is not None
    assert claim.claim_type == "OUTPATIENT"
    assert claim.claim_risk_score == 95.07029
    assert claim.model_evidence.values["model_score"] == 0.9507029
    assert claim.claim_features["claim_line_count"] == 15.0
    assert claim.claim_features["procedure_code_count"] == 375.0


def test_investigation_contract_preserves_findings_evidence_and_context():
    orchestrator = Orchestrator(
        enable_genai_explanation=False,
        enable_llm_agent_reasoning=False,
    )
    result = orchestrator.investigate_claim(TARGET_CLAIM)
    case = orchestrator.to_investigation_case(result)

    assert case.risk_synthesis is not None
    assert case.risk_synthesis.claim_anomaly == 95.07029
    assert case.findings
    assert case.evidence
    assert len(case.findings) == len(case.evidence)
    assert all(finding.evidence_ids for finding in case.findings)
    assert all(evidence.metric != "None" for evidence in case.evidence)
    assert case.investigation_context is not None
    assert case.investigation_context.claim_features["claim_line_count"] == 15.0
    assert case.investigation_context.claim_features["procedure_code_count"] == 375.0
    assert case.genai_explanation is None


def test_explainability_model_defaults_to_requested_model(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "openai/gpt-oss-120b")
    monkeypatch.delenv("GROQ_MODEL", raising=False)

    from explainability.genai_explainer import StructuredGroqExplainer
    from multi_agent.services.explanation_service import InvestigationExplanationService

    assert StructuredGroqExplainer(api_key="test").model == "openai/gpt-oss-120b"
    assert InvestigationExplanationService(api_key=None).model == "openai/gpt-oss-120b"
