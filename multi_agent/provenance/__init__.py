"""Provenance layer for investigation audit trail and evidence traceability.

This module provides comprehensive provenance tracking that enables end-to-end
audit trails from case creation through agent execution, evidence collection,
risk synthesis, and GenAI explanation.

Key exports:
- ProvenanceTracer: Main orchestrator for trace_id propagation
- TraceContext: Context object for active traces
- SourceType, SourceMetadata: Source documentation
- RuleProvenance, ModelProvenance: Rule/ML metadata
- AgentExecutionMetadata, SynthesisMetadata, GenAIMetadata: Execution metadata
- ProvenanceValidator: Validation of provenance completeness
"""

from .builders import (
    AgentExecutionMetadataBuilder,
    GenAIMetadataBuilder,
    ModelProvenanceBuilder,
    RuleProvenanceBuilder,
    RoutingMetadataBuilder,
    SourceMetadataBuilder,
    SynthesisMetadataBuilder,
)
from .capture import ProvenanceCapture
from .models import (
    AgentExecutionMetadata,
    CaseTraceMetadata,
    GenAIMetadata,
    ModelProvenance,
    RuleProvenance,
    RoutingDecision,
    RoutingMetadata,
    SourceMetadata,
    SourceType,
    SynthesisContribution,
    SynthesisMetadata,
)
from .tracer import ProvenanceTracer, TraceContext
from .validator import ProvenanceReport, ProvenanceValidator

__all__ = [
    # Models
    "SourceType",
    "SourceMetadata",
    "RuleProvenance",
    "ModelProvenance",
    "AgentExecutionMetadata",
    "RoutingMetadata",
    "RoutingDecision",
    "SynthesisMetadata",
    "SynthesisContribution",
    "GenAIMetadata",
    "CaseTraceMetadata",
    # Tracer
    "ProvenanceTracer",
    "TraceContext",
    # Builders
    "SourceMetadataBuilder",
    "RuleProvenanceBuilder",
    "ModelProvenanceBuilder",
    "AgentExecutionMetadataBuilder",
    "RoutingMetadataBuilder",
    "SynthesisMetadataBuilder",
    "GenAIMetadataBuilder",
    # Capture
    "ProvenanceCapture",
    # Validator
    "ProvenanceValidator",
    "ProvenanceReport",
]
