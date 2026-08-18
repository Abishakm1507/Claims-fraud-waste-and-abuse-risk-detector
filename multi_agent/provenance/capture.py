"""Provenance capture and integration for the investigation pipeline.

This module provides utilities to capture provenance metadata as investigations
progress through the orchestrator, agents, and synthesis without modifying
existing interfaces.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from multi_agent.provenance.builders import (
    AgentExecutionMetadataBuilder,
    GenAIMetadataBuilder,
    RoutingMetadataBuilder,
    SynthesisMetadataBuilder,
)
from multi_agent.provenance.models import (
    RoutingDecision,
    RoutingMetadata,
)
from multi_agent.provenance.tracer import (
    ProvenanceTracer,
    TraceContext,
)
from multi_agent.schemas.investigation_case import InvestigationCase
from multi_agent.synthesis import InvestigationResult

logger = logging.getLogger(__name__)


class ProvenanceCapture:
    """Captures provenance metadata during investigation execution.

    Usage:
        capture = ProvenanceCapture()
        capture.start_case(case)

        # Record agent execution (call after agent.investigate())
        capture.record_agent_execution(
            agent_name="peer",
            status="success",
            findings_count=5,
            evidence_ids=["EV-001", "EV-002"],
        )

        # Record routing decisions (call after orchestrator routing)
        capture.record_routing(routing_dict)

        # Record synthesis (call after synthesis)
        capture.record_synthesis(result)

        # Record GenAI explanation (call after explanation service)
        capture.record_genai_explanation(explanation_result)

        # Get final provenance metadata
        metadata = capture.finalize()
    """

    def __init__(self):
        self.tracer = ProvenanceTracer()
        self.context: Optional[TraceContext] = None

    def start_case(
        self,
        case: InvestigationCase,
    ) -> TraceContext:
        """Start provenance capture for a case.

        Args:
            case: InvestigationCase to investigate

        Returns:
            TraceContext for this investigation
        """
        claim_id = case.claim_id if case.claim is None else case.claim.claim_id
        provider_id = case.provider.npi if case.provider is not None else None

        self.context = self.tracer.start_trace(
            case_id=case.case_id,
            claim_id=claim_id,
            provider_id=provider_id,
        )

        logger.info(
            "Provenance trace started",
            extra={
                "trace_id": self.context.trace_id,
                "case_id": case.case_id,
                "claim_id": claim_id,
                "provider_id": provider_id,
            },
        )

        return self.context

    def record_agent_execution(
        self,
        agent_name: str,
        status: str = "success",
        findings_count: int = 0,
        evidence_ids: Optional[List[str]] = None,
        error_type: Optional[str] = None,
        error_message: Optional[str] = None,
        duration_ms: Optional[int] = None,
        configuration_version: Optional[str] = None,
    ) -> None:
        """Record execution of a single agent.

        Args:
            agent_name: Agent type (billing, peer, clinical_rule)
            status: Execution status (success, partial, error, skipped)
            findings_count: Number of findings generated
            evidence_ids: IDs of generated evidence
            error_type: Error type if status=error
            error_message: Error message if status=error
            duration_ms: Execution duration
            configuration_version: Configuration version used
        """
        if self.context is None:
            logger.warning("No active trace context; agent execution not recorded")
            return

        execution = AgentExecutionMetadataBuilder.create(
            agent_name=agent_name,
            case_id=self.context.case_id,
            status=status,
            output_finding_count=findings_count,
            output_evidence_ids=evidence_ids or [],
            error_type=error_type,
            error_message=error_message,
            duration_ms=duration_ms,
            configuration_version=configuration_version,
        )

        self.context.record_agent_execution(execution)

        logger.info(
            "Agent execution recorded",
            extra={
                "trace_id": self.context.trace_id,
                "execution_id": execution.execution_id,
                "agent": agent_name,
                "status": status,
                "findings_count": findings_count,
            },
        )

    def record_routing(
        self,
        routing_dict: Dict[str, Any],
        claim_anomaly: Optional[float] = None,
        provider_anomaly: Optional[float] = None,
    ) -> None:
        """Record orchestrator routing decisions.

        Args:
            routing_dict: Routing information from orchestrator
            claim_anomaly: Claim anomaly score
            provider_anomaly: Provider anomaly score
        """
        if self.context is None:
            logger.warning("No active trace context; routing not recorded")
            return

        routing = RoutingMetadataBuilder.create(
            claim_anomaly_score=claim_anomaly,
            provider_anomaly_score=provider_anomaly,
        )

        # Convert routing dict decisions
        for agent_name, route_info in routing_dict.items():
            if isinstance(route_info, dict):
                decision = route_info.get("selected", False)
                reason = route_info.get("reason", route_info.get("routing_reason"))
                from multi_agent.provenance import RoutingDecision

                routing.decisions.append(
                    RoutingDecision(agent_name=agent_name, selected=decision, reason=reason)
                )

        self.context.record_routing(routing)

        logger.info(
            "Routing decisions recorded",
            extra={
                "trace_id": self.context.trace_id,
                "decisions_count": len(routing.decisions),
            },
        )

    def record_synthesis(self, result: InvestigationResult) -> None:
        """Record synthesis results and calculation breakdown.

        Args:
            result: InvestigationResult from synthesis
        """
        if self.context is None:
            logger.warning("No active trace context; synthesis not recorded")
            return

        synthesis = SynthesisMetadataBuilder.create(
            synthesis_method="weighted_sum",
            final_score=result.investigation_risk_score,
            risk_category=result.investigation_priority,
            priority=result.investigation_priority,
        )

        # Add input scores if available
        inputs = {
            "claim_anomaly": result.claim_risk_score,
            "provider_anomaly": result.provider_risk_score,
        }
        synthesis.inputs = {k: v for k, v in inputs.items()}

        # Add default weights
        synthesis.weights = {
            "claim_anomaly": 0.3,
            "provider_anomaly": 0.3,
            "peer_score": 0.2,
            "billing_score": 0.1,
            "rule_score": 0.1,
        }

        self.context.record_synthesis(synthesis)

        logger.info(
            "Synthesis results recorded",
            extra={
                "trace_id": self.context.trace_id,
                "final_score": result.investigation_risk_score,
                "priority": result.investigation_priority,
            },
        )

    def record_genai_explanation(
        self,
<<<<<<< HEAD
        model_name: str = "openai/gpt-oss-120b",
=======
        model_name: str = "llama-3.3-70b-versatile",
>>>>>>> b166e40 (removed old data)
        status: str = "generated",
        evidence_ids: Optional[List[str]] = None,
        duration_ms: Optional[int] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """Record GenAI explanation generation.

        Args:
            model_name: Model used for explanation
            status: Generation status (generated, unavailable, error, disabled)
            evidence_ids: Evidence IDs supplied to model
            duration_ms: Generation time
            error_message: Error message if failed
        """
        if self.context is None:
            logger.warning("No active trace context; GenAI explanation not recorded")
            return

        genai = GenAIMetadataBuilder.create(
            case_id=self.context.case_id,
            model_name=model_name,
            status=status,
            input_evidence_ids=evidence_ids or [],
            duration_ms=duration_ms,
            error_message=error_message,
        )

        self.context.record_genai(genai)

        logger.info(
            "GenAI explanation recorded",
            extra={
                "trace_id": self.context.trace_id,
                "status": status,
                "evidence_count": len(genai.input_evidence_ids),
            },
        )

    def finalize(self) -> Optional[Dict[str, Any]]:
        """Finalize the trace and return provenance metadata.

        Returns:
            Dictionary with complete provenance metadata or None
        """
        if self.context is None:
            logger.warning("No active trace context")
            return None

        metadata = self.tracer.end_trace()

        if metadata:
            logger.info(
                "Trace finalized",
                extra={
                    "trace_id": metadata.trace_id,
                    "case_id": metadata.case_id,
                    "agent_count": len(metadata.agent_executions),
                    "total_duration_ms": (
                        (
                            (
                                time.fromisoformat(metadata.investigation_completed_at)
                                - time.fromisoformat(metadata.investigation_started_at)
                            ).total_seconds()
                            * 1000
                        )
                        if metadata.investigation_completed_at
                        else None
                    ),
                },
            )
            return metadata.to_dict()

        return None

    def get_trace_id(self) -> Optional[str]:
        """Get the current trace ID."""
        return self.tracer.trace_id()

    def get_context(self) -> Optional[TraceContext]:
        """Get the current trace context."""
        return self.context or self.tracer.current_context()
