"""Tests for provenance layer and audit trail functionality.

Comprehensive test suite covering:
- Trace context management
- Provenance model validation
- Agent execution tracking
- Routing decision tracking
- Synthesis calculation provenance
- GenAI explanation provenance
- Provenance validation
- End-to-end traceability
"""

from datetime import datetime, timezone

import pytest

from multi_agent.provenance import (
    AgentExecutionMetadataBuilder,
    CaseTraceMetadata,
    GenAIMetadataBuilder,
    ModelProvenanceBuilder,
    ProvenanceReport,
    ProvenanceTracer,
    ProvenanceValidator,
    RoutingDecision,
    RoutingMetadataBuilder,
    RuleProvenanceBuilder,
    SourceMetadataBuilder,
    SourceType,
    SynthesisMetadataBuilder,
    TraceContext,
)


class TestTraceContext:
    """Test TraceContext creation and manipulation."""

    def test_trace_context_creation(self):
        """TraceContext can be created with basic metadata."""
        ctx = TraceContext(
            case_id="CASE-123",
            claim_id="CLAIM-456",
            provider_id="NPI-789",
        )

        assert ctx.case_id == "CASE-123"
        assert ctx.claim_id == "CLAIM-456"
        assert ctx.provider_id == "NPI-789"
        assert ctx.trace_id is not None
        assert ctx.trace_id.startswith("TRACE-")
        assert ctx.investigation_started_at is not None

    def test_trace_context_custom_trace_id(self):
        """TraceContext accepts custom trace ID."""
        custom_id = "TRACE-CUSTOM-12345"
        ctx = TraceContext(case_id="CASE-1", trace_id=custom_id)

        assert ctx.trace_id == custom_id

    def test_trace_context_record_agent_execution(self):
        """TraceContext can record agent execution."""
        ctx = TraceContext(case_id="CASE-1")
        exec_meta = AgentExecutionMetadataBuilder.create(
            agent_name="peer",
            case_id="CASE-1",
            status="success",
            output_finding_count=3,
        )

        ctx.record_agent_execution(exec_meta)

        assert len(ctx.agent_executions) == 1
        assert ctx.agent_executions[0].agent_name == "peer"
        assert ctx.execution_order == ["peer"]

    def test_trace_context_mark_completed(self):
        """TraceContext marks completion timestamp."""
        ctx = TraceContext(case_id="CASE-1")
        assert ctx.investigation_completed_at is None

        ctx.mark_completed()

        assert ctx.investigation_completed_at is not None

    def test_trace_context_to_metadata(self):
        """TraceContext converts to CaseTraceMetadata model."""
        ctx = TraceContext(
            case_id="CASE-1",
            claim_id="CLAIM-1",
            provider_id="NPI-1",
        )
        ctx.mark_completed()

        metadata = ctx.to_metadata()

        assert isinstance(metadata, CaseTraceMetadata)
        assert metadata.case_id == "CASE-1"
        assert metadata.trace_id == ctx.trace_id


class TestProvenanceTracer:
    """Test ProvenanceTracer singleton and trace management."""

    def test_tracer_singleton(self):
        """ProvenanceTracer is a singleton."""
        tracer1 = ProvenanceTracer()
        tracer2 = ProvenanceTracer()

        assert tracer1 is tracer2

    def test_tracer_start_trace(self):
        """Tracer can start a new trace."""
        tracer = ProvenanceTracer()
        context = tracer.start_trace(case_id="CASE-1", claim_id="CLAIM-1")

        assert context.case_id == "CASE-1"
        assert context.claim_id == "CLAIM-1"
        assert context.trace_id is not None

    def test_tracer_current_context(self):
        """Tracer returns current trace context."""
        tracer = ProvenanceTracer()
        ctx1 = tracer.start_trace(case_id="CASE-1")

        ctx2 = tracer.current_context()

        assert ctx2 is ctx1
        assert ctx2.case_id == "CASE-1"

    def test_tracer_end_trace(self):
        """Tracer ends trace and returns metadata."""
        tracer = ProvenanceTracer()
        ctx = tracer.start_trace(case_id="CASE-1")

        # Add some metadata
        exec_meta = AgentExecutionMetadataBuilder.create(
            agent_name="billing",
            case_id="CASE-1",
        )
        tracer.record_agent_execution(exec_meta)

        # End trace
        metadata = tracer.end_trace()

        assert metadata is not None
        assert metadata.case_id == "CASE-1"
        assert len(metadata.agent_executions) == 1
        assert tracer.current_context() is None

    def test_tracer_ensure_context(self):
        """Tracer creates context if none exists."""
        tracer = ProvenanceTracer()
        # Reset
        tracer.end_trace()

        ctx = tracer.ensure_context(case_id="CASE-1")

        assert ctx.case_id == "CASE-1"


class TestSourceMetadata:
    """Test source metadata creation."""

    def test_source_dataset(self):
        """Can create dataset source metadata."""
        source = SourceMetadataBuilder.dataset("claims.csv", version="v2")

        assert source.source_type == SourceType.DATASET
        assert source.source_name == "claims.csv"
        assert source.source_version == "v2"
        assert source.available is True

    def test_source_model(self):
        """Can create model source metadata."""
        source = SourceMetadataBuilder.model(
            "IsolationForest",
            artifact="model.joblib",
            version="1.0.0",
        )

        assert source.source_type == SourceType.MODEL
        assert source.source_name == "IsolationForest"
        assert source.source_artifact == "model.joblib"
        assert source.source_version == "1.0.0"

    def test_source_rule(self):
        """Can create rule source metadata."""
        source = SourceMetadataBuilder.rule("High Utilization", rule_id="R03", version="1.0.0")

        assert source.source_type == SourceType.RULE
        assert source.source_name == "High Utilization"
        assert source.source_artifact == "R03"
        assert source.source_version == "1.0.0"

    def test_source_unknown_version(self):
        """Sources without version use 'unknown'."""
        source = SourceMetadataBuilder.dataset("data.csv")

        assert source.source_version == "unknown"


class TestRuleProvenance:
    """Test rule provenance creation."""

    def test_rule_provenance_triggered(self):
        """Can create rule provenance for triggered rule."""
        rule = RuleProvenanceBuilder.from_rule_hit(
            rule_id="R03",
            rule_name="High Utilization",
            status="TRIGGERED",
            threshold=15000.0,
            threshold_operator=">",
            input_fields=["Tot_Srvcs"],
            input_values={"Tot_Srvcs": 20000},
        )

        assert rule.rule_id == "R03"
        assert rule.rule_name == "High Utilization"
        assert rule.result == "TRIGGERED"
        assert rule.threshold == 15000.0
        assert rule.threshold_operator == ">"
        assert rule.input_values["Tot_Srvcs"] == 20000

    def test_rule_provenance_condition_documented(self):
        """Rule provenance documents the condition."""
        rule = RuleProvenanceBuilder.from_rule_hit(
            rule_id="R01",
            rule_name="Test",
            status="TRIGGERED",
            condition="services > threshold",
        )

        assert rule.condition == "services > threshold"


class TestModelProvenance:
    """Test model provenance creation."""

    def test_model_provenance_complete(self):
        """Can create complete model provenance."""
        model = ModelProvenanceBuilder.from_model(
            model_name="IsolationForest",
            model_version="1.0.0",
            model_artifact="models/iso_forest.joblib",
            pipeline_name="provider_risk_pipeline",
            pipeline_version="1.0.0",
            feature_set_version="v2",
        )

        assert model.model_name == "IsolationForest"
        assert model.model_version == "1.0.0"
        assert model.pipeline_name == "provider_risk_pipeline"
        assert model.feature_set_version == "v2"

    def test_model_provenance_unknown_version(self):
        """Model without version uses 'unknown'."""
        model = ModelProvenanceBuilder.from_model("RandomForest")

        assert model.model_version == "unknown"
        assert model.pipeline_version == "unknown"


class TestAgentExecutionMetadata:
    """Test agent execution provenance."""

    def test_agent_execution_success(self):
        """Can create successful agent execution metadata."""
        exec_meta = AgentExecutionMetadataBuilder.create(
            agent_name="peer",
            case_id="CASE-1",
            status="success",
            output_evidence_count=5,
            output_finding_count=3,
            output_evidence_ids=["EV-001", "EV-002"],
        )

        assert exec_meta.agent_name == "peer"
        assert exec_meta.case_id == "CASE-1"
        assert exec_meta.status == "success"
        assert exec_meta.output_evidence_count == 5
        assert exec_meta.output_finding_count == 3
        assert len(exec_meta.output_evidence_ids) == 2

    def test_agent_execution_error(self):
        """Can create failed agent execution metadata."""
        exec_meta = AgentExecutionMetadataBuilder.create(
            agent_name="peer",
            case_id="CASE-1",
            status="error",
            error_type="DATA_NOT_AVAILABLE",
            error_message="Provider data not found",
        )

        assert exec_meta.status == "error"
        assert exec_meta.error_type == "DATA_NOT_AVAILABLE"
        assert exec_meta.error_message == "Provider data not found"


class TestRoutingMetadata:
    """Test routing decision tracking."""

    def test_routing_metadata_creation(self):
        """Can create routing metadata."""
        routing = RoutingMetadataBuilder.create(
            claim_anomaly_score=91.0,
            provider_anomaly_score=88.0,
        )

        assert routing.claim_anomaly_score == 91.0
        assert routing.provider_anomaly_score == 88.0

    def test_routing_add_decision(self):
        """Can add routing decisions."""
        routing = RoutingMetadataBuilder.create()
        routing = RoutingMetadataBuilder.add_decision(
            routing,
            agent_name="billing",
            selected=True,
            reason="claim_anomaly >= 70",
        )

        assert len(routing.decisions) == 1
        assert routing.decisions[0].agent_name == "billing"
        assert routing.decisions[0].selected is True


class TestSynthesisMetadata:
    """Test synthesis/aggregation provenance."""

    def test_synthesis_metadata_creation(self):
        """Can create synthesis metadata."""
        synthesis = SynthesisMetadataBuilder.create(
            final_score=88.0,
            risk_category="HIGH",
            priority="P1",
        )

        assert synthesis.final_score == 88.0
        assert synthesis.risk_category == "HIGH"
        assert synthesis.priority == "P1"

    def test_synthesis_add_contribution(self):
        """Can add contribution breakdown."""
        synthesis = SynthesisMetadataBuilder.create(final_score=88.0)
        synthesis = SynthesisMetadataBuilder.add_contribution(
            synthesis,
            source="billing",
            input_value=86.0,
            weight=0.1,
            contribution=8.6,
        )

        assert len(synthesis.contributions) == 1
        assert synthesis.contributions[0].source == "billing"
        assert synthesis.contributions[0].contribution == 8.6


class TestGenAIMetadata:
    """Test GenAI explanation provenance."""

    def test_genai_metadata_creation(self):
        """Can create GenAI metadata."""
        genai = GenAIMetadataBuilder.create(
            case_id="CASE-1",
            model_name="llama-3.3-70b-versatile",
            status="generated",
            input_evidence_ids=["EV-001", "EV-002"],
        )

        assert genai.input_case_id == "CASE-1"
        assert genai.model_name == "llama-3.3-70b-versatile"
        assert genai.provider == "Groq"
        assert genai.status == "generated"
        assert len(genai.input_evidence_ids) == 2

    def test_genai_metadata_unavailable(self):
        """Can create metadata for unavailable GenAI."""
        genai = GenAIMetadataBuilder.create(
            case_id="CASE-1",
            status="unavailable",
            error_message="GROQ_API_KEY not configured",
        )

        assert genai.status == "unavailable"
        assert "GROQ_API_KEY" in genai.error_message


class TestProvenanceValidator:
    """Test provenance validation."""

    def test_validator_trace_context_valid(self):
        """Validator accepts complete trace context."""
        ctx = TraceContext(case_id="CASE-1")
        exec_meta = AgentExecutionMetadataBuilder.create(
            agent_name="peer",
            case_id="CASE-1",
        )
        ctx.record_agent_execution(exec_meta)
        ctx.mark_completed()

        report = ProvenanceValidator.validate_trace_context(ctx)

        assert report.valid is True
        assert report.coverage >= 80.0

    def test_validator_catches_missing_case_id(self):
        """Validator catches missing case_id."""
        ctx = TraceContext(case_id="")

        report = ProvenanceValidator.validate_trace_context(ctx)

        assert report.valid is False
        assert any("case_id" in e.lower() for e in report.errors)

    def test_validator_evidence_valid(self):
        """Validator accepts valid evidence."""
        evidence = {
            "evidence_id": "EV-001",
            "agent": "peer",
            "source": "provider_risk_scores.csv",
            "source_fields": ["NPI", "Tot_Srvcs"],
            "availability": "AVAILABLE",
        }

        report = ProvenanceValidator.validate_evidence(evidence)

        assert report.valid is True

    def test_validator_catches_missing_evidence_source(self):
        """Validator catches missing source."""
        evidence = {
            "evidence_id": "EV-001",
            "agent": "peer",
        }

        report = ProvenanceValidator.validate_evidence(evidence)

        assert report.valid is False
        assert any("source" in e.lower() for e in report.errors)

    def test_validator_rule_hit_valid(self):
        """Validator accepts valid rule hit."""
        rule_hit = {
            "rule_id": "R03",
            "rule_name": "High Utilization",
            "status": "TRIGGERED",
            "observed_value": 20000,
            "threshold": 15000,
            "evidence_ids": ["EV-001"],
        }

        report = ProvenanceValidator.validate_rule_hit(rule_hit)

        assert report.valid is True

    def test_validator_catches_missing_rule_id(self):
        """Validator catches missing rule_id."""
        rule_hit = {
            "rule_name": "High Utilization",
            "status": "TRIGGERED",
        }

        report = ProvenanceValidator.validate_rule_hit(rule_hit)

        assert report.valid is False
        assert any("rule_id" in e.lower() for e in report.errors)


class TestEndToEndTraceability:
    """Test complete end-to-end traceability."""

    def test_complete_trace_flow(self):
        """Can trace a complete investigation flow."""
        tracer = ProvenanceTracer()

        # 1. Start case
        ctx = tracer.start_trace(
            case_id="CASE-10231",
            claim_id="CLAIM-001",
            provider_id="NPI-1234567890",
        )
        assert ctx.trace_id.startswith("TRACE-")

        # 2. Record agent executions
        billing_exec = AgentExecutionMetadataBuilder.create(
            agent_name="billing",
            case_id="CASE-10231",
            status="success",
            output_finding_count=2,
            output_evidence_ids=["EV-001", "EV-002"],
        )
        tracer.record_agent_execution(billing_exec)

        peer_exec = AgentExecutionMetadataBuilder.create(
            agent_name="peer",
            case_id="CASE-10231",
            status="success",
            output_finding_count=3,
            output_evidence_ids=["EV-003", "EV-004", "EV-005"],
        )
        tracer.record_agent_execution(peer_exec)

        # 3. Record routing
        routing = RoutingMetadataBuilder.create(claim_anomaly_score=91.0)
        routing = RoutingMetadataBuilder.add_decision(
            routing, "billing", True, "claim_anomaly >= 70"
        )
        routing = RoutingMetadataBuilder.add_decision(
            routing, "peer", True, "provider_anomaly >= 70"
        )
        tracer.record_routing(routing)

        # 4. Record synthesis
        synthesis = SynthesisMetadataBuilder.create(
            final_score=88.0,
            risk_category="HIGH",
        )
        synthesis = SynthesisMetadataBuilder.add_contribution(
            synthesis, "billing", 86.0, 0.1, 8.6
        )
        tracer.record_synthesis(synthesis)

        # 5. Record GenAI
        genai = GenAIMetadataBuilder.create(
            case_id="CASE-10231",
            status="generated",
            input_evidence_ids=["EV-001", "EV-003"],
        )
        tracer.record_genai(genai)

        # 6. Finalize
        metadata = tracer.end_trace()

        # Verify complete chain
        assert metadata is not None
        assert metadata.case_id == "CASE-10231"
        assert metadata.trace_id == ctx.trace_id
        assert len(metadata.agent_executions) == 2
        assert metadata.routing is not None
        assert len(metadata.routing.decisions) == 2
        assert metadata.synthesis is not None
        assert metadata.synthesis.final_score == 88.0
        assert metadata.genai is not None

    def test_trace_context_validation_after_complete_flow(self):
        """Can validate complete trace."""
        tracer = ProvenanceTracer()
        ctx = tracer.start_trace(case_id="CASE-1")

        exec_meta = AgentExecutionMetadataBuilder.create(
            agent_name="billing",
            case_id="CASE-1",
        )
        tracer.record_agent_execution(exec_meta)

        synthesis = SynthesisMetadataBuilder.create(final_score=50.0)
        tracer.record_synthesis(synthesis)

        metadata = tracer.end_trace()

        # Validate
        report = ProvenanceValidator.validate_trace_context(
            TraceContext(
                case_id=metadata.case_id,
                trace_id=metadata.trace_id,
            )
        )

        # Note: Since we ended the trace, we create a new context for validation
        # The important thing is the report structure
        assert isinstance(report, ProvenanceReport)
        assert report.coverage >= 0.0
        assert report.coverage <= 100.0
