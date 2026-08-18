"""Builders for creating provenance metadata objects.

These builders simplify creation of provenance objects and ensure consistent
metadata across the system. Builders are factory methods that set sensible defaults
and validate required fields.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from .models import (
    AgentExecutionMetadata,
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


class SourceMetadataBuilder:
    """Builder for SourceMetadata objects."""

    @staticmethod
    def dataset(
        source_name: str,
        version: Optional[str] = None,
        available: bool = True,
    ) -> SourceMetadata:
        """Create metadata for a dataset source.

        Args:
            source_name: Dataset name (e.g., 'provider_risk_scores.csv')
            version: Dataset version or tag
            available: Whether source is currently accessible

        Returns:
            SourceMetadata for dataset
        """
        return SourceMetadata(
            source_type=SourceType.DATASET,
            source_name=source_name,
            source_version=version or "unknown",
            available=available,
        )

    @staticmethod
    def model(
        model_name: str,
        artifact: Optional[str] = None,
        version: Optional[str] = None,
        available: bool = True,
    ) -> SourceMetadata:
        """Create metadata for an ML model source.

        Args:
            model_name: Model type (e.g., 'IsolationForest')
            artifact: Path to model file
            version: Model version
            available: Whether model is currently accessible

        Returns:
            SourceMetadata for model
        """
        return SourceMetadata(
            source_type=SourceType.MODEL,
            source_name=model_name,
            source_artifact=artifact,
            source_version=version or "unknown",
            available=available,
        )

    @staticmethod
    def rule(
        rule_name: str,
        rule_id: Optional[str] = None,
        version: Optional[str] = None,
    ) -> SourceMetadata:
        """Create metadata for a rule source.

        Args:
            rule_name: Rule name
            rule_id: Rule identifier
            version: Rule version

        Returns:
            SourceMetadata for rule
        """
        return SourceMetadata(
            source_type=SourceType.RULE,
            source_name=rule_name,
            source_artifact=rule_id,
            source_version=version or "unknown",
            available=True,
        )

    @staticmethod
    def configuration(
        config_name: str,
        version: Optional[str] = None,
    ) -> SourceMetadata:
        """Create metadata for a configuration source.

        Args:
            config_name: Configuration name
            version: Configuration version

        Returns:
            SourceMetadata for configuration
        """
        return SourceMetadata(
            source_type=SourceType.CONFIGURATION,
            source_name=config_name,
            source_version=version or "unknown",
            available=True,
        )


class RuleProvenanceBuilder:
    """Builder for RuleProvenance objects."""

    @staticmethod
    def from_rule_hit(
        rule_id: str,
        rule_name: str,
        status: str,
        condition: Optional[str] = None,
        threshold: Optional[float] = None,
        threshold_operator: Optional[str] = None,
        input_fields: Optional[List[str]] = None,
        input_values: Optional[Dict[str, Any]] = None,
        rule_version: Optional[str] = None,
    ) -> RuleProvenance:
        """Create RuleProvenance from rule execution data.

        Args:
            rule_id: Rule identifier
            rule_name: Human-readable rule name
            status: Execution status (TRIGGERED, NOT_TRIGGERED, etc.)
            condition: Rule condition
            threshold: Numerical threshold
            threshold_operator: Comparison operator
            input_fields: Field names used
            input_values: Actual values during execution
            rule_version: Rule version

        Returns:
            RuleProvenance object
        """
        return RuleProvenance(
            rule_id=rule_id,
            rule_name=rule_name,
            rule_version=rule_version or "unknown",
            condition=condition,
            threshold=threshold,
            threshold_operator=threshold_operator,
            input_fields=input_fields or [],
            input_values=input_values or {},
            result=status,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )


class ModelProvenanceBuilder:
    """Builder for ModelProvenance objects."""

    @staticmethod
    def from_model(
        model_name: str,
        model_version: Optional[str] = None,
        model_artifact: Optional[str] = None,
        pipeline_name: Optional[str] = None,
        pipeline_version: Optional[str] = None,
        feature_set_version: Optional[str] = None,
        preprocessing_version: Optional[str] = None,
        configuration: Optional[Dict[str, Any]] = None,
    ) -> ModelProvenance:
        """Create ModelProvenance from model metadata.

        Args:
            model_name: Model type (e.g., 'IsolationForest')
            model_version: Model version
            model_artifact: Path to model file
            pipeline_name: ML pipeline name
            pipeline_version: Pipeline version
            feature_set_version: Feature engineering version
            preprocessing_version: Preprocessing version
            configuration: Model configuration dict

        Returns:
            ModelProvenance object
        """
        return ModelProvenance(
            model_name=model_name,
            model_version=model_version or "unknown",
            model_artifact=model_artifact,
            pipeline_name=pipeline_name,
            pipeline_version=pipeline_version or "unknown",
            feature_set_version=feature_set_version or "unknown",
            preprocessing_version=preprocessing_version or "unknown",
            configuration=configuration or {},
            scoring_timestamp=datetime.now(timezone.utc).isoformat(),
        )


class AgentExecutionMetadataBuilder:
    """Builder for AgentExecutionMetadata objects."""

    @staticmethod
    def create(
        agent_name: str,
        case_id: str,
        status: str = "success",
        agent_version: Optional[str] = None,
        started_at: Optional[str] = None,
        completed_at: Optional[str] = None,
        duration_ms: Optional[int] = None,
        input_sources: Optional[List[str]] = None,
        input_record_count: Optional[int] = None,
        output_evidence_count: int = 0,
        output_finding_count: int = 0,
        output_evidence_ids: Optional[List[str]] = None,
        error_type: Optional[str] = None,
        error_message: Optional[str] = None,
        configuration_version: Optional[str] = None,
    ) -> AgentExecutionMetadata:
        """Create AgentExecutionMetadata.

        Args:
            agent_name: Agent type (billing, peer, clinical_rule)
            case_id: Case being investigated
            status: Execution status (success, partial, error, skipped)
            agent_version: Agent code version
            started_at: ISO8601 start timestamp
            completed_at: ISO8601 completion timestamp
            duration_ms: Total execution time
            input_sources: Data sources used
            input_record_count: Records processed
            output_evidence_count: Evidence pieces created
            output_finding_count: Findings generated
            output_evidence_ids: IDs of generated evidence
            error_type: Error type if status=error
            error_message: Error message if status=error
            configuration_version: Configuration version used

        Returns:
            AgentExecutionMetadata object
        """
        now = datetime.now(timezone.utc).isoformat()

        return AgentExecutionMetadata(
            execution_id=f"EXEC-{uuid4().hex[:12].upper()}",
            case_id=case_id,
            agent_name=agent_name,
            agent_version=agent_version or "unknown",
            status=status,
            error_type=error_type,
            error_message=error_message,
            started_at=started_at or now,
            completed_at=completed_at or now,
            duration_ms=duration_ms or 0,
            input_sources=input_sources or [],
            input_record_count=input_record_count,
            output_evidence_count=output_evidence_count,
            output_finding_count=output_finding_count,
            output_evidence_ids=output_evidence_ids or [],
            configuration_version=configuration_version or "unknown",
        )


class RoutingMetadataBuilder:
    """Builder for RoutingMetadata objects."""

    @staticmethod
    def create(
        claim_anomaly_score: Optional[float] = None,
        provider_anomaly_score: Optional[float] = None,
        decisions: Optional[List[RoutingDecision]] = None,
        routing_policy_version: Optional[str] = None,
    ) -> RoutingMetadata:
        """Create RoutingMetadata.

        Args:
            claim_anomaly_score: Claim anomaly score (0-100)
            provider_anomaly_score: Provider anomaly score (0-100)
            decisions: List of routing decisions
            routing_policy_version: Routing policy version

        Returns:
            RoutingMetadata object
        """
        return RoutingMetadata(
            routing_policy_version=routing_policy_version or "1.0.0",
            decisions=decisions or [],
            claim_anomaly_score=claim_anomaly_score,
            provider_anomaly_score=provider_anomaly_score,
        )

    @staticmethod
    def add_decision(
        routing: RoutingMetadata,
        agent_name: str,
        selected: bool,
        reason: Optional[str] = None,
    ) -> RoutingMetadata:
        """Add a routing decision to existing routing metadata.

        Args:
            routing: Existing RoutingMetadata
            agent_name: Agent name
            selected: Whether agent was selected
            reason: Reason for selection/skipping

        Returns:
            Updated RoutingMetadata
        """
        decision = RoutingDecision(agent_name=agent_name, selected=selected, reason=reason)
        routing.decisions.append(decision)
        return routing


class SynthesisMetadataBuilder:
    """Builder for SynthesisMetadata objects."""

    @staticmethod
    def create(
        synthesis_method: str = "weighted_sum",
        inputs: Optional[Dict[str, Optional[float]]] = None,
        weights: Optional[Dict[str, float]] = None,
        final_score: float = 0.0,
        risk_category: str = "LOW",
        priority: str = "P3",
        threshold_configuration: Optional[Dict[str, float]] = None,
        synthesis_version: Optional[str] = None,
    ) -> SynthesisMetadata:
        """Create SynthesisMetadata.

        Args:
            synthesis_method: Aggregation method
            inputs: Input scores dict
            weights: Weights dict
            final_score: Final risk score
            risk_category: Risk category (LOW, MEDIUM, HIGH, CRITICAL)
            priority: Priority (P0-P3)
            threshold_configuration: Thresholds for categories
            synthesis_version: Synthesis version

        Returns:
            SynthesisMetadata object
        """
        return SynthesisMetadata(
            synthesis_method=synthesis_method,
            synthesis_version=synthesis_version or "1.0.0",
            inputs=inputs or {},
            weights=weights or {},
            contributions=[],
            final_score=final_score,
            risk_category=risk_category,
            priority=priority,
            threshold_configuration=threshold_configuration or {},
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    @staticmethod
    def add_contribution(
        synthesis: SynthesisMetadata,
        source: str,
        input_value: Optional[float],
        weight: float,
        contribution: float,
    ) -> SynthesisMetadata:
        """Add a contribution to synthesis metadata.

        Args:
            synthesis: Existing SynthesisMetadata
            source: Component name
            input_value: Raw input score
            weight: Weight applied
            contribution: Weighted contribution

        Returns:
            Updated SynthesisMetadata
        """
        contrib = SynthesisContribution(
            source=source, input_value=input_value, weight=weight, contribution=contribution
        )
        synthesis.contributions.append(contrib)
        return synthesis


class GenAIMetadataBuilder:
    """Builder for GenAIMetadata objects."""

    @staticmethod
    def create(
        case_id: str,
<<<<<<< HEAD
        model_name: str = "openai/gpt-oss-120b",
=======
        model_name: str = "llama-3.3-70b-versatile",
>>>>>>> b166e40 (removed old data)
        provider: str = "Groq",
        model_version: Optional[str] = None,
        prompt_version: Optional[str] = None,
        input_evidence_ids: Optional[List[str]] = None,
        input_finding_count: int = 0,
        status: str = "generated",
        error_message: Optional[str] = None,
        generated_at: Optional[str] = None,
        duration_ms: Optional[int] = None,
    ) -> GenAIMetadata:
        """Create GenAIMetadata.

        Args:
            case_id: Case ID given to model
            model_name: Model name
            provider: GenAI provider (Groq)
            model_version: Model version
            prompt_version: Prompt template version
            input_evidence_ids: Evidence IDs supplied
            input_finding_count: Number of findings
            status: Generation status
            error_message: Error message if failed
            generated_at: ISO8601 timestamp
            duration_ms: Generation time

        Returns:
            GenAIMetadata object
        """
        return GenAIMetadata(
            provider=provider,
            model_name=model_name,
            model_version=model_version or "unknown",
            prompt_version=prompt_version or "unknown",
            input_case_id=case_id,
            input_evidence_ids=input_evidence_ids or [],
            input_finding_count=input_finding_count,
            status=status,
            error_message=error_message,
            generated_at=generated_at or datetime.now(timezone.utc).isoformat(),
            duration_ms=duration_ms,
        )
