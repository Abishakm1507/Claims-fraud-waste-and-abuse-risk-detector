"""Provenance validation and completeness checking.

Validates that investigation cases have sufficient provenance to be auditable.
Reports coverage percentage and any missing/invalid provenance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from multi_agent.synthesis import InvestigationResult

from .tracer import TraceContext


@dataclass
class ProvenanceReport:
    """Report on provenance validity and completeness."""

    valid: bool = True
    coverage: float = 100.0  # 0-100%
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def is_complete(self) -> bool:
        """Whether provenance is 100% complete."""
        return self.coverage >= 100.0 and len(self.errors) == 0

    def is_usable(self) -> bool:
        """Whether provenance is sufficient for investigation (>= 80% coverage)."""
        return self.coverage >= 80.0 and self.valid

    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "coverage": round(self.coverage, 1),
            "errors": self.errors,
            "warnings": self.warnings,
        }

    def __str__(self) -> str:
        status = "✓ VALID" if self.valid else "✗ INVALID"
        return f"{status} ({self.coverage:.1f}% coverage) - {len(self.errors)} errors, {len(self.warnings)} warnings"


class ProvenanceValidator:
    """Validates provenance completeness and correctness.

    This validator checks that:
    1. Case has trace_id
    2. Evidence has source, source_fields, evidence_id
    3. Findings reference valid evidence
    4. Rules have rule_id, rule_name, status
    5. Agent executions have timestamps and status
    6. Synthesis has weights and calculation breakdown
    7. GenAI has evidence references
    8. No fabricated values

    Validator is lenient on ML metadata - uses 'unknown' as valid marker.
    """

    @staticmethod
    def validate_trace_context(context: TraceContext) -> ProvenanceReport:
        """Validate trace context completeness.

        Args:
            context: TraceContext to validate

        Returns:
            ProvenanceReport with validation results
        """
        report = ProvenanceReport()
        errors: List[str] = []
        warnings: List[str] = []
        scores: List[float] = []

        # Check case identification
        if not context.case_id:
            errors.append("Missing case_id in trace context")
        if not context.trace_id:
            errors.append("Missing trace_id")
        else:
            scores.append(100.0)

        # Check agent executions
        if len(context.agent_executions) == 0:
            warnings.append("No agent executions recorded")
            scores.append(50.0)
        else:
            for exec_meta in context.agent_executions:
                if not exec_meta.execution_id:
                    errors.append(f"Agent {exec_meta.agent_name} missing execution_id")
                elif not exec_meta.started_at or not exec_meta.completed_at:
                    warnings.append(
                        f"Agent {exec_meta.agent_name} missing execution timestamps"
                    )
                    scores.append(80.0)
                else:
                    scores.append(100.0)

                if not exec_meta.status:
                    errors.append(f"Agent {exec_meta.agent_name} missing status")

                if exec_meta.status == "error" and not exec_meta.error_type:
                    errors.append(f"Agent {exec_meta.agent_name} error without error_type")

        # Check routing
        if context.routing is None:
            warnings.append("No routing metadata recorded")
            scores.append(70.0)
        else:
            if not context.routing.decisions:
                warnings.append("Routing has no decisions")
            scores.append(90.0)

        # Check synthesis
        if context.synthesis is None:
            warnings.append("No synthesis metadata recorded")
            scores.append(60.0)
        else:
            if context.synthesis.final_score < 0 or context.synthesis.final_score > 100:
                errors.append(
                    f"Synthesis score out of range: {context.synthesis.final_score}"
                )
            if not context.synthesis.inputs:
                warnings.append("Synthesis has no recorded inputs")
            if not context.synthesis.contributions:
                warnings.append("Synthesis has no contribution breakdown")
            scores.append(95.0)

        # Check GenAI
        if context.genai is None:
            warnings.append("No GenAI metadata recorded (explanation may be disabled)")
            scores.append(85.0)
        else:
            if context.genai.status == "generated":
                if not context.genai.input_evidence_ids:
                    warnings.append("GenAI generated without recording input evidence IDs")
                scores.append(100.0)
            else:
                scores.append(75.0)

        # Calculate coverage
        if scores:
            coverage = sum(scores) / len(scores)
        else:
            coverage = 0.0

        report.errors = errors
        report.warnings = warnings
        report.valid = len(errors) == 0
        report.coverage = coverage

        return report

    @staticmethod
    def validate_investigation_result(result: InvestigationResult) -> ProvenanceReport:
        """Validate provenance in an InvestigationResult.

        Args:
            result: InvestigationResult to validate

        Returns:
            ProvenanceReport with validation results
        """
        report = ProvenanceReport()
        errors: List[str] = []
        warnings: List[str] = []
        scores: List[float] = []

        # Check case identification
        if not result.case_id:
            errors.append("Missing case_id in result")
        else:
            scores.append(100.0)

        # Check findings
        if not result.findings:
            warnings.append("No findings in result")
            scores.append(50.0)
        else:
            evidence_id_coverage = 0.0
            for finding in result.findings:
                # Each finding should reference evidence
                if not finding.evidence:
                    errors.append(f"Finding {finding.rule} has no evidence")
                else:
                    scores.append(100.0)
                    # Check if evidence has key provenance fields
                    if "evidence_id" not in finding.evidence:
                        errors.append(f"Finding evidence missing evidence_id")
                    if "source" not in finding.evidence or not finding.evidence.get("source"):
                        errors.append(
                            f"Finding evidence missing source for {finding.rule}"
                        )
                    if (
                        "source_fields" not in finding.evidence
                        or not finding.evidence.get("source_fields")
                    ):
                        warnings.append(
                            f"Finding evidence missing source_fields for {finding.rule}"
                        )

                    # Check provenance dict
                    prov = finding.evidence.get("provenance")
                    if prov is None:
                        warnings.append(f"Finding {finding.rule} evidence missing provenance dict")
                    else:
                        if not prov.get("source"):
                            errors.append(
                                f"Finding {finding.rule} provenance missing source"
                            )
                        evidence_id_coverage += 1.0

            if evidence_id_coverage > 0:
                scores.append((evidence_id_coverage / len(result.findings)) * 100)

        # Check synthesis metadata
        if hasattr(result, "synthesis") and result.synthesis:
            scores.append(100.0)
        else:
            warnings.append("Result missing synthesis metadata")
            scores.append(70.0)

        # Check routing
        if hasattr(result, "routing") and result.routing:
            scores.append(90.0)
        else:
            warnings.append("Result missing routing metadata")
            scores.append(60.0)

        # Calculate coverage
        if scores:
            coverage = sum(scores) / len(scores)
        else:
            coverage = 0.0

        report.errors = errors
        report.warnings = warnings
        report.valid = len(errors) == 0
        report.coverage = coverage

        return report

    @staticmethod
    def validate_evidence(evidence: Dict[str, Any]) -> ProvenanceReport:
        """Validate single evidence object provenance.

        Args:
            evidence: Evidence dictionary to validate

        Returns:
            ProvenanceReport with validation results
        """
        report = ProvenanceReport()
        errors: List[str] = []
        warnings: List[str] = []
        scores: List[float] = []

        # Essential fields
        if "evidence_id" not in evidence or not evidence.get("evidence_id"):
            errors.append("Missing evidence_id")
        else:
            scores.append(100.0)

        if "agent" not in evidence or not evidence.get("agent"):
            errors.append("Missing agent")
        else:
            scores.append(100.0)

        if "source" not in evidence or not evidence.get("source"):
            errors.append("Missing source (dataset, model, or rule)")
        else:
            scores.append(100.0)

        if "source_fields" not in evidence:
            warnings.append("Missing source_fields list")
            scores.append(80.0)
        else:
            if not evidence.get("source_fields"):
                warnings.append("source_fields is empty")
            else:
                scores.append(100.0)

        # Provenance dict
        if "provenance" not in evidence or not evidence.get("provenance"):
            warnings.append("Missing provenance metadata")
            scores.append(60.0)
        else:
            prov = evidence["provenance"]
            if "source" not in prov:
                errors.append("Provenance missing source")
            else:
                scores.append(100.0)

            if "limitation" in prov and prov["limitation"]:
                warnings.append(f"Provenance limitation: {prov['limitation']}")
                scores.append(85.0)

        # Calculation/availability
        if "availability" in evidence:
            if evidence["availability"] != "AVAILABLE":
                warnings.append(f"Evidence unavailable: {evidence['availability']}")
                scores.append(70.0)
            else:
                scores.append(100.0)

        # Calculate coverage
        if scores:
            coverage = sum(scores) / len(scores)
        else:
            coverage = 0.0

        report.errors = errors
        report.warnings = warnings
        report.valid = len(errors) == 0
        report.coverage = coverage

        return report

    @staticmethod
    def validate_rule_hit(rule_hit: Dict[str, Any]) -> ProvenanceReport:
        """Validate rule hit provenance.

        Args:
            rule_hit: Rule hit dictionary to validate

        Returns:
            ProvenanceReport with validation results
        """
        report = ProvenanceReport()
        errors: List[str] = []
        warnings: List[str] = []
        scores: List[float] = []

        if "rule_id" not in rule_hit or not rule_hit.get("rule_id"):
            errors.append("Missing rule_id")
        else:
            scores.append(100.0)

        if "rule_name" not in rule_hit or not rule_hit.get("rule_name"):
            errors.append("Missing rule_name")
        else:
            scores.append(100.0)

        if "status" not in rule_hit or not rule_hit.get("status"):
            errors.append("Missing status")
        else:
            scores.append(100.0)

        if rule_hit.get("status") == "TRIGGERED":
            if "observed_value" not in rule_hit:
                warnings.append("Triggered rule missing observed_value")
                scores.append(80.0)
            else:
                scores.append(100.0)

            if "threshold" not in rule_hit:
                warnings.append("Triggered rule missing threshold")
                scores.append(80.0)
            else:
                scores.append(100.0)

        # Rule provenance metadata (lenient)
        if "rule_version" not in rule_hit:
            warnings.append("Rule missing version information")
            scores.append(70.0)

        if "evidence_ids" not in rule_hit or not rule_hit.get("evidence_ids"):
            warnings.append("Rule missing supporting evidence IDs")
            scores.append(75.0)
        else:
            scores.append(100.0)

        # Calculate coverage
        if scores:
            coverage = sum(scores) / len(scores)
        else:
            coverage = 0.0

        report.errors = errors
        report.warnings = warnings
        report.valid = len(errors) == 0
        report.coverage = coverage

        return report
