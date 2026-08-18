# Multi-Agent Investigation Module

## Project Context

This module is the **Multi-Agent Investigation layer** of our Cognizant
Hackathon 2026 healthcare/Medicare fraud detection system.

The upstream ML modules produce claim-level and provider-level
anomaly/risk signals. This module turns those signals into a
**structured, evidence-driven investigation** by coordinating:

-   Billing Agent
-   Peer Benchmark Agent
-   Clinical / Rule Agent
-   Orchestrator
-   Evidence Aggregation
-   Deterministic Risk Synthesis
-   Groq GenAI Investigation Explanation

The core principle is:

> **Deterministic investigation produces evidence and risk; Groq
> interprets that evidence.**

The LLM is not the authority for numerical risk, rule hits, source
values, or fraud determination.

------------------------------------------------------------------------

# 1. Purpose and Role

The Multi-Agent Module answers:

> **Why is a claim/provider suspicious, what evidence supports that
> suspicion, and which investigation dimensions require attention?**

It sits between the upstream ML layer and the downstream
RAG/explainability layer.

``` text
Provider ML ───────┐
                   ├──> Multi-Agent Investigation ──> RAG / Explainability
Claims ML ─────────┘
```

The module performs investigation rather than merely classification.

It combines:

-   Claim anomaly information
-   Provider anomaly information
-   Billing/utilization evidence
-   Peer/geographic benchmark evidence
-   Deterministic rule evidence
-   LEIE evidence where available
-   Data availability
-   Provenance
-   Investigation findings
-   Deterministic risk synthesis

------------------------------------------------------------------------

# 2. Architecture

``` text
                    ┌────────────────────────────┐
                    │     INVESTIGATION ENTRY    │
                    │      / API / Service       │
                    └─────────────┬──────────────┘
                                  │
                                  ▼
                    ┌────────────────────────────┐
                    │ CASE / CONTEXT BUILDER     │
                    │ Claim + Provider + ML data │
                    │ Availability + provenance  │
                    └─────────────┬──────────────┘
                                  │
                                  ▼
                    ┌────────────────────────────┐
                    │       ORCHESTRATOR          │
                    │ Case creation               │
                    │ Routing policy              │
                    │ Agent execution             │
                    └─────────────┬──────────────┘
                                  │
                    ┌─────────────┼─────────────┐
                    ▼             ▼             ▼
             ┌────────────┐ ┌────────────┐ ┌──────────────┐
             │  BILLING   │ │    PEER    │ │  CLINICAL /  │
             │   AGENT    │ │   AGENT    │ │ RULE AGENT   │
             └─────┬──────┘ └─────┬──────┘ └──────┬───────┘
                   │              │               │
                   └──────────────┼───────────────┘
                                  ▼
                    ┌────────────────────────────┐
                    │    EVIDENCE AGGREGATOR     │
                    │ Findings + evidence        │
                    │ Deduplication + provenance │
                    └─────────────┬──────────────┘
                                  │
                                  ▼
                    ┌────────────────────────────┐
                    │  DETERMINISTIC SYNTHESIS   │
                    │ Score + category + priority│
                    └─────────────┬──────────────┘
                                  │
                                  ▼
                    ┌────────────────────────────┐
                    │    INVESTIGATION CASE      │
                    │ Versioned structured output│
                    └─────────────┬──────────────┘
                                  │
                                  ▼
                    ┌────────────────────────────┐
                    │      GROQ EXPLANATION      │
                    │ Evidence-grounded language │
                    └─────────────┬──────────────┘
                                  │
                                  ▼
                    ┌────────────────────────────┐
                    │       RAG HANDOFF          │
                    │ Frozen investigation       │
                    │ contract + provenance      │
                    └────────────────────────────┘
```

------------------------------------------------------------------------

# 3. Current Architecture (Phase 3/4 Hardening)

The module follows a two-layer pattern:

1. Deterministic case selection and evidence collection
2. Optional LLM guidance for rationale, synthesis, and narrative explanation

The orchestrator first computes a routing decision using deterministic rules and then, when enabled, calls a redacted LLM planner to add a per-agent rationale. That rationale is passed to each specialist as a `focus_hint`, but it is never allowed to alter the frozen risk formula.

```python
routing = self._select_agents(case)
if self.enable_llm_agent_reasoning:
    llm_plan = self._llm_plan(case)
    routing.update(llm_plan)

for agent_name in self.AGENT_ORDER:
    route = routing[agent_name]
    result = self.billing_agent.investigate_with_llm(
        case,
        focus_hint=route.get("rationale") or route.get("reason"),
    )
```

Critical hardening decisions:

- Redaction is applied before every LLM call for `claim_id`, `provider_id`, `provider_npi`, and `bene_id` using `redact_for_llm()`.
- Grounding checks enforce that agent narratives only reference numbers that appear in tool outputs.
- Determinism checks confirm that `investigation_risk_score` and priority remain identical whether LLM reasoning is enabled or disabled.
- Agent execution is parallelized for the independent billing / peer / clinical stages after the plan is fixed, while synthesis still occurs once all results are assembled.

------------------------------------------------------------------------

# 4. Core Design Principles

## 3.1 Deterministic first

Each specialist follows:

``` text
Input
  ↓
Deterministic investigation logic
  ↓
Evidence
  ↓
Structured AgentResult
  ↓
Optional GenAI interpretation
```

Agents are not simply LLM prompts.

## 3.2 Evidence before explanation

Evidence should answer:

-   What happened?
-   What was observed?
-   What was the provider/claim value?
-   What was the baseline?
-   How different was it?
-   Where did the value come from?
-   Which agent produced it?

## 3.3 Contract-driven architecture

Agents do not return arbitrary dictionaries. They use shared schemas.

## 3.4 Data access is separated from investigation logic

Agents consume structured contexts/repositories rather than directly
reading CSV files.

Core concepts:

``` text
ClaimContext
ProviderContext
ClaimStore
ProviderStore
```

## 3.5 Reproducibility

For the same inputs, ML outputs, configuration and pipeline version,
deterministic investigation results should be reproducible.

------------------------------------------------------------------------

# 4. Milestone History

## Milestone 1 --- Schemas and Data Stores

Established the foundation of the investigation system.

Core concepts:

``` text
ClaimContext
ProviderContext
InvestigationCase
Finding
ClaimStore
ProviderStore
```

The stores provide controlled access to claim/provider information.

Agents do not own CSV-loading logic.

### Outcome

The investigation layer receives normalized context instead of coupling
each agent directly to source files.

------------------------------------------------------------------------

## Milestone 2 --- Billing Agent

Implemented the Billing Agent for claim-level financial and utilization
investigation.

It evaluates available signals such as:

-   Claim anomaly
-   Claim amount/payment information
-   Claim frequency
-   Service frequency
-   Repeated/similar behavior
-   Temporal behavior
-   Procedure-related evidence where available
-   Utilization abnormalities

The output is structured evidence and findings rather than a simple
fraud declaration.

------------------------------------------------------------------------

## Milestone 3 --- Peer Benchmark Agent

Implemented the Peer Benchmark Agent.

Its purpose is to identify provider behavior that is unusual relative to
appropriate peer/geographic benchmarks.

Investigation dimensions include:

``` text
service deviation
payment deviation
beneficiary deviation
service-mix deviation
geographic deviation
```

The agent is designed to preserve underlying quantitative evidence
rather than expose only a blended peer score.

Example:

``` text
Provider services = 20,000
Peer median       = 5,000
Deviation ratio   = 4.0x
Percentile        = 98.7
```

This is substantially more useful for investigation than:

``` text
peer_deviation_score = 0.93
```

alone.

------------------------------------------------------------------------

## Milestone 4 --- Clinical / Rule Agent

Implemented the deterministic Clinical/Rule Agent.

It is a rule engine, not an LLM-based fraud detector.

Representative rules include:

``` text
R01 → excessive service frequency
R02 → unusual procedure/diagnosis combination
R03 → extreme utilization
R04 → abnormal payment/service ratio
R05 → unusual temporal pattern
R06 → LEIE evidence
```

Rules generate rule hits, findings and supporting evidence.

A rule hit indicates review-worthy behavior. It does not prove fraud.

------------------------------------------------------------------------

## Milestone 5 --- Evidence Aggregation and Deterministic Synthesis

Implemented evidence aggregation and risk synthesis.

Important upstream ML fields remain preserved:

``` text
CLAIM_RISK_SCORE
FINAL_RISK_LEVEL
FINAL_RISK_PRIORITY
FINAL_CLAIM_RANK
```

These are not silently overwritten.

The system distinguishes:

``` text
upstream ML risk
```

from:

``` text
deterministic investigation risk
```

Agent findings are grouped by:

``` text
billing
peer
clinical_rule
```

Duplicate substantive evidence is avoided while retaining meaningful
upstream evidence.

------------------------------------------------------------------------

## Milestone 6 --- Orchestrator and Routing

Implemented the Orchestrator as the coordination layer.

Responsibilities:

1.  Create/receive investigation context
2.  Read claim/provider risk signals
3.  Apply routing policy
4.  Select relevant agents
5.  Execute selected agents
6.  Collect structured results
7.  Send results to aggregation/synthesis

The system does not blindly execute every agent.

Example routing:

``` text
High Claim + Low Provider
→ Billing + Rule

Low Claim + High Provider
→ Peer + Rule

High Claim + High Provider
→ Billing + Peer + Rule
```

Conditional routing is what makes the architecture genuinely multi-agent
rather than a fixed sequence of independent prompts.

------------------------------------------------------------------------

## Milestone 7 --- End-to-End Pipeline Validation

Validated the complete investigation path:

``` text
Investigation request
        ↓
Context creation
        ↓
Orchestrator
        ↓
Agent routing
        ↓
Specialist agents
        ↓
Evidence aggregation
        ↓
Risk synthesis
        ↓
InvestigationCase
```

Validation included normal and edge-case behavior.

------------------------------------------------------------------------

## Milestone 8 --- Groq GenAI Investigation Explanation Layer

Added the GenAI explanation layer using **Groq**.

The architecture is:

``` text
Deterministic investigation
          ↓
Structured evidence
          ↓
Risk synthesis
          ↓
InvestigationCase
          ↓
Groq
          ↓
Human-readable explanation
```

Groq does not replace the investigation logic.

It interprets the already-produced investigation result.

------------------------------------------------------------------------

# 5. Investigation Context

`InvestigationContext` is the common input boundary for specialist
agents.

Conceptually:

``` text
InvestigationContext
│
├── claim information
├── provider information
├── claim anomaly
├── provider anomaly
├── claim features
├── provider features
├── peer information
├── LEIE information
├── data availability
└── provenance
```

Agents should not independently fetch arbitrary source data.

------------------------------------------------------------------------

# 6. Specialist Agents

## 6.1 Billing Agent

### Objective

Investigate suspicious claim-level billing and utilization behavior.

### Input

``` text
ClaimContext
ProviderContext
claim anomaly
claim features
```

### Analysis

Depending on available claim-type data:

-   Financial deviation
-   Payment/charge relationships
-   Claim frequency
-   Service frequency
-   Repeated behavior
-   Temporal behavior
-   Procedure/diagnosis counts
-   Utilization abnormalities

### Output

``` json
{
  "agent": "billing",
  "status": "success",
  "score": 84,
  "risk": "HIGH",
  "findings": [],
  "evidence": [],
  "limitations": [],
  "provenance": {}
}
```

Evidence availability is claim-type dependent.

------------------------------------------------------------------------

## 6.2 Peer Benchmark Agent

### Objective

Determine whether provider behavior is unusual compared with peers or
geographic benchmarks.

### Input

``` text
ProviderContext
peer metrics
geographic metrics
provider risk
```

### Analysis

Where available:

``` text
service deviation
payment deviation
beneficiary deviation
service mix deviation
geographic deviation
```

### Output

Quantitative findings backed by evidence:

``` text
provider value
peer mean
peer median
peer std
deviation ratio
percentile
peer group
peer sample size
```

The agent should expose the comparison behind the score.

------------------------------------------------------------------------

## 6.3 Clinical / Rule Agent

### Objective

Apply deterministic domain/consistency rules.

### Input

``` text
ClaimContext
ProviderContext
available evidence
LEIE evidence
```

### Output

``` text
rule hits
findings
evidence
score
limitations
```

Rule hits indicate review-worthy behavior, not confirmed fraud.

------------------------------------------------------------------------

# 7. Orchestrator

The Orchestrator coordinates investigation.

``` text
Case creation
     ↓
Routing
     ↓
Agent selection
     ↓
Execution
     ↓
Result collection
     ↓
Aggregation
```

It uses claim/provider risk signals to determine which investigation
dimensions need deeper analysis.

------------------------------------------------------------------------

# 8. Agent Execution Contract

Every specialist returns the common structure:

``` json
{
  "agent": "peer",
  "status": "success",
  "score": 91,
  "risk": "HIGH",
  "findings": [],
  "evidence": [],
  "limitations": [],
  "provenance": {}
}
```

The exact frozen schema is authoritative.

Agent failures or unavailable evidence must be represented explicitly
rather than converted into fabricated or silently zeroed results.

------------------------------------------------------------------------

# 9. Evidence Contract

Evidence is the most important output of the investigation layer.

A rich peer evidence record can contain:

``` json
{
  "evidence_id": "EV-001",
  "agent": "peer",
  "category": "utilization",
  "metric": "services",
  "provider_value": 20000,
  "peer_mean": 6200,
  "peer_median": 5000,
  "peer_std": 2100,
  "deviation_ratio": 4.0,
  "percentile": 98.7,
  "peer_group": "Cardiology-TX",
  "peer_sample_size": 184,
  "source": "provider_risk_scores.csv",
  "source_fields": [
    "Tot_Srvcs",
    "Provider_Type",
    "Prvdr_State"
  ]
}
```

The contract is designed to answer:

``` text
What happened?
What was observed?
What was the baseline?
How different was it?
Where did the value come from?
```

------------------------------------------------------------------------

# 10. Evidence Availability

The Claims ML audit identified unequal evidence availability by claim
type.

### CARRIER

Some financial fields are first-line rather than claim-total evidence.
Several internally computed features were not originally exported.

### INPATIENT

Several valuable financial, temporal, utilization and length-of-stay
fields existed internally but were not initially exported.

### OUTPATIENT

The richest exported evidence set is available here, including
financial, utilization, procedure/diagnosis counts, temporal and
rule-related evidence.

### Provider

Provider ML provides core risk information and peer/geographic scores.
Investigation-quality peer evidence requires underlying benchmark values
where available, not only blended scores.

The Multi-Agent layer records unavailable/limited evidence rather than
inventing values.

------------------------------------------------------------------------

# 11. Provenance

Investigation outputs are traceable through:

``` text
Source data
    ↓
Source field(s)
    ↓
Derived metric
    ↓
Agent evidence
    ↓
Finding
    ↓
Risk synthesis
    ↓
GenAI explanation
```

The system distinguishes:

-   Observed source values
-   Derived metrics
-   Agent findings
-   Deterministic scores
-   GenAI-generated wording

This is critical for auditability.

------------------------------------------------------------------------

# 12. Deterministic Risk Synthesis

Numerical investigation risk is calculated by deterministic code.

It is **not generated by Groq**.

The target structure is:

``` text
Claim anomaly
Provider anomaly
Peer score
Billing score
Rule score
        ↓
Investigation risk
        ↓
Risk category
        ↓
Priority
```

The previously defined target configuration uses transparent weighted
aggregation rather than arbitrary LLM scoring.

The important distinction is:

``` text
ML risk ≠ investigation risk
```

The upstream ML values remain preserved.

------------------------------------------------------------------------

# 13. Investigation Case

All results are represented as one standardized case.

Conceptually:

``` json
{
  "case_id": "CASE-10231",
  "provider_id": "P10023",
  "claim_id": "CLM10231",

  "claim_anomaly": 91,
  "provider_anomaly": 88,

  "billing_score": 86,
  "peer_score": 93,
  "rule_score": 72,

  "overall_risk": 88,
  "risk_category": "CRITICAL",
  "priority": "P0",

  "findings": [],
  "evidence": [],
  "explanation": ""
}
```

The frozen schema is authoritative over this conceptual example.

------------------------------------------------------------------------

# 14. Groq GenAI Explanation

Groq receives controlled investigation information such as:

``` text
InvestigationCase
Findings
Evidence
Risk synthesis
Limitations
Provenance
```

It generates a human-readable investigation explanation.

It may explain:

-   Why the case was flagged
-   Which findings are significant
-   What evidence supports each finding
-   What limitations exist
-   What should be reviewed

It must not:

-   Invent evidence
-   Create source values
-   Change deterministic scores
-   Change risk category
-   Create unsupported rule hits
-   Treat missing data as available
-   Claim fraud is proven solely from anomaly detection

The core rule is:

> **Evidence is authoritative; Groq text is interpretive.**

------------------------------------------------------------------------

# 15. Multi-Agent vs RAG

  --------------------------------------------------------------------------------
  Component               Multi-Agent             RAG / Explainability
                          Investigation           
  ----------------------- ----------------------- --------------------------------
  Main purpose            Investigate suspicious  Explain/retrieve/contextualize
                          behavior                

  Primary input           Claim/provider ML data  Investigation case + knowledge

  Deterministic analysis  Yes                     Not the primary role

  Specialist agents       Yes                     No

  Evidence generation     Yes                     Consumes evidence

  Risk calculation        Yes                     Should not override it

  Rule execution          Yes                     No

  Peer benchmarking       Yes                     Consumes result

  LLM                     Groq for controlled     RAG/LLM for downstream
                          interpretation          explanation/Q&A

  Provenance              Produced                Consumed

  Numerical risk          Multi-Agent synthesis   No
  authority                                       
  --------------------------------------------------------------------------------

### Why both exist

The Multi-Agent layer determines **what the investigation found**.

The RAG layer helps answer **questions about the investigation and
supporting knowledge**.

RAG should consume the frozen investigation contract rather than
recreate agent logic.

------------------------------------------------------------------------

# 16. Contract Hardening After Milestone 8

## Milestone 9 --- Investigation Contract v1

Frozen schemas:

``` text
InvestigationContext
AgentResult
Evidence
Finding
RuleHit
AgentExecution
RiskSynthesis
InvestigationCase
GenAIExplanation
```

This prevents arbitrary agent outputs.

------------------------------------------------------------------------

## Milestone 10 --- Data Contract Validation

Validated incoming claim/provider information for:

-   Required identifiers
-   Correct types
-   Risk ranges
-   Claim/provider linkage
-   Evidence availability
-   Claim-type-specific fields
-   Schema compatibility

Invalid or incomplete data is surfaced explicitly.

------------------------------------------------------------------------

## Milestone 11 --- Evidence Enrichment

Expanded evidence so findings contain measurements instead of only
high-level scores.

Target evidence includes, where available:

``` text
value
baseline
deviation
ratio
percentile
group
sample size
source
source fields
```

This is especially important for peer investigation.

------------------------------------------------------------------------

## Milestone 12 --- Provenance

Added explicit source/provenance information connecting evidence back to
source data and calculations.

------------------------------------------------------------------------

## Milestone 13 --- Risk/Synthesis Freeze

Frozen deterministic risk synthesis so:

``` text
same inputs
+
same configuration
=
same investigation risk
```

Groq cannot modify the deterministic numerical result.

------------------------------------------------------------------------

## Milestone 14 --- RAG Handoff Contract

Defined the stable interface between Multi-Agent and RAG.

The handoff contains the structured investigation result, findings,
evidence, provenance and limitations.

RAG integrates against this contract rather than individual agent
internals.

------------------------------------------------------------------------

## Milestone 15 --- Groq Guardrails + Failure Testing + Anti-Hallucination Testing

Hardened the Groq layer against:

-   Missing evidence
-   Partial evidence
-   Agent failure
-   Conflicting signals
-   Unsupported claims
-   Invalid generated output
-   Numerical/risk manipulation
-   Hallucinated source values

The deterministic investigation remains authoritative.

------------------------------------------------------------------------

## Final Milestone --- End-to-End Validation + RAG Handoff

Validated the complete path:

``` text
ML outputs
   ↓
InvestigationContext
   ↓
Orchestrator
   ↓
Conditional Agent Routing
   ↓
Billing / Peer / Clinical Rule
   ↓
Evidence Aggregation
   ↓
Deterministic Risk Synthesis
   ↓
InvestigationCase
   ↓
Provenance
   ↓
Groq Explanation
   ↓
Guardrails
   ↓
RAG Handoff Contract
```

At this boundary the Multi-Agent module is ready for integration by the
RAG/explainability team.

------------------------------------------------------------------------

# 17. Failure Handling

The module distinguishes states such as:

``` text
SUCCESS
UNAVAILABLE
LIMITED
ERROR
```

Examples:

``` text
Provider data missing
→ Peer evidence unavailable

Claim-type field not exported
→ Evidence unavailable

Agent execution error
→ Agent marked failed
→ Case continues where possible
```

Missing evidence must never become fabricated evidence.

------------------------------------------------------------------------

# 18. Testing Strategy

## Unit tests

Cover:

``` text
metric calculations
rules
routing
risk synthesis
schema validation
evidence construction
```

## Agent tests

Cover:

``` text
Billing Agent
Peer Agent
Clinical Rule Agent
```

with known inputs and expected outputs.

## Orchestrator tests

Cover:

``` text
High claim + Low provider
Low claim + High provider
High claim + High provider
Low + Low
Missing provider
Missing peer data
```

## Claim-type tests

Cover:

``` text
CARRIER
INPATIENT
OUTPATIENT
```

because evidence availability differs.

## GenAI tests

Cover:

``` text
normal evidence
missing evidence
conflicting evidence
agent failure
unsupported claims
hallucination attempts
```

## End-to-end tests

Validate:

``` text
request
→ context
→ routing
→ agents
→ evidence
→ synthesis
→ Groq
→ final handoff contract
```

------------------------------------------------------------------------

# 19. Important Technical Decisions

### Why not make every agent an LLM?

Because investigation evidence must be reproducible and auditable.

### Why multiple agents?

Each specializes in a distinct investigation dimension:

``` text
Billing → claim behavior
Peer → provider comparison
Rule → domain/consistency checks
```

### Why conditional routing?

Different suspicious cases require different investigation paths.

### Why preserve provenance?

Every important finding must be traceable.

### Why separate ML risk from investigation risk?

ML detects anomalies; Multi-Agent investigates them.

### Why keep Groq downstream?

The LLM explains evidence instead of becoming the source of evidence.

------------------------------------------------------------------------

# 20. Final Handoff Contents

The Multi-Agent module provides:

``` text
✓ Investigation schemas
✓ Claim/provider contexts
✓ ClaimStore / ProviderStore
✓ Billing Agent
✓ Peer Benchmark Agent
✓ Clinical / Rule Agent
✓ Conditional Orchestrator
✓ Evidence aggregation
✓ Deterministic risk synthesis
✓ InvestigationCase
✓ Evidence enrichment
✓ Provenance
✓ Groq explanation layer
✓ Groq guardrails
✓ Failure testing
✓ Anti-hallucination testing
✓ RAG handoff contract
✓ End-to-end validation
```

The RAG team should integrate against the **frozen InvestigationCase /
RAG handoff contract**, not internal agent implementations.

------------------------------------------------------------------------

# 21. Developer Quick Reference

``` text
INPUT
  Claim + Provider ML outputs
          │
          ▼
InvestigationContext
          │
          ▼
Orchestrator
          │
          ├── BillingAgent
          ├── PeerAgent
          └── ClinicalRuleAgent
                    │
                    ▼
             AgentResult[]
                    │
                    ▼
           Evidence Aggregation
                    │
                    ▼
           Risk/Synthesis Engine
                    │
                    ▼
           InvestigationCase
                    │
                    ▼
             Groq Explanation
                    │
                    ▼
           RAG Handoff Contract
```

## Core rule

> **The Multi-Agent Module produces investigation evidence and
> deterministic risk. Groq explains that investigation. RAG consumes the
> frozen investigation contract for downstream explainability and
> retrieval.**

------------------------------------------------------------------------

# 22. Running the Multi-Agent System

## Prerequisites

- Python 3.10.11+
- Dependencies: `pip install -r requirements.txt`
- Environment variables configured (see below)
- Real claim and provider data loaded via ETL pipeline

## Environment Setup

```bash
# Set PYTHONPATH to include the workspace root
export PYTHONPATH="."

# Configure Groq API (optional, for LLM-powered explanations)
export GROQ_API_KEY="your-groq-api-key"
export GROQ_MODEL="openai/gpt-oss-120b"

# Optional: Disable LLM reasoning for faster deterministic mode
export ENABLE_LLM_AGENT_REASONING="false"
export ENABLE_GENAI_EXPLANATION="false"
```

## Installation

```bash
# Install required packages
pip install -r requirements.txt

# Optional: Install Groq SDK for live LLM integration
pip install groq
```

## Basic Usage

### 1. Investigate a Single Claim

```python
from multi_agent.orchestrator import Orchestrator

# Create orchestrator instance
orchestrator = Orchestrator(
    enable_genai_explanation=True,      # Enable Groq explanations
    enable_llm_agent_reasoning=True     # Enable LLM-backed agent reasoning
)

# Investigate a claim by claim_id
result = orchestrator.investigate_claim(claim_id="YOUR_CLAIM_ID")

# Access investigation results
print(f"Case ID: {result.case_id}")
print(f"Risk Score: {result.investigation_risk_score}")
print(f"Priority: {result.investigation_priority}")
print(f"Findings: {len(result.findings)}")
print(f"Explanation: {result.explanation}")

# Access findings by agent
print(f"Billing Findings: {result.findings_by_agent['billing']}")
print(f"Peer Findings: {result.findings_by_agent['peer']}")
print(f"Clinical Findings: {result.findings_by_agent['clinical_rule']}")
```

### 2. Investigate a Provider

```python
from multi_agent.orchestrator import Orchestrator

orchestrator = Orchestrator()

# Investigate a provider by NPI
result = orchestrator.investigate_provider(npi=1003569997)

print(f"Provider NPI: {result.provider_npi}")
print(f"Provider Risk Score: {result.provider_risk_score}")
print(f"Investigation Risk: {result.investigation_risk_score}")
print(f"Peer Agent Findings: {result.findings_by_agent['peer']}")
```

### 3. Use the Orchestrator Directly

```python
from multi_agent.orchestrator import Orchestrator
from multi_agent.data.claim_store import ClaimStore
from multi_agent.schemas.investigation_case import InvestigationCase

# Load claim data
claim_store = ClaimStore()
claim = claim_store.get_claim(claim_id="YOUR_CLAIM_ID")

# Create investigation case
case = InvestigationCase(
    case_id=f"case-{claim.claim_id}",
    claim_id=claim.claim_id,
    claim=claim
)

# Run investigation
orchestrator = Orchestrator()
result = orchestrator.investigate(case)

print(f"Investigation Complete: {result.case_id}")
print(f"Total Findings: {result.summary.get('total_findings')}")
print(f"Selected Agents: {result.summary.get('selected_agents')}")
```

### 4. Build RAG Handoff

```python
from multi_agent.orchestrator import Orchestrator
from multi_agent.rag.handoff import build_rag_handoff

# Run investigation
orchestrator = Orchestrator(enable_genai_explanation=False)
result = orchestrator.investigate_claim(claim_id="YOUR_CLAIM_ID")

# Convert to RAG handoff contract
rag_handoff = build_rag_handoff(result)

print(f"RAG Case ID: {rag_handoff.case.case_id}")
print(f"Risk Synthesis: {rag_handoff.risk_synthesis.overall_risk}")
print(f"Findings Count: {len(rag_handoff.findings)}")

# Serialize to JSON for downstream consumption
import json
rag_json = json.dumps(
    rag_handoff.model_dump(mode='json', exclude_none=True),
    indent=2
)
```

## Running Tests

### All Multi-Agent Tests

```bash
cd /path/to/workspace
export PYTHONPATH="."

# Run full test suite
python -m pytest multi_agent/tests -v

# Run with coverage
python -m pytest multi_agent/tests --cov=multi_agent --cov-report=html

# Run specific test file
python -m pytest multi_agent/tests/test_end_to_end.py -v

# Run specific test
python -m pytest multi_agent/tests/test_end_to_end.py::test_full_claim_pipeline_end_to_end -v
```

### Test Categories

```bash
# Agent-specific tests
python -m pytest multi_agent/tests/test_billing_agent.py -v
python -m pytest multi_agent/tests/test_peer_agent.py -v
python -m pytest multi_agent/tests/test_clinical_rule_agent.py -v

# Orchestrator tests
python -m pytest multi_agent/tests/test_orchestrator.py -v

# End-to-end tests
python -m pytest multi_agent/tests/test_end_to_end.py -v

# Contract validation tests
python -m pytest multi_agent/tests/test_investigation_contract_v1.py -v
python -m pytest multi_agent/tests/test_data_contract_validation_v1.py -v

# Evidence and provenance tests
python -m pytest multi_agent/tests/test_evidence_enrichment.py -v
python -m pytest multi_agent/tests/test_provenance.py -v
```

### Quick Test Verification

```bash
# Verify agent removal (should return 0 results)
grep -r "claim_agent\|ClaimAgent" multi_agent/ --include="*.py"

# Verify architecture (should show 3 agents)
grep "AGENT_ORDER" multi_agent/orchestrator.py

# Run quick sanity check
python -c "
from multi_agent.orchestrator import Orchestrator
o = Orchestrator()
print('✓ Orchestrator initialized')
print(f'✓ Agent order: {o.AGENT_ORDER}')
"
```

## Running the Investigation Demo Script

```bash
# Run the demo investigation script
python multi_agent/scripts/run_investigation_demo.py --claim-id YOUR_CLAIM_ID

# With provider investigation
python multi_agent/scripts/run_investigation_demo.py --npi 1003569997

# With LLM explanations enabled
ENABLE_GENAI_EXPLANATION=true python multi_agent/scripts/run_investigation_demo.py --claim-id YOUR_CLAIM_ID
```

## Advanced Configuration

### Disable LLM Reasoning (Deterministic Mode)

```python
from multi_agent.orchestrator import Orchestrator

# Run purely deterministic investigation (no LLM)
orchestrator = Orchestrator(
    enable_genai_explanation=False,
    enable_llm_agent_reasoning=False
)

result = orchestrator.investigate_claim(claim_id="YOUR_CLAIM_ID")
# Explanation will be generated from deterministic rules only
```

### Custom Agent Configuration

```python
from multi_agent.orchestrator import Orchestrator
from multi_agent.agents.billing_agent import BillingAgent
from multi_agent.data.claim_store import ClaimStore

# Create custom agent instances
claim_store = ClaimStore()
custom_billing_agent = BillingAgent()

# Create orchestrator with custom agents
orchestrator = Orchestrator(
    claim_store=claim_store,
    billing_agent=custom_billing_agent,
    enable_genai_explanation=True
)

result = orchestrator.investigate_claim(claim_id="YOUR_CLAIM_ID")
```

### Latency and Timing

```python
import time
from multi_agent.orchestrator import Orchestrator

orchestrator = Orchestrator(enable_genai_explanation=True)

start = time.perf_counter()
result = orchestrator.investigate_claim(claim_id="YOUR_CLAIM_ID")
elapsed = time.perf_counter() - start

print(f"Investigation time: {elapsed:.2f}s")
print(f"Orchestrator total: {result.diagnostic_timing.get('orchestrator_total_seconds'):.2f}s")
print(f"Explanation status: {result.summary.get('explanation_status')}")
print(f"Selected agents: {result.summary.get('selected_agents')}")
```

## Troubleshooting

### Common Issues

**Q: Investigation returns no findings**
- Normal for low-risk claims. Check `selected_agents` in summary to see which agents ran.
- Verify claim data is loaded: `claim_store.get_claim(claim_id)` should not be None.

**Q: Groq explanation unavailable**
- Check GROQ_API_KEY is set: `echo $GROQ_API_KEY`
- Verify model is available in your account
- Set `enable_genai_explanation=False` to use deterministic mode

**Q: Tests timeout**
- Tests include real data loads and parallel execution. May take 5-10 minutes.
- Run subset: `python -m pytest multi_agent/tests/test_orchestrator.py -v`

**Q: ImportError for multi_agent modules**
- Ensure PYTHONPATH is set: `export PYTHONPATH="."`
- Run from workspace root directory

### Enabling Debug Logging

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('multi_agent')
logger.setLevel(logging.DEBUG)

# Now run investigation with debug output
from multi_agent.orchestrator import Orchestrator
result = Orchestrator().investigate_claim(claim_id="YOUR_CLAIM_ID")
```

------------------------------------------------------------------------

# 23. Maintenance Rule

Any future change to the module should update:

1.  Contract/schema version
2.  Agent output contract
3.  Evidence/provenance behavior
4.  Risk synthesis configuration
5.  RAG handoff contract
6.  Tests
7.  This README

