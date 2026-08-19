from __future__ import annotations

from typing import Any, Dict, Optional

from explainability.claims_explainer_prod import explain_claim
from explainability.feature_mapping import humanize_feature
from explainability.genai_explainer import StructuredGroqExplainer
from explainability.multi_agent_adapter import normalize_investigation_output
from explainability.provider_explainer import ProviderExplainer


def _normalize_shap_section(raw_shap: Any) -> Dict[str, Any]:
    if raw_shap is None:
        return {"status": "NOT_AVAILABLE", "reason": "No SHAP output available."}

    if isinstance(raw_shap, dict):
        status = raw_shap.get("status")
        if status in {"success", "READY"}:
            top = raw_shap.get("top_features") or raw_shap.get("shap", {}).get("top_features") or []
            normalized_top = []
            for idx, item in enumerate(top[:10], start=1):
                if isinstance(item, dict):
                    normalized_top.append({
                        "feature": item.get("feature") or item.get("model_feature") or "Unknown",
                        "value": item.get("value"),
                        "shap_value": item.get("shap_value"),
                        "direction": "increases_risk" if float(item.get("shap_value", 0.0)) > 0 else "reduces_risk",
                        "human_description": humanize_feature(item.get("feature") or item.get("model_feature") or "Unknown"),
                        "rank": idx,
                    })
            return {
                "status": "READY",
                "top_features": normalized_top,
                "shap_values": [float(item["shap_value"]) for item in normalized_top if "shap_value" in item],
            }
        if "BLOCKED_MISSING_FEATURE_ARTIFACT" in str(status).upper() or status == "blocked_missing_feature_artifact":
            return {
                "status": "BLOCKED_MISSING_FEATURE_ARTIFACT",
                "reason": raw_shap.get("reason") or raw_shap.get("error") or "Feature lineage is missing.",
            }
        if status == "not_found":
            return {"status": "NOT_FOUND", "reason": raw_shap.get("reason") or "Entity not found."}

    return {"status": "NOT_AVAILABLE", "reason": "No SHAP explanation available."}


def _normalize_risk_section(entity_type: str, entity_id: Any, value: Any, claim_type: Optional[str] = None) -> Dict[str, Any]:
    if value is None:
        return {"score": None, "rank": None, "band": None}
    if isinstance(value, dict):
        return {
            "score": value.get("risk_score") or value.get("score"),
            "rank": value.get("risk_rank") or value.get("rank"),
            "band": value.get("risk_band") or value.get("band"),
        }
    return {"score": value, "rank": None, "band": None}


def _build_genai_payload(entity_type: str, entity_id: Any, claim_type: Optional[str], risk: Dict[str, Any], shap: Dict[str, Any], investigation: Dict[str, Any], model_evidence: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {
        "entity_type": entity_type,
        "entity_id": str(entity_id),
        "claim_type": claim_type,
        "risk_score": risk.get("score"),
        "risk_rank": risk.get("rank"),
        "risk_band": risk.get("band"),
        "shap_status": shap.get("status"),
        "shap_top_features": shap.get("top_features") or [],
        "shap_values": shap.get("shap_values") or [],
        "model_evidence": model_evidence or {},
        "multi_agent_evidence": {
            "status": investigation.get("status"),
            "findings": investigation.get("findings") or [],
            "evidence": investigation.get("evidence") or [],
            "peer_comparison": investigation.get("peer_comparison") or [],
            "recommendations": investigation.get("recommendations") or [],
            "narrative": investigation.get("narrative") or "Investigation output unavailable.",
        },
    }


def explain_entity(
    entity_type: str,
    entity_id: Any,
    entity_data: Optional[Dict[str, Any]] = None,
    claim_type: Optional[str] = None,
    investigation_output: Optional[Any] = None,
    risk_score: Optional[float] = None,
    groq_explainer: Optional[Any] = None,
) -> Dict[str, Any]:
    """Common explainability interface for Claims and Providers."""
    normalized_entity_type = str(entity_type).upper()
    if normalized_entity_type == "CLAIM":
        entity_claim_type = str(claim_type or entity_data.get("claim_type") if isinstance(entity_data, dict) else claim_type or "").upper()
        if not entity_claim_type:
            raise ValueError("A claim_type is required for claim explainability.")

        claim_result = explain_claim(str(entity_id), entity_claim_type)
        risk_section = _normalize_risk_section("CLAIM", entity_id, claim_result.get("risk"), entity_claim_type)
        shap_section = _normalize_shap_section({
            "status": claim_result.get("status", {}).get("code"),
            "reason": claim_result.get("status", {}).get("message"),
            "top_features": claim_result.get("explanation", {}).get("top_features") or [],
            "shap_values": claim_result.get("explanation", {}).get("shap_values") or [],
            "base_value": claim_result.get("explanation", {}).get("base_value"),
        })
        model_evidence = claim_result.get("model") or {}
        investigation = normalize_investigation_output(investigation_output)
        payload = _build_genai_payload(
            "CLAIM",
            entity_id,
            entity_claim_type,
            risk_section,
            shap_section,
            investigation,
            model_evidence=model_evidence,
        )

        if groq_explainer is None:
            groq_explainer = StructuredGroqExplainer()

        try:
            genai_result = groq_explainer.generate(payload)
        except Exception as exc:
            genai_result = {
                "status": "UNAVAILABLE",
                "reason": str(exc),
                "model": getattr(groq_explainer, "model", "unknown"),
                "summary": "GenAI explanation unavailable. Deterministic evidence remains authoritative.",
                "key_reasons": [],
                "supporting_evidence": [],
                "recommended_action": "Review the deterministic evidence and model output.",
                "input_tokens": None,
                "output_tokens": None,
                "total_tokens": None,
            }

        return {
            "entity_type": "CLAIM",
            "entity_id": str(entity_id),
            "claim_type": entity_claim_type,
            "risk": risk_section,
            "shap": shap_section,
            "investigation": investigation,
            "genai": genai_result,
        }

    if normalized_entity_type == "PROVIDER":
        provider_explainer = ProviderExplainer()
        raw_provider = entity_data or {}
        provider_risk = float(risk_score) if risk_score is not None else 0.0
        shap_output = provider_explainer.explain_provider(entity_id, provider_risk, raw_provider)
        shap_section = _normalize_shap_section(shap_output)
        risk_section = _normalize_risk_section("PROVIDER", entity_id, {"score": provider_risk, "band": "UNKNOWN"})
        investigation = normalize_investigation_output(investigation_output)
        payload = _build_genai_payload(
            "PROVIDER",
            entity_id,
            claim_type,
            risk_section,
            shap_section,
            investigation,
            model_evidence={"model_type": "Provider IsolationForest", "provider_id": str(entity_id)},
        )

        if groq_explainer is None:
            groq_explainer = StructuredGroqExplainer()

        try:
            genai_result = groq_explainer.generate(payload)
        except Exception as exc:
            genai_result = {
                "status": "UNAVAILABLE",
                "reason": str(exc),
                "model": getattr(groq_explainer, "model", "unknown"),
                "summary": "GenAI explanation unavailable. Deterministic evidence remains authoritative.",
                "key_reasons": [],
                "supporting_evidence": [],
                "recommended_action": "Review the deterministic evidence and model output.",
                "input_tokens": None,
                "output_tokens": None,
                "total_tokens": None,
            }

        return {
            "entity_type": "PROVIDER",
            "entity_id": str(entity_id),
            "claim_type": claim_type,
            "risk": risk_section,
            "shap": shap_section,
            "investigation": investigation,
            "genai": genai_result,
        }

    raise ValueError(f"Unsupported entity type: {entity_type}")
