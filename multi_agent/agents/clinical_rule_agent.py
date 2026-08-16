from __future__ import annotations

from math import isnan
from typing import Any, Dict, List, Optional

from multi_agent.schemas.finding import Finding
from multi_agent.schemas.investigation_case import InvestigationCase


class ClinicalRuleAgent:
    """Deterministic, evidence-based claim rule engine using only ClaimContext.

    This milestone intentionally does not fabricate unsupported medical diagnoses,
    unsupported fraud conclusions, or synthetic clinical thresholds. It only surfaces
    rule and utilization evidence that is already present in the exported claim data.
    """

    def investigate(self, case: InvestigationCase) -> List[Finding]:
        if case is None or case.claim is None:
            return []

        claim = case.claim
        if claim.claim_type in {None, "CARRIER"}:
            return []

        findings: List[Finding] = []

        if claim.claim_type == "OUTPATIENT":
            findings.extend(self._outpatient_findings(claim))
        elif claim.claim_type == "INPATIENT":
            findings.extend(self._inpatient_findings(claim))

        return findings

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
