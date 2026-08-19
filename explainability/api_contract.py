from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ExplainabilityFinding:
    feature: str
    value: Any
    shap_value: float
    absolute_shap_value: float
    rank: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "feature": self.feature,
            "value": self.value,
            "shap_value": float(self.shap_value),
            "absolute_shap_value": float(self.absolute_shap_value),
            "rank": int(self.rank),
        }


@dataclass
class ExplainabilityPayload:
    entity_type: str
    entity_id: str
    risk_score: float
    top_features: List[ExplainabilityFinding] = field(default_factory=list)
    multi_agent_findings: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "risk_score": float(self.risk_score),
            "top_features": [item.to_dict() for item in self.top_features],
            "multi_agent_findings": self.multi_agent_findings,
        }
