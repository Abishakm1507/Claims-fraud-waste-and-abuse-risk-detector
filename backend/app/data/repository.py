from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import numpy as np
import pandas as pd

from backend.app.core.config import settings
from backend.app.data.integrity import IntegrityCheckResult, check_data_integrity
from backend.app.schemas.claim_evidence import ClaimEvidence
from backend.app.schemas.provider_evidence import ProviderEvidence


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    """Convert value to int, return default if missing/invalid."""
    try:
        if value is None or pd.isna(value):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_upper(value: Any) -> str:
    if value is None or pd.isna(value):
        return "UNKNOWN"
    return str(value).strip().upper()


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, np.datetime64):
        return pd.Timestamp(value).isoformat()
    if isinstance(value, (np.generic,)):
        return _json_safe(value.item())
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    if isinstance(value, (float, np.floating)):
        if np.isfinite(value):
            return float(value)
        return None
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    return value


class DataRepository:
    def __init__(self, claim_csv_path: str | None = None, provider_csv_path: str | None = None) -> None:
        self.claim_csv_path = claim_csv_path or settings.claim_risk_csv_path
        self.provider_csv_path = provider_csv_path or settings.provider_risk_csv_path
        self.claims_df = self._load_claims()
        self.providers_df = self._load_providers()
        
        # Load claim-type-specific ML artifacts
        self.carrier_df = self._load_carrier_claims()
        self.inpatient_df = self._load_inpatient_claims()
        self.outpatient_df = self._load_outpatient_claims()
        
        # Run data integrity check
        self.integrity_check = check_data_integrity(
            self.carrier_df,
            self.inpatient_df,
            self.outpatient_df,
            self.claims_df,
        )
        print(self.integrity_check.log_summary())
        
        # Build claim evidence lookup: claim_id -> ClaimEvidence
        self._claim_evidence_cache: Dict[str, ClaimEvidence] = {}
        self._build_claim_evidence_cache()

        # Build provider evidence lookup: npi -> ProviderEvidence
        self.provider_evidence_cache: Dict[str, ProviderEvidence] = {}
        self.provider_evidence_integrity = self._build_provider_evidence_integrity()
        self._load_provider_evidence_cache()

    def _load_claims(self) -> pd.DataFrame:
        df = pd.read_csv(self.claim_csv_path, low_memory=False)
        return self._normalize_claims(df)

    def _load_providers(self) -> pd.DataFrame:
        df = pd.read_csv(self.provider_csv_path, low_memory=False)
        return self._normalize_providers(df)

    def _load_carrier_claims(self) -> pd.DataFrame:
        """Load carrier claim-type ML artifacts."""
        path = Path("models/claims/carrier/carrier_final_risk_scores.csv")
        if not path.exists():
            return pd.DataFrame()
        df = pd.read_csv(path, low_memory=False)
        return df

    def _load_inpatient_claims(self) -> pd.DataFrame:
        """Load inpatient claim-type ML artifacts."""
        path = Path("models/claims/inpatient/inpatient_final_risk_scores.csv")
        if not path.exists():
            return pd.DataFrame()
        df = pd.read_csv(path, low_memory=False)
        return df

    def _load_outpatient_claims(self) -> pd.DataFrame:
        """Load outpatient claim-type ML artifacts."""
        path = Path("models/claims/outpatient/outpatient_final_risk_scores.csv")
        if not path.exists():
            return pd.DataFrame()
        df = pd.read_csv(path, low_memory=False)
        return df

    def _build_claim_evidence_cache(self) -> None:
        """Build a lookup of claim_id -> ClaimEvidence from all three ML pipelines."""
        # Carrier claims
        for _, row in self.carrier_df.iterrows():
            claim_id = str(row.get("CLM_ID", ""))
            if not claim_id or claim_id == "nan":
                continue
            evidence = ClaimEvidence(
                claim_id=claim_id,
                claim_type="CARRIER",
                ensemble_score=_as_float(row.get("carrier_ensemble_score", 0.0)) * 100,  # scale 0-1 to 0-100
                risk_rank=_as_int(row.get("carrier_risk_rank")),
                risk_band=_safe_upper(row.get("carrier_risk_band", "UNKNOWN")),
                model_scores={
                    "isolation_forest": _as_float(row.get("IF_score", 0.0)),
                    "lof": _as_float(row.get("LOF_score", 0.0)),
                    "ocsvm": _as_float(row.get("OCSVM_score", 0.0)),
                },
                model_consensus=None,
                model_consensus_count=None,
                risk_percentile=None,
                feature_evidence={
                    k: _json_safe(v)
                    for k, v in row.items()
                    if k not in {"CLM_ID", "IF_score", "LOF_score", "OCSVM_score", "carrier_ensemble_score", "carrier_risk_rank", "carrier_risk_band"}
                },
                source_pipeline="models/claims/carrier/carrier_final_risk_scores.csv",
            )
            self._claim_evidence_cache[claim_id] = evidence

        # Inpatient claims
        for _, row in self.inpatient_df.iterrows():
            claim_id = str(row.get("clm_id", ""))
            if not claim_id or claim_id == "nan":
                continue
            evidence = ClaimEvidence(
                claim_id=claim_id,
                claim_type="INPATIENT",
                ensemble_score=_as_float(row.get("ensemble_risk_score", 0.0)),  # already 0-100
                risk_rank=_as_int(row.get("risk_rank")),
                risk_band=_safe_upper(row.get("risk_band", "UNKNOWN")),
                model_scores={
                    "isolation_forest": _as_float(row.get("isolation_forest_score", 0.0)),
                    "lof": _as_float(row.get("lof_score", 0.0)),
                    "ocsvm": _as_float(row.get("one_class_svm_score", 0.0)),
                },
                model_consensus=str(row.get("model_consensus", "")).strip() or None,
                model_consensus_count=_as_int(row.get("model_consensus_count")),
                risk_percentile=_as_float(row.get("risk_percentile")) if pd.notna(row.get("risk_percentile")) else None,
                feature_evidence={
                    k: _json_safe(v)
                    for k, v in row.items()
                    if k not in {"clm_id", "isolation_forest_score", "lof_score", "one_class_svm_score", "ensemble_risk_score", "risk_rank", "risk_band", "risk_percentile", "model_consensus", "model_consensus_count", "isolation_forest_flag", "lof_flag", "one_class_svm_flag"}
                },
                source_pipeline="models/claims/inpatient/inpatient_final_risk_scores.csv",
            )
            self._claim_evidence_cache[claim_id] = evidence

        # Outpatient claims
        for _, row in self.outpatient_df.iterrows():
            claim_id = str(row.get("CLM_ID", ""))
            if not claim_id or claim_id == "nan":
                continue
            evidence = ClaimEvidence(
                claim_id=claim_id,
                claim_type="OUTPATIENT",
                ensemble_score=_as_float(row.get("outpatient_ensemble_score", 0.0)) * 100,  # scale 0-1 to 0-100
                risk_rank=_as_int(row.get("outpatient_risk_rank")),
                risk_band=_safe_upper(row.get("outpatient_risk_band", "UNKNOWN")),
                model_scores={
                    "isolation_forest": _as_float(row.get("IF_score", 0.0)),
                    "lof": _as_float(row.get("LOF_score", 0.0)),
                    "ocsvm": _as_float(row.get("OCSVM_score", 0.0)),
                },
                model_consensus=None,
                model_consensus_count=None,
                risk_percentile=None,
                feature_evidence={
                    k: _json_safe(v)
                    for k, v in row.items()
                    if k not in {"CLM_ID", "IF_score", "LOF_score", "OCSVM_score", "outpatient_ensemble_score", "outpatient_risk_rank", "outpatient_risk_band"}
                },
                source_pipeline="models/claims/outpatient/outpatient_final_risk_scores.csv",
            )
            self._claim_evidence_cache[claim_id] = evidence

    def _normalize_claims(self, df: pd.DataFrame) -> pd.DataFrame:
        claim_id_col = next((c for c in ["CLAIM_ID", "clm_id", "CLM_ID"] if c in df.columns), None)
        provider_id_col = next((c for c in ["PROVIDER_ID", "provider_id"] if c in df.columns), None)
        claim_type_col = next((c for c in ["CLAIM_TYPE", "claim_type"] if c in df.columns), None)
        risk_score_col = next((c for c in ["CLAIM_RISK_SCORE", "claim_risk_score", "MODEL_SCORE"] if c in df.columns), None)
        risk_band_col = next((c for c in ["FINAL_RISK_LEVEL", "FINAL_RISK_LEVEL", "risk_band", "carrier_risk_band", "outpatient_risk_band"] if c in df.columns), None)
        risk_priority_col = next((c for c in ["FINAL_RISK_PRIORITY", "final_risk_priority", "risk_priority", "FINAL_RISK_PRIORITY"] if c in df.columns), None)
        risk_rank_col = next((c for c in ["FINAL_CLAIM_RANK", "CLAIM_RISK_RANK", "risk_rank", "FINAL_RISK_PRIORITY"] if c in df.columns), None)
        date_col = next((c for c in ["claim_from_dt", "claim_date", "claim_thru_dt", "CLAIM_FROM_DT", "claim_dt"] if c in df.columns), None)

        if claim_id_col is None:
            raise ValueError("Claim CSV is missing a canonical claim id column.")

        normalized = df.copy()
        normalized["claim_id"] = normalized[claim_id_col].map(lambda v: str(v).strip() if not pd.isna(v) else "")
        normalized["provider_id"] = (
            normalized[provider_id_col].map(lambda v: str(v).strip() if not pd.isna(v) else "")
            if provider_id_col
            else ""
        )
        normalized["claim_type"] = normalized[claim_type_col].map(lambda v: str(v).strip().upper() if not pd.isna(v) else "UNKNOWN") if claim_type_col else "UNKNOWN"
        normalized["claim_risk_score"] = pd.to_numeric(normalized[risk_score_col], errors="coerce").fillna(0.0) if risk_score_col else 0.0
        if claim_type_col and "MODEL_SCORE" in normalized.columns:
            outpatient_mask = normalized[claim_type_col].astype(str).str.upper().eq("OUTPATIENT")
            model_score = pd.to_numeric(normalized["MODEL_SCORE"], errors="coerce")
            valid_model_score = outpatient_mask & model_score.between(0.0, 1.0)
            normalized.loc[valid_model_score, "claim_risk_score"] = model_score.loc[valid_model_score] * 100.0
        normalized["risk_level"] = normalized["claim_risk_score"].map(self._risk_band_from_score)
        if risk_band_col:
            normalized["risk_level"] = normalized[risk_band_col].map(lambda v: str(v).strip().upper() if not pd.isna(v) else "UNKNOWN").where(
                normalized[risk_band_col].notna(), normalized["risk_level"]
            )
        normalized["risk_priority"] = pd.to_numeric(normalized[risk_priority_col], errors="coerce").fillna(0) if risk_priority_col else 0
        normalized["risk_rank"] = pd.to_numeric(normalized[risk_rank_col], errors="coerce").fillna(0) if risk_rank_col else 0
        if date_col:
            normalized["claim_date"] = pd.to_datetime(normalized[date_col], errors="coerce")
        else:
            normalized["claim_date"] = pd.NaT

        normalized["risk_level"] = normalized["risk_level"].map(lambda v: str(v).strip().upper() if not pd.isna(v) else "UNKNOWN")
        normalized["risk_level"] = normalized["risk_level"].map(lambda v: self._risk_band_from_score(v) if str(v).upper() not in {"LOW", "MEDIUM", "HIGH", "CRITICAL", "UNKNOWN"} else v)
        normalized["risk_priority"] = normalized["risk_priority"].map(lambda v: int(v) if pd.notna(v) else 0)
        normalized = normalized[
            [
                "claim_id",
                "provider_id",
                "claim_type",
                "claim_risk_score",
                "risk_level",
                "risk_rank",
                "risk_priority",
                "claim_date",
            ] + [c for c in normalized.columns if c not in {"claim_id", "provider_id", "claim_type", "claim_risk_score", "risk_level", "risk_rank", "risk_priority", "claim_date"}]
        ]
        normalized = normalized.drop_duplicates(subset=["claim_id"]).reset_index(drop=True)
        return normalized

    @staticmethod
    def _risk_band_from_score(value: Any) -> str:
        try:
            score = float(value)
        except (TypeError, ValueError):
            return "UNKNOWN"
        if score >= 85:
            return "CRITICAL"
        if score >= 70:
            return "HIGH"
        if score >= 40:
            return "MEDIUM"
        if score >= 0:
            return "LOW"
        return "UNKNOWN"

    @staticmethod
    def _normalize_npi(value: Any) -> str:
        if value is None or pd.isna(value):
            return ""
        return str(value).strip().replace(".0", "")

    def _normalize_providers(self, df: pd.DataFrame) -> pd.DataFrame:
        npi_col = next((c for c in ["npi", "NPI"] if c in df.columns), None)
        risk_score_col = next((c for c in ["risk_score_0_100", "RISK_SCORE_0_100"] if c in df.columns), None)
        risk_level_col = next((c for c in ["risk_category", "RISK_CATEGORY"] if c in df.columns), None)
        if npi_col is None:
            raise ValueError("Provider CSV is missing the NPI column.")

        normalized = df.copy()
        normalized["npi"] = normalized[npi_col].map(self._normalize_npi)
        normalized["provider_risk_score"] = pd.to_numeric(normalized[risk_score_col], errors="coerce").fillna(0.0) if risk_score_col else 0.0
        normalized["provider_risk_level"] = normalized[risk_level_col].map(lambda v: str(v).strip().upper() if not pd.isna(v) else "UNKNOWN") if risk_level_col else "UNKNOWN"
        normalized["provider_type"] = normalized.get("provider_type", pd.Series(["UNKNOWN"] * len(normalized), index=normalized.index))
        normalized["state"] = normalized.get("state", pd.Series(["UNKNOWN"] * len(normalized), index=normalized.index))
        normalized["top_risk_reasons"] = normalized.get("top_risk_reasons", pd.Series([""] * len(normalized), index=normalized.index))
        return normalized[["npi", "provider_type", "state", "provider_risk_score", "provider_risk_level", "top_risk_reasons"]].drop_duplicates(subset=["npi"]).reset_index(drop=True)

    def _build_provider_evidence_integrity(self) -> Dict[str, Any]:
        provider_npis = {self._normalize_npi(v) for v in self.providers_df["npi"].dropna()}
        leie_df = pd.DataFrame()
        if Path("data/interim/leie_clean.parquet").exists():
            leie_df = pd.read_parquet("data/interim/leie_clean.parquet", engine="fastparquet")
        if not leie_df.empty and "npi" in leie_df.columns:
            leie_df["npi"] = leie_df["npi"].map(self._normalize_npi)
        service_df = pd.DataFrame()
        if Path("data/interim/provider_service_clean.parquet").exists():
            service_df = pd.read_parquet("data/interim/provider_service_clean.parquet", engine="fastparquet")
        if not service_df.empty and "npi" in service_df.columns:
            service_df["npi"] = service_df["npi"].map(self._normalize_npi)

        leie_npis = set(leie_df["npi"].dropna().astype(str).unique()) if not leie_df.empty and "npi" in leie_df.columns else set()
        service_npis = set(service_df["npi"].dropna().astype(str).unique()) if not service_df.empty and "npi" in service_df.columns else set()

        missing_from_service = sorted(provider_npis - service_npis)
        missing_from_leie = sorted(provider_npis - leie_npis)

        return {
            "provider_count": len(provider_npis),
            "service_match_count": len(provider_npis & service_npis),
            "leie_match_count": len(provider_npis & leie_npis),
            "missing_from_service": missing_from_service,
            "missing_from_leie": missing_from_leie,
            "expected_leie_sparse": len(provider_npis & leie_npis) <= 10,
            "status": "healthy" if len(missing_from_service) == 0 and len(provider_npis & leie_npis) <= len(provider_npis) else "warn",
        }

    def _load_provider_evidence_cache(self) -> None:
        """Build an evidence lookup for provider NPIs from LEIE and peer/service benchmarks."""
        provider_npis = sorted({self._normalize_npi(v) for v in self.providers_df["npi"].dropna()})
        if not provider_npis:
            return

        leie_df = pd.DataFrame()
        leie_path = Path("data/interim/leie_clean.parquet")
        if leie_path.exists():
            leie_df = pd.read_parquet(leie_path, engine="fastparquet")
        if not leie_df.empty and "npi" in leie_df.columns:
            leie_df["npi"] = leie_df["npi"].map(self._normalize_npi)

        service_df = pd.DataFrame()
        service_path = Path("data/interim/provider_service_clean.parquet")
        if service_path.exists():
            service_df = pd.read_parquet(service_path, engine="fastparquet")
        if not service_df.empty and "npi" in service_df.columns:
            service_df["npi"] = service_df["npi"].map(self._normalize_npi)

        geo_df = pd.DataFrame()
        geo_path = Path("data/interim/geo_benchmark_clean.parquet")
        if geo_path.exists():
            geo_df = pd.read_parquet(geo_path, engine="fastparquet")

        provider_meta_by_npi = {
            self._normalize_npi(row.get("npi")): row
            for row in self.providers_df.to_dict(orient="records")
            if row.get("npi") is not None
        }
        leie_lookup = (
            leie_df.dropna(subset=["npi"]).groupby("npi", sort=False).first().to_dict(orient="index")
            if not leie_df.empty and "npi" in leie_df.columns else {}
        )
        service_lookup = (
            service_df.groupby("npi", sort=False) if not service_df.empty and "npi" in service_df.columns else None
        )
        specialty_service_lookup = (
            service_df.groupby(["provider_specialty", "provider_state"], sort=False)
            if not service_df.empty and {"provider_specialty", "provider_state"}.issubset(service_df.columns)
            else None
        )

        for npi in provider_npis:
            provider_meta = provider_meta_by_npi.get(npi, {})
            provider_type = str(provider_meta.get("provider_type") or "").strip() or None
            provider_state = str(provider_meta.get("state") or "").strip() or None

            leie_match = leie_lookup.get(npi)
            leie_payload: Optional[Dict[str, Any]] = None
            if leie_match:
                leie_payload = {
                    "exclusion_type": leie_match.get("exclusion_type"),
                    "exclusion_date": _json_safe(leie_match.get("exclusion_date")),
                    "reinstatement_date": _json_safe(leie_match.get("reinstatement_date")),
                    "waiver_date": _json_safe(leie_match.get("waiver_date")),
                    "state": leie_match.get("state"),
                    "specialty": leie_match.get("specialty"),
                    "business_name": leie_match.get("business_name"),
                    "is_individual": leie_match.get("is_individual"),
                }

            service_rows = service_lookup.get_group(npi) if service_lookup is not None and npi in service_lookup.groups else pd.DataFrame()
            peer_payload: Dict[str, Any] = {}
            if not service_rows.empty:
                peer_payload.update({
                    "service_row_count": int(len(service_rows)),
                    "avg_allowed_amount": round(float(service_rows["avg_allowed_amount"].mean()), 2) if service_rows["avg_allowed_amount"].notna().any() else None,
                    "avg_payment_amount": round(float(service_rows["avg_payment_amount"].mean()), 2) if service_rows["avg_payment_amount"].notna().any() else None,
                    "total_services": round(float(service_rows["services"].sum()), 2) if service_rows["services"].notna().any() else None,
                    "year_coverage": sorted({int(v) for v in service_rows["year"].dropna().astype(int).tolist()}),
                })
                if provider_type and provider_state and specialty_service_lookup is not None:
                    key = (str(provider_type), str(provider_state))
                    specialty_rows = specialty_service_lookup.get_group(key) if key in specialty_service_lookup.groups else pd.DataFrame()
                    if not specialty_rows.empty:
                        provider_avg = float(service_rows["avg_payment_amount"].mean()) if service_rows["avg_payment_amount"].notna().any() else 0.0
                        peer_percentile = round(float((specialty_rows["avg_payment_amount"] <= provider_avg).mean() * 100), 2)
                        peer_payload["peer_percentile"] = peer_percentile
                        peer_payload["peer_comparison_basis"] = {
                            "provider_type": provider_type,
                            "state": provider_state,
                            "peer_population_count": int(specialty_rows["npi"].nunique()),
                        }
                if not geo_df.empty:
                    hcpcs = set(service_rows["hcpcs_code"].dropna().astype(str).tolist())
                    geo_matches = geo_df[geo_df["hcpcs_code"].astype(str).isin(hcpcs)]
                    if not geo_matches.empty:
                        peer_payload["geo_benchmark_matches"] = int(geo_matches["hcpcs_code"].nunique())
                        peer_payload["geo_benchmark_years"] = sorted({int(v) for v in geo_matches["year"].dropna().astype(int).tolist()})

            source_files = [
                str(leie_path) if leie_match else None,
                str(service_path) if not service_rows.empty else None,
                str(geo_path) if (not geo_df.empty and not service_rows.empty) else None,
            ]
            evidence = ProviderEvidence(
                npi=npi,
                provider_type=provider_type or None,
                state=provider_state or None,
                exclusion_status="EXCLUDED" if leie_match else "NOT_FOUND",
                leie_match=leie_payload,
                peer_benchmark=peer_payload,
                service_summary={
                    "total_services": round(float(service_rows["services"].sum()), 2) if not service_rows.empty and service_rows["services"].notna().any() else None,
                    "avg_allowed_amount": round(float(service_rows["avg_allowed_amount"].mean()), 2) if not service_rows.empty and service_rows["avg_allowed_amount"].notna().any() else None,
                    "avg_payment_amount": round(float(service_rows["avg_payment_amount"].mean()), 2) if not service_rows.empty and service_rows["avg_payment_amount"].notna().any() else None,
                    "provider_specialty": str(service_rows["provider_specialty"].dropna().unique()[:1][0]) if not service_rows.empty and service_rows["provider_specialty"].notna().any() else provider_type,
                    "provider_state": str(service_rows["provider_state"].dropna().unique()[:1][0]) if not service_rows.empty and service_rows["provider_state"].notna().any() else provider_state,
                },
                provenance={
                    "leie_match": bool(leie_match),
                    "has_service_rows": bool(not service_rows.empty),
                    "has_geo_benchmark_rows": bool(not geo_df.empty and not service_rows.empty),
                },
                source_files=[s for s in source_files if s is not None],
            )
            self.provider_evidence_cache[npi] = evidence

    def get_provider_evidence(self, npi: str) -> Optional[ProviderEvidence]:
        return self.provider_evidence_cache.get(self._normalize_npi(npi))

    def get_providers(self, *, risk_band: Optional[str] = None, state: Optional[str] = None, sort_by: str = "provider_risk_score", order: str = "desc", page: int = 1, page_size: int = 25) -> Dict[str, Any]:
        df = self.providers_df.copy()
        if risk_band:
            df = df[df["provider_risk_level"].astype(str).str.upper() == str(risk_band).upper()]
        if state:
            df = df[df["state"].astype(str).str.upper() == str(state).upper()]
        if sort_by not in df.columns:
            sort_by = "provider_risk_score"
        df = df.sort_values(by=sort_by, ascending=(order.lower() != "desc"), na_position="last")
        total = int(len(df))
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        rows = []
        for row in df.iloc[start_idx:end_idx].to_dict(orient="records"):
            item = _json_safe(row)
            npi = self._normalize_npi(row.get("npi"))
            evidence = self.get_provider_evidence(npi)
            if evidence is not None:
                item["provider_evidence"] = {
                    "exclusion_status": evidence.exclusion_status,
                    "peer_percentile": evidence.peer_benchmark.get("peer_percentile"),
                }
            rows.append(item)
        return {
            "items": rows,
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": max(1, (total + page_size - 1) // page_size) if total else 1,
        }

    def get_claim(self, claim_id: str) -> Optional[Dict[str, Any]]:
        matches = self.claims_df[self.claims_df["claim_id"].astype(str) == str(claim_id)]
        if matches.empty:
            return None
        return _json_safe(matches.iloc[0].to_dict())

    def get_provider(self, npi: str) -> Optional[Dict[str, Any]]:
        matches = self.providers_df[self.providers_df["npi"].astype(str) == str(npi)]
        if matches.empty:
            return None
        provider = _json_safe(matches.iloc[0].to_dict())
        return provider

    def get_claims(self, *, claim_type: Optional[str] = None, risk_band: Optional[str] = None, provider_id: Optional[str] = None, date_from: Optional[str] = None, date_to: Optional[str] = None, sort_by: str = "claim_risk_score", order: str = "desc", page: int = 1, page_size: int = 25) -> Dict[str, Any]:
        df = self.claims_df.copy()
        if claim_type:
            df = df[df["claim_type"].astype(str).str.upper() == str(claim_type).upper()]
        if risk_band:
            df = df[df["risk_level"].astype(str).str.upper() == str(risk_band).upper()]
        if provider_id:
            df = df[df["provider_id"].astype(str).str.upper() == str(provider_id).upper()]
        if date_from:
            start = pd.to_datetime(date_from, errors="coerce")
            df = df[df["claim_date"].notna() & (df["claim_date"] >= start)]
        if date_to:
            end = pd.to_datetime(date_to, errors="coerce")
            df = df[df["claim_date"].notna() & (df["claim_date"] <= end)]
        if sort_by not in df.columns:
            sort_by = "claim_risk_score"
        df = df.sort_values(by=sort_by, ascending=(order.lower() != "desc"), na_position="last")
        total = int(len(df))
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        rows_data = df.iloc[start_idx:end_idx].to_dict(orient="records")
        
        # Enrich each row with lean ml_evidence (without feature_evidence)
        enriched_rows = []
        for row in rows_data:
            enriched_row = _json_safe(row)
            claim_id = str(row.get("claim_id", ""))
            ml_evidence = self.get_claim_evidence(claim_id)
            if ml_evidence:
                # Include only essential ML fields for list view (exclude feature_evidence)
                enriched_row["ml_evidence"] = {
                    "claim_type": ml_evidence.claim_type,
                    "ensemble_score": ml_evidence.ensemble_score,
                    "risk_band": ml_evidence.risk_band,
                }
            enriched_rows.append(enriched_row)
        
        return {
            "items": enriched_rows,
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": max(1, (total + page_size - 1) // page_size) if total else 1,
        }

    def get_providers(self, *, risk_band: Optional[str] = None, state: Optional[str] = None, sort_by: str = "provider_risk_score", order: str = "desc", page: int = 1, page_size: int = 25) -> Dict[str, Any]:
        df = self.providers_df.copy()
        if risk_band:
            df = df[df["provider_risk_level"].astype(str).str.upper() == str(risk_band).upper()]
        if state:
            df = df[df["state"].astype(str).str.upper() == str(state).upper()]
        if sort_by not in df.columns:
            sort_by = "provider_risk_score"
        df = df.sort_values(by=sort_by, ascending=(order.lower() != "desc"), na_position="last")
        total = int(len(df))
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        rows = [_json_safe(row) for row in df.iloc[start_idx:end_idx].to_dict(orient="records")]
        return {
            "items": rows,
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": max(1, (total + page_size - 1) // page_size) if total else 1,
        }

    def stats_overview(self) -> Dict[str, Any]:
        claims = self.claims_df
        providers = self.providers_df
        risk_distribution = {
            key: int((claims["risk_level"] == key).sum())
            for key in ["LOW", "MEDIUM", "HIGH", "CRITICAL", "UNKNOWN"]
        }
        provider_distribution = {
            key: int((providers["provider_risk_level"] == key).sum())
            for key in ["LOW", "MEDIUM", "HIGH", "CRITICAL", "UNKNOWN"]
        }

        factor_counts: Dict[str, int] = {}
        for reasons in providers["top_risk_reasons"].fillna("").astype(str):
            for chunk in reasons.split(";"):
                cleaned = chunk.strip()
                if cleaned:
                    factor_counts[cleaned] = factor_counts.get(cleaned, 0) + 1
        top_risk_factors = [
            {"factor": factor, "count": count}
            for factor, count in sorted(factor_counts.items(), key=lambda item: (-item[1], item[0]))[:10]
        ]

        # Per-claim-type breakdown
        per_type_stats = self._stats_by_claim_type()

        return {
            "total_claims": int(len(claims)),
            "total_providers": int(len(providers)),
            "high_risk_claims": int((claims["risk_level"].isin(["HIGH", "CRITICAL"])).sum()),
            "high_risk_providers": int((providers["provider_risk_score"] >= 70).sum()),
            "risk_distribution": risk_distribution,
            "provider_risk_distribution": provider_distribution,
            "top_risk_factors": top_risk_factors,
            "per_claim_type": per_type_stats,
        }

    def _stats_by_claim_type(self) -> Dict[str, Any]:
        """Calculate per-claim-type stats: count, avg ensemble score, risk distribution."""
        result = {}
        
        for claim_type in ["CARRIER", "INPATIENT", "OUTPATIENT"]:
            type_claims = self.claims_df[self.claims_df["claim_type"] == claim_type]
            
            # Get ML evidence for this type
            type_evidences = [
                ev for ev in self._claim_evidence_cache.values()
                if ev.claim_type == claim_type
            ]
            
            avg_ensemble = 0.0
            if type_evidences:
                avg_ensemble = sum(ev.ensemble_score for ev in type_evidences) / len(type_evidences)
            
            # Risk band distribution from ML evidence
            risk_dist = {
                "LOW": sum(1 for ev in type_evidences if ev.risk_band == "LOW"),
                "MEDIUM": sum(1 for ev in type_evidences if ev.risk_band == "MEDIUM"),
                "HIGH": sum(1 for ev in type_evidences if ev.risk_band == "HIGH"),
                "CRITICAL": sum(1 for ev in type_evidences if ev.risk_band == "CRITICAL"),
            }
            
            result[claim_type] = {
                "count": len(type_claims),
                "avg_ensemble_score": round(avg_ensemble, 2),
                "risk_band_distribution": risk_dist,
            }
        
        return result

    def get_claim_id_candidates(self) -> Iterable[str]:
        return [str(v) for v in self.claims_df["claim_id"].dropna().astype(str).unique()]

    def get_provider_id_candidates(self) -> Iterable[str]:
        return [str(v) for v in self.providers_df["npi"].dropna().astype(str).unique()]

    def get_claim_evidence(self, claim_id: str) -> Optional[ClaimEvidence]:
        """Retrieve type-specific ML evidence for a claim.
        
        Returns None if the claim_id is not in any of the three ML pipelines.
        """
        return self._claim_evidence_cache.get(str(claim_id))


repository = DataRepository()
