"""Pydantic models for provenance metadata.

These models provide strong typing for provenance tracking across the investigation pipeline.
All models use ConfigDict(extra="forbid") to enforce strict schema compliance.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class SourceType(str, Enum):
    """Enumeration of valid source types in the investigation pipeline."""

    DATASET = "dataset"  # CSV exports, database tables
    MODEL = "model"  # ML model artifacts (joblib, pkl)
    RULE = "rule"  # Clinical/business rule
    CONFIGURATION = "configuration"  # Thresholds, weights, policies
    AGENT = "agent"  # Agent name/type
    DERIVED = "derived"  # Calculated/transformed values
    EXTERNAL = "external"  # External data (LEIE, benchmarks)


class SourceMetadata(BaseModel):
    """Metadata about a data source.

    Examples:
        Dataset: source_type=DATASET, source_name="provider_risk_scores.csv", version="v1"
        Model: source_type=MODEL, source_name="IsolationForest", artifact="provider_isolation_forest.joblib"
        Rule: source_type=RULE, source_name="R03", version="1.0.0"
    """

    model_config = ConfigDict(extra="forbid")

    source_type: SourceType
    source_name: str = Field(..., min_length=1, description="Dataset, model, or rule name")
    source_version: Optional[str] = Field(
        None, description="Version or timestamp; 'unknown' if not available"
    )
    source_artifact: Optional[str] = Field(None, description="File path or artifact ID")
    available: bool = Field(True, description="Whether source exists and is accessible")


class RuleProvenance(BaseModel):
    """Provenance for clinical/business rule findings.

    Documents the rule that triggered, its configuration, inputs, and result.
    Enables investigators to understand exactly why a rule was triggered.
    """

    model_config = ConfigDict(extra="forbid")

    rule_id: str = Field(..., min_length=1, description="Rule identifier")
    rule_name: str = Field(..., min_length=1, description="Human-readable rule name")
    rule_version: Optional[str] = Field(None, description="Rule version; 'unknown' if not tracked")

    condition: Optional[str] = Field(None, description="Rule condition (e.g., 'services > 15000')")
    threshold: Optional[float] = Field(None, description="Numerical threshold if applicable")
    threshold_operator: Optional[str] = Field(
        None, description="Operator: >, <, >=, <=, ==, !=", pattern="^(>|<|>=|<=|==|!=)$"
    )

    input_fields: List[str] = Field(default_factory=list, description="Fields used by rule")
    input_values: Dict[str, Any] = Field(
        default_factory=dict, description="Actual input values during execution"
    )

    result: str = Field(
        ..., pattern="^(TRIGGERED|NOT_TRIGGERED|NOT_APPLICABLE|INSUFFICIENT_DATA)$"
    )

    timestamp: Optional[str] = None


class ModelProvenance(BaseModel):
    """Provenance for ML model-derived evidence.

    Documents model name, version, artifact, pipeline, features, and preprocessing.
    Never invents missing versions; uses 'unknown' for unavailable metadata.
    """

    model_config = ConfigDict(extra="forbid")

    model_name: str = Field(..., min_length=1, description="Model type (e.g., 'IsolationForest')")
    model_version: Optional[str] = Field(
        None, description="Semantic version; 'unknown' if not available"
    )
    model_artifact: Optional[str] = Field(None, description="Path to model file (joblib, pkl, etc.)")

    pipeline_name: Optional[str] = Field(None, description="ML pipeline name")
    pipeline_version: Optional[str] = Field(
        None, description="Pipeline version; 'unknown' if not available"
    )

    feature_set_version: Optional[str] = Field(
        None, description="Version of feature engineering; 'unknown' if not tracked"
    )
    preprocessing_version: Optional[str] = Field(
        None, description="Version of preprocessing; 'unknown' if not tracked"
    )

    training_timestamp: Optional[str] = None
    scoring_timestamp: Optional[str] = None

    configuration: Dict[str, Any] = Field(
        default_factory=dict, description="Model hyperparameters or configuration"
    )


class TransformationStep(BaseModel):
    """Single transformation/calculation step in evidence derivation."""

    model_config = ConfigDict(extra="forbid")

    operation: str = Field(
        ...,
        min_length=1,
        description="Operation name (e.g., 'peer_deviation_ratio', 'threshold_check')",
    )
    formula: Optional[str] = Field(None, description="Mathematical formula")
    input_fields: List[str] = Field(default_factory=list, description="Input field names")
    output_field: Optional[str] = Field(None, description="Output field name")


class AgentExecutionMetadata(BaseModel):
    """Comprehensive execution metadata for a single agent run.

    Documents what agent ran, when, how long, what inputs, what outputs,
    configuration versions, and any errors.
    """

    model_config = ConfigDict(extra="forbid")

    execution_id: str = Field(..., min_length=1, description="Unique execution identifier")
    case_id: str = Field(..., min_length=1, description="Case being investigated")
    agent_name: str = Field(..., min_length=1, description="Agent type (billing, peer, clinical_rule)")
    agent_version: Optional[str] = Field(
        None, description="Agent code version; 'unknown' if not tracked"
    )

    status: str = Field(
        ..., pattern="^(success|partial|error|skipped)$", description="Execution status"
    )
    error_type: Optional[str] = Field(None, description="Error type if status=error")
    error_message: Optional[str] = Field(None, description="Error message if status=error")

    started_at: Optional[str] = Field(None, description="ISO8601 timestamp")
    completed_at: Optional[str] = Field(None, description="ISO8601 timestamp")
    duration_ms: Optional[int] = Field(None, ge=0, description="Total execution time")

    input_sources: List[str] = Field(
        default_factory=list, description="Data sources used (CSV, model files, etc.)"
    )
    input_record_count: Optional[int] = Field(None, ge=0, description="Records processed")

    output_evidence_count: int = Field(default=0, ge=0, description="Evidence pieces created")
    output_finding_count: int = Field(default=0, ge=0, description="Findings generated")
    output_evidence_ids: List[str] = Field(
        default_factory=list, description="IDs of generated evidence"
    )

    configuration_version: Optional[str] = Field(
        None, description="Configuration version used"
    )


class RoutingDecision(BaseModel):
    """Documents why an agent was selected or skipped."""

    model_config = ConfigDict(extra="forbid")

    agent_name: str
    selected: bool
    reason: Optional[str] = None


class RoutingMetadata(BaseModel):
    """Orchestrator routing decisions for this case."""

    model_config = ConfigDict(extra="forbid")

    routing_policy_version: Optional[str] = None
    decisions: List[RoutingDecision] = Field(default_factory=list)
    claim_anomaly_score: Optional[float] = None
    provider_anomaly_score: Optional[float] = None


class SynthesisContribution(BaseModel):
    """Contribution of a single component to final synthesis score."""

    model_config = ConfigDict(extra="forbid")

    source: str = Field(..., description="Component name (billing, peer, rule, etc.)")
    input_value: Optional[float] = Field(None, description="Raw input score/metric")
    weight: float = Field(..., ge=0.0, le=1.0, description="Weight applied")
    contribution: float = Field(..., description="Weighted contribution to final score")


class SynthesisMetadata(BaseModel):
    """Comprehensive synthesis/aggregation metadata.

    Documents how the final risk score was calculated, enabling full reconstruction
    of the score from its inputs.
    """

    model_config = ConfigDict(extra="forbid")

    synthesis_method: str = Field(..., description="Aggregation method (weighted_sum, etc.)")
    synthesis_version: Optional[str] = Field(None, description="Synthesis algorithm version")

    inputs: Dict[str, Optional[float]] = Field(
        default_factory=dict,
        description="All input scores (claim_anomaly, peer_score, etc.)",
    )
    weights: Dict[str, float] = Field(
        default_factory=dict, description="Weight for each input"
    )
    contributions: List[SynthesisContribution] = Field(
        default_factory=list, description="Breakdown of each contribution"
    )

    final_score: float = Field(..., ge=0.0, le=100.0, description="Final risk score")
    risk_category: str = Field(..., description="Risk level (LOW, MEDIUM, HIGH, CRITICAL)")
    priority: str = Field(..., description="Priority (P0-P3)")

    threshold_configuration: Dict[str, float] = Field(
        default_factory=dict, description="Thresholds used for risk category"
    )

    timestamp: Optional[str] = None


class GenAIMetadata(BaseModel):
    """Metadata for GenAI/Groq explanation layer.

    Documents provider, model, input case/evidence, output status.
    Enables verification that explanations reference actual evidence.
    """

    model_config = ConfigDict(extra="forbid")

    provider: str = Field(default="Groq", description="GenAI provider")
    model_name: str = Field(..., description="Model name (e.g., openai/gpt-oss-120b)")
    model_version: Optional[str] = Field(None, description="Model version if available")

    prompt_version: Optional[str] = Field(
        None, description="Prompt template version; 'unknown' if not tracked"
    )

    input_case_id: str = Field(..., description="Case ID given to model")
    input_evidence_ids: List[str] = Field(
        default_factory=list, description="Evidence IDs supplied to model"
    )
    input_finding_count: int = Field(default=0, ge=0, description="Number of findings")

    status: str = Field(..., pattern="^(generated|unavailable|error|disabled)$")
    error_message: Optional[str] = None

    generated_at: Optional[str] = Field(None, description="ISO8601 timestamp")
    duration_ms: Optional[int] = Field(None, ge=0, description="Generation time")

    references_evidence: bool = Field(
        True, description="Whether explanation should reference evidence"
    )


class CaseTraceMetadata(BaseModel):
    """Trace and correlation metadata for entire case investigation.

    Provides case-level tracking for audit, logging, and debugging.
    """

    model_config = ConfigDict(extra="forbid")

    trace_id: str = Field(
        ..., min_length=1, description="Unique trace ID for this investigation"
    )
    case_id: str = Field(..., min_length=1, description="Unique case identifier")
    claim_id: Optional[str] = None
    provider_id: Optional[str] = None

    investigation_started_at: Optional[str] = Field(None, description="ISO8601 timestamp")
    investigation_completed_at: Optional[str] = Field(None, description="ISO8601 timestamp")

    agent_executions: List[AgentExecutionMetadata] = Field(
        default_factory=list, description="All agent runs"
    )
    routing: Optional[RoutingMetadata] = None
    synthesis: Optional[SynthesisMetadata] = None
    genai: Optional[GenAIMetadata] = None

    execution_order: List[str] = Field(
        default_factory=list, description="Order of execution (agent names)"
    )

    # Correlation and debugging
    log_file: Optional[str] = None
    debug_enabled: bool = False
