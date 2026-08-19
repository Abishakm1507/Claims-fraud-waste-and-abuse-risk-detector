from __future__ import annotations

from math import isfinite
from typing import Any, Dict, Iterable, Optional

from .evidence_calculators import (
    deviation,
    deviation_ratio,
    percentage_deviation,
    safe_float,
    threshold_comparison,
)
from .provenance import Provenance


class EvidenceNormalizer:
    """Normalize evidence objects to a stable, traceable schema."""

    @staticmethod
    def normalize(
        *,
        metric: str,
        agent: Optional[str] = None,
        category: Optional[str] = None,
        description: Optional[str] = None,
        provider_value: Any = None,
        claim_value: Any = None,
        baseline_value: Any = None,
        peer_mean: Any = None,
        peer_median: Any = None,
        peer_std: Any = None,
        deviation_value: Any = None,
        deviation_ratio_value: Any = None,
        percentile: Any = None,
        threshold: Any = None,
        threshold_comparison_value: Any = None,
        peer_group: Any = None,
        peer_sample_size: Any = None,
        geographic_group: Any = None,
        time_period: Any = None,
        source: Optional[str] = None,
        source_fields: Optional[Iterable[str]] = None,
        calculation: Optional[Dict[str, Any]] = None,
        confidence: Any = None,
        availability: Optional[str] = None,
        provenance: Optional[Dict[str, Any]] = None,
        evidence_id: Optional[str] = None,
        **extra: Any,
    ) -> Dict[str, Any]:
        normalized: Dict[str, Any] = {
            "metric": metric,
            "agent": agent,
            "category": category,
            "description": description,
            "provider_value": EvidenceNormalizer._clean_numeric(provider_value),
            "claim_value": EvidenceNormalizer._clean_numeric(claim_value),
            "baseline_value": EvidenceNormalizer._clean_numeric(baseline_value),
            "peer_mean": EvidenceNormalizer._clean_numeric(peer_mean),
            "peer_median": EvidenceNormalizer._clean_numeric(peer_median),
            "peer_std": EvidenceNormalizer._clean_numeric(peer_std),
            "deviation": EvidenceNormalizer._clean_numeric(deviation_value),
            "deviation_ratio": EvidenceNormalizer._clean_numeric(deviation_ratio_value),
            "percentile": EvidenceNormalizer._clean_numeric(percentile),
            "threshold": EvidenceNormalizer._clean_numeric(threshold),
            "threshold_comparison": threshold_comparison_value,
            "peer_group": peer_group,
            "peer_sample_size": EvidenceNormalizer._clean_int(peer_sample_size),
            "geographic_group": geographic_group,
            "time_period": time_period,
            "source": source,
            "source_fields": list(source_fields) if source_fields is not None else [],
            "calculation": calculation,
            "confidence": EvidenceNormalizer._clean_confidence(confidence),
            "availability": availability or "AVAILABLE",
            "provenance": provenance or {},
            "evidence_id": evidence_id,
        }

        if normalized["deviation"] is None:
            if normalized["provider_value"] is not None and normalized["baseline_value"] is not None:
                normalized["deviation"] = deviation(normalized["provider_value"], normalized["baseline_value"])
            elif normalized["claim_value"] is not None and normalized["baseline_value"] is not None:
                normalized["deviation"] = deviation(normalized["claim_value"], normalized["baseline_value"])

        if normalized["deviation_ratio"] is None:
            observed = normalized["provider_value"] if normalized["provider_value"] is not None else normalized["claim_value"]
            if observed is not None and normalized["baseline_value"] is not None:
                normalized["deviation_ratio"] = deviation_ratio(observed, normalized["baseline_value"])

        if normalized["threshold_comparison"] is None and normalized["threshold"] is not None:
            observed = normalized["provider_value"] if normalized["provider_value"] is not None else normalized["claim_value"]
            normalized["threshold_comparison"] = threshold_comparison(observed, normalized["threshold"], operator=extra.get("operator", ">"))

        if normalized["calculation"] is None:
            observed = normalized["provider_value"] if normalized["provider_value"] is not None else normalized["claim_value"]
            baseline = normalized["baseline_value"]
            formula = None
            inputs = {}
            result = None
            if observed is not None and baseline is not None and baseline != 0:
                formula = "observed / baseline"
                inputs = {"observed": observed, "baseline": baseline}
                result = deviation_ratio(observed, baseline)
            elif observed is not None and normalized["peer_median"] is not None and normalized["peer_median"] != 0:
                formula = "provider_value / peer_median"
                inputs = {"provider_value": observed, "peer_median": normalized["peer_median"]}
                result = deviation_ratio(observed, normalized["peer_median"])
            if formula is not None:
                normalized["calculation"] = {"formula": formula, "inputs": inputs, "result": result}

        for key in list(normalized.keys()):
            if key in {"provider_value", "claim_value", "baseline_value", "peer_mean", "peer_median", "peer_std", "deviation", "deviation_ratio", "percentile", "threshold"}:
                if normalized[key] is not None and (not isfinite(float(normalized[key]))):
                    normalized[key] = None

        if normalized["source_fields"]:
            normalized["provenance"] = {
                **(provenance or {}),
                **Provenance.build(
                    source=source,
                    source_fields=normalized["source_fields"],
                    pipeline="multi_agent",
                    pipeline_version=None,
                ),
            }

        normalized.update({k: v for k, v in extra.items() if v is not None and k not in normalized})
        return normalized

    @staticmethod
    def _clean_numeric(value: Any) -> Any:
        if value is None:
            return None
        number = safe_float(value)
        return None if number is None or not isfinite(number) else number

    @staticmethod
    def _clean_int(value: Any) -> Optional[int]:
        if value is None:
            return None
        if isinstance(value, bool):
            return None
        try:
            cleaned = int(value)
            return cleaned if isfinite(cleaned) else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _clean_confidence(value: Any) -> Optional[float]:
        if value is None:
            return None
        cleaned = safe_float(value)
        if cleaned is None:
            return None
        if cleaned < 0.0:
            return 0.0
        if cleaned > 1.0:
            return 1.0
        return cleaned
