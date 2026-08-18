from __future__ import annotations

<<<<<<< HEAD
from dataclasses import dataclass
from math import isnan
from typing import Any, Dict, List, Optional

from multi_agent.config.agent_llm_config import DEFAULT_AGENT_LLM_CONFIG
from multi_agent.schemas.finding import Finding
from multi_agent.schemas.investigation_case import InvestigationCase
from multi_agent.services.llm_agent_service import LLMAgentService, ToolDefinition
from multi_agent.services.explanation_service import InvestigationExplanationService
from multi_agent.utils.redaction import redact_for_llm


@dataclass
class ClinicalRuleAgentResult:
    """Result from clinical rule agent investigation."""

    findings: List[Finding]
    narrative: str
    tools_called: List[str]
    status: str
=======
from math import isnan
from typing import Any, Dict, List, Optional

from multi_agent.schemas.finding import Finding
from multi_agent.schemas.investigation_case import InvestigationCase
>>>>>>> b166e40 (removed old data)


class ClinicalRuleAgent:
    """Deterministic, evidence-based claim rule engine using only ClaimContext.

    This milestone intentionally does not fabricate unsupported medical diagnoses,
    unsupported fraud conclusions, or synthetic clinical thresholds. It only surfaces
    rule and utilization evidence that is already present in the exported claim data.
    """

<<<<<<< HEAD
    def __init__(self, llm_service: Optional[InvestigationExplanationService] = None, llm_agent_service: Optional[LLMAgentService] = None, llm_config: Optional[Dict[str, Any]] = None):
        self.llm_service = llm_service or InvestigationExplanationService(enabled=True)
        self.llm_config = llm_config or DEFAULT_AGENT_LLM_CONFIG["clinical_rule"].to_dict()
        # Create LLMAgentService with config-driven max_tokens
        self.llm_agent_service = llm_agent_service or LLMAgentService(
            enabled=True,
            max_tokens=self.llm_config.get("max_tokens", 600),
        )

    def investigate_with_llm(
        self,
        case: InvestigationCase,
        claim_risk_score: Optional[float] = None,
        enable_llm: bool = True,
        focus_hint: Optional[str] = None,
    ) -> ClinicalRuleAgentResult:
        """Investigate claim using LLM-directed tool calling.

        Args:
            case: Investigation case with claim and provider context.
            claim_risk_score: Pre-computed claim risk score for context.
            enable_llm: Whether to use LLM; fall back to deterministic if False.
            focus_hint: Optional LLM guidance for investigation focus (from orchestrator routing rationale).

        Returns:
            ClinicalRuleAgentResult with findings, narrative, tools called, and status.
        """
        if not enable_llm or not self.llm_agent_service.enabled:
            # Fallback to deterministic investigation
            findings = self.investigate(case)
            return ClinicalRuleAgentResult(
                findings=findings,
                narrative="Deterministic clinical review completed.",
                tools_called=[],
                status="fallback",
            )

        # Build tool registry for this investigation
        tool_registry = {
            "check_outpatient_utilization": lambda ctx: self._tool_outpatient_utilization(ctx),
            "check_inpatient_consensus": lambda ctx: self._tool_inpatient_consensus(ctx),
            "check_procedure_volume": lambda ctx: self._tool_procedure_volume(ctx),
        }

        # Build case context for LLM
        case_context = {
            "case_id": case.case_id,
            "claim_id": getattr(case.claim, "claim_id", None) if case.claim else None,
            "claim_type": getattr(case.claim, "claim_type", None) if case.claim else None,
            "claim_risk_score": claim_risk_score or (getattr(case.claim, "claim_risk_score", None) if case.claim else None),
        }
        # Redact PHI/PII before sending to LLM (HIPAA compliance)
        case_context = redact_for_llm(case_context)

        # Get tool definitions from config
        tool_defs = [ToolDefinition(name=t.name, description=t.description) for t in DEFAULT_AGENT_LLM_CONFIG["clinical_rule"].tools]

        # Invoke LLM to reason about which tools to run
        fallback = "Clinical investigation complete; deterministic findings remain authoritative."
        reasoning_result = self.llm_agent_service.reason_with_tools(
            agent_name="clinical_rule",
            case_context=case_context,
            available_tools=tool_defs,
            tool_registry=tool_registry,
            fallback_narrative=fallback,
            focus_hint=focus_hint,
            case=case,
        )

        # If LLM call failed, fall back to deterministic
        if reasoning_result.status != "success":
            findings = self.investigate(case)
            return ClinicalRuleAgentResult(
                findings=findings,
                narrative=reasoning_result.narrative,
                tools_called=[],
                status="fallback",
            )

        # Call selected tools and collect findings
        findings = []
        for tool_name in reasoning_result.selected_tools:
            if tool_name in tool_registry:
                try:
                    tool_result = tool_registry[tool_name](case)
                    if isinstance(tool_result, list):
                        findings.extend(tool_result)
                    elif isinstance(tool_result, Finding):
                        findings.append(tool_result)
                except Exception:  # pragma: no cover
                    pass

        # If no tools returned findings, fall back to deterministic
        if not findings:
            findings = self.investigate(case)

        return ClinicalRuleAgentResult(
            findings=findings,
            narrative=reasoning_result.narrative,
            tools_called=reasoning_result.selected_tools,
            status="partial" if reasoning_result.tool_failures else "success",
        )

    def _tool_outpatient_utilization(self, case: InvestigationCase) -> List[Finding]:
        """Tool: Check outpatient utilization patterns."""
        if case is None or case.claim is None or case.claim.claim_type != "OUTPATIENT":
            return []
        return self._outpatient_findings(case.claim)

    def _tool_inpatient_consensus(self, case: InvestigationCase) -> List[Finding]:
        """Tool: Check inpatient model consensus."""
        if case is None or case.claim is None or case.claim.claim_type != "INPATIENT":
            return []
        return self._inpatient_findings(case.claim)

    def _tool_procedure_volume(self, case: InvestigationCase) -> List[Finding]:
        """Tool: Check procedure volume in claim."""
        if case is None or case.claim is None:
            return []
        procedure = self._values(case.claim.procedure_evidence)
        findings = []
        if procedure:
            procedure_count = self._float(procedure.get("procedure_code_count"))
            unique_procedure_count = self._float(procedure.get("unique_procedure_code_count"))
            has_procedure = self._as_bool(procedure.get("has_procedure"))
            if has_procedure is True or (procedure_count is not None and procedure_count >= 10):
                findings.append(
                    self._finding(
                        rule="high_procedure_volume",
                        category="procedure",
                        severity="medium",
                        description="Claim shows elevated procedure volume.",
                        evidence={
                            "has_procedure": has_procedure,
                            "procedure_code_count": procedure_count,
                            "unique_procedure_code_count": unique_procedure_count,
                        },
                        confidence=0.76,
                    )
                )
        return findings

=======
>>>>>>> b166e40 (removed old data)
    def investigate(self, case: InvestigationCase) -> List[Finding]:
        if case is None or case.claim is None:
            return []

        claim = case.claim
        if claim.claim_type in {None, "CARRIER"}:
<<<<<<< HEAD
            return self._complete_with_llm(case, [])
=======
            return []
>>>>>>> b166e40 (removed old data)

        findings: List[Finding] = []

        if claim.claim_type == "OUTPATIENT":
            findings.extend(self._outpatient_findings(claim))
        elif claim.claim_type == "INPATIENT":
            findings.extend(self._inpatient_findings(claim))

<<<<<<< HEAD
        return self._complete_with_llm(case, findings)

    def _complete_with_llm(self, case: InvestigationCase, findings: List[Finding]) -> List[Finding]:
        narrative = self._llm_narrative(case, findings)
        for finding in findings:
            finding.agent_narrative = narrative
            finding.tool_results = {"tool": "clinical_rule_review", "finding_count": len(findings)}
        return findings

    def _llm_narrative(self, case: InvestigationCase, findings: List[Finding]) -> str:
        if not self.llm_service.enabled:
            return "Deterministic clinical and rule checks remain the source of truth for this claim."
        context = {
            "case_id": getattr(case, "case_id", "UNKNOWN"),
            "claim_id": getattr(case.claim, "claim_id", "UNKNOWN") if case.claim else "UNKNOWN",
            "claim_type": getattr(case.claim, "claim_type", None) if case.claim else None,
            "findings": [{"rule": f.rule, "severity": f.severity, "description": f.description, "evidence": f.evidence} for f in findings],
        }
        fallback = "Clinical and rule review shows the claim requires additional context review, but the deterministic rule findings remain the authoritative basis for the investigation."
        reasoning = self.llm_service.generate_structured_reasoning("clinical_rule", context, fallback=fallback)
        return str(reasoning.get("narrative") or fallback)

=======
        return findings

>>>>>>> b166e40 (removed old data)
    def _outpatient_findings(self, claim) -> List[Finding]:
        findings: List[Finding] = []
        utilization = self._values(claim.utilization_evidence)
        procedure = self._values(claim.procedure_evidence)

        if not utilization and not procedure:
            return findings

        multiple_lines = self._as_bool(utilization.get("has_multiple_lines"))
        multiple_diagnoses = self._as_bool(utilization.get("has_multiple_diagnoses"))
        repeat_beneficiary = self._as_bool(utilization.get("is_repeat_beneficiary_claim"))
        beneficiary_count = self._float(utilization.get("beneficiary_claim_count"))
        provider_count = self._float(utilization.get("provider_claim_count"))
        line_count = self._float(utilization.get("claim_line_count"))

        procedure_count = self._float(procedure.get("procedure_code_count"))
        unique_procedure_count = self._float(procedure.get("unique_procedure_code_count"))
        has_procedure = self._as_bool(procedure.get("has_procedure"))

        if multiple_lines is True or (line_count is not None and line_count >= 6):
            findings.append(
                self._finding(
                    rule="outpatient_multiple_lines_utilization",
                    category="utilization",
                    severity="medium",
                    description="Outpatient claim includes a high number of billing lines, increasing review priority.",
                    evidence={
                        "claim_line_count": line_count,
                        "has_multiple_lines": multiple_lines,
                    },
                    confidence=0.78,
                )
            )

        if multiple_diagnoses is True or (beneficiary_count is not None and beneficiary_count >= 3):
            findings.append(
                self._finding(
                    rule="outpatient_repeat_beneficiary_pattern",
                    category="utilization",
                    severity="medium",
                    description="Outpatient utilization pattern shows repeated beneficiary activity and/or multiple diagnoses for review.",
                    evidence={
                        "has_multiple_diagnoses": multiple_diagnoses,
                        "beneficiary_claim_count": beneficiary_count,
                        "is_repeat_beneficiary_claim": repeat_beneficiary,
                    },
                    confidence=0.75,
                )
            )

        if has_procedure is True or (procedure_count is not None and procedure_count >= 10):
            findings.append(
                self._finding(
                    rule="outpatient_high_procedure_volume",
                    category="procedure",
                    severity="medium",
                    description="Outpatient claim shows elevated procedure volume relative to the claim’s normal procedural footprint.",
                    evidence={
                        "has_procedure": has_procedure,
                        "procedure_code_count": procedure_count,
                        "unique_procedure_code_count": unique_procedure_count,
                    },
                    confidence=0.76,
                )
            )

        if provider_count is not None and provider_count >= 3:
            findings.append(
                self._finding(
                    rule="outpatient_provider_activity_pattern",
                    category="utilization",
                    severity="low",
                    description="Outpatient claim is associated with repeated provider activity patterns that warrant additional context review.",
                    evidence={"provider_claim_count": provider_count},
                    confidence=0.68,
                )
            )

        return findings

    def _inpatient_findings(self, claim) -> List[Finding]:
        model = self._values(claim.model_evidence)
        if not model:
            return []

        consensus = self._coerce_text(model.get("model_consensus"))
        consensus_count = self._float(model.get("model_consensus_count"))
        if consensus is None and consensus_count is None:
            return []

        findings: List[Finding] = []
        if consensus and "MODEL_CONSENSUS" in str(consensus):
            findings.append(
                self._finding(
                    rule="inpatient_model_consensus",
                    category="model",
                    severity="high" if (consensus_count is not None and consensus_count >= 3) else "medium",
                    description="Inpatient claim has model consensus signals that align with elevated review priority.",
                    evidence={
                        "model_consensus": consensus,
                        "model_consensus_count": consensus_count,
                        "isolation_forest_flag": self._as_bool(model.get("isolation_forest_flag")),
                        "lof_flag": self._as_bool(model.get("lof_flag")),
                        "one_class_svm_flag": self._as_bool(model.get("one_class_svm_flag")),
                    },
                    confidence=0.9 if (consensus_count is not None and consensus_count >= 3) else 0.8,
                )
            )
        return findings

    @staticmethod
    def _values(bundle: Optional[Any]) -> Dict[str, Any]:
        if bundle is None:
            return {}
        if isinstance(bundle, dict):
            values = bundle.get("values") if isinstance(bundle.get("values"), dict) else bundle
            return values if isinstance(values, dict) else {}
        if hasattr(bundle, "values"):
            values = getattr(bundle, "values") or {}
            return values if isinstance(values, dict) else {}
        return {}

    @staticmethod
    def _float(value: Any) -> Optional[float]:
        if value is None:
            return None
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            f = float(value)
            return None if isnan(f) else f
        if isinstance(value, str):
            cleaned = value.strip()
            if cleaned == "" or cleaned.lower() in {"nan", "none", "null"}:
                return None
            try:
                f = float(cleaned)
                return None if isnan(f) else f
            except ValueError:
                return None
        return None

    @staticmethod
    def _as_bool(value: Any) -> Optional[bool]:
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "y", "t"}:
                return True
            if normalized in {"0", "false", "no", "n", "f"}:
                return False
        return None

    @staticmethod
    def _coerce_text(value: Any) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, str):
            cleaned = value.strip()
            return cleaned if cleaned else None
        return str(value)

    @staticmethod
    def _finding(
        rule: str,
        category: str,
        severity: str,
        description: str,
        evidence: Dict[str, Any],
        confidence: float,
    ) -> Finding:
        return Finding(
            agent="clinical_rule",
            category=category,
            rule=rule,
            severity=severity,
            description=description,
            evidence=evidence,
            confidence=confidence,
        )
