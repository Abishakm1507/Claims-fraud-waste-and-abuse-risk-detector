from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field

from backend.app.data.repository import repository
from backend.app.services.investigation_service import explainability_service, investigation_service

router = APIRouter()


def _recommendation(investigation) -> str:
    risk = investigation.risk_synthesis.overall_risk if investigation.risk_synthesis else 0.0
    evidence_count = len(investigation.evidence)
    critical_or_high = sum(
        1 for finding in investigation.findings
        if finding.severity in {"HIGH", "CRITICAL"}
    )
    if risk >= 85 and critical_or_high > 0 and evidence_count > 0:
        return "Escalate for detailed billing, documentation, and claim-line review because high-severity findings are supported by structured evidence."
    if risk >= 70:
        return "Prioritize manual review and validate supporting documentation for the identified claim anomalies."
    if risk >= 40:
        return "Review the identified anomalies and compare the claim against available peer behavior."
    return "No immediate escalation; continue monitoring and retain the deterministic evidence for review."


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    case_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    case_id: Optional[str] = None
    status: str = "stub"


class ErrorEnvelope(BaseModel):
    error: Dict[str, Any]


@router.get("/health")
def health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service": "claims-fwa-risk-api",
        "data_loaded": {
            "claims": len(repository.claims_df),
            "providers": len(repository.providers_df),
        },
    }


@router.get("/stats/overview")
def get_overview() -> Dict[str, Any]:
    return repository.stats_overview()


@router.get("/claims")
def get_claims(
    claim_type: Optional[str] = Query(default=None),
    risk_band: Optional[str] = Query(default=None),
    provider: Optional[str] = Query(default=None, alias="provider"),
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    sort_by: str = Query(default="claim_risk_score"),
    order: str = Query(default="desc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
) -> Dict[str, Any]:
    result = repository.get_claims(
        claim_type=claim_type,
        risk_band=risk_band,
        provider_id=provider,
        date_from=date_from,
        date_to=date_to,
        sort_by=sort_by,
        order=order,
        page=page,
        page_size=page_size,
    )
    return result


@router.get("/providers")
def get_providers(
    risk_band: Optional[str] = Query(default=None),
    state: Optional[str] = Query(default=None),
    sort_by: str = Query(default="provider_risk_score"),
    order: str = Query(default="desc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
) -> Dict[str, Any]:
    return repository.get_providers(
        risk_band=risk_band,
        state=state,
        sort_by=sort_by,
        order=order,
        page=page,
        page_size=page_size,
    )


@router.get("/claims/{claim_id}")
def get_claim_detail(claim_id: str) -> Dict[str, Any]:
    claim = repository.get_claim(claim_id)
    if claim is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "CLAIM_NOT_FOUND", "message": f"Claim {claim_id} not found"})

    provider = repository.get_provider(claim.get("provider_id") or "") if claim.get("provider_id") else None
    investigation = investigation_service.get_investigation(claim_id)
    explanation = explainability_service.get_explanation(claim_id, investigation)
    ml_evidence = repository.get_claim_evidence(claim_id)

    explainability_payload = explanation.metadata.provenance or {}
    shap = explainability_payload.get("shap") or {
        "status": "UNAVAILABLE",
        "reason": "No model-faithful SHAP artifact was returned for this claim type.",
        "top_features": [],
    }
    genai_narrative = explainability_payload.get("genai") or {
        "status": "UNAVAILABLE",
        "reason": "GENAI_PROVIDER_UNAVAILABLE",
        "summary": None,
    }

    case_detail = {
        "claim": claim,
        "provider": provider,
        "ml_evidence": ml_evidence.model_dump(mode="json", exclude_none=True) if ml_evidence else None,
        "investigation": investigation.model_dump(mode="json", exclude_none=True),
        "shap": shap,
        "genai_narrative": genai_narrative,
        "recommendation": _recommendation(investigation),
        "risk_summary": {
            "overall_risk": investigation.risk_synthesis.overall_risk if investigation.risk_synthesis else 0.0,
            "risk_category": (investigation.risk_synthesis.risk_category.value if investigation.risk_synthesis else "UNKNOWN"),
            "priority": (investigation.risk_synthesis.priority.value if investigation.risk_synthesis else "P3"),
            "risk_score": ml_evidence.ensemble_score if ml_evidence else None,
            "anomaly_score": (ml_evidence.model_scores.get("isolation_forest") if ml_evidence else None),
            "model": "IsolationForest" if ml_evidence else None,
        },
    }
    return case_detail


@router.get("/providers/{npi}")
def get_provider_detail(npi: str) -> Dict[str, Any]:
    provider = repository.get_provider(npi)
    if provider is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "PROVIDER_NOT_FOUND", "message": f"Provider {npi} not found"})

    provider_payload = {k: v for k, v in provider.items() if k != "provider_evidence"}
    claims = repository.claims_df[repository.claims_df["provider_id"].astype(str).str.upper() == str(npi).upper()].to_dict(orient="records")
    risk_summary = provider.get("provider_risk_score", 0.0)
    evidence = repository.get_provider_evidence(npi)
    case = {
        "provider": provider_payload,
        "provider_evidence": evidence.model_dump(mode="json", exclude_none=False) if evidence else None,
        "claims": claims,
        "investigation": {
            "provider_npi": npi,
            "provider_risk_score": risk_summary,
            "risk_level": provider.get("provider_risk_level", "UNKNOWN"),
            "related_claim_count": len(claims),
            "recommendation": "Review billing patterns and peer utilization deviations before dismissal.",
        },
    }
    return case


@router.post("/investigations/{case_id}/run")
def run_investigation(case_id: str) -> Dict[str, Any]:
    try:
        case = investigation_service.run_investigation(case_id)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "CLAIM_NOT_FOUND", "message": f"Investigation case {case_id} not found"})

    return {
        "case_id": case.case_id,
        "status": "started",
        "investigation": case.model_dump(mode="json", exclude_none=True),
        "message": "Investigation run completed through the multi-agent orchestration contract.",
    }


@router.get("/reports/{case_id}")
def get_report(case_id: str) -> Dict[str, Any]:
    try:
        investigation = investigation_service.get_investigation(case_id)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "CASE_NOT_FOUND", "message": f"Report for case {case_id} not found"})

    explanation = explainability_service.get_explanation(case_id, investigation)
    ml_evidence = repository.get_claim_evidence(case_id)
    
    report = {
        "case_id": case_id,
        "report_type": "investigation_report",
        "status": "ready",
        "generated_at": explanation.metadata.generated_at,
        "ml_evidence": ml_evidence.model_dump(mode="json", exclude_none=True) if ml_evidence else None,
        "risk_synthesis": investigation.risk_synthesis.model_dump(mode="json", exclude_none=True) if investigation.risk_synthesis else None,
        "findings": [finding.model_dump(mode="json", exclude_none=True) for finding in investigation.findings],
        "evidence": [evidence.model_dump(mode="json", exclude_none=True) for evidence in investigation.evidence],
        "narrative": (explanation.metadata.provenance.get("genai") or {
            "status": "UNAVAILABLE",
            "reason": "GENAI_PROVIDER_UNAVAILABLE",
            "summary": None,
        }),
        "recommendation": _recommendation(investigation),
        "download": {
            "format": "json",
            "filename": f"report-{case_id}.json",
            "content_type": "application/json",
        },
        "pdf_ready": {
            "title": f"Investigation Report - {case_id}",
            "sections": ["executive_summary", "findings", "evidence", "recommendation"],
        },
    }
    return report


@router.post("/chat")
def chat_stub(payload: ChatRequest) -> ChatResponse:
    prompt = payload.message.strip()
    response = (
        "This is a placeholder RAG response from the backend stub. "
        "The real chatbot service is intentionally deferred and will plug in later without changing the API contract."
    )
    if payload.case_id:
        response = f"Stubbed RAG response for case {payload.case_id}: {response}"
    if prompt.lower().startswith("hello"):
        response = "Hello. I am the backend RAG chatbot stub and I am ready for the real service integration."
    return ChatResponse(response=response, case_id=payload.case_id, status="stub")


