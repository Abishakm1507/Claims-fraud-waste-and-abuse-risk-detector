from __future__ import annotations

<<<<<<< HEAD
from dataclasses import dataclass
from math import isnan
from typing import Any, Dict, List, Optional

from multi_agent.config.agent_llm_config import DEFAULT_AGENT_LLM_CONFIG, ToolSchema
from multi_agent.schemas.finding import Finding
from multi_agent.schemas.investigation_case import InvestigationCase
from multi_agent.services.llm_agent_service import LLMAgentService, ToolDefinition
from multi_agent.services.explanation_service import InvestigationExplanationService
from multi_agent.utils.redaction import redact_for_llm


@dataclass
class BillingAgentResult:
    """Result from billing agent investigation."""

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


class BillingAgent:
    """Deterministic billing-focused rule engine over ClaimContext data."""

<<<<<<< HEAD
    def __init__(
        self,
        llm_service: Optional[InvestigationExplanationService] = None,
        llm_agent_service: Optional[LLMAgentService] = None,
        llm_config: Optional[Dict[str, Any]] = None,
    ):
        self.llm_service = llm_service or InvestigationExplanationService(enabled=True)
        self.llm_config = llm_config or DEFAULT_AGENT_LLM_CONFIG["billing"].to_dict()
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
    ) -> BillingAgentResult:
        """Investigate claim using LLM-directed tool calling.

        Args:
            case: Investigation case with claim and provider context.
            claim_risk_score: Pre-computed claim risk score for context.
            enable_llm: Whether to use LLM; fall back to deterministic if False.
            focus_hint: Optional LLM guidance for investigation focus (from orchestrator routing rationale).

        Returns:
            BillingAgentResult with findings, narrative, tools called, and status.
        """
        if not enable_llm or not self.llm_agent_service.enabled:
            # Fallback to deterministic investigation
            findings = self.investigate(case)
            return BillingAgentResult(
                findings=findings,
                narrative="Deterministic billing review completed.",
                tools_called=[],
                status="fallback",
            )

        # Build tool registry for this investigation
        tool_registry = {
            "check_payment_charge_ratio": lambda ctx: self._tool_payment_charge_ratio(ctx),
            "check_payment_deviation": lambda ctx: self._tool_payment_deviation(ctx),
            "check_reconciliation_issue": lambda ctx: self._tool_reconciliation_issue(ctx),
            "check_claim_volume": lambda ctx: self._tool_claim_volume(ctx),
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
        tool_defs = [ToolDefinition(name=t.name, description=t.description) for t in DEFAULT_AGENT_LLM_CONFIG["billing"].tools]

        # Invoke LLM to reason about which tools to run
        fallback = "Billing investigation complete; deterministic findings remain authoritative."
        reasoning_result = self.llm_agent_service.reason_with_tools(
            agent_name="billing",
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
            return BillingAgentResult(
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

        return BillingAgentResult(
            findings=findings,
            narrative=reasoning_result.narrative,
            tools_called=reasoning_result.selected_tools,
            status="partial" if reasoning_result.tool_failures else "success",
        )

    def _tool_payment_charge_ratio(self, case: InvestigationCase) -> List[Finding]:
        """Tool: Check payment-to-charge ratio."""
        if case is None or case.claim is None:
            return []

        claim = case.claim
        financial_values = self._values(claim.financial_evidence)

        payment = self._float(
            financial_values.get("total_claim_payment")
            if financial_values.get("total_claim_payment") is not None
            else financial_values.get("claim_payment")
        )
        charge = self._float(
            financial_values.get("total_claim_charge")
            if financial_values.get("total_claim_charge") is not None
            else financial_values.get("submitted_charge")
        )

        findings = []
        if payment is not None and charge is not None and charge > 0:
            ratio = payment / charge
            if ratio >= 2.5:
                findings.append(
                    self._finding(
                        rule="payment_charge_ratio",
                        category="financial",
                        severity="high",
                        description=f"Claim payment-to-charge ratio is {ratio:.2f}x, well above typical reimbursement levels.",
                        evidence={"payment": payment, "charge": charge, "ratio": ratio},
                        confidence=0.94,
                    )
                )
        return findings

    def _tool_payment_deviation(self, case: InvestigationCase) -> List[Finding]:
        """Tool: Check payment deviation from provider benchmark."""
        if case is None or case.claim is None:
            return []

        claim = case.claim
        financial_values = self._values(claim.financial_evidence)
        utilization_values = self._values(claim.utilization_evidence)

        payment = self._float(
            financial_values.get("total_claim_payment")
            if financial_values.get("total_claim_payment") is not None
            else financial_values.get("claim_payment")
        )
        avg_payment = self._float(utilization_values.get("provider_avg_claim_payment"))

        findings = []
        if payment is not None and avg_payment is not None and avg_payment > 0:
            deviation_ratio = payment / avg_payment
            if deviation_ratio >= 2.0:
                findings.append(
                    self._finding(
                        rule="provider_payment_deviation",
                        category="financial",
                        severity="high",
                        description=f"Claim payment exceeds the provider benchmark by {deviation_ratio:.2f}x.",
                        evidence={"payment": payment, "provider_avg_claim_payment": avg_payment, "ratio": deviation_ratio},
                        confidence=0.9,
                    )
                )
        return findings

    def _tool_reconciliation_issue(self, case: InvestigationCase) -> List[Finding]:
        """Tool: Check payment reconciliation issues."""
        if case is None or case.claim is None:
            return []

        claim = case.claim
        financial_values = self._values(claim.financial_evidence)
        utilization_values = self._values(claim.utilization_evidence)

        reconciliation_flag = self._as_bool(
            financial_values.get("has_payment_reconciliation_issue")
            if financial_values.get("has_payment_reconciliation_issue") is not None
            else utilization_values.get("has_payment_reconciliation_issue")
        )

        findings = []
        if reconciliation_flag is True:
            findings.append(
                self._finding(
                    rule="payment_reconciliation_issue",
                    category="financial",
                    severity="medium",
                    description="Claim shows a payment reconciliation issue that merits billing review.",
                    evidence={"has_payment_reconciliation_issue": True},
                    confidence=0.82,
                )
            )
        return findings

    def _tool_claim_volume(self, case: InvestigationCase) -> List[Finding]:
        """Tool: Check claim volume and line count."""
        if case is None or case.claim is None:
            return []

        claim = case.claim
        utilization_values = self._values(claim.utilization_evidence)

        findings = []

        # Check high volume provider
        is_high_volume_provider = self._as_bool(utilization_values.get("is_high_volume_provider"))
        if is_high_volume_provider is True:
            findings.append(
                self._finding(
                    rule="high_volume_provider",
                    category="utilization",
                    severity="medium",
                    description="Provider is flagged as high-volume, increasing the significance of the billing pattern.",
                    evidence={"is_high_volume_provider": True},
                    confidence=0.75,
                )
            )

        # Check multiple lines
        line_count = self._float(utilization_values.get("claim_line_count"))
        multiple_lines = self._as_bool(utilization_values.get("has_multiple_lines"))
        if multiple_lines is True or (line_count is not None and line_count >= 5):
            findings.append(
                self._finding(
                    rule="multiple_claim_lines",
                    category="utilization",
                    severity="medium",
                    description="Claim contains multiple billing lines or a high line count, which can increase review priority.",
                    evidence={"claim_line_count": line_count, "has_multiple_lines": multiple_lines},
                    confidence=0.7,
                )
            )

        return findings

=======
>>>>>>> b166e40 (removed old data)
    def investigate(self, case: InvestigationCase) -> List[Finding]:
        if case is None or case.claim is None:
            return []

        claim = case.claim
        financial_values = self._values(claim.financial_evidence)
        utilization_values = self._values(claim.utilization_evidence)

        findings: List[Finding] = []

        if claim.claim_type == "CARRIER":
            payment = self._float(financial_values.get("claim_payment"))
            submitted = self._float(financial_values.get("submitted_charge"))
            if payment is not None and submitted is not None and submitted > 0:
                findings.append(
                    self._finding(
                        rule="carrier_first_line_payment",
                        category="financial",
                        severity="medium",
                        description=(
                            "Carrier claim includes a first claim line payment of "
                            f"${payment:,.2f} against a submitted charge of ${submitted:,.2f}."
                        ),
                        evidence={"payment": payment, "submitted_charge": submitted, "ratio": payment / submitted},
                        confidence=0.72,
                    )
                )

        if claim.claim_type not in {"CARRIER", "OUTPATIENT", "INPATIENT"} and not financial_values and not utilization_values:
<<<<<<< HEAD
            return self._complete_with_llm(case, findings)
=======
            return findings
>>>>>>> b166e40 (removed old data)

        payment = self._float(
            financial_values.get("total_claim_payment")
            if financial_values.get("total_claim_payment") is not None
            else financial_values.get("claim_payment")
        )
        charge = self._float(
            financial_values.get("total_claim_charge")
            if financial_values.get("total_claim_charge") is not None
            else financial_values.get("submitted_charge")
        )

        if payment is not None and charge is not None and charge > 0:
            ratio = payment / charge
            if ratio >= 2.5:
                findings.append(
                    self._finding(
                        rule="payment_charge_ratio",
                        category="financial",
                        severity="high",
                        description=(
                            "Claim payment-to-charge ratio is "
                            f"{ratio:.2f}x, well above typical reimbursement levels."
                        ),
                        evidence={"payment": payment, "charge": charge, "ratio": ratio},
                        confidence=0.94,
                    )
                )

        reconciliation_flag = self._as_bool(
            financial_values.get("has_payment_reconciliation_issue")
            if financial_values.get("has_payment_reconciliation_issue") is not None
            else utilization_values.get("has_payment_reconciliation_issue")
        )
        if reconciliation_flag is True:
            findings.append(
                self._finding(
                    rule="payment_reconciliation_issue",
                    category="financial",
                    severity="medium",
                    description="Claim shows a payment reconciliation issue that merits billing review.",
                    evidence={"has_payment_reconciliation_issue": True},
                    confidence=0.82,
                )
            )

        avg_payment = self._float(utilization_values.get("provider_avg_claim_payment"))
        if payment is not None and avg_payment is not None and avg_payment > 0:
            deviation_ratio = payment / avg_payment
            if deviation_ratio >= 2.0:
                findings.append(
                    self._finding(
                        rule="provider_payment_deviation",
                        category="financial",
                        severity="high",
                        description=(
                            "Claim payment exceeds the provider benchmark by "
                            f"{deviation_ratio:.2f}x (payment: ${payment:,.2f}; average: ${avg_payment:,.2f})."
                        ),
                        evidence={"payment": payment, "provider_avg_claim_payment": avg_payment, "ratio": deviation_ratio},
                        confidence=0.9,
                    )
                )

        is_high_volume_provider = self._as_bool(utilization_values.get("is_high_volume_provider"))
        if is_high_volume_provider is True:
            findings.append(
                self._finding(
                    rule="high_volume_provider",
                    category="utilization",
                    severity="medium",
                    description="Provider is flagged as high-volume, increasing the significance of the billing pattern.",
                    evidence={"is_high_volume_provider": True},
                    confidence=0.75,
                )
            )

        line_count = self._float(utilization_values.get("claim_line_count"))
        multiple_lines = self._as_bool(utilization_values.get("has_multiple_lines"))
        if multiple_lines is True or (line_count is not None and line_count >= 5):
            findings.append(
                self._finding(
                    rule="multiple_claim_lines",
                    category="utilization",
                    severity="medium",
                    description=(
                        "Claim contains multiple billing lines or a high line count, which can increase review priority."
                    ),
                    evidence={"claim_line_count": line_count, "has_multiple_lines": multiple_lines},
                    confidence=0.7,
                )
            )

<<<<<<< HEAD
        return self._complete_with_llm(case, findings)

    def _complete_with_llm(self, case: InvestigationCase, findings: List[Finding]) -> List[Finding]:
        narrative = self._llm_narrative(case, findings)
        for finding in findings:
            finding.agent_narrative = narrative
            finding.tool_results = {"tool": "billing_rule_engine", "finding_count": len(findings)}
        return findings

    def _llm_narrative(self, case: InvestigationCase, findings: List[Finding]) -> str:
        if not self.llm_service.enabled:
            return "Deterministic billing review remains the source of truth for this claim."
        context = {
            "case_id": getattr(case, "case_id", "UNKNOWN"),
            "claim_id": getattr(case.claim, "claim_id", "UNKNOWN") if case.claim else "UNKNOWN",
            "claim_risk_score": getattr(case.claim, "claim_risk_score", None) if case.claim else None,
            "claim_type": getattr(case.claim, "claim_type", None) if case.claim else None,
            "findings": [{"rule": f.rule, "severity": f.severity, "description": f.description, "evidence": f.evidence} for f in findings],
        }
        fallback = "Billing evidence indicates the claim is being reviewed for payment and utilization anomalies, but the deterministic billing findings remain the authoritative basis for the investigation."
        reasoning = self.llm_service.generate_structured_reasoning("billing", context, fallback=fallback)
        return str(reasoning.get("narrative") or fallback)

=======
        return findings

>>>>>>> b166e40 (removed old data)
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
    def _finding(
        rule: str,
        category: str,
        severity: str,
        description: str,
        evidence: Dict[str, Any],
        confidence: float,
    ) -> Finding:
        return Finding(
            agent="billing",
            category=category,
            rule=rule,
            severity=severity,
            description=description,
            evidence=evidence,
            confidence=confidence,
        )
