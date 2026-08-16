# RAG Team Integration Guide

## Overview

The RAG team receives one canonical artifact: `RAGExplanationRequest`.

This contract is designed to carry the investigation output and supporting evidence without exposing the internal agent implementation or raw data dependencies.

## Input contract

```python
from multi_agent.rag.handoff import build_rag_handoff

request = build_rag_handoff(investigation_case)
```

The result is a typed `RAGExplanationRequest`.

## They may use

- `request.case`
- `request.evidence`
- `request.findings`
- `request.risk_synthesis`
- `request.agent_results`
- `request.genai_context`
- `request.metadata`
- `request.metadata.provenance`
- `request.metadata.limitations`

## They must not treat as source of truth

- raw CSV files
- provider repository objects
- claim repository objects
- ML joblib artifacts
- internal agent code paths
- rule implementation details
- LLM-generated risk values

## Expected responsibility

The RAG team should do the following only with the handoff contract:

1. Retrieve policy/domain knowledge relevant to the evidence
2. Ground the explanation in the concrete quantitative evidence provided
3. Summarize the investigation in plain language for investigators
4. Answer investigator questions about the claim/provider basis for concern
5. Surface limitations and missing evidence transparently

## Not allowed

The RAG team must not:
- re-run claim/provider risk scoring
- recompute overall risk or risk category
- improvise peer baselines or provider statistics
- re-interpret the case without using the provided evidence and limitations

## Example

```python
from multi_agent.rag.handoff import build_rag_handoff

handoff = build_rag_handoff(investigation_case)
print(handoff.request_id)
print(handoff.risk_synthesis.overall_risk)
print(handoff.genai_context.risk_category)
```

## Groq compatibility

The existing Groq explanation layer remains compatible with this contract. The system may pass the `GenAIExplanationContext` or a reduced explanation-friendly view into the Groq model, but the model is still not permitted to create the authoritative numerical risk output.

## Data availability contract

The RAG system should respect the explicit availability metadata from the investigation case. Missing fields are not equal to normal or low risk.

## Support boundary

If required data is unavailable, the handoff includes the limitation instead of fabricating a value.
