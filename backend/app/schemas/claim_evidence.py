"""Claim-level ML evidence abstraction for claim-type-specific model outputs.

This schema normalizes the claim-type ML artifacts (carrier/inpatient/outpatient)
into a unified internal representation that downstream agents can consume.
Each claim type preserves its native field structure while presenting a common interface.
"""

from __future__ import annotations

from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class ClaimEvidence(BaseModel):
    """Unified wrapper for claim-type-specific ML evidence.
    
    Each claim belongs to exactly one type (CARRIER, INPATIENT, or OUTPATIENT).
    Type-specific fields are preserved as-is; generic fields are normalized.
    """

    claim_id: str
    """Canonical claim ID across all pipelines."""

    claim_type: Literal["CARRIER", "INPATIENT", "OUTPATIENT"]
    """Which ML pipeline this claim came from."""

    ensemble_score: float = Field(..., ge=0.0, le=100.0)
    """Normalized ensemble risk score: higher = more anomalous.
    
    Carrier: carrier_ensemble_score (0-1 range, scaled to 0-100)
    Inpatient: ensemble_risk_score (0-100)
    Outpatient: outpatient_ensemble_score (0-1 range, scaled to 0-100)
    """

    risk_rank: Optional[int] = None
    """Model-assigned rank within its type (1 = most anomalous).
    
    All types provide this; None only if missing in source data.
    """

    risk_band: str
    """Normalized risk category: LOW, MEDIUM, HIGH, CRITICAL.
    
    Source values are uppercased and mapped if needed.
    """

    model_scores: Dict[str, float] = Field(default_factory=dict)
    """Per-model anomaly scores (type-specific keys).
    
    Carrier: {isolation_forest, lof, ocsvm}
    Inpatient: {isolation_forest, lof, one_class_svm}
    Outpatient: {isolation_forest, lof, ocsvm}
    """

    model_consensus: Optional[str] = None
    """Inpatient only: consensus count/label (e.g., '3_MODEL_CONSENSUS').
    
    None for other types.
    """

    model_consensus_count: Optional[int] = None
    """Inpatient only: number of models in consensus.
    
    None for other types.
    """

    risk_percentile: Optional[float] = None
    """Inpatient only: percentile rank within type (0-100).
    
    None for other types.
    """

    feature_evidence: Dict[str, Any] = Field(default_factory=dict)
    """Type-specific raw feature columns (not model scores).
    
    Carrier: minimal (claim amount fields only)
    Inpatient: provider_id, claim metadata
    Outpatient: 44 feature columns (temporal, volume, diversity, payment ratios, etc.)
    """

    source_pipeline: str
    """Filename/path this evidence came from (for provenance/debugging).
    
    E.g., 'models/claims/carrier/carrier_final_risk_scores.csv'
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "claim_id": "-10000930068276",
                "claim_type": "CARRIER",
                "ensemble_score": 83.98,
                "risk_rank": 1,
                "risk_band": "HIGH",
                "model_scores": {
                    "isolation_forest": 0.917,
                    "lof": 0.282,
                    "ocsvm": 1.0,
                },
                "model_consensus": None,
                "model_consensus_count": None,
                "risk_percentile": None,
                "feature_evidence": {
                    "CLM_PMT_AMT_first": 42062.86,
                    "NCH_CARR_CLM_SBMTD_CHRG_AMT_first": 52578.57,
                },
                "source_pipeline": "models/claims/carrier/carrier_final_risk_scores.csv",
            }
        }
    )
