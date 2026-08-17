# Investigation Contract v1

## Purpose

This contract defines the typed, versioned payload that moves through the deterministic Multi-Agent investigation stack and into the Groq explanation layer. It is designed to preserve evidence, provenance, and risk outputs without allowing the GenAI layer to alter the underlying investigation logic.

Deterministic agents produce evidence and scores.
Deterministic synthesis produces risk.
Groq produces interpretation only.

## Architecture Position

The contract sits between:

1. Claim/provider context loaders
2. Billing agent / Peer agent / Clinical rule agent
3. Deterministic synthesis
4. InvestigationCase handoff to downstream systems
5. Optional GenAI explanation layer

The contract is intentionally explicit and JSON-serializable so the RAG-based explainability team can consume the final structured case directly without reading individual agent implementations.

## Contract Version

`CONTRACT_VERSION = "1.0"`

## Core Schemas

### InvestigationContext

Represents the claim and provider context available to specialist agents.

Key fields:
- `case_id`
- `claim_id`
- `provider_id`
- `provider_id_type`
- `claim_type`
- `claim_anomaly`
- `provider_anomaly`
- `claim_features`
- `provider_features`
- `peer_features`
- `leie_evidence`
- `data_availability`
- `metadata`
- `provenance`

Provider ID types are restricted to:
- `NPI`
- `PRVDR_NUM`
- `UNKNOWN`

### Evidence

`Evidence` stores rich investigation-level evidence, including baseline and peer comparison data when available.

Important fields:
- `evidence_id`
- `agent`
- `category`
- `metric`
- `provider_value`
- `claim_value`
- `baseline_value`
- `peer_mean`
- `peer_median`
- `peer_std`
- `deviation`
- `deviation_ratio`
- `percentile`
- `peer_group`
- `peer_sample_size`
- `geographic_baseline`
- `threshold`
- `direction`
- `unit`
- `source`
- `source_fields`
- `source_record_id`
- `methodology`
- `confidence`
- `metadata`

Missing values are represented as `None` or via `data_availability` and `limitations`; they are never fabricated.

### Finding

A finding references evidence by `evidence_id` instead of duplicating full evidence documents.

### RuleHit

A rule hit is structured investigation evidence from the clinical or rule layer. It never means confirmed fraud. It is a review trigger only.

### AgentResult

Every deterministic specialist agent returns this shape:

- `agent`
- `status`
- `score`
- `risk`
- `findings`
- `evidence`
- `rule_hits`
- `limitations`
- `provenance`
- `execution_id`
- `execution_time_ms`
- `contract_version`

Allowed statuses:
- `success`
- `partial`
- `error`
- `skipped`

Allowed risk values:
- `LOW`
- `MEDIUM`
- `HIGH`
- `CRITICAL`
- `UNKNOWN`

Scores are validated to the range 0–100.

### AgentExecution

A minimal audit record for each agent execution.

### RiskSynthesis

The deterministic score produced from the investigation outputs.

Current documented methodology (authoritative weights used by the current pipeline):
- claim anomaly: 30%
- provider anomaly: 30%
- peer score: 20%
- billing score: 10%
- rule score: 10%

Overall risk is validated to 0–100.

Risk category mapping:
- 0–39: LOW
- 40–69: MEDIUM
- 70–84: HIGH
- 85–100: CRITICAL

Priority mapping:
- LOW => P3
- MEDIUM => P2
- HIGH => P1
- CRITICAL => P0

### InvestigationCase

The final packaged contract for the RAG and downstream explainability pipeline.

It includes:
- `contract_version`
- `case_id`
- `claim_id`
- `provider_id`
- `provider_id_type`
- `claim_type`
- `investigation_context`
- `agent_results`
- `agent_executions`
- `findings`
- `evidence`
- `risk_synthesis`
- `genai_explanation`
- `provenance`
- `created_at`
- `updated_at`

### GenAIExplanation

This is the Groq-generated interpretation layer after deterministic synthesis.

It must not generate or alter:
- fraud score
- risk category
- priority
- rule hits
- evidence

It only interprets the structured case.

## Data Availability and Limitations

The platform tracks missing evidence explicitly. Examples:
- `Peer median unavailable in current Provider ML export.`
- `Raw diagnosis/procedure codes are unavailable.`
- `INPATIENT financial evidence was not exported.`
- `Provider ID type is PRVDR_NUM.`

Availability values:
- `AVAILABLE`
- `NOT_AVAILABLE`
- `NOT_APPLICABLE`
- `ERROR`

## Example InvestigationCase

```json
{
  "contract_version": "1.0",
  "case_id": "CASE-10231",
  "claim_id": "CLM10231",
  "provider_id": "P10023",
  "provider_id_type": "NPI",
  "claim_type": "OUTPATIENT",
  "investigation_context": {
    "case_id": "CASE-10231",
    "claim_id": "CLM10231",
    "provider_id": "P10023",
    "provider_id_type": "NPI",
    "claim_type": "OUTPATIENT",
    "claim_anomaly": 91,
    "provider_anomaly": 88,
    "data_availability": {
      "peer_benchmark": "NOT_AVAILABLE"
    }
  },
  "findings": [
    {
      "finding_id": "F-001",
      "agent": "billing",
      "title": "Payment-to-charge ratio",
      "description": "Claim has a high payment-to-charge ratio.",
      "severity": "HIGH",
      "category": "financial",
      "evidence_ids": ["EV-001"],
      "confidence": 0.92
    }
  ],
  "evidence": [
    {
      "evidence_id": "EV-001",
      "agent": "billing",
      "category": "financial",
      "metric": "payment_to_charge_ratio",
      "provider_value": 30000,
      "claim_value": 7000,
      "deviation_ratio": 4.29,
      "source": "claims.csv",
      "source_fields": ["total_claim_payment", "total_claim_charge"],
      "methodology": "billing_ratio",
      "confidence": 0.9
    }
  ],
  "risk_synthesis": {
    "overall_risk": 81,
    "risk_category": "HIGH",
    "priority": "P1",
    "contract_version": "1.0"
  }
}
```

## Deterministic vs GenAI Responsibilities

- Deterministic agents: create findings and evidence
- Deterministic synthesis: computes risk and priority
- Groq: only explains the deterministic case in narrative form

## Contract Validation Rules

The contract rejects arbitrary fields and enforces:
- required fields
- enum values
- score ranges
- risk values
- status values
- evidence references
- timestamps
- contract version

This prevents silent schema drift and keeps downstream systems deterministic.
