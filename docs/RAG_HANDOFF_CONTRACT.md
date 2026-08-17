# RAG Handoff Contract (M14)

## Purpose

The Multi-Agent Investigation System produces one canonical artifact for the RAG Explainability team: a validated `RAGExplanationRequest`.

The RAG team is not expected to know how the system derived a score, how the agents routed, or how the CSV and provider repositories work. Their responsibility is to retrieve the relevant policy/domain knowledge, ground the evidence, and explain the determination.

## Contract Version

The contract uses the existing project versioning convention.

- Internal model contract version: `1.0`
- RAG handoff contract is versioned on the payload itself via `contract_version`
- Backward-compatible changes should preserve the same `contract_version` until a breaking change is required
- Breaking changes require a new major version and explicit migration notes

## Canonical Request

```python
class RAGExplanationRequest(BaseModel):
    contract_version: str
    request_id: str
    case: InvestigationCase
    evidence: list[Evidence]
    findings: list[Finding]
    risk_synthesis: RiskSynthesis
    agent_results: list[AgentResult]
    genai_context: GenAIExplanationContext
    metadata: HandoffMetadata
```

## Field definitions

### `request_id`
A stable ID derived from the investigation case to preserve traceability without inventing an unrelated identifier.

Example:

```text
rag-CASE-1001
```

### `case`
The completed `InvestigationCase` representing the investigation state and associated data model.

### `evidence`
All evidence preserved as structured, quantitative investigation evidence with provenance and limitations.

### `findings`
All findings produced by the investigation agents and retained in the canonical contract.

### `risk_synthesis`
The deterministic M13 risk synthesis result. This is authoritative for scoring and classification.

### `agent_results`
Each agent's status, score, findings, evidence, limitations, and execution metadata.

### `genai_context`
A read-only explanation context used as a safe input for the Groq explanation layer without allowing the LLM to reconstruct or override core risk values.

### `metadata`
Investigation metadata including request ID, case ID, generated timestamp, provenance, and availability summary.

## Evidence preservation

Evidence remains investigation-grade:
- observed value
- baseline value
- deviation
- deviation ratio
- percentile
- peer group
- sample size
- source
- source fields
- provenance
- limitations

If underlying data is unavailable, the contract explicitly records that rather than inventing a zero or default value.

## Limitations behavior

The RAG team must see limitations explicitly:

```python
{
  "category": "temporal",
  "status": "NOT_AVAILABLE",
  "reason": "No temporal fields exported for this claim type."
}
```

Missing data is never silently converted into:
- 0
- false
- normal
- low risk

## Agent status behavior

Agent results retain status values from the existing contracts, for example:
- `SUCCESS`
- `PARTIAL`
- `ERROR`
- `SKIPPED`
- `NOT_APPLICABLE`

The RAG contract cannot silently discard failure or skip states.

## Risk ownership boundary

The Multi-Agent system owns the risk computation. The RAG team must not recalculate:
- claim anomaly
- provider anomaly
- agent scores
- overall risk
- risk category
- priority

RAG is responsible for:
- retrieval
- grounding
- explanation
- investigator support

It is not responsible for fraud scoring.

## Serialization

The contract is JSON-serializable and supports both:
- Python dict serialization
- JSON string serialization

The adapter ensures:
- enums serialize to their values
- NaN and Infinity are rejected
- unsupported Python objects are not emitted
- internal implementation details are not leaked

## Validation rules

The adapter validates before returning a handoff request:
- `contract_version` exists
- `request_id` exists
- `case` exists
- `case_id` exists
- `risk_synthesis` exists
- evidence IDs are unique
- numeric values are finite
- invalid agent statuses are rejected
- missing risk data triggers a fail-fast error

## Example payload

See `examples/rag_handoff_example.json`.

## Compatibility policy

- `v1.x` = backward compatible changes
- `v2.x` = breaking changes
- M14 implements the initial stable contract without introducing a v2 schema

## Error handling

If required input is missing, the handoff builder fails explicitly with a `ValueError` rather than manufacturing data.
