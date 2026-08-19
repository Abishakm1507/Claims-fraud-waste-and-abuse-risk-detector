from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


VALID_PROVIDER_ID_TYPES = {"NPI", "PRVDR_NUM"}


@dataclass
class EvidenceBundle:
    """Container for one claim evidence group. Missing evidence stays None."""

    available: bool = False
    values: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ClaimContext:
    """Typed claim contract used by the future Multi-Agent investigation layer."""

    claim_id: str
    claim_type: Optional[str] = None
    provider_id: Optional[str] = None
    provider_id_type: Optional[str] = None
    bene_id: Optional[str] = None
    claim_risk_score: Optional[float] = None
    final_risk_level: Optional[str] = None
    final_risk_priority: Optional[int] = None
    final_claim_rank: Optional[int] = None
    claim_status: Optional[str] = None
    financial_evidence: Optional[EvidenceBundle] = None
    utilization_evidence: Optional[EvidenceBundle] = None
    procedure_evidence: Optional[EvidenceBundle] = None
    temporal_evidence: Optional[EvidenceBundle] = None
    peer_evidence: Optional[EvidenceBundle] = None
    rule_evidence: Optional[EvidenceBundle] = None
    model_evidence: Optional[EvidenceBundle] = None
    claim_features: Dict[str, Any] = field(default_factory=dict)
    data_availability: Dict[str, bool] = field(default_factory=dict)

    def __post_init__(self):
        if self.provider_id_type is not None:
            normalized = str(self.provider_id_type).upper()
            if normalized not in VALID_PROVIDER_ID_TYPES:
                raise ValueError(
                    f"provider_id_type must be one of {sorted(VALID_PROVIDER_ID_TYPES)}; "
                    f"got {self.provider_id_type!r}"
                )
            self.provider_id_type = normalized

        if self.bene_id is None and self.claim_id is not None:
            self.bene_id = self.claim_id

    def to_dict(self) -> Dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "claim_type": self.claim_type,
            "provider_id": self.provider_id,
            "provider_id_type": self.provider_id_type,
            "bene_id": self.bene_id,
            "claim_risk_score": self.claim_risk_score,
            "final_risk_level": self.final_risk_level,
            "final_risk_priority": self.final_risk_priority,
            "final_claim_rank": self.final_claim_rank,
            "claim_status": self.claim_status,
            "financial_evidence": self.financial_evidence,
            "utilization_evidence": self.utilization_evidence,
            "procedure_evidence": self.procedure_evidence,
            "temporal_evidence": self.temporal_evidence,
            "peer_evidence": self.peer_evidence,
            "rule_evidence": self.rule_evidence,
            "model_evidence": self.model_evidence,
            "claim_features": self.claim_features,
            "data_availability": self.data_availability,
        }
