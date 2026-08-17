# Evidence Contract v1

**Status:** Active (Milestone 11 — Evidence Enrichment)  
**Version:** 1.0  
**Last Updated:** 2026-08-16

## Overview

The Evidence Contract v1 defines the schema and semantics for investigation-grade, traceable evidence that moves through the Multi-Agent investigation pipeline. Evidence is produced by deterministic agents (Billing, Peer, Clinical/Rule), preserved through synthesis, and optionally explained by the GenAI layer.

Evidence is **never fabricated**. Missing values are explicitly represented using availability states. Calculation traces and provenance metadata are preserved to enable auditability.

---

## Evidence Schema

### Core Fields

```python
{
  "evidence_id": str,                    # Unique identifier: EV-<hash>
  "agent": str,                          # Source agent: "billing", "peer", "clinical_rule"
  "category": str,                       # Category: "financial", "utilization", "peer_comparison", "geo_comparison", "clinical"
  "metric": str,                         # What is being measured: "payment_ratio", "service_utilization", "peer_deviation", etc.
  "description": str,                    # Human-readable narrative
  
  # Observed and baseline values
  "provider_value": float | None,        # Actual observed value for the provider or claim
  "claim_value": float | None,           # Claim-level observed value (alternative to provider_value)
  "baseline_value": float | None,        # Internal baseline or threshold (e.g., provider's own average)
  
  # Peer and geographic benchmarks
  "peer_mean": float | None,             # Peer group mean (when available)
  "peer_median": float | None,           # Peer group median (when available)
  "peer_std": float | None,              # Peer group standard deviation (when available)
  "peer_group": str | None,              # Peer group name (e.g., "Cardiology-TX")
  "peer_sample_size": int | None,        # Number of providers in peer group
  
  "geographic_group": str | None,        # Geographic region or state
  
  # Derived calculations (auto-calculated, not hand-supplied)
  "deviation": float | None,             # observed - baseline
  "deviation_ratio": float | None,       # observed / baseline (always ≥ 0)
  "percentage_deviation": float | None,  # ((observed - baseline) / baseline) * 100
  "percentile": float | None,            # Percentile rank (0–100)
  
  # Threshold comparisons
  "threshold": float | None,             # Comparison threshold
  "threshold_comparison": str | None,    # "ABOVE", "AT_OR_BELOW", "AT_OR_ABOVE", "BELOW", "EQUAL", "NOT_EQUAL"
  
  # Metadata
  "source": str | None,                  # Data source file (e.g., "provider_risk_scores.csv", "final_unified_claim_risk.csv")
  "source_fields": list[str],            # CSV column names used to derive the evidence
  "confidence": float | None,            # 0.0–1.0 confidence in the evidence
  "availability": str,                   # "AVAILABLE", "NOT_AVAILABLE", "NOT_APPLICABLE", "ERROR"
  
  # Provenance and calculation trace
  "provenance": {
    "source": str,                       # Data source
    "source_fields": list[str],          # CSV columns
    "record_key": str | None,            # "CLAIM_ID=xyz" or "NPI=abc"
    "pipeline": str,                     # "multi_agent"
    "pipeline_version": str | None,      # Version of the pipeline
    "limitation": str | None,            # Explicit limitation (e.g., "Raw peer statistics unavailable")
  },
  
  "calculation": {
    "formula": str,                      # Formula used (e.g., "observed / baseline")
    "inputs": dict,                      # Input values to the formula
    "result": float | None,              # Output of the formula
  },
  
  "time_period": str | None,             # Time period (e.g., "2025-01-01 to 2025-12-31")
}
```

---

## Availability States

Evidence fields are marked with one of four availability states:

| State | Meaning | When to Use |
|-------|---------|------------|
| `AVAILABLE` | The field was successfully extracted from the ML export and is ready for use. | Normal case; evidence is present and valid. |
| `NOT_AVAILABLE` | The field was not exported by the upstream ML pipeline. | Peer benchmarks, specific claim types, or temporal data not in the CSV. |
| `NOT_APPLICABLE` | The field is not relevant to this investigation. | Peer comparison for a provider-only case; clinical rules for CARRIER claims. |
| `ERROR` | The field was present but could not be parsed or validated. | Corrupted or malformed data; downstream calculation failed. |

---

## Calculation Traces

Every evidence item includes a `calculation` object that documents exactly how derived values were computed:

```python
"calculation": {
  "formula": "observed / baseline",
  "inputs": {"observed": 30000.0, "baseline": 7000.0},
  "result": 4.29,
}
```

Calculation inputs are **never fabricated**. If a value is missing (e.g., `baseline_value` is None), the calculation is omitted or marked as `not_applicable`.

### Supported Formulas

| Formula | Purpose | Safety |
|---------|---------|--------|
| `observed / baseline` | Deviation ratio | Returns None if baseline ≤ 0 |
| `(observed - baseline) / baseline * 100` | Percentage deviation | Returns None if baseline = 0 |
| `observed - baseline` | Absolute deviation | Always safe; may be negative |
| `observed compared to threshold` | Threshold comparison | Returns "ABOVE", "BELOW", etc. |
| `not_applicable` | No calculation performed | Used when missing critical inputs |

---

## Provenance Semantics

The `provenance` object explicitly records data lineage and limitations:

```python
"provenance": {
  "source": "provider_risk_scores.csv",
  "source_fields": ["NPI", "Payment_per_Service", "Payment_per_Service_Peer_Median"],
  "record_key": "NPI=1003569997",
  "pipeline": "multi_agent",
  "pipeline_version": None,
  "limitation": "Underlying peer statistics were not exported by the Provider ML pipeline; only blended peer deviation score is available."
}
```

### Limitations

Limitations are **required** when:
- Peer benchmarks are referenced but raw peer statistics are unavailable.
- Claim type or provider type is not fully supported.
- Temporal data (trends, growth) is not available.
- Evidence is based on blended or aggregated ML scores rather than granular data.

Example:
```
"limitation": "Underlying peer statistics were not exported by the Provider ML pipeline; only blended peer deviation score is available."
```

---

## Agent-Specific Evidence Contracts

### Billing Agent

**Source:** `final_unified_claim_risk.csv`

**Metrics:**
- `payment_charge_ratio`: Claim payment ÷ submitted charge
- `provider_payment_deviation`: Claim payment ÷ provider average claim payment
- `payment_reconciliation_issue`: Boolean flag indicating reconciliation problems

**Evidence Example:**
```python
{
  "evidence_id": "EV-001",
  "agent": "billing",
  "category": "financial",
  "metric": "payment_charge_ratio",
  "provider_value": 30000.0,
  "claim_value": 7000.0,
  "baseline_value": None,
  "deviation_ratio": 4.29,
  "source": "final_unified_claim_risk.csv",
  "source_fields": ["total_claim_payment", "total_claim_charge"],
  "availability": "AVAILABLE",
  "confidence": 0.94,
  "calculation": {
    "formula": "observed / baseline",
    "inputs": {"observed": 30000.0, "baseline": 7000.0},
    "result": 4.29,
  },
  "provenance": {
    "source": "final_unified_claim_risk.csv",
    "source_fields": ["total_claim_payment", "total_claim_charge"],
    "record_key": "CLAIM_ID=-10000930090156",
    "pipeline": "multi_agent",
    "limitation": None,
  },
}
```

---

### Peer Agent

**Source:** `provider_risk_scores.csv`

**Metrics:**
- `high_payment_per_service_vs_peers`: Provider payment/service ÷ peer median
- `high_charge_per_service_vs_peers`: Provider charge/service ÷ peer median
- `high_services_per_beneficiary_vs_peers`: Provider services/beneficiary ÷ peer median
- `high_payment_to_charge_ratio_vs_peers`: Provider payment/charge ÷ peer ratio
- `high_svc_hhi_concentration_vs_peers`: Provider service concentration ÷ peer concentration
- `high_geo_deviation`: Provider metric ÷ geographic (state) baseline
- `peer_deviation_score_only`: Blended peer score available; underlying benchmarks not exported
- `geo_deviation_score_only`: Blended geographic score available; underlying benchmarks not exported

**Evidence Example (with underlying peer statistics):**
```python
{
  "evidence_id": "EV-002",
  "agent": "peer",
  "category": "peer_comparison",
  "metric": "high_payment_per_service_vs_peers",
  "provider_value": 15.22,
  "baseline_value": None,
  "peer_mean": 47.25,
  "peer_median": 5.0,
  "peer_std": 31.46,
  "deviation_ratio": 3.04,
  "percentile": 96.0,
  "peer_group": "Cardiology-TX",
  "peer_sample_size": 184,
  "source": "provider_risk_scores.csv",
  "source_fields": ["NPI", "Payment_per_Service", "Payment_per_Service_Peer_Median", "Payment_per_Service_Deviation_Ratio"],
  "availability": "AVAILABLE",
  "confidence": 0.9,
  "calculation": {
    "formula": "provider_value / peer_median",
    "inputs": {"provider_value": 15.22, "peer_median": 5.0},
    "result": 3.04,
  },
  "provenance": {
    "source": "provider_risk_scores.csv",
    "source_fields": ["NPI", "Payment_per_Service", "Payment_per_Service_Peer_Median"],
    "record_key": "NPI=1003569997",
    "pipeline": "multi_agent",
    "limitation": None,
  },
}
```

**Evidence Example (score-only, benchmarks unavailable):**
```python
{
  "evidence_id": "EV-003",
  "agent": "peer",
  "category": "peer_comparison",
  "metric": "peer_deviation_score_only",
  "provider_value": None,
  "peer_median": None,
  "peer_group": "Mass Immunizer Roster Biller",
  "deviation_ratio": None,
  "source": "provider_risk_scores.csv",
  "source_fields": ["NPI", "Peer_Deviation_Score"],
  "availability": "AVAILABLE",
  "confidence": 0.82,
  "calculation": {
    "formula": "not_applicable",
    "inputs": {},
    "result": None,
  },
  "provenance": {
    "source": "provider_risk_scores.csv",
    "source_fields": ["NPI", "Peer_Deviation_Score"],
    "record_key": "NPI=1003569997",
    "pipeline": "multi_agent",
    "limitation": "Underlying peer statistics were not exported by the Provider ML pipeline; only blended peer deviation score is available.",
  },
}
```

---

### Clinical/Rule Agent

**Source:** `final_unified_claim_risk.csv`

**Metrics (Outpatient):**
- `outpatient_multiple_lines_utilization`: Claim has multiple billing lines or high line count
- `outpatient_multiple_diagnoses_utilization`: Claim has multiple diagnoses
- `outpatient_extreme_procedure_count`: Claim has high procedure code count

**Metrics (Inpatient):**
- `inpatient_length_of_stay_outlier`: Length of stay exceeds typical range
- `inpatient_charge_outlier`: Inpatient charges exceed threshold
- `inpatient_multiple_diagnoses_utilization`: Claim has multiple diagnoses

**Evidence Example:**
```python
{
  "evidence_id": "EV-004",
  "agent": "clinical_rule",
  "category": "utilization",
  "metric": "outpatient_multiple_lines_utilization",
  "claim_value": 9,
  "baseline_value": 1,
  "threshold": 5,
  "threshold_comparison": "ABOVE",
  "source": "final_unified_claim_risk.csv",
  "source_fields": ["CLAIM_ID", "claim_line_count", "has_multiple_lines"],
  "availability": "AVAILABLE",
  "confidence": 0.85,
  "calculation": {
    "formula": "observed compared to threshold",
    "inputs": {"observed": 9, "threshold": 5},
    "result": "ABOVE",
  },
  "provenance": {
    "source": "final_unified_claim_risk.csv",
    "source_fields": ["CLAIM_ID", "claim_line_count", "has_multiple_lines"],
    "record_key": "CLAIM_ID=CLM-1001",
    "pipeline": "multi_agent",
    "limitation": None,
  },
}
```

---

## Zero/Null Safety

All calculation functions are **zero- and null-safe**:

| Calculation | When Baseline = 0 | When Value = None | Result |
|-------------|-------------------|-------------------|--------|
| `value / baseline` | Returns None | Returns None | None |
| `(value - baseline) / baseline * 100` | Returns None | Returns None | None |
| `value - baseline` | Returns difference | Returns None | diff or None |
| `value compared to threshold` | Returns comparison | Returns None | comparison or None |

---

## Backward Compatibility

The evidence enrichment layer is **fully backward compatible**:

1. Existing `Finding` objects continue to work unchanged.
2. The enrichment layer **extends** evidence metadata without altering risk synthesis.
3. Upstream ML scores, synthesis weights, and GenAI boundaries remain unchanged.
4. Evidence enrichment is **optional**; systems that do not enrich evidence will not break.

---

## Integration with Findings

Findings reference evidence by ID:

```python
Finding(
  agent="peer",
  category="peer_comparison",
  rule="high_payment_per_service_vs_peers",
  severity="HIGH",
  description="Provider payment per service is 3.04x the peer median.",
  evidence={
    "evidence_id": "EV-002",
    "provider_value": 15.22,
    "peer_median": 5.0,
    "deviation_ratio": 3.04,
    "percentile": 96.0,
    "peer_group": "Cardiology-TX",
    "source": "provider_risk_scores.csv",
    "provenance": {...},
    "calculation": {...},
  },
  confidence=0.9,
)
```

---

## Examples

### Example 1: Billing Finding with Full Evidence Trace

**Scenario:** Claim payment is 4.29x the submitted charge.

```python
evidence = {
  "evidence_id": "EV-BILL-001",
  "agent": "billing",
  "category": "financial",
  "metric": "payment_charge_ratio",
  "provider_value": 30000.0,
  "claim_value": 7000.0,
  "baseline_value": None,
  "deviation_ratio": 4.29,
  "source": "final_unified_claim_risk.csv",
  "source_fields": ["total_claim_payment", "total_claim_charge"],
  "availability": "AVAILABLE",
  "confidence": 0.94,
  "calculation": {
    "formula": "observed / baseline",
    "inputs": {"observed": 30000.0, "baseline": 7000.0},
    "result": 4.29,
  },
  "provenance": {
    "source": "final_unified_claim_risk.csv",
    "source_fields": ["total_claim_payment", "total_claim_charge"],
    "record_key": "CLAIM_ID=-10000930090156",
    "pipeline": "multi_agent",
    "limitation": None,
  },
}
```

### Example 2: Peer Finding with Score-Only Evidence

**Scenario:** Provider peer deviation score is high, but underlying benchmarks are unavailable.

```python
evidence = {
  "evidence_id": "EV-PEER-SCORE",
  "agent": "peer",
  "category": "peer_comparison",
  "metric": "peer_deviation_score_only",
  "provider_value": None,
  "peer_median": None,
  "deviation_ratio": None,
  "percentile": None,
  "peer_group": "Mass Immunizer Roster Biller",
  "source": "provider_risk_scores.csv",
  "source_fields": ["NPI", "Peer_Deviation_Score"],
  "availability": "AVAILABLE",
  "confidence": 0.82,
  "calculation": {
    "formula": "not_applicable",
    "inputs": {},
    "result": None,
  },
  "provenance": {
    "source": "provider_risk_scores.csv",
    "source_fields": ["NPI", "Peer_Deviation_Score"],
    "record_key": "NPI=1003569997",
    "pipeline": "multi_agent",
    "limitation": "Underlying peer statistics were not exported by the Provider ML pipeline; only blended peer deviation score is available.",
  },
}
```

### Example 3: Clinical Finding with Missing Baseline

**Scenario:** Claim has 9 lines; baseline is 1; threshold check shows "ABOVE".

```python
evidence = {
  "evidence_id": "EV-CLIN-001",
  "agent": "clinical_rule",
  "category": "utilization",
  "metric": "outpatient_multiple_lines_utilization",
  "claim_value": 9,
  "baseline_value": 1,
  "threshold": 5,
  "threshold_comparison": "ABOVE",
  "source": "final_unified_claim_risk.csv",
  "source_fields": ["claim_line_count", "has_multiple_lines"],
  "availability": "AVAILABLE",
  "confidence": 0.85,
  "calculation": {
    "formula": "observed compared to threshold",
    "inputs": {"observed": 9, "threshold": 5},
    "result": "ABOVE",
  },
  "provenance": {
    "source": "final_unified_claim_risk.csv",
    "source_fields": ["claim_line_count"],
    "record_key": "CLAIM_ID=CLM-1001",
    "pipeline": "multi_agent",
    "limitation": None,
  },
}
```

---

## Limitations and Future Work

### Known Limitations

1. **Temporal Evidence:** Trend data and temporal growth rates are not yet supported.
2. **LEIE Evidence:** Exclusion list evidence is not yet structured in the evidence contract.
3. **Complex Rules:** Multi-factor rules (e.g., "A AND B AND C") are not yet decomposed into independent evidence.
4. **Evidence Aggregation:** Evidence across multiple claims for the same provider is not yet rolled up.

### Future Enhancements

- Temporal evidence with growth rates and trend analysis.
- LEIE status as structured evidence with lookup metadata.
- Evidence rollup and correlation across claims and providers.
- Evidence ranking and importance scoring.

---

## Related Documents

- [Investigation Contract v1](investigation_contract_v1.md) — High-level case payload and findings.
- [Data Contract Validation v1](data_contract_validation_v1.md) — Real dataset validation and coverage.
- [Multi-Agent README](../multi_agent/README.md) — Architecture and agent descriptions.

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-08-16 | Initial release; Milestone 11 evidence enrichment. |
