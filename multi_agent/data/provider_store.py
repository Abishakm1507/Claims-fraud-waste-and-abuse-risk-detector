from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

import pandas as pd

from multi_agent.schemas.provider_context import ProviderContext

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_PROVIDER_CSV = PROJECT_ROOT / "models" / "provider" / "output" / "provider_risk_scores.csv"


class ProviderStore:
    """Reads the authoritative provider ML output and returns typed ProviderContext records."""

    def __init__(self, csv_path: Optional[str | Path] = None):
        csv_path = Path(csv_path) if csv_path is not None else DEFAULT_PROVIDER_CSV
        if not csv_path.exists():
            raise FileNotFoundError(f"Provider risk output not found: {csv_path}")
        self.csv_path = csv_path
        self._df = pd.read_csv(csv_path, low_memory=False)
        self._by_npi: Dict[int, pd.Series] = {}
        for _, row in self._df.iterrows():
            npi = self._coerce_npi(row.get("NPI"))
            if npi is None:
                continue
            if npi in self._by_npi:
                raise ValueError(f"Duplicate NPI rows found in provider output: {npi}")
            self._by_npi[npi] = row

    @staticmethod
    def _coerce_npi(value):
        if value is None or pd.isna(value):
            return None
        try:
            return int(str(value).strip())
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _to_float(value):
        if value is None or pd.isna(value):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _to_int(value):
        if value is None or pd.isna(value):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _build_context(self, row: pd.Series) -> ProviderContext:
        npi = self._coerce_npi(row.get("NPI"))
        if npi is None:
            return None

        provider_type = str(row.get("Provider_Type")) if pd.notna(row.get("Provider_Type")) else None
        provider_state = str(row.get("Prvdr_State")) if pd.notna(row.get("Prvdr_State")) else None
        provider_risk_score = self._to_float(row.get("Provider_Risk_Score"))
        risk_tier = str(row.get("Risk_Tier")) if pd.notna(row.get("Risk_Tier")) else None
        global_anomaly_score = self._to_float(row.get("global_anomaly_score"))
        peer_deviation_score = self._to_float(row.get("peer_deviation_score"))
        geo_deviation_score = self._to_float(row.get("geo_deviation_score"))
        is_leie_excluded = bool(row.get("is_leie_excluded")) if pd.notna(row.get("is_leie_excluded")) else None

        geo_provider_value = self._to_float(row.get("Geo_Provider_Avg_Pymt"))
        geo_mean = self._to_float(row.get("Geo_Bench_Pymt_Mean"))
        geo_median = self._to_float(row.get("Geo_Bench_Pymt_Median"))
        geo_std = self._to_float(row.get("Geo_Bench_Pymt_Std"))
        geo_ratio = None
        if geo_provider_value is not None and geo_mean is not None and geo_mean != 0:
            geo_ratio = geo_provider_value / geo_mean

        ctx = ProviderContext(
            npi=npi,
            provider_type=provider_type,
            provider_state=provider_state,
            provider_risk_score=provider_risk_score,
            risk_tier=risk_tier,
            global_anomaly_score=global_anomaly_score,
            peer_deviation_score=peer_deviation_score,
            geo_deviation_score=geo_deviation_score,
            is_leie_excluded=is_leie_excluded,
            peer_group=str(row.get("peer_group")) if pd.notna(row.get("peer_group")) else None,
            peer_mean=self._to_float(row.get("Payment_per_Service_Peer_Mean")),
            peer_median=self._to_float(row.get("Payment_per_Service_Peer_Median")),
            peer_std=self._to_float(row.get("Payment_per_Service_Peer_Std")),
            provider_value=self._to_float(row.get("Payment_per_Service")),
            deviation_ratio=self._to_float(row.get("Payment_per_Service_Deviation_Ratio")),
            percentile=self._to_float(row.get("Payment_per_Service_Peer_Pctile")),
            charge_per_service=self._to_float(row.get("Charge_per_Service")),
            charge_per_service_peer_mean=self._to_float(row.get("Charge_per_Service_Peer_Mean")),
            charge_per_service_peer_median=self._to_float(row.get("Charge_per_Service_Peer_Median")),
            charge_per_service_peer_std=self._to_float(row.get("Charge_per_Service_Peer_Std")),
            charge_per_service_deviation_ratio=self._to_float(row.get("Charge_per_Service_Deviation_Ratio")),
            charge_per_service_percentile=self._to_float(row.get("Charge_per_Service_Peer_Pctile")),
            services_per_beneficiary=self._to_float(row.get("Services_per_Beneficiary")),
            services_per_beneficiary_peer_mean=self._to_float(row.get("Services_per_Beneficiary_Peer_Mean")),
            services_per_beneficiary_peer_median=self._to_float(row.get("Services_per_Beneficiary_Peer_Median")),
            services_per_beneficiary_peer_std=self._to_float(row.get("Services_per_Beneficiary_Peer_Std")),
            services_per_beneficiary_deviation_ratio=self._to_float(row.get("Services_per_Beneficiary_Deviation_Ratio")),
            services_per_beneficiary_percentile=self._to_float(row.get("Services_per_Beneficiary_Peer_Pctile")),
            payment_to_charge_ratio=self._to_float(row.get("Payment_to_Charge_Ratio")),
            payment_to_charge_ratio_peer_mean=self._to_float(row.get("Payment_to_Charge_Ratio_Peer_Mean")),
            payment_to_charge_ratio_peer_median=self._to_float(row.get("Payment_to_Charge_Ratio_Peer_Median")),
            payment_to_charge_ratio_peer_std=self._to_float(row.get("Payment_to_Charge_Ratio_Peer_Std")),
            payment_to_charge_ratio_deviation_ratio=self._to_float(row.get("Payment_to_Charge_Ratio_Deviation_Ratio")),
            payment_to_charge_ratio_percentile=self._to_float(row.get("Payment_to_Charge_Ratio_Peer_Pctile")),
            svc_hhi_concentration=self._to_float(row.get("Svc_HHI_Concentration")),
            svc_hhi_concentration_peer_mean=self._to_float(row.get("Svc_HHI_Concentration_Peer_Mean")),
            svc_hhi_concentration_peer_median=self._to_float(row.get("Svc_HHI_Concentration_Peer_Median")),
            svc_hhi_concentration_peer_std=self._to_float(row.get("Svc_HHI_Concentration_Peer_Std")),
            svc_hhi_concentration_deviation_ratio=self._to_float(row.get("Svc_HHI_Concentration_Deviation_Ratio")),
            svc_hhi_concentration_percentile=self._to_float(row.get("Svc_HHI_Concentration_Peer_Pctile")),
            geo_state=provider_state,
            geo_mean=geo_mean,
            geo_median=geo_median,
            geo_std=geo_std,
            geo_provider_value=geo_provider_value,
            geo_deviation_ratio=geo_ratio,
            geo_percentile=None,
            geo_metric="Payment_per_Service",
            year_first=self._to_int(row.get("Year_First")),
            year_last=self._to_int(row.get("Year_Last")),
            tot_benes=self._to_int(row.get("Tot_Benes")),
            tot_srvcs=self._to_float(row.get("Tot_Srvcs")),
            tot_sbmtd_chrg=self._to_float(row.get("Tot_Sbmtd_Chrg")),
            tot_mdcr_pymt_amt=self._to_float(row.get("Tot_Mdcr_Pymt_Amt")),
            payment_per_service=self._to_float(row.get("Payment_per_Service")),
            data_availability={
                "peer": pd.notna(row.get("peer_deviation_score")),
                "geo": pd.notna(row.get("geo_deviation_score")),
                "temporal": pd.notna(row.get("Year_First")) or pd.notna(row.get("Year_Last")),
                "leie": pd.notna(row.get("is_leie_excluded")),
            },
        )
        return ctx

    def get_provider(self, npi: int | str) -> Optional[ProviderContext]:
        key = self._coerce_npi(npi)
        if key is None:
            return None
        row = self._by_npi.get(key)
        if row is None:
            return None
        return self._build_context(row)

    def exists(self, npi: int | str) -> bool:
        return self.get_provider(npi) is not None

    def __len__(self):
        return len(self._by_npi)
