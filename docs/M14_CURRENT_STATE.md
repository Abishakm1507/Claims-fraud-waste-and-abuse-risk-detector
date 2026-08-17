# M14 Current State Audit

## 1. What already exists before M14

### Existing canonical contracts and schemas
- `multi_agent/models/schemas.py` defines the core investigation contract:
  - `Evidence`
  - `Finding`
  - `RuleHit`
  - `AgentResult`
  - `AgentExecution`
  - `RiskSynthesis`
  - `GenAIExplanation`
  - `InvestigationCase`
  - `InvestigationContext`
- The project already preserves `contract_version`, typed enums, evidence IDs, findings, and provenance-friendly fields.

### Validation already implemented (M10)
- Pydantic v2 models use `ConfigDict(extra="forbid")`
- Field validation enforces enum values and ranges (for example, `AgentResult.score` is bounded to 0..100)
- `RiskSynthesis` validates the category/risk consistency with the score threshold model
- InvestigationCase has type-safe validation for `provider_id_type`

### Evidence enrichment already implemented (M11)
- `multi_agent/evidence/evidence_enricher.py` enriches raw finding evidence with numeric metadata, deviation ratios, peer baselines, and provenance metadata
- `multi_agent/evidence/provenance.py` provides structured provenance capture helpers
- Evidence is kept quantitative and traceable rather than reduced to opaque text

### Provenance already implemented (M12)
- `multi_agent/provenance/capture.py` captures per-agent execution metadata and routing metadata
- `multi_agent/provenance/tracer.py` provides trace metadata support for investigations
- `multi_agent/provenance/validator.py` supports provenance validation and reporting

### Risk synthesis freeze already implemented (M13)
- `multi_agent/config/risk_synthesis_config.py` defines frozen weights and thresholds
- `multi_agent/services/risk_synthesis_service.py` computes deterministic weighted risk scores
- `RiskSynthesis` in `multi_agent/models/schemas.py` includes contributions and version metadata

### Existing GenAI explanation layer
- `multi_agent/services/explanation_service.py` implements Groq-backed explanation generation
- It is explicitly non-authoritative for numerical risk scoring and is designed to explain a completed investigation result rather than create it

### Existing investigation structure
- `multi_agent/schemas/investigation_case.py` defines the current operational InvestigationCase used by the orchestrator
- `multi_agent/synthesis.py` defines the deterministic synthesis and aggregated investigation result
- `multi_agent/orchestrator.py` coordinates the agent flow

## 2. What M14 requires

M14 adds a stable, versioned, external-facing handoff contract for the separate RAG Explainability team. The requirement is to expose one canonical artifact that does NOT depend on:

- internal agent implementation details
- raw CSV/repository access
- ML joblib or provider logic details
- case routing internals
- risk model internals
- unstructured LLM reconstruction work

The RAG team should receive a typed `RAGExplanationRequest` containing:
- `case`
- `evidence`
- `findings`
- `risk_synthesis`
- `agent_results`
- `genai_context`
- `metadata`

The contract must be JSON-serializable, validated, versioned, and deterministic.

## 3. What can be reused as-is

- `InvestigationCase` from `multi_agent/models/schemas.py`
- `Evidence`, `Finding`, `RuleHit`, `AgentResult`, `RiskSynthesis`, `GenAIExplanation` and `AgentExecution`
- Existing `InvestigationContext` and provenance patterns
- Existing Groq explanation context as a read-only explanation package
- Existing validation rules in Pydantic models
- Existing risk synthesis configuration and thresholds from M13
- Existing `EvidenceEnricher` and provenance metadata

## 4. What needs modification

M14 requires a new canonical external handoff object and adapter layer:

- add `GenAIExplanationContext` to the contract layer
- add `HandoffMetadata`
- add `RAGExplanationRequest`
- add `build_rag_handoff(case)` adapter and serialization helpers
- add validation to reject missing case IDs, missing risk synthesis, duplicate evidence IDs, NaN/Infinity, invalid agent statuses, and invalid scores
- add example payload and docs for the RAG team
- add dedicated contract tests that validate the external handoff boundary

## 5. Files that will be changed

- `multi_agent/models/schemas.py`
- `multi_agent/rag/handoff.py` (new)
- `multi_agent/rag/__init__.py` (new)
- `docs/M14_CURRENT_STATE.md` (new)
- `docs/RAG_HANDOFF_CONTRACT.md` (new)
- `docs/RAG_TEAM_INTEGRATION.md` (new)
- `examples/rag_handoff_example.json` (new)
- `tests/contract/test_rag_handoff.py` (new)

## 6. Files that will not be changed

The following are intentionally left alone to preserve the existing multi-agent behavior:

- `multi_agent/orchestrator.py`
- `multi_agent/synthesis.py`
- `multi_agent/agents/*`
- `multi_agent/data/*`
- `multi_agent/services/explanation_service.py`
- `multi_agent/config/risk_synthesis_config.py`
- `multi_agent/services/risk_synthesis_service.py`
- `multi_agent/provenance/*`
- `multi_agent/evidence/*`
- existing public investigation tests under `multi_agent/tests/*`

This preserves the deterministic investigation logic, scoring methodology, thresholds, weights, and GenAI explanation flow already completed in Milestones 1–13.
