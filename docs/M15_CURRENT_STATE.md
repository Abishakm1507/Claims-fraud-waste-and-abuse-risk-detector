# M15 Current State Audit

## Scope

This audit captures the current state of the Groq explanation layer before and during the M15 guardrail work. The intent is to keep the deterministic investigation system unchanged while restricting the LLM to explanation-only behavior.

## Current Groq flow

The authoritative flow in the project remains:

1. Claim/provider data enters the investigation process.
2. Deterministic agents produce findings and evidence.
3. The synthesis layer computes or preserves risk outputs.
4. The `InvestigationCase` object stores the evidence, findings, and risk synthesis.
5. The RAG handoff uses `RAGExplanationRequest` and `GenAIExplanationContext` as the safe external contract.
6. Groq explains the already-computed investigation context.

This is the intended boundary. Groq does not score fraud, compute risk, revise rule hits, or fabricate evidence.

## Current implementation files

### Core explanation service
- `multi_agent/services/explanation_service.py`
- `InvestigationExplanationService.generate_explanation()`
- `_build_prompt()`
- `_system_prompt()`
- `_call_groq()`
- `_parse_response()`

### Canonical schema layer
- `multi_agent/models/schemas.py`
- `GenAIExplanation`
- `GenAIExplanationContext`
- `HandoffMetadata`
- `RAGExplanationRequest`
- `InvestigationCase`

### RAG handoff boundary
- `multi_agent/rag/handoff.py`
- `build_rag_handoff()`
- `serialize_rag_handoff()`

## Current prompt construction

The current explanation service builds a JSON payload that includes:
- claim metadata
- provider metadata
- risk level / priority fields
- agent errors
- findings
- evidence summary

The system prompt directs Groq to summarize deterministic findings and avoid inventing facts, but this is primarily advisory and not a strict validation gate.

## Current output schema

The current `GenAIExplanation` model already includes:
- explanation_id
- model_provider
- model_name
- summary
- key_findings
- evidence_references
- investigation_narrative
- limitations
- generated_at
- source_case_id
- contract_version

The M15 work strengthened this schema with:
- `case_id`
- `risk_interpretation`
- `recommended_review_actions`
- `disclaimer`
- `model_metadata`
- `status`

This keeps the schema aligned with the existing project while making explanation fields safer and more explicit.

## Current validation

Before M15, the primary validation was limited to:
- missing API key
- missing Groq SDK
- malformed JSON parsing
- timeout failures
- general exceptions

The project did not yet validate:
- evidence ID membership
- unsupported numerical claims
- conflicting risk category/priority overrides
- unsupported fraud confirmation language
- prompt-injection handling
- bounded retry policy with classification
- strict fallback behavior
- anti-hallucination checks for invented ratios, dates, procedures, diagnoses, or peer comparisons

## Current failure handling

The existing service handles:
- missing API key
- SDK missing
- timeout
- malformed response
- generic exception

It returns an `InvestigationExplanation` with a failure status instead of crashing the deterministic pipeline.

## Current hallucination risks

The main risks are:
- free-form JSON output is not checked for unsupported metric claims
- no validation that a generated ratio is actually supported by evidence
- no enforcement that risk category/priority follows the deterministic result
- no guardrail against fraud-confirmation language
- no prompt-injection boundary beyond general prompt instructions
- no structured validation of evidence references
- no explicit handling for agent error/skipped states in the explanation layer

## Current test coverage

The project has existing tests for:
- successful explanation generation
- missing API key
- timeout
- malformed JSON
- empty findings
- peer evidence unavailable
- risk preservation after explanation generation
- evidence attribution preservation

This coverage validates basic resilience, but it does not yet stress unsupported factual generation or model-output fraud, risk override, or evidence reference integrity.

## Files requiring modification for M15

- `multi_agent/services/explanation_service.py`
- `multi_agent/models/schemas.py`
- `tests/genai/test_anti_hallucination.py`
- `tests/genai/test_groq_failures.py`
- `docs/M15_ANTI_HALLUCINATION_REPORT.md`
- `docs/GROQ_GUARDRAILS.md`

## Files intentionally left untouched

- `multi_agent/orchestrator.py`
- `multi_agent/synthesis.py`
- `multi_agent/services/risk_synthesis_service.py`
- `multi_agent/config/risk_synthesis_config.py`
- `multi_agent/agents/`
- deterministic agent logic and scoring logic
- risk thresholds and weight configuration
- data ingestion/repository logic

## Conclusion

The Groq explanation layer is already isolated from the deterministic risk calculation, but it lacked strict output validation and anti-hallucination controls. M15 adds guardrails around the explanation output, evidence referencing, risk consistency, prompt injection, and retry/fallback safety without altering the underlying investigation pipeline.
