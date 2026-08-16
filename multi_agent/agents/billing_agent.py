from __future__ import annotations

from math import isnan
from typing import Any, Dict, List, Optional

from multi_agent.schemas.finding import Finding
from multi_agent.schemas.investigation_case import InvestigationCase


class BillingAgent:
    """Deterministic billing-focused rule engine over ClaimContext data."""

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
            return findings

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
