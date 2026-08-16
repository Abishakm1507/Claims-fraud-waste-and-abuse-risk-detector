"""
provider_repository.py

Data-access layer for the downstream Multi-Agent Investigation module.

The Multi-Agent layer must NOT read the provider CSVs directly. Instead it
calls ``get_provider(npi)`` (or ``ProviderRepository``) and receives a typed
:class:`~provider_context.ProviderContext` with the complete investigation
context: risk scores, provider features, peer evidence, geographic evidence,
temporal evidence and the LEIE exclusion flag.

Source of truth
---------------
This repository is backed by the authoritative Provider ML output:

    models/provider/output/provider_risk_scores.csv

produced by the s1 -> s2 -> s3 -> s4 pipeline (see
PROVIDER_ML_MULTI_AGENT_HANDOFF.md). The full file is loaded once into memory
and indexed by NPI (dict lookup, O(1)); contexts are built on demand.

Usage
-----
    from provider_repository import get_provider, search_providers

    ctx = get_provider(1003569997)          # -> ProviderContext | None
    if ctx is not None:
        print(ctx.risk_score, ctx.peer_evidence.peer_group)

    high = search_providers(risk_tier="Critical", limit=10)
"""

from pathlib import Path
from typing import Any, Iterable, List, Optional

import pandas as pd

from provider_context import (
    PEER_METRICS,
    GeoEvidence,
    LeieEvidence,
    PeerEvidence,
    PeerMetricEvidence,
    ProviderContext,
    TemporalEvidence,
    _f,
    _i,
)

# models/provider/provider_repository.py -> models/provider -> models -> <project root>
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_OUTPUT_CSV = (
    PROJECT_ROOT / "models" / "provider" / "output" / "provider_risk_scores.csv"
)


class ProviderRepository:
    """NPI-indexed access to the authoritative provider risk output."""

    def __init__(self, csv_path: Optional[Any] = None):
        """
        Parameters
        ----------
        csv_path : path-like, optional
            Path to the provider risk CSV. Defaults to the authoritative
            ``models/provider/output/provider_risk_scores.csv``.
        """
        self.csv_path = Path(csv_path) if csv_path is not None else DEFAULT_OUTPUT_CSV
        if not self.csv_path.exists():
            raise FileNotFoundError(
                f"Provider risk output not found: {self.csv_path}. "
                "Run the s1 -> s2 -> s3 -> s4 pipeline first."
            )
        self._df = pd.read_csv(self.csv_path, low_memory=False)
        self._npis = self._df["NPI"].astype("int64").to_numpy()
        self._by_npi: dict = {int(n): i for i, n in enumerate(self._npis)}
        if len(self._by_npi) != len(self._npis):
            raise ValueError("Duplicate NPI rows found in provider risk output.")

    # ------------------------------------------------------------------
    # lookup helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _normalize_npi(npi: Any) -> Optional[int]:
        try:
            return int(str(npi).strip())
        except (TypeError, ValueError):
            return None

    def __len__(self) -> int:
        return len(self._by_npi)

    def __contains__(self, npi: Any) -> bool:
        key = self._normalize_npi(npi)
        return key is not None and key in self._by_npi

    def get_provider(self, npi: Any) -> Optional[ProviderContext]:
        """Return the full investigation context for one NPI, or None if absent."""
        key = self._normalize_npi(npi)
        if key is None:
            return None
        idx = self._by_npi.get(key)
        if idx is None:
            return None
        return self._row_to_context(self._df.iloc[idx])

    def get_providers(self, npis: Iterable[Any]) -> List[ProviderContext]:
        """Batch lookup; preserves input order, skips unknown NPIs."""
        out: List[ProviderContext] = []
        for npi in npis:
            ctx = self.get_provider(npi)
            if ctx is not None:
                out.append(ctx)
        return out

    def search_providers(
        self,
        provider_type: Optional[str] = None,
        state: Optional[str] = None,
        risk_tier: Optional[str] = None,
        min_risk: Optional[float] = None,
        max_risk: Optional[float] = None,
        limit: Optional[int] = None,
    ) -> List[ProviderContext]:
        """
        Filter providers (exact state / risk_tier; case-insensitive substring
        for provider_type) and return contexts sorted by risk (descending).
        """
        df = self._df
        mask = pd.Series(True, index=df.index)
        if provider_type is not None:
            mask &= (
                df["Provider_Type"].astype(str).str.contains(
                    str(provider_type), case=False, na=False
                )
            )
        if state is not None:
            mask &= df["Prvdr_State"].astype(str).str.upper() == str(state).upper()
        if risk_tier is not None:
            mask &= (
                df["Risk_Tier"].astype(str).str.lower() == str(risk_tier).lower()
            )
        if min_risk is not None:
            mask &= df["Provider_Risk_Score"] >= min_risk
        if max_risk is not None:
            mask &= df["Provider_Risk_Score"] <= max_risk
        subset = df[mask].sort_values("Provider_Risk_Score", ascending=False)
        if limit is not None and limit > 0:
            subset = subset.head(limit)
        return [self._row_to_context(row) for _, row in subset.iterrows()]

    # ------------------------------------------------------------------
    # context construction
    # ------------------------------------------------------------------
    def _row_to_context(self, row: pd.Series) -> ProviderContext:
        f = lambda col: _f(row.get(col))  # noqa: E731
        i = lambda col: _i(row.get(col))  # noqa: E731
        s = lambda col: (  # noqa: E731
            str(row[col]) if col in row and pd.notna(row[col]) else None
        )

        peer_metrics = [
            PeerMetricEvidence(
                metric=m,
                provider_value=f(m),
                peer_mean=f(f"{m}_Peer_Mean"),
                peer_median=f(f"{m}_Peer_Median"),
                peer_std=f(f"{m}_Peer_Std"),
                deviation_ratio=f(f"{m}_Deviation_Ratio"),
                percentile=f(f"{m}_Peer_Pctile"),
            )
            for m in PEER_METRICS
        ]

        peer_evidence = PeerEvidence(
            peer_group=s("peer_group"),
            score=f("peer_deviation_score"),
            zsum=f("peer_deviation_zsum"),
            metrics=peer_metrics,
        )

        geo_evidence = GeoEvidence(
            score=f("geo_deviation_score"),
            avg_pymt_deviation=f("Peer_Avg_Pymt_Deviation"),
            max_pymt_deviation=f("Peer_Max_Pymt_Deviation"),
            avg_chrg_deviation=f("Peer_Avg_Chrg_Deviation"),
            pct_services_above_2x_bench=f("Peer_Pct_Services_Above_2x_Bench"),
            rows_matched=i("Geo_Rows_Matched"),
            rows_by_level={
                "state_year": i("Geo_Rows_state_year") or 0,
                "state": i("Geo_Rows_state") or 0,
                "national": i("Geo_Rows_national") or 0,
            },
            provider_avg_pymt=f("Geo_Provider_Avg_Pymt"),
            bench_pymt_mean=f("Geo_Bench_Pymt_Mean"),
            bench_pymt_median=f("Geo_Bench_Pymt_Median"),
            bench_pymt_std=f("Geo_Bench_Pymt_Std"),
            provider_avg_chrg=f("Geo_Provider_Avg_Chrg"),
            bench_chrg_mean=f("Geo_Bench_Chrg_Mean"),
            bench_chrg_median=f("Geo_Bench_Chrg_Median"),
            bench_chrg_std=f("Geo_Bench_Chrg_Std"),
        )

        temporal_evidence = TemporalEvidence(
            year_first=i("Year_First"),
            year_last=i("Year_Last"),
            num_years_observed=i("Num_Years_Observed"),
            metrics={
                "Tot_Srvcs": {
                    "first": f("Svc_First_Year"),
                    "last": f("Svc_Last_Year"),
                    "growth_pct": f("Svc_Growth_Pct"),
                },
                "Tot_Mdcr_Pymt_Amt": {
                    "first": f("Pymt_First_Year"),
                    "last": f("Pymt_Last_Year"),
                    "growth_pct": f("Pymt_Growth_Pct"),
                },
                "Tot_Benes": {
                    "first": f("Benes_First_Year"),
                    "last": f("Benes_Last_Year"),
                    "growth_pct": f("Benes_Growth_Pct"),
                },
            },
        )

        provider_features = {
            "Tot_Benes": f("Tot_Benes"),
            "Tot_Srvcs": f("Tot_Srvcs"),
            "Tot_Sbmtd_Chrg": f("Tot_Sbmtd_Chrg"),
            "Tot_Mdcr_Pymt_Amt": f("Tot_Mdcr_Pymt_Amt"),
            "Tot_Mdcr_Alowd_Amt": f("Tot_Mdcr_Alowd_Amt"),
            "Payment_per_Service": f("Payment_per_Service"),
            "Payment_per_Beneficiary": f("Payment_per_Beneficiary"),
            "Services_per_Beneficiary": f("Services_per_Beneficiary"),
            "Charge_per_Service": f("Charge_per_Service"),
            "Payment_to_Charge_Ratio": f("Payment_to_Charge_Ratio"),
            "Tot_HCPCS_Cds": f("Tot_HCPCS_Cds"),
            "Svc_Unique_HCPCS": f("Svc_Unique_HCPCS"),
            "Svc_HHI_Concentration": f("Svc_HHI_Concentration"),
            "has_service_detail": f("has_service_detail"),
            "service_pattern_score": f("service_pattern_score"),
            "iso_score_raw": f("iso_score_raw"),
            "lof_score_raw": f("lof_score_raw"),
            "iso_flag": f("iso_flag"),
            "lof_flag": f("lof_flag"),
            "dbscan_flag": f("dbscan_flag"),
        }

        return ProviderContext(
            npi=int(row["NPI"]),
            provider_type=s("Provider_Type"),
            state=s("Prvdr_State"),
            risk_score=f("Provider_Risk_Score"),
            risk_tier=s("Risk_Tier"),
            anomaly_score=f("global_anomaly_score"),
            provider_features=provider_features,
            peer_evidence=peer_evidence,
            geo_evidence=geo_evidence,
            temporal_evidence=temporal_evidence,
            leie_evidence=LeieEvidence(is_excluded=bool(row.get("is_leie_excluded", 0))),
        )


# ----------------------------------------------------------------------
# Module-level convenience API (lazily shares one repository instance)
# ----------------------------------------------------------------------
_default_repo: Optional[ProviderRepository] = None


def _default() -> ProviderRepository:
    global _default_repo
    if _default_repo is None:
        _default_repo = ProviderRepository()
    return _default_repo


def get_provider(npi: Any) -> Optional[ProviderContext]:
    """Return the complete investigation context for one NPI (or None)."""
    return _default().get_provider(npi)


def get_providers(npis: Iterable[Any]) -> List[ProviderContext]:
    """Batch NPI lookup."""
    return _default().get_providers(npis)


def search_providers(
    provider_type: Optional[str] = None,
    state: Optional[str] = None,
    risk_tier: Optional[str] = None,
    min_risk: Optional[float] = None,
    max_risk: Optional[float] = None,
    limit: Optional[int] = None,
) -> List[ProviderContext]:
    """Filter providers by type/state/tier/risk range; highest risk first."""
    return _default().search_providers(
        provider_type=provider_type,
        state=state,
        risk_tier=risk_tier,
        min_risk=min_risk,
        max_risk=max_risk,
        limit=limit,
    )
