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

# 3. Core Design Principles

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

# 22. Maintenance Rule

Any future change to the module should update:

1.  Contract/schema version
2.  Agent output contract
3.  Evidence/provenance behavior
4.  Risk synthesis configuration
5.  RAG handoff contract
6.  Tests
7.  This README

