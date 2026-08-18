# Explainability Integration Final Contract

## Summary

The final explainability module reuses the repository's working artifacts instead of re-implementing or fabricating model logic.

- Provider SHAP remains the validated path using the persisted provider pipeline.
- Claim SHAP remains artifact-first: Outpatient is READY, Carrier and Inpatient are explicitly BLOCKED_MISSING_FEATURE_ARTIFACT.
- Multi-agent investigation output is normalized through a lightweight adapter that preserves the real InvestigationResult contract.
- Groq is treated as a structured summarization layer that receives only compact evidence, never raw data.

## Canonical interfaces

### 1) Claim explainability

Public entry point:

- explainability.explain_claim(claim_id, claim_type, features=None)

Contract:

- claim_id
- claim_type
- risk
- explanation
- model
- status

Important behavior:

- Carrier and Inpatient return explicit `BLOCKED_MISSING_FEATURE_ARTIFACT` status when the repo does not contain provenance enough to preserve model-faithful SHAP.
- Outpatient returns a deterministically normalized SHAP payload when persisted artifact lineage is present.

### 2) Provider explainability

Public entry point:

- explainability.provider_explainer.ProviderExplainer.explain_provider(...)

This is a persisted pipeline-based SHAP implementation with explicit top-feature output and raw provider feature handling.

### 3) Common explainability interface

Public entry point:

- explainability.explain_entity(entity_type, entity_id, entity_data=None, claim_type=None, investigation_output=None, risk_score=None, groq_explainer=None)

This method normalizes structured evidence into a stable response:

- entity_type
- entity_id
- claim_type
- risk
- shap
- investigation
- genai

### 4) Multi-agent adapter

Adapter module:

- explainability.multi_agent_adapter.normalize_investigation_output(...)

This adapter converts the deterministic multi-agent output (`InvestigationResult`) into a compact explainability payload:

- findings
- evidence
- peer_comparison
- recommendations
- narrative
- summary

### 5) Groq generation

Service module:

- explainability.genai_explainer.StructuredGroqExplainer

This component accepts a compact JSON payload containing only:

- entity metadata
- risk summary
- SHAP status and top features
- multi-agent findings and recommendations

It does not receive raw claim or provider datasets.

## Final integration pattern

1. Determine the entity type.
2. Run the relevant SHAP explainer or return a blocked status if feature lineage cannot be proven.
3. Normalize the investigation result through the multi-agent adapter.
4. Build a compact evidence-only payload for Groq.
5. Return a stable explainability contract to the dashboard or API layer.

## Guardrails

- No model retraining.
- No fabricated features.
- No claim of fraud without evidence.
- Missing evidence is surfaced as `BLOCKED_MISSING_FEATURE_ARTIFACT`, `NOT_AVAILABLE`, or `UNAVAILABLE` rather than silently faked.
