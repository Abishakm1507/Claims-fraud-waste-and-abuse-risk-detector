from __future__ import annotations

from typing import Any, Dict, List


def normalize_investigation_output(investigation_output: Any) -> Dict[str, Any]:
    """Normalize multi-agent result objects to the explainability contract.

    This adapter intentionally reuses the existing multi_agent InvestigationResult
    and Finding objects rather than assuming a new schema.
    """
    if investigation_output is None:
        return {
            "status": "NOT_AVAILABLE",
            "findings": [],
            "evidence": [],
            "peer_comparison": [],
            "recommendations": [],
            "narrative": "Investigation output is unavailable.",
        }

    if isinstance(investigation_output, dict):
        result = investigation_output
    else:
        result = getattr(investigation_output, "to_dict", lambda: {})()
        if not result:
            result = {
                "case_id": getattr(investigation_output, "case_id", None),
                "claim_id": getattr(investigation_output, "claim_id", None),
                "provider_id": getattr(investigation_output, "provider_id", None),
                "final_risk_level": getattr(investigation_output, "final_risk_level", None),
                "investigation_risk_score": getattr(investigation_output, "investigation_risk_score", None),
                "explanation": getattr(investigation_output, "explanation", None),
                "summary": getattr(investigation_output, "summary", {}),
                "findings": list(getattr(investigation_output, "findings", []) or []),
            }

    findings = result.get("findings") or getattr(investigation_output, "findings", []) or []
    if hasattr(investigation_output, "findings") and not findings:
        findings = list(getattr(investigation_output, "findings", []))

    normalized_findings: List[Dict[str, Any]] = []
    evidence: List[Dict[str, Any]] = []
    peer_comparison: List[str] = []
    recommendations: List[str] = []

    for finding in findings:
        if isinstance(finding, dict):
            record = {
                "agent": finding.get("agent") or "unknown",
                "category": finding.get("category") or "general",
                "rule": finding.get("rule") or "general_rule",
                "severity": finding.get("severity") or "INFO",
                "description": finding.get("description") or finding.get("summary") or "Finding available.",
                "evidence": finding.get("evidence") or {},
                "confidence": finding.get("confidence"),
            }
        else:
            record = {
                "agent": getattr(finding, "agent", "unknown"),
                "category": getattr(finding, "category", "general"),
                "rule": getattr(finding, "rule", "general_rule"),
                "severity": getattr(finding, "severity", "INFO"),
                "description": getattr(finding, "description", "Finding available."),
                "evidence": getattr(finding, "evidence", {}) or {},
                "confidence": getattr(finding, "confidence", None),
            }
        normalized_findings.append(record)

        ev = record["evidence"] if isinstance(record["evidence"], dict) else {}
        base = {
            "agent": record["agent"],
            "category": record["category"],
            "rule": record["rule"],
            "severity": record["severity"],
            "description": record["description"],
        }
        if isinstance(ev, dict):
            base.update(ev)
        evidence.append(base)

        if record["category"].lower() in {"peer", "peer_comparison"} or "peer" in str(record["description"]).lower():
            peer_comparison.append(record["description"])

        if "recommend" in str(record["description"]).lower() or "review" in str(record["description"]).lower():
            recommendations.append(record["description"])

    if not recommendations:
        recommendations = [
            "Review the top contributing features and investigation evidence before making a determination.",
        ]

    narrative = result.get("explanation") or getattr(investigation_output, "explanation", "") or (
        "Investigation findings were produced by the deterministic multi-agent pipeline."
        if normalized_findings else "No investigation narrative was supplied."
    )

    summary = result.get("summary") if isinstance(result, dict) else getattr(investigation_output, "summary", {}) or {}
    risk_level = result.get("final_risk_level") or getattr(investigation_output, "final_risk_level", None)
    investigation_risk_score = result.get("investigation_risk_score") or getattr(investigation_output, "investigation_risk_score", None)

    has_real_investigation = bool(result) or hasattr(investigation_output, "case_id") or hasattr(investigation_output, "summary") or hasattr(investigation_output, "explanation")
    return {
        "status": "READY" if has_real_investigation else "NOT_AVAILABLE",
        "case_id": result.get("case_id") if isinstance(result, dict) else getattr(investigation_output, "case_id", None),
        "claim_id": result.get("claim_id") if isinstance(result, dict) else getattr(investigation_output, "claim_id", None),
        "provider_id": result.get("provider_id") if isinstance(result, dict) else getattr(investigation_output, "provider_id", None),
        "risk_level": risk_level,
        "investigation_risk_score": investigation_risk_score,
        "findings": normalized_findings,
        "evidence": evidence,
        "peer_comparison": peer_comparison,
        "recommendations": recommendations,
        "narrative": narrative,
        "summary": summary,
    }
