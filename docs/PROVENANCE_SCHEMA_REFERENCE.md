# PROVENANCE SCHEMA REFERENCE

Complete schema documentation for all provenance objects.

## SourceType Enum

```python
class SourceType(str, Enum):
    DATASET = "dataset"              # Data exported from CSV/database
    MODEL = "model"                  # ML model (joblib, pickle, etc.)
    RULE = "rule"                    # Clinical/business rule
    CONFIGURATION = "configuration"  # Threshold, weight, policy config
    AGENT = "agent"                  # Agent system (billing, peer, etc.)
    DERIVED = "derived"              # Calculated/transformed value
    EXTERNAL = "external"            # External source (LEIE, etc.)
```

## SourceMetadata

Record about where data/calculation came from.

```python
class SourceMetadata(BaseModel):
    source_type: SourceType      # One of enum values above
    source_name: str             # "final_unified_claim_risk.csv"
    source_version: str          # "1.0.0" or "unknown"
    source_artifact: Optional[str] = None  # File path, URL, joblib name
    available: bool = True       # Whether source is accessible
```

### Examples

**Dataset source**:
```python
SourceMetadata(
    source_type="dataset",
    source_name="final_unified_claim_risk.csv",
    source_version="1.0.0",
    source_artifact="/data/claims/final_unified_claim_risk.csv",
    available=True
)
```

**Model source**:
```python
SourceMetadata(
    source_type="model",
    source_name="IsolationForest",
    source_version="1.0.0",
    source_artifact="provider_isolation_forest.joblib",
    available=True
)
```

**Rule source**:
```python
SourceMetadata(
    source_type="rule",
    source_name="High Utilization",
    source_version="1.0.0",
    available=True
)
```

**Unknown version**:
```python
SourceMetadata(
    source_type="model",
    source_name="SomeModel",
    source_version="unknown",  # Not fabricated
    available=True
)
```

## RuleProvenance

Complete record of a rule execution.

```python
class RuleProvenance(BaseModel):
    rule_id: str                    # "R01", "R02", etc.
    rule_name: str                  # "High Payment Charge Ratio"
    rule_version: str               # "1.0.0" or "unknown"
    condition: Optional[str]        # "payment / charge > 2.0"
    threshold: Optional[float]      # 2.0
    threshold_operator: Optional[str] = None  # ">", ">=", "<", "<="
    input_fields: List[str]         # ["payment", "charge"]
    input_values: Dict[str, Any]    # {"payment": 30000, "charge": 7000}
    result: Literal["TRIGGERED", "NOT_TRIGGERED", "NOT_APPLICABLE", "INSUFFICIENT_DATA"]
    timestamp: datetime             # When rule was evaluated
```

### Example

```python
RuleProvenance(
    rule_id="R01",
    rule_name="High Payment Charge Ratio",
    rule_version="1.0.0",
    condition="payment / charge > 2.0",
    threshold=2.0,
    threshold_operator=">",
    input_fields=["payment", "charge"],
    input_values={"payment": 30000, "charge": 7000},
    result="TRIGGERED",
    timestamp=datetime.utcnow()
)
```

## ModelProvenance

Complete record of an ML model used in calculation.

```python
class ModelProvenance(BaseModel):
    model_name: str                 # "IsolationForest", "LogisticRegression"
    model_version: str              # "1.0.0" or "unknown"
    model_artifact: Optional[str] = None  # "provider_isolation_forest.joblib"
    pipeline_name: Optional[str] = None  # "provider_risk_pipeline"
    pipeline_version: str = "unknown"
    feature_set_version: str = "unknown"  # Feature engineering version
    preprocessing_version: str = "unknown"  # Preprocessing step version
    training_timestamp: Optional[datetime] = None
    scoring_timestamp: Optional[datetime] = None
    configuration: Dict[str, Any] = Field(default_factory=dict)
```

### Example

```python
ModelProvenance(
    model_name="IsolationForest",
    model_version="1.0.0",
    model_artifact="provider_isolation_forest.joblib",
    pipeline_name="provider_risk_pipeline",
    pipeline_version="1.0.0",
    feature_set_version="1.0.0",
    preprocessing_version="1.0.0",
    training_timestamp=datetime(2025, 6, 1, 10, 0),
    scoring_timestamp=datetime.utcnow(),
    configuration={
        "contamination": 0.05,
        "random_state": 42,
        "n_estimators": 100
    }
)
```

## TransformationStep

Single step in a data transformation.

```python
class TransformationStep(BaseModel):
    operation: str              # "ratio", "z_score", "percentile"
    formula: str                # "observed / baseline"
    input_fields: List[str]     # ["observed", "baseline"]
    output_field: str           # "deviation_ratio"
```

### Example

```python
TransformationStep(
    operation="ratio",
    formula="observed / baseline",
    input_fields=["payment", "charge"],
    output_field="payment_charge_ratio"
)
```

## AgentExecutionMetadata

Record of a single agent's execution.

```python
class AgentExecutionMetadata(BaseModel):
    execution_id: str           # "EXEC-ABC123DEF456"
    case_id: str                # "CASE-10231"
    agent_name: str             # "billing", "peer", "clinical_rule"
    agent_version: str          # "1.0.0" or "unknown"
    status: Literal["success", "partial", "error", "skipped"]
    error_type: Optional[str] = None  # "KeyError", "ValueError", etc.
    error_message: Optional[str] = None  # Full error message
    started_at: datetime        # ISO8601 timestamp
    completed_at: datetime      # ISO8601 timestamp
    duration_ms: int            # Milliseconds elapsed
    input_sources: List[str] = Field(default_factory=list)  # CSV files read
    input_record_count: Optional[int] = None  # Records processed
    output_evidence_count: int = 0  # Evidence objects created
    output_finding_count: int = 0  # Findings created
    output_evidence_ids: List[str] = Field(default_factory=list)
    configuration_version: str = "unknown"
```

### Example - Success

```python
AgentExecutionMetadata(
    execution_id="EXEC-ABC123DEF456",
    case_id="CASE-10231",
    agent_name="billing",
    agent_version="1.0.0",
    status="success",
    started_at=datetime(2026, 8, 16, 14, 0, 0),
    completed_at=datetime(2026, 8, 16, 14, 0, 2, 340000),  # 2.34 sec
    duration_ms=2340,
    input_sources=["final_unified_claim_risk.csv"],
    input_record_count=10,
    output_evidence_count=3,
    output_finding_count=2,
    output_evidence_ids=["EV-001", "EV-002", "EV-003"],
    configuration_version="1.0.0"
)
```

### Example - Error

```python
AgentExecutionMetadata(
    execution_id="EXEC-XYZ789GHI012",
    case_id="CASE-10231",
    agent_name="peer",
    agent_version="1.0.0",
    status="error",
    error_type="FileNotFoundError",
    error_message="provider_risk_scores.csv not found in expected location",
    started_at=datetime(2026, 8, 16, 14, 0, 2, 500000),
    completed_at=datetime(2026, 8, 16, 14, 0, 2, 750000),
    duration_ms=250,
    output_evidence_count=0,
    output_finding_count=0
)
```

## RoutingDecision

Single routing decision for one agent.

```python
class RoutingDecision(BaseModel):
    agent_name: str                # "billing", "peer", "clinical_rule"
    selected: bool                 # Whether agent will run
    reason: Optional[str] = None   # "claim_anomaly >= 70"
```

## RoutingMetadata

Complete routing decision set for case.

```python
class RoutingMetadata(BaseModel):
    routing_policy_version: str = "unknown"
    decisions: List[RoutingDecision] = Field(default_factory=list)
    claim_anomaly_score: Optional[float] = None  # 0-100
    provider_anomaly_score: Optional[float] = None  # 0-100
```

### Example

```python
RoutingMetadata(
    routing_policy_version="1.0.0",
    decisions=[
        RoutingDecision(
            agent_name="billing",
            selected=True,
            reason="claim_anomaly (91) >= threshold (70)"
        ),
        RoutingDecision(
            agent_name="peer",
            selected=True,
            reason="provider_anomaly (88) >= threshold (70)"
        ),
        RoutingDecision(
            agent_name="clinical_rule",
            selected=True,
            reason="Always run"
        )
    ],
    claim_anomaly_score=91.0,
    provider_anomaly_score=88.0
)
```

## SynthesisContribution

Single contribution to final score.

```python
class SynthesisContribution(BaseModel):
    source: str                 # "claim_anomaly", "provider_anomaly"
    input_value: float          # 91.0
    weight: float               # 0-1, typically 0.1-0.5
    contribution: float         # input_value * weight
```

## SynthesisMetadata

Risk score synthesis calculation.

```python
class SynthesisMetadata(BaseModel):
    synthesis_method: str = "weighted_sum"  # How final score calculated
    synthesis_version: str = "unknown"
    inputs: Dict[str, float]    # {"claim_anomaly": 91.0, "provider_anomaly": 88.0}
    weights: Dict[str, float]   # {"claim_anomaly": 0.3, "provider_anomaly": 0.3}
    contributions: List[SynthesisContribution]  # Breakdown
    final_score: float          # 0-100, final risk score
    risk_category: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]  # 0-40, 40-70, 70-85, 85+
    priority: Literal["P3", "P2", "P1", "P0"]  # LOW, MEDIUM, HIGH, CRITICAL
    threshold_configuration: Optional[Dict[str, float]] = None  # Thresholds used
    timestamp: datetime         # When synthesis occurred
```

### Example

```python
SynthesisMetadata(
    synthesis_method="weighted_sum",
    synthesis_version="1.0.0",
    inputs={
        "claim_anomaly": 91.0,
        "provider_anomaly": 88.0,
        "clinical_anomaly": 65.0
    },
    weights={
        "claim_anomaly": 0.30,
        "provider_anomaly": 0.30,
        "clinical_anomaly": 0.10
    },
    contributions=[
        SynthesisContribution(source="claim_anomaly", input_value=91.0, weight=0.30, contribution=27.3),
        SynthesisContribution(source="provider_anomaly", input_value=88.0, weight=0.30, contribution=26.4),
        SynthesisContribution(source="clinical_anomaly", input_value=65.0, weight=0.10, contribution=6.5)
    ],
    final_score=88.0,
    risk_category="HIGH",
    priority="P1",
    threshold_configuration={
        "low_threshold": 40,
        "medium_threshold": 70,
        "high_threshold": 85,
        "critical_threshold": 95
    },
    timestamp=datetime.utcnow()
)
```

**Note**: Contributions must sum to <= final_score (other sources may contribute too).

## GenAIMetadata

GenAI explanation generation record.

```python
class GenAIMetadata(BaseModel):
    provider: str               # "Groq"
    model_name: str             # "llama-3.3-70b-versatile"
    model_version: str = "unknown"
    prompt_version: str = "unknown"
    input_case_id: str          # Case being explained
    input_evidence_ids: List[str] = Field(default_factory=list)  # Evidence given to model
    input_finding_count: int = 0  # Finding count
    status: Literal["generated", "unavailable", "error", "disabled"]
    error_message: Optional[str] = None
    generated_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    references_evidence: List[str] = Field(default_factory=list)  # Evidence cited in response
```

### Example - Generated

```python
GenAIMetadata(
    provider="Groq",
    model_name="llama-3.3-70b-versatile",
    model_version="2024-03-28",
    prompt_version="1.0.0",
    input_case_id="CASE-10231",
    input_evidence_ids=["EV-001", "EV-003", "EV-005"],
    input_finding_count=3,
    status="generated",
    generated_at=datetime.utcnow(),
    duration_ms=1240,
    references_evidence=["EV-001", "EV-003"]
)
```

### Example - Unavailable

```python
GenAIMetadata(
    provider="Groq",
    model_name="llama-3.3-70b-versatile",
    input_case_id="CASE-10231",
    input_evidence_ids=[],
    status="unavailable",
    error_message="Groq API rate limit exceeded"
)
```

## CaseTraceMetadata

Top-level trace for entire investigation.

```python
class CaseTraceMetadata(BaseModel):
    trace_id: str               # "TRACE-20260816-ABC123"
    case_id: str                # "CASE-10231"
    claim_id: Optional[str] = None  # "CLAIM-001"
    provider_id: Optional[str] = None  # "NPI-1234567890"
    investigation_started_at: datetime
    investigation_completed_at: Optional[datetime] = None
    agent_executions: List[AgentExecutionMetadata] = Field(default_factory=list)
    routing: Optional[RoutingMetadata] = None
    synthesis: Optional[SynthesisMetadata] = None
    genai: Optional[GenAIMetadata] = None
    execution_order: List[str] = Field(default_factory=list)  # ["routing", "agent:billing", "agent:peer", ...]
    log_file: Optional[str] = None  # Path to investigation log
    debug_enabled: bool = False
```

### Example

```python
CaseTraceMetadata(
    trace_id="TRACE-20260816-ABC123",
    case_id="CASE-10231",
    claim_id="CLAIM-001",
    provider_id="NPI-1234567890",
    investigation_started_at=datetime(2026, 8, 16, 14, 0, 0),
    investigation_completed_at=datetime(2026, 8, 16, 14, 0, 30),
    agent_executions=[
        # Billing agent execution
        # Peer agent execution
        # Clinical rule agent execution
    ],
    routing=RoutingMetadata(...),
    synthesis=SynthesisMetadata(...),
    genai=GenAIMetadata(...),
    execution_order=[
        "ROUTING",
        "AGENT_EXECUTION:billing",
        "AGENT_EXECUTION:peer",
        "AGENT_EXECUTION:clinical_rule",
        "SYNTHESIS",
        "GENAI"
    ],
    log_file="/logs/case-10231-trace.log"
)
```

## Evidence Provenance (M11 Extension)

Evidence schema already includes provenance (from M11):

```python
class Evidence(BaseModel):
    # M11 fields
    evidence_id: str
    agent: str
    rule: Optional[str] = None
    source: str              # Dataset/model/rule name
    source_fields: List[str]  # ["payment", "charge"]
    availability: Literal["AVAILABLE", "NOT_AVAILABLE", "NOT_APPLICABLE", "ERROR"]
    
    # M11 Provenance fields
    provenance: Dict[str, Any] = Field(default_factory=dict)
    # Structure:
    # {
    #     "source": "final_unified_claim_risk.csv",
    #     "limitation": null or "reason",
    #     "calculation": {
    #         "formula": "observed / baseline",
    #         "inputs": {"observed": 30000, "baseline": 7000},
    #         "result": 4.29
    #     },
    #     "model_provenance": {...}  # if ML-derived
    # }
```

## Validation Report

Result of validation operations.

```python
class ProvenanceReport(BaseModel):
    valid: bool                 # No critical errors
    coverage: float             # 0-100, percentage complete
    errors: List[str]           # Critical issues
    warnings: List[str]         # Missing but non-critical
```

### Example - Valid

```python
ProvenanceReport(
    valid=True,
    coverage=100.0,
    errors=[],
    warnings=[]
)
```

### Example - Incomplete

```python
ProvenanceReport(
    valid=True,  # Still valid (>= 80%)
    coverage=85.2,
    errors=[],
    warnings=[
        "agent_version not provided (using 'unknown')",
        "error_message not set for error_type"
    ]
)
```

### Example - Invalid

```python
ProvenanceReport(
    valid=False,  # Critical errors
    coverage=40.0,
    errors=[
        "case_id is required",
        "trace_id is required"
    ],
    warnings=[
        "agent_version not provided"
    ]
)
```

---

## Field Naming Conventions

- **ID fields**: End with `_id` (case_id, trace_id, evidence_id)
- **Count fields**: Start with count or end with `_count` (input_record_count, output_evidence_count)
- **Score fields**: End with `_score` (claim_anomaly_score, final_score)
- **Timestamp fields**: End with `_at` (started_at, completed_at, generated_at)
- **Duration fields**: Named `duration_ms` (milliseconds)
- **Version fields**: End with `_version` (model_version, agent_version)
- **Dict fields**: Named thoughtfully (inputs, weights, contributions, configuration)

## Type Safety

All provenance models use Pydantic v2 with:

```python
model_config = ConfigDict(extra="forbid")  # No extra fields allowed
```

This ensures schema compliance and prevents accidental data leaks.

## Immutability

All provenance objects are effectively immutable:
- Created once via builders
- Never modified after creation
- Stored in lists/dicts for appending new records
- Can be converted to dict for serialization

## Serialization

All models support `.model_dump()` for JSON:

```python
metadata_dict = case_trace.model_dump(mode="json")
# All datetime objects serialized to ISO8601
# All enums serialized to string values
# Ready for API response or storage
```

---

**Last Updated**: 2026-08-16
**Schema Version**: 1.0.0
**Pydantic Version**: 2.13.4
