from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class ProviderContext:
    """Typed provider contract used by the future Multi-Agent investigation layer."""

    npi: int
    provider_type: Optional[str] = None
    provider_state: Optional[str] = None
    provider_risk_score: Optional[float] = None
    risk_tier: Optional[str] = None
    global_anomaly_score: Optional[float] = None
    peer_deviation_score: Optional[float] = None
    geo_deviation_score: Optional[float] = None
    is_leie_excluded: Optional[bool] = None
    peer_group: Optional[str] = None
    peer_mean: Optional[float] = None
    peer_median: Optional[float] = None
    peer_std: Optional[float] = None
    provider_value: Optional[float] = None
    deviation_ratio: Optional[float] = None
    percentile: Optional[float] = None
    charge_per_service: Optional[float] = None
    charge_per_service_peer_mean: Optional[float] = None
    charge_per_service_peer_median: Optional[float] = None
    charge_per_service_peer_std: Optional[float] = None
    charge_per_service_deviation_ratio: Optional[float] = None
    charge_per_service_percentile: Optional[float] = None
    services_per_beneficiary: Optional[float] = None
    services_per_beneficiary_peer_mean: Optional[float] = None
    services_per_beneficiary_peer_median: Optional[float] = None
    services_per_beneficiary_peer_std: Optional[float] = None
    services_per_beneficiary_deviation_ratio: Optional[float] = None
    services_per_beneficiary_percentile: Optional[float] = None
    payment_to_charge_ratio: Optional[float] = None
    payment_to_charge_ratio_peer_mean: Optional[float] = None
    payment_to_charge_ratio_peer_median: Optional[float] = None
    payment_to_charge_ratio_peer_std: Optional[float] = None
    payment_to_charge_ratio_deviation_ratio: Optional[float] = None
    payment_to_charge_ratio_percentile: Optional[float] = None
    svc_hhi_concentration: Optional[float] = None
    svc_hhi_concentration_peer_mean: Optional[float] = None
    svc_hhi_concentration_peer_median: Optional[float] = None
    svc_hhi_concentration_peer_std: Optional[float] = None
    svc_hhi_concentration_deviation_ratio: Optional[float] = None
    svc_hhi_concentration_percentile: Optional[float] = None
    geo_state: Optional[str] = None
    geo_mean: Optional[float] = None
    geo_median: Optional[float] = None
    geo_std: Optional[float] = None
    geo_provider_value: Optional[float] = None
    geo_deviation_ratio: Optional[float] = None
    geo_percentile: Optional[float] = None
    geo_metric: Optional[str] = None
    year_first: Optional[int] = None
    year_last: Optional[int] = None
    tot_benes: Optional[int] = None
    tot_srvcs: Optional[float] = None
    tot_sbmtd_chrg: Optional[float] = None
    tot_mdcr_pymt_amt: Optional[float] = None
    payment_per_service: Optional[float] = None
    data_availability: Dict[str, bool] = field(default_factory=dict)

    def __post_init__(self):
        if self.npi is not None:
            self.npi = int(self.npi)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "npi": self.npi,
            "provider_type": self.provider_type,
            "provider_state": self.provider_state,
            "provider_risk_score": self.provider_risk_score,
            "risk_tier": self.risk_tier,
            "global_anomaly_score": self.global_anomaly_score,
            "peer_deviation_score": self.peer_deviation_score,
            "geo_deviation_score": self.geo_deviation_score,
            "is_leie_excluded": self.is_leie_excluded,
            "peer_group": self.peer_group,
            "peer_mean": self.peer_mean,
            "peer_median": self.peer_median,
            "peer_std": self.peer_std,
            "provider_value": self.provider_value,
            "deviation_ratio": self.deviation_ratio,
            "percentile": self.percentile,
            "charge_per_service": self.charge_per_service,
            "charge_per_service_peer_mean": self.charge_per_service_peer_mean,
            "charge_per_service_peer_median": self.charge_per_service_peer_median,
            "charge_per_service_peer_std": self.charge_per_service_peer_std,
            "charge_per_service_deviation_ratio": self.charge_per_service_deviation_ratio,
            "charge_per_service_percentile": self.charge_per_service_percentile,
            "services_per_beneficiary": self.services_per_beneficiary,
            "services_per_beneficiary_peer_mean": self.services_per_beneficiary_peer_mean,
            "services_per_beneficiary_peer_median": self.services_per_beneficiary_peer_median,
            "services_per_beneficiary_peer_std": self.services_per_beneficiary_peer_std,
            "services_per_beneficiary_deviation_ratio": self.services_per_beneficiary_deviation_ratio,
            "services_per_beneficiary_percentile": self.services_per_beneficiary_percentile,
            "payment_to_charge_ratio": self.payment_to_charge_ratio,
            "payment_to_charge_ratio_peer_mean": self.payment_to_charge_ratio_peer_mean,
            "payment_to_charge_ratio_peer_median": self.payment_to_charge_ratio_peer_median,
            "payment_to_charge_ratio_peer_std": self.payment_to_charge_ratio_peer_std,
            "payment_to_charge_ratio_deviation_ratio": self.payment_to_charge_ratio_deviation_ratio,
            "payment_to_charge_ratio_percentile": self.payment_to_charge_ratio_percentile,
            "svc_hhi_concentration": self.svc_hhi_concentration,
            "svc_hhi_concentration_peer_mean": self.svc_hhi_concentration_peer_mean,
            "svc_hhi_concentration_peer_median": self.svc_hhi_concentration_peer_median,
            "svc_hhi_concentration_peer_std": self.svc_hhi_concentration_peer_std,
            "svc_hhi_concentration_deviation_ratio": self.svc_hhi_concentration_deviation_ratio,
            "svc_hhi_concentration_percentile": self.svc_hhi_concentration_percentile,
            "geo_state": self.geo_state,
            "geo_mean": self.geo_mean,
            "geo_median": self.geo_median,
            "geo_std": self.geo_std,
            "geo_provider_value": self.geo_provider_value,
            "geo_deviation_ratio": self.geo_deviation_ratio,
            "geo_percentile": self.geo_percentile,
            "geo_metric": self.geo_metric,
            "year_first": self.year_first,
            "year_last": self.year_last,
            "tot_benes": self.tot_benes,
            "tot_srvcs": self.tot_srvcs,
            "tot_sbmtd_chrg": self.tot_sbmtd_chrg,
            "tot_mdcr_pymt_amt": self.tot_mdcr_pymt_amt,
            "payment_per_service": self.payment_per_service,
            "data_availability": self.data_availability,
        }
