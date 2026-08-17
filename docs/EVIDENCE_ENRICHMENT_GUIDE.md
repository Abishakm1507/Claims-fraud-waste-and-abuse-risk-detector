# Evidence Enrichment Integration Guide

This guide explains how the evidence enrichment layer works and how to use it in your investigation pipeline.

## Quick Start

### 1. Enrich Findings from an Agent

```python
from multi_agent.evidence import EvidenceEnricher
from multi_agent.agents.billing_agent import BillingAgent
from multi_agent.schemas.investigation_case import InvestigationCase

# Get findings from billing agent
case = InvestigationCase(case_id="test", claim_id="claim-1", claim=claim_context)
findings = BillingAgent().investigate(case)

# Enrich with provenance and calculation traces
enriched = EvidenceEnricher.enrich_findings(findings, case=case)

# Inspect enriched evidence
for finding in enriched:
    print(f"Evidence ID: {finding.evidence['evidence_id']}")
    print(f"Source: {finding.evidence['source']}")
    print(f"Provenance: {finding.evidence['provenance']}")
    print(f"Calculation: {finding.evidence['calculation']}")
```

### 2. What You Get

Each enriched finding now contains:

```python
{
  "evidence": {
    "evidence_id": "EV-abc123...",      # Unique, deterministic ID
    "agent": "billing",                  # Source agent
    "category": "financial",             # Evidence category
    "metric": "payment_charge_ratio",    # What's being measured
    
    # Raw values
    "payment": 30000.0,
    "charge": 7000.0,
    "deviation_ratio": 4.29,
    
    # Provenance and lineage
    "source": "final_unified_claim_risk.csv",
    "source_fields": ["total_claim_payment", "total_claim_charge"],
    "provenance": {
      "source": "final_unified_claim_risk.csv",
      "source_fields": ["total_claim_payment", "total_claim_charge"],
      "record_key": "CLAIM_ID=xyz",
      "pipeline": "multi_agent",
      "limitation": None,  # or explicit limitation text
    },
    
    # Calculation trace
    "calculation": {
      "formula": "observed / baseline",
      "inputs": {"observed": 30000.0, "baseline": 7000.0},
      "result": 4.29,
    },
    
    # Availability and quality
    "availability": "AVAILABLE",
    "confidence": 0.94,
  }
}
```

## Agent-Specific Usage

### Billing Agent

```python
from multi_agent.evidence import EvidenceEnricher
from multi_agent.agents.billing_agent import BillingAgent

findings = BillingAgent().investigate(case)
enriched = EvidenceEnricher.enrich_findings(findings, case=case)

# Evidence will include:
# - payment_charge_ratio
# - provider_payment_deviation
# - payment_reconciliation_issue
# Source: final_unified_claim_risk.csv
```

### Peer Agent

```python
from multi_agent.evidence import EvidenceEnricher
from multi_agent.agents.peer_agent import PeerAgent

findings = PeerAgent().investigate(case)
enriched = EvidenceEnricher.enrich_findings(findings, case=case)

# Evidence will include:
# - high_payment_per_service_vs_peers
# - high_charge_per_service_vs_peers
# - high_services_per_beneficiary_vs_peers
# - peer_deviation_score_only (with limitation: "Raw peer statistics unavailable")
# - geo_deviation_score_only (with limitation: "Raw geographic statistics unavailable")
# Source: provider_risk_scores.csv
```

### Clinical/Rule Agent

```python
from multi_agent.evidence import EvidenceEnricher
from multi_agent.agents.clinical_rule_agent import ClinicalRuleAgent

findings = ClinicalRuleAgent().investigate(case)
enriched = EvidenceEnricher.enrich_findings(findings, case=case)

# Evidence will include:
# - outpatient_multiple_lines_utilization
# - outpatient_multiple_diagnoses_utilization
# - inpatient_length_of_stay_outlier
# etc.
# Source: final_unified_claim_risk.csv
```

## Integration with Orchestrator

The orchestrator can optionally enrich findings:

```python
from multi_agent.orchestrator import Orchestrator
from multi_agent.evidence import EvidenceEnricher

# Option 1: Enrich manually after orchestration
orch = Orchestrator()
result = orch.investigate(case)
result.findings = EvidenceEnricher.enrich_findings(result.findings, case=case)

# Option 2: Create a custom enriching orchestrator
class EnrichedOrchestrator(Orchestrator):
    def investigate(self, case):
        result = super().investigate(case)
        # Enrich all findings
        result.findings = EvidenceEnricher.enrich_findings(result.findings, case=case)
        # Also enrich by-agent findings
        for agent_name in ["billing", "peer", "clinical_rule"]:
            if agent_name in result.findings_by_agent:
                result.findings_by_agent[agent_name] = EvidenceEnricher.enrich_findings(
                    result.findings_by_agent[agent_name], case=case
                )
        return result

orch = EnrichedOrchestrator()
result = orch.investigate(case)
```

## Handling Missing Data

The evidence enricher handles missing data gracefully:

```python
# When baseline is missing:
evidence = {
    "provider_value": 15.22,
    "baseline_value": None,  # Not available
}

enriched = EvidenceEnricher.enrich_finding(finding)

# Result:
assert enriched.evidence["deviation_ratio"] is None  # Not fabricated
assert enriched.evidence["availability"] in ["AVAILABLE", "NOT_AVAILABLE"]
assert enriched.evidence["provenance"]["limitation"] is not None  # Explains why

# Example limitation:
# "Underlying peer statistics were not exported by the Provider ML pipeline; 
#  only blended peer deviation score is available."
```

## Calculations and Formulas

The enricher supports these safe calculations:

### Division (Deviation Ratio)
```python
from multi_agent.evidence import safe_divide, deviation_ratio

ratio = safe_divide(30000.0, 7000.0)  # Returns 4.29
ratio = safe_divide(30000.0, 0)       # Returns None (safe, not inf)
ratio = deviation_ratio(30000.0, 7000.0)  # Same as safe_divide
```

### Deviation (Difference)
```python
from multi_agent.evidence import deviation

dev = deviation(30000.0, 7000.0)  # Returns 23000.0
dev = deviation(None, 7000.0)     # Returns None
```

### Percentage Deviation
```python
from multi_agent.evidence import percentage_deviation

pct = percentage_deviation(30000.0, 7000.0)  # Returns ~328.57%
pct = percentage_deviation(30000.0, 0)       # Returns None (safe)
```

### Threshold Comparison
```python
from multi_agent.evidence import threshold_comparison

comp = threshold_comparison(30000.0, 7000.0, operator=">")   # "ABOVE"
comp = threshold_comparison(30000.0, 7000.0, operator=">=")  # "AT_OR_ABOVE"
comp = threshold_comparison(5000.0, 7000.0, operator="<")    # "BELOW"
```

## Availability States

Evidence fields use explicit availability states:

```python
# AVAILABLE: Field is present and valid
"availability": "AVAILABLE"

# NOT_AVAILABLE: Field was not exported by upstream ML pipeline
"availability": "NOT_AVAILABLE"
"provenance": {"limitation": "Underlying peer statistics were not exported..."}

# NOT_APPLICABLE: Field is not relevant to this investigation
"availability": "NOT_APPLICABLE"

# ERROR: Field was present but could not be parsed
"availability": "ERROR"
```

## Deterministic Evidence IDs

Evidence IDs are deterministic based on content:

```python
# Same finding → same evidence ID
finding1 = Finding(..., rule="payment_charge_ratio", ...)
finding2 = Finding(..., rule="payment_charge_ratio", ...)

enriched1 = EvidenceEnricher.enrich_finding(finding1)
enriched2 = EvidenceEnricher.enrich_finding(finding2)

assert enriched1.evidence["evidence_id"] == enriched2.evidence["evidence_id"]
```

This allows consistent evidence tracking and linking across multiple investigations.

## No Fabrication Guarantee

The enricher **never fabricates missing values**:

```python
# If baseline is missing, deviation_ratio is None (not calculated)
evidence = {"provider_value": 15.22, "baseline_value": None}
enriched = EvidenceEnricher.enrich_finding(finding)
assert enriched.evidence["deviation_ratio"] is None  # Not fabricated

# If peer statistics are unavailable, only score is used
evidence = {"peer_deviation_score": 0.95}
# enriched.evidence["peer_median"] remains None
# provenance includes limitation explaining why

# Calculation trace shows exactly what was computed
assert enriched.evidence["calculation"]["formula"] in [
    "observed / baseline",
    "not_applicable",  # When inputs are missing
]
```

## Testing and Debugging

### Print Evidence Metadata

```python
from multi_agent.evidence import EvidenceEnricher
import json

findings = agent.investigate(case)
enriched = EvidenceEnricher.enrich_findings(findings, case=case)

for finding in enriched:
    print(f"Finding: {finding.rule}")
    print(f"Evidence ID: {finding.evidence['evidence_id']}")
    print(f"Provenance: {json.dumps(finding.evidence['provenance'], indent=2)}")
    print(f"Calculation: {json.dumps(finding.evidence['calculation'], indent=2)}")
    print()
```

### Check Availability

```python
# Verify all evidence fields are available
for finding in enriched:
    if finding.evidence.get("availability") != "AVAILABLE":
        print(f"⚠️ {finding.rule}: {finding.evidence.get('availability')}")
        if "limitation" in finding.evidence.get("provenance", {}):
            print(f"   Reason: {finding.evidence['provenance']['limitation']}")
```

### Validate Calculations

```python
# Verify calculation inputs and results
for finding in enriched:
    calc = finding.evidence.get("calculation", {})
    if calc.get("formula") != "not_applicable":
        print(f"Formula: {calc['formula']}")
        print(f"Inputs: {calc['inputs']}")
        print(f"Result: {calc['result']}")
```

## Best Practices

1. **Always Enrich with Case Context**
   ```python
   # Good: includes case context for record_key and provider_group
   enriched = EvidenceEnricher.enrich_findings(findings, case=case)
   
   # Also works but loses context:
   enriched = EvidenceEnricher.enrich_findings(findings)
   ```

2. **Batch Enrich Together**
   ```python
   # Good: efficient
   enriched = EvidenceEnricher.enrich_findings(findings, case=case)
   
   # Also works but less efficient:
   enriched = [EvidenceEnricher.enrich_finding(f, case=case) for f in findings]
   ```

3. **Check Availability Explicitly**
   ```python
   # Instead of assuming evidence is present
   if finding.evidence.get("peer_median") is not None:
       ratio = finding.evidence["deviation_ratio"]
   else:
       # Handle missing data
       print("Peer median unavailable")
   ```

4. **Use Provenance Limitations**
   ```python
   # Explain limitations to investigators
   limitation = finding.evidence["provenance"].get("limitation")
   if limitation:
       print(f"Note: {limitation}")
   ```

## See Also

- [Evidence Contract v1](evidence_contract_v1.md) — Detailed evidence schema
- [Investigation Contract v1](investigation_contract_v1.md) — Case and finding schemas
- [MILESTONE 11 Implementation](MILESTONE_11_IMPLEMENTATION.md) — Technical details
