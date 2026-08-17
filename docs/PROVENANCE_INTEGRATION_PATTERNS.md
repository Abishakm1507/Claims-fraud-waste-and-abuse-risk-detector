# PROVENANCE INTEGRATION PATTERNS

Guide for integrating ProvenanceCapture with the orchestrator, synthesis, and GenAI services in future milestones.

## Pattern 1: Orchestrator Integration (Future)

### Current State
Orchestrator routes to agents but doesn't record provenance.

### Integration Pattern

```python
# multi_agent/orchestrator.py

from multi_agent.provenance import ProvenanceCapture
from multi_agent.models.schemas import InvestigationCase

class Orchestrator:
    def __init__(self):
        # ... existing init code ...
        self.provenance = ProvenanceCapture()  # New
    
    def investigate(self, case: InvestigationCase) -> InvestigationResult:
        # START TRACE
        self.provenance.start_case(case)
        
        # ROUTE: Determine which agents to run
        routing = self._determine_routing(case)
        
        # RECORD ROUTING
        self.provenance.record_routing(
            routing_dict=routing["decisions"],
            claim_anomaly=routing["claim_anomaly_score"],
            provider_anomaly=routing["provider_anomaly_score"]
        )
        
        # RUN AGENTS
        findings = []
        for agent_name in routing["selected_agents"]:
            agent = self.agents[agent_name]
            
            # RECORD AGENT START
            start_time = time.time()
            
            try:
                # Run agent (unchanged)
                agent_result = agent.investigate(case)
                
                # RECORD AGENT EXECUTION (success)
                duration_ms = (time.time() - start_time) * 1000
                self.provenance.record_agent_execution(
                    agent_name=agent_name,
                    status="success",
                    findings_count=len(agent_result.findings),
                    evidence_ids=[f.evidence_id for f in agent_result.findings],
                    duration_ms=int(duration_ms)
                )
                
                findings.extend(agent_result.findings)
                
            except Exception as e:
                # RECORD AGENT EXECUTION (error)
                duration_ms = (time.time() - start_time) * 1000
                self.provenance.record_agent_execution(
                    agent_name=agent_name,
                    status="error",
                    error_type=type(e).__name__,
                    error_message=str(e),
                    duration_ms=int(duration_ms)
                )
                # Continue with other agents (fault-tolerant)
        
        # SYNTHESIZE RESULTS
        result = self._synthesize(findings)
        
        # RECORD SYNTHESIS (next pattern)
        self.provenance.record_synthesis(result)
        
        # GENERATE EXPLANATION
        explanation = self.genai_service.explain(case, findings)
        
        # RECORD GENAI (next pattern)
        self.provenance.record_genai_explanation(
            model_name="llama-3.3-70b-versatile",
            status="generated",
            evidence_ids=[f.evidence_id for f in findings],
            duration_ms=int(explanation.duration_ms)
        )
        
        # ATTACH PROVENANCE TO RESULT
        result.provenance = self.provenance.finalize()
        
        return result
```

**Key Points**:
- ProvenanceCapture initialized in `__init__`
- `start_case()` called at beginning of `investigate()`
- `record_routing()` after routing decision
- `record_agent_execution()` after each agent (success or error)
- `record_synthesis()` after synthesis
- `record_genai_explanation()` after GenAI
- `finalize()` returns metadata dict attached to result

## Pattern 2: Synthesis Integration (Future)

### Current State
Synthesis aggregates scores but doesn't record weights/contributions.

### Integration Pattern

```python
# multi_agent/synthesis.py

from multi_agent.provenance import ProvenanceCapture

def synthesize(case: InvestigationCase, findings: List[Finding]) -> InvestigationResult:
    """Synthesize findings into risk score."""
    
    # Access the tracer's current context
    tracer = ProvenanceTracer()
    context = tracer.current_context()
    
    # ... existing synthesis logic ...
    
    # CAPTURE SYNTHESIS BREAKDOWN
    synthesis_metadata = SynthesisMetadataBuilder.create(
        synthesis_method="weighted_sum",
        final_score=final_risk_score,
        risk_category=risk_category,
        priority=priority,
        threshold_configuration={
            "low_threshold": 40,
            "medium_threshold": 70,
            "high_threshold": 85,
            "critical_threshold": 95,
        }
    )
    
    # ADD CONTRIBUTIONS (show how score was computed)
    for source, anomaly_score in scores.items():
        weight = weights[source]
        contribution = anomaly_score * weight
        
        synthesis_metadata = SynthesisMetadataBuilder.add_contribution(
            synthesis=synthesis_metadata,
            source=source,              # "claim_anomaly", "provider_anomaly"
            input_value=anomaly_score,  # 91.0
            weight=weight,              # 0.30
            contribution=contribution   # 27.3
        )
    
    # RECORD IN TRACER
    if context:
        tracer.record_synthesis(synthesis_metadata)
    
    # Create result (unchanged)
    result = InvestigationResult(
        case_id=case.case_id,
        risk_score=final_risk_score,
        risk_category=risk_category,
        priority=priority,
        findings=findings,
        ...
    )
    
    return result
```

**Key Points**:
- Access tracer from current context (don't pass as parameter)
- Create SynthesisMetadata with all inputs/weights
- Add contributions to show calculation breakdown
- Record in tracer (tracer is thread-local)
- Synthesis logic remains unchanged

## Pattern 3: GenAI Explanation Integration (Future)

### Current State
Groq GenAI generates explanation without recording input sources.

### Integration Pattern

```python
# multi_agent/services/explanation_service.py

from multi_agent.provenance import ProvenanceCapture, ProvenanceTracer

class ExplanationService:
    def explain(self, case: InvestigationCase, 
                findings: List[Finding], 
                synthesis_result: InvestigationResult) -> ExplanationResult:
        """Generate explanation using Groq GenAI."""
        
        # Get current trace context
        tracer = ProvenanceTracer()
        context = tracer.current_context()
        
        # Prepare prompt with evidence IDs (not internal data)
        evidence_ids = [f.evidence_id for f in findings]
        
        prompt = self._build_prompt(
            case=case,
            findings=findings,
            risk_score=synthesis_result.risk_score,
            evidence_ids=evidence_ids  # Include for traceability
        )
        
        # Record GenAI START
        start_time = time.time()
        
        try:
            # Call Groq API (unchanged)
            response = self.groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}]
            )
            
            explanation = response.choices[0].message.content
            duration_ms = (time.time() - start_time) * 1000
            
            # RECORD GENAI SUCCESS
            if context:
                tracer.current_tracer().record_genai(
                    GenAIMetadataBuilder.create(
                        case_id=case.case_id,
                        model_name="llama-3.3-70b-versatile",
                        provider="Groq",
                        status="generated",
                        input_evidence_ids=evidence_ids,
                        input_finding_count=len(findings),
                        duration_ms=int(duration_ms)
                    )
                )
            
            return ExplanationResult(
                explanation=explanation,
                evidence_ids=evidence_ids,
                model="llama-3.3-70b-versatile"
            )
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            
            # RECORD GENAI ERROR
            if context:
                tracer.record_genai(
                    GenAIMetadataBuilder.create(
                        case_id=case.case_id,
                        model_name="llama-3.3-70b-versatile",
                        provider="Groq",
                        status="error",
                        error_message=str(e),
                        duration_ms=int(duration_ms)
                    )
                )
            
            # Return unavailable explanation
            return ExplanationResult(
                explanation=f"Explanation unavailable: {str(e)}",
                evidence_ids=[],
                model="llama-3.3-70b-versatile",
                error=True
            )
```

**Key Points**:
- Include `evidence_ids` in prompt for traceability
- Record GenAI metadata with evidence IDs input
- Handle both success and error paths
- Groq API call unchanged
- Duration captured for performance monitoring

## Pattern 4: Agent-Level Integration (Future)

### Current State
Agents generate findings without recording their internal logic.

### Integration Pattern

```python
# Example: multi_agent/agents/billing_agent.py

from multi_agent.provenance import ProvenanceTracer, RuleProvenanceBuilder

class BillingAgent:
    def investigate(self, case: InvestigationCase) -> AgentResult:
        """Billing analysis."""
        
        tracer = ProvenanceTracer()
        context = tracer.current_context()
        
        findings = []
        
        for claim in case.claims:
            # Check rule: High Payment Charge Ratio
            if claim.payment_charge_ratio > THRESHOLD:
                finding = Finding(
                    finding_id=f"F-{uuid.uuid4().hex[:8]}",
                    rule="high_payment_charge_ratio",
                    evidence_id="EV-001",
                    ...
                )
                
                # RECORD RULE PROVENANCE (optional detail)
                if context:
                    rule_prov = RuleProvenanceBuilder.from_rule_hit(
                        rule_id="R01",
                        rule_name="High Payment Charge Ratio",
                        status="TRIGGERED",
                        condition="payment / charge > 2.0",
                        threshold=2.0,
                        threshold_operator=">",
                        input_fields=["payment", "charge"],
                        input_values=[claim.payment, claim.charge],
                        rule_version="1.0.0"
                    )
                    # Store on finding for synthesis phase
                    finding.rule_provenance = rule_prov
                
                findings.append(finding)
        
        return AgentResult(findings=findings)
```

**Key Points**:
- Optional agent-level rule recording
- RuleProvenanceBuilder captures complete rule logic
- Rule provenance stored on Finding object
- Allows synthesis/RAG team to validate rules

## Backward Compatibility Checklist

When integrating ProvenanceCapture:

- ✅ All existing method signatures unchanged
- ✅ ProvenanceCapture is optional (no exceptions if not called)
- ✅ Provenance errors don't propagate to investigation (defensive)
- ✅ Tracer is thread-safe (contextvars)
- ✅ All findings unchanged (provenance added but not required)
- ✅ Synthesis result format unchanged
- ✅ GenAI explanation format unchanged
- ✅ All agents work with/without provenance
- ✅ Existing tests still pass

## Testing Integration

### Test Pattern for Orchestrator

```python
def test_orchestrator_with_provenance():
    """Verify orchestrator records provenance."""
    case = create_test_case()
    orchestrator = Orchestrator()
    
    result = orchestrator.investigate(case)
    
    # Provenance should be attached
    assert result.provenance is not None
    
    # Should have recorded agent executions
    assert len(result.provenance["agent_executions"]) >= 1
    
    # Should have routing decisions
    assert result.provenance["routing"] is not None
    
    # Should have synthesis breakdown
    assert result.provenance["synthesis"] is not None
    
    # Trace ID should be present
    assert result.provenance["trace_id"] is not None
    
    # Result score should match synthesis calculation
    assert result.risk_score == result.provenance["synthesis"]["final_score"]
```

### Test Pattern for Evidence Traceability

```python
def test_evidence_traceability():
    """Verify evidence is traceable to source."""
    result = run_investigation(case)
    
    for finding in result.findings:
        for evidence_id in finding.evidence_ids:
            evidence = find_evidence(evidence_id)
            
            # Evidence must have source
            assert evidence.source is not None
            
            # Source must be in provenance
            assert evidence.source in result.provenance["synthesis"]["inputs"]
            
            # Must have provenance dict
            assert evidence.provenance is not None
            
            # Source fields must be populated
            assert evidence.source_fields is not None
            assert len(evidence.source_fields) > 0
```

## Performance Considerations

Provenance capture has minimal overhead:

| Operation | Time | Notes |
|-----------|------|-------|
| start_trace() | <1ms | Creates trace context |
| record_agent_execution() | <1ms | Appends to list |
| record_routing() | <1ms | Assigns metadata |
| record_synthesis() | <1ms | Assigns metadata |
| record_genai() | <1ms | Appends to list |
| finalize() | <5ms | Converts to dict |
| **Total per case** | <15ms | Negligible |

Provenance adds <15ms per investigation (typically 5-10 minute investigations = 0.02% overhead).

## Error Handling Strategy

ProvenanceCapture is defensive:

```python
class ProvenanceCapture:
    def record_agent_execution(self, ...):
        """Record gracefully, don't break investigation."""
        try:
            tracer = ProvenanceTracer()
            context = tracer.current_context()
            if not context:
                return  # No trace context, skip
            
            # Create and record metadata
            ...
            
        except Exception as e:
            # Log error but don't propagate
            logger.warning(f"Provenance recording failed: {e}")
            return
```

Never fails the investigation if provenance fails.

---

## Summary

These patterns enable non-invasive provenance integration:

1. **Orchestrator**: Records routing + agent executions
2. **Synthesis**: Records contribution breakdown
3. **GenAI**: Records model + evidence IDs + status
4. **Agents** (optional): Records rule logic details

All changes are additive, backward compatible, and maintain the existing deterministic scoring methodology.
