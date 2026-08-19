from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ProviderEvidence(BaseModel):
    """Normalized provider evidence drawn from LEIE, provider-service, and peer benchmark data."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "npi": "1003078684",
                "provider_type": "Family Practice",
                "state": "FL",
                "exclusion_status": "EXCLUDED",
                "leie_match": {
                    "exclusion_type": "1128A1",
                    "exclusion_date": "2020-03-19",
                    "state": "FL",
                    "specialty": "FAMILY PRACTICE",
                    "business_name": "EXAMPLE GROUP LLC",
                    "is_individual": False,
                },
                "peer_benchmark": {
                    "peer_percentile": 92.5,
                    "avg_payment_amount": 142.5,
                    "total_services": 890.0,
                    "provider_type": "Family Practice",
                    "state": "FL",
                },
                "service_summary": {
                    "total_services": 891.0,
                    "avg_payment_amount": 182.1,
                    "provider_specialty": "Family Practice",
                    "provider_state": "FL",
                },
                "provenance": {
                    "leie_match": True,
                    "has_service_rows": True,
                    "has_geo_benchmark_rows": True,
                },
                "source_files": [
                    "data/interim/leie_clean.parquet",
                    "data/interim/provider_service_clean.parquet",
                ],
            }
        },
    )

    npi: str
    provider_type: Optional[str] = None
    state: Optional[str] = None
    exclusion_status: str = Field(description="EXCLUDED | NOT_FOUND | UNKNOWN")
    leie_match: Optional[Dict[str, Any]] = None
    peer_benchmark: Dict[str, Any] = Field(default_factory=dict)
    service_summary: Dict[str, Any] = Field(default_factory=dict)
    provenance: Dict[str, Any] = Field(default_factory=dict)
    source_files: List[str] = Field(default_factory=list)
