"""Trace ID propagation and context management.

Provides a simple thread-local context for propagating trace_id and metadata
through the investigation pipeline without invasive changes to agent interfaces.
"""

from __future__ import annotations

import contextvars
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .models import AgentExecutionMetadata, CaseTraceMetadata, GenAIMetadata, RoutingMetadata, SynthesisMetadata


@dataclass
class TraceContext:
    """Context object for an active investigation trace.

    Holds trace_id, case metadata, execution tracking, and provides methods
    to record agent executions, routing decisions, synthesis results, and GenAI calls.
    """

    trace_id: str = field(default_factory=lambda: f"TRACE-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}")
    case_id: str = field(default="")
    claim_id: Optional[str] = None
    provider_id: Optional[str] = None

    investigation_started_at: Optional[str] = None
    investigation_completed_at: Optional[str] = None

    agent_executions: List[AgentExecutionMetadata] = field(default_factory=list)
    routing: Optional[RoutingMetadata] = None
    synthesis: Optional[SynthesisMetadata] = None
    genai: Optional[GenAIMetadata] = None

    execution_order: List[str] = field(default_factory=list)

    _metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.investigation_started_at:
            self.investigation_started_at = datetime.now(timezone.utc).isoformat()

    def record_agent_execution(self, execution: AgentExecutionMetadata) -> None:
        """Record an agent execution."""
        self.agent_executions.append(execution)
        if execution.agent_name not in self.execution_order:
            self.execution_order.append(execution.agent_name)

    def record_routing(self, routing: RoutingMetadata) -> None:
        """Record routing decisions."""
        self.routing = routing

    def record_synthesis(self, synthesis: SynthesisMetadata) -> None:
        """Record synthesis result."""
        self.synthesis = synthesis

    def record_genai(self, genai: GenAIMetadata) -> None:
        """Record GenAI explanation."""
        self.genai = genai

    def mark_completed(self) -> None:
        """Mark investigation as completed."""
        self.investigation_completed_at = datetime.now(timezone.utc).isoformat()

    def to_metadata(self) -> CaseTraceMetadata:
        """Convert context to formal provenance metadata model."""
        return CaseTraceMetadata(
            trace_id=self.trace_id,
            case_id=self.case_id,
            claim_id=self.claim_id,
            provider_id=self.provider_id,
            investigation_started_at=self.investigation_started_at,
            investigation_completed_at=self.investigation_completed_at,
            agent_executions=self.agent_executions,
            routing=self.routing,
            synthesis=self.synthesis,
            genai=self.genai,
            execution_order=self.execution_order,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "trace_id": self.trace_id,
            "case_id": self.case_id,
            "claim_id": self.claim_id,
            "provider_id": self.provider_id,
            "investigation_started_at": self.investigation_started_at,
            "investigation_completed_at": self.investigation_completed_at,
            "agent_executions": [e.__dict__ for e in self.agent_executions],
            "routing": self.routing.__dict__ if self.routing else None,
            "synthesis": self.synthesis.__dict__ if self.synthesis else None,
            "genai": self.genai.__dict__ if self.genai else None,
            "execution_order": self.execution_order,
        }


# Thread-local (or async-safe) context for trace propagation
_trace_context: contextvars.ContextVar[Optional[TraceContext]] = contextvars.ContextVar(
    "trace_context", default=None
)


class ProvenanceTracer:
    """Singleton for managing trace context throughout investigation pipeline.

    Usage:
        tracer = ProvenanceTracer()
        
        # Start a new trace for a case
        tracer.start_trace(case_id="CASE-123", claim_id="claim-456")
        
        # Get the current trace context
        context = tracer.current_context()
        
        # Record an agent execution
        tracer.record_agent_execution(execution_metadata)
        
        # Complete the trace
        tracer.mark_completed()
        metadata = tracer.current_context().to_metadata()
    """

    _instance: Optional[ProvenanceTracer] = None

    def __new__(cls) -> ProvenanceTracer:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def start_trace(
        self,
        case_id: str,
        claim_id: Optional[str] = None,
        provider_id: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> TraceContext:
        """Start a new investigation trace.

        Args:
            case_id: Case identifier
            claim_id: Claim identifier (optional)
            provider_id: Provider identifier (optional)
            trace_id: Custom trace ID (optional; auto-generated if not provided)

        Returns:
            TraceContext for this investigation
        """
        context = TraceContext(
            trace_id=trace_id or f"TRACE-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}",
            case_id=case_id,
            claim_id=claim_id,
            provider_id=provider_id,
        )
        _trace_context.set(context)
        return context

    def current_context(self) -> Optional[TraceContext]:
        """Get the current trace context.

        Returns:
            Current TraceContext or None if no trace is active
        """
        return _trace_context.get()

    def ensure_context(self, case_id: str = "") -> TraceContext:
        """Get current context or create a new one.

        Useful for defensive code that may be called without explicit
        trace initialization.

        Args:
            case_id: Case ID to use if creating new context

        Returns:
            Current or newly created TraceContext
        """
        ctx = self.current_context()
        if ctx is None:
            ctx = self.start_trace(case_id=case_id)
        return ctx

    def record_agent_execution(self, execution: AgentExecutionMetadata) -> None:
        """Record an agent execution in the current trace."""
        ctx = self.current_context()
        if ctx:
            ctx.record_agent_execution(execution)

    def record_routing(self, routing: RoutingMetadata) -> None:
        """Record routing decisions in the current trace."""
        ctx = self.current_context()
        if ctx:
            ctx.record_routing(routing)

    def record_synthesis(self, synthesis: SynthesisMetadata) -> None:
        """Record synthesis result in the current trace."""
        ctx = self.current_context()
        if ctx:
            ctx.record_synthesis(synthesis)

    def record_genai(self, genai: GenAIMetadata) -> None:
        """Record GenAI explanation in the current trace."""
        ctx = self.current_context()
        if ctx:
            ctx.record_genai(genai)

    def mark_completed(self) -> None:
        """Mark the current investigation as completed."""
        ctx = self.current_context()
        if ctx:
            ctx.mark_completed()

    def end_trace(self) -> Optional[CaseTraceMetadata]:
        """End the current trace and return final metadata.

        Returns:
            CaseTraceMetadata or None if no active trace
        """
        ctx = self.current_context()
        if ctx:
            ctx.mark_completed()
            metadata = ctx.to_metadata()
            _trace_context.set(None)
            return metadata
        return None

    def trace_id(self) -> Optional[str]:
        """Get the current trace ID."""
        ctx = self.current_context()
        return ctx.trace_id if ctx else None
