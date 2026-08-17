"""
provider_context.py

Typed schema for the information handed from the Provider ML module to the
downstream Multi-Agent Investigation module.

The schema mirrors the authoritative output file
``models/provider/output/provider_risk_scores.csv`` produced by the
s1 -> s2 -> s3 -> s4 pipeline (see PROVIDER_ML_MULTI_AGENT_HANDOFF.md).

Implementation notes
--------------------
* The project does not use pydantic, so plain stdlib ``dataclasses`` are used
  (the claim-side module uses plain pandas; no schema framework exists).
* Every optional numeric field is ``None`` when the underlying value is not
  available for that provider (e.g. a provider without Dataset B service
  detail has no Svc_HHI_Concentration peer stats).
* Values are NOT invented here: they come straight from the pipeline output.
* Score interpretation: higher ``risk_score`` / ``anomaly_score`` /
  ``peer_evidence.score`` / ``geo_evidence.score`` = higher anomaly/risk.
"""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


# The provider metrics that the Provider ML pipeline uses for peer deviation
# (s4_model_risk.py, section 6). Peer evidence is exposed for exactly these.
PEER_METRICS: List[str] = [
    "Payment_per_Service",
    "Charge_per_Service",
    "Services_per_Beneficiary",
    "Payment_to_Charge_Ratio",
    "Svc_HHI_Concentration",
]


@dataclass
class PeerMetricEvidence:
    """Per-metric peer comparison for one provider metric."""

    metric: str
    provider_value: Optional[float] = None
    peer_mean: Optional[float] = None
    peer_median: Optional[float] = None
    peer_std: Optional[float] = None
    deviation_ratio: Optional[float] = None  # provider_value / peer_mean (x)
    percentile: Optional[float] = None       # provider's percentile within peer group, 0-1


@dataclass
class PeerEvidence:
    """Why a provider received a high ``peer_deviation_score``."""

    peer_group: Optional[str] = None          # Provider_Type (or "Other/Small-Specialty")
    score: Optional[float] = None             # peer_deviation_score, 0-1
    zsum: Optional[float] = None              # peer_deviation_zsum (mean abs z-score)
    metrics: List[PeerMetricEvidence] = field(default_factory=list)


@dataclass
class GeoEvidence:
    """Why a provider received a high ``geo_deviation_score``."""

    score: Optional[float] = None                     # geo_deviation_score, 0-1 (percentile rank of avg pymt deviation)
    avg_pymt_deviation: Optional[float] = None        # Peer_Avg_Pymt_Deviation (mean of provider/benchmark ratios)
    max_pymt_deviation: Optional[float] = None        # Peer_Max_Pymt_Deviation
    avg_chrg_deviation: Optional[float] = None        # Peer_Avg_Chrg_Deviation
    pct_services_above_2x_bench: Optional[float] = None  # Peer_Pct_Services_Above_2x_Bench
    rows_matched: Optional[int] = None                # Geo_Rows_Matched
    rows_by_level: Dict[str, int] = field(default_factory=dict)  # state_year / state / national
    provider_avg_pymt: Optional[float] = None         # Geo_Provider_Avg_Pymt
    bench_pymt_mean: Optional[float] = None           # Geo_Bench_Pymt_Mean
    bench_pymt_median: Optional[float] = None         # Geo_Bench_Pymt_Median
    bench_pymt_std: Optional[float] = None            # Geo_Bench_Pymt_Std
    provider_avg_chrg: Optional[float] = None         # Geo_Provider_Avg_Chrg
    bench_chrg_mean: Optional[float] = None           # Geo_Bench_Chrg_Mean
    bench_chrg_median: Optional[float] = None         # Geo_Bench_Chrg_Median
    bench_chrg_std: Optional[float] = None            # Geo_Bench_Chrg_Std


@dataclass
class TemporalEvidence:
    """Provider-level temporal context (from Dataset A NPI x Year rows)."""

    year_first: Optional[int] = None
    year_last: Optional[int] = None
    num_years_observed: Optional[int] = None
    # metric name -> {"first": value, "last": value, "growth_pct": pct}
    metrics: Dict[str, Dict[str, Optional[float]]] = field(default_factory=dict)


@dataclass
class LeieEvidence:
    """LEIE (List of Excluded Individuals/Entities) exclusion flag."""

    is_excluded: bool = False


@dataclass
class ProviderContext:
    """Complete investigation context for one provider (NPI)."""

    npi: int
    provider_type: Optional[str] = None
    state: Optional[str] = None
    risk_score: Optional[float] = None       # Provider_Risk_Score, 0-100
    risk_tier: Optional[str] = None          # Low / Moderate / High / Critical
    anomaly_score: Optional[float] = None    # global_anomaly_score, 0-1
    provider_features: Dict[str, Any] = field(default_factory=dict)
    peer_evidence: Optional[PeerEvidence] = None
    geo_evidence: Optional[GeoEvidence] = None
    temporal_evidence: Optional[TemporalEvidence] = None
    leie_evidence: LeieEvidence = field(default_factory=LeieEvidence)

    def to_dict(self) -> Dict[str, Any]:
        """Plain-dict form (JSON-serializable after ``float()`` coercion)."""
        return asdict(self)


def _f(value: Any) -> Optional[float]:
    """Coerce to float or None (used by the repository when building contexts)."""
    if value is None or (isinstance(value, float) and value != value):  # NaN
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f


def _i(value: Any) -> Optional[int]:
    if value is None or (isinstance(value, float) and value != value):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
