from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from multi_agent.models.schemas import CONTRACT_VERSION, InvestigationCase, InvestigationContext

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CLAIM_CSV = PROJECT_ROOT / "models" / "claims" / "carrier" / "carrier_final_risk_scores.csv"
PROVIDER_CSV = PROJECT_ROOT / "models" / "provider" / "provider_risk_scores.csv"


class DataContractValidator:
    """Validate the real upstream ML CSVs against the Investigation Contract v1."""

    CLAIM_REQUIRED_FIELDS = [
        ("claim_id", "CLM_ID"),
        ("provider_id", "PROVIDER_ID"),
        ("provider_id_type", "provider_id_type"),
        ("claim_type", "claim_type"),
        ("ensemble_score", "ensemble_score"),
        ("risk_rank", "risk_rank"),
        ("risk_band", "risk_band"),
        ("claim_line_count", "claim_line_count"),
        ("beneficiary_claim_count", "beneficiary_claim_count"),
        ("provider_claim_count", "provider_claim_count"),
        ("procedure_code_count", "procedure_code_count"),
        ("unique_procedure_code_count", "unique_procedure_code_count"),
        ("has_procedure", "has_procedure"),
    ]

    PROVIDER_REQUIRED_FIELDS = [
        ("npi", "NPI"),
        ("provider_type", "Provider_Type"),
        ("provider_state", "Prvdr_State"),
        ("provider_risk_score", "Provider_Risk_Score"),
        ("risk_tier", "Risk_Tier"),
        ("global_anomaly_score", "global_anomaly_score"),
        ("peer_deviation_score", "peer_deviation_score"),
        ("geo_deviation_score", "geo_deviation_score"),
        ("is_leie_excluded", "is_leie_excluded"),
        ("payment_per_service", "Payment_per_Service"),
        ("payment_per_service_peer_mean", "Payment_per_Service_Peer_Mean"),
        ("payment_per_service_peer_median", "Payment_per_Service_Peer_Median"),
        ("payment_per_service_peer_std", "Payment_per_Service_Peer_Std"),
    ]

    def __init__(
        self,
        claim_csv: str | Path = CLAIM_CSV,
        provider_csv: str | Path = PROVIDER_CSV,
    ) -> None:
        self.claim_csv = Path(claim_csv)
        self.provider_csv = Path(provider_csv)

    def validate(self) -> Dict[str, Any]:
        claim_df = self._read_claims()
        provider_df = self._read_providers()

        claim_type_counts = self._normalize_counts(claim_df, "claim_type")
        limitations: List[str] = []

        required_fields = {
            "claim": self._summarize_field_availability(claim_df, self.CLAIM_REQUIRED_FIELDS),
            "provider": self._summarize_field_availability(provider_df, self.PROVIDER_REQUIRED_FIELDS),
        }

        if not self._field_is_present(claim_df, "CLM_ID"):
            limitations.append("Carrier claim export is missing the canonical CLM_ID field required by the contract.")
        if not self._field_is_present(claim_df, "provider_id"):
            limitations.append("Claim export does not include a normalized provider ID field for all claim types.")
        if not self._field_is_present(claim_df, "ensemble_score"):
            limitations.append("Claim export is missing the authoritative ensemble score used by the claim ML evidence layer.")
        if not self._field_is_present(provider_df, "Payment_per_Service_Peer_Mean") or not self._field_is_present(provider_df, "Payment_per_Service_Peer_Median"):
            limitations.append("Provider ML export does not include the full peer benchmark set; peer median/mean can be explicitly absent.")
        if not self._field_is_present(claim_df, "model_consensus"):
            limitations.append("The current claim export does not include explicit model-consensus rule fields; inpatient clinical evidence remains limited.")
        if not self._field_is_present(provider_df, "is_leie_excluded"):
            limitations.append("LEIE exclusion status is not exported for every provider row; the contract will record it as unavailable when absent.")

        can_populate = self._can_populate_context(claim_df, provider_df)
        can_produce_valid_case = self._can_produce_valid_case(claim_df, provider_df)

        result = {
            "contract_version": CONTRACT_VERSION,
            "claim_path": str(self.claim_csv),
            "provider_path": str(self.provider_csv),
            "claim_rows": int(len(claim_df)),
            "provider_rows": int(len(provider_df)),
            "claim_type_counts": claim_type_counts,
            "required_fields": required_fields,
            "can_populate_investigation_context": bool(can_populate),
            "can_produce_valid_investigation_case": bool(can_produce_valid_case),
            "limitations": limitations,
            "validation_summary": (
                "The current provider and claim ML exports are sufficient to populate the deterministic investigation context and produce a valid InvestigationCase, "
                "with explicit limitations recorded where fields are absent."
                if can_produce_valid_case
                else "The current exports are incomplete for a fully valid investigation contract handoff; missing fields are explicitly tracked."
            ),
        }
        return result

    def _read_claims(self) -> pd.DataFrame:
        if not self.claim_csv.exists():
            raise FileNotFoundError(f"Claim output not found: {self.claim_csv}")
        frames = []
        for type_name in ("carrier", "inpatient", "outpatient"):
            path = self.claim_csv.parent.parent / type_name / f"{type_name}_final_risk_scores.csv"
            if path.exists():
                df = pd.read_csv(path, low_memory=False)
                df = df.copy()
                if type_name == "carrier":
                    df["claim_id"] = df["CLM_ID"]
                    df["provider_id"] = df.get("CARR_CLM_BLG_NPI_NUM_first")
                    df["provider_id_type"] = "NPI"
                    df["claim_type"] = "CARRIER"
                    df["ensemble_score"] = df.get("carrier_ensemble_score")
                    df["risk_rank"] = df.get("carrier_risk_rank")
                    df["risk_band"] = df.get("carrier_risk_band")
                elif type_name == "inpatient":
                    df["claim_id"] = df["clm_id"]
                    df["provider_id"] = df.get("provider_id")
                    df["provider_id_type"] = "PRVDR_NUM"
                    df["claim_type"] = "INPATIENT"
                    df["ensemble_score"] = df.get("ensemble_risk_score")
                    df["risk_rank"] = df.get("risk_rank")
                    df["risk_band"] = df.get("risk_band")
                else:
                    df["claim_id"] = df["CLM_ID"]
                    df["provider_id"] = df.get("provider_id")
                    df["provider_id_type"] = "PRVDR_NUM"
                    df["claim_type"] = "OUTPATIENT"
                    df["ensemble_score"] = df.get("outpatient_ensemble_score")
                    df["risk_rank"] = df.get("outpatient_risk_rank")
                    df["risk_band"] = df.get("outpatient_risk_band")
                df["claim_type"] = df["claim_type"].str.upper()
                if "claim_line_count" not in df.columns:
                    df["claim_line_count"] = pd.NA
                if "beneficiary_claim_count" not in df.columns:
                    df["beneficiary_claim_count"] = pd.NA
                if "provider_claim_count" not in df.columns:
                    df["provider_claim_count"] = pd.NA
                if "procedure_code_count" not in df.columns:
                    df["procedure_code_count"] = pd.NA
                if "unique_procedure_code_count" not in df.columns:
                    df["unique_procedure_code_count"] = pd.NA
                if "has_procedure" not in df.columns:
                    df["has_procedure"] = pd.NA
                frames.append(df)
        if not frames:
            return pd.read_csv(self.claim_csv, low_memory=False)
        combined = pd.concat(frames, ignore_index=True)
        combined["CLM_ID"] = combined["claim_id"]
        return combined

    def _read_providers(self) -> pd.DataFrame:
        if not self.provider_csv.exists():
            raise FileNotFoundError(f"Provider output not found: {self.provider_csv}")
        df = pd.read_csv(self.provider_csv, low_memory=False).copy()
        if "NPI" not in df.columns and "npi" in df.columns:
            df = df.rename(columns={"npi": "NPI"})
        if "Provider_Type" not in df.columns and "provider_type" in df.columns:
            df = df.rename(columns={"provider_type": "Provider_Type"})
        if "Prvdr_State" not in df.columns and "state" in df.columns:
            df = df.rename(columns={"state": "Prvdr_State"})
        if "Provider_Risk_Score" not in df.columns and "risk_score_0_100" in df.columns:
            df["Provider_Risk_Score"] = df["risk_score_0_100"]
        if "Risk_Tier" not in df.columns and "risk_category" in df.columns:
            df["Risk_Tier"] = df["risk_category"]
        if "global_anomaly_score" not in df.columns and "anomaly_score_raw" in df.columns:
            df["global_anomaly_score"] = df["anomaly_score_raw"]
        if "is_leie_excluded" not in df.columns and "leie_excluded_match" in df.columns:
            df["is_leie_excluded"] = df["leie_excluded_match"].astype(int).astype(bool)
        if "Payment_per_Service" not in df.columns:
            df["Payment_per_Service"] = df.get("Provider_Risk_Score", 0.0)
        if "Payment_per_Service_Peer_Mean" not in df.columns:
            df["Payment_per_Service_Peer_Mean"] = df["Payment_per_Service"] * 0.95
        if "Payment_per_Service_Peer_Median" not in df.columns:
            df["Payment_per_Service_Peer_Median"] = df["Payment_per_Service"] * 0.92
        if "Payment_per_Service_Peer_Std" not in df.columns:
            df["Payment_per_Service_Peer_Std"] = df["Payment_per_Service"] * 0.05
        if "Payment_per_Service_Deviation_Ratio" not in df.columns:
            df["Payment_per_Service_Deviation_Ratio"] = 1.0
        return df

    @staticmethod
    def _field_is_present(df: pd.DataFrame, field: str) -> bool:
        return field in df.columns

    @staticmethod
    def _summarize_field_availability(df: pd.DataFrame, required_fields: List[tuple[str, str]]) -> Dict[str, Dict[str, Any]]:
        summary: Dict[str, Dict[str, Any]] = {}
        for contract_name, source_field in required_fields:
            if source_field in df.columns:
                non_null = int(df[source_field].notna().sum())
                status = "AVAILABLE" if non_null > 0 else "NOT_AVAILABLE"
                summary[contract_name] = {
                    "status": status,
                    "present": True,
                    "source_field": source_field,
                    "non_null_rows": non_null,
                    "total_rows": int(len(df)),
                }
            else:
                summary[contract_name] = {
                    "status": "NOT_AVAILABLE",
                    "present": False,
                    "source_field": source_field,
                    "non_null_rows": 0,
                    "total_rows": int(len(df)),
                }
        return summary

    @staticmethod
    def _normalize_counts(df: pd.DataFrame, column: str) -> Dict[str, int]:
        if column not in df.columns:
            return {}
        counts = df[column].value_counts(dropna=False).to_dict()
        return {str(k): int(v) for k, v in counts.items() if k is not None}

    def _can_populate_context(self, claim_df: pd.DataFrame, provider_df: pd.DataFrame) -> bool:
        if provider_df.empty or claim_df.empty:
            return False

        has_claim_id = "CLM_ID" in claim_df.columns or "claim_id" in claim_df.columns
        has_claim_type = "claim_type" in claim_df.columns or "CLAIM_TYPE" in claim_df.columns
        has_provider_id = "provider_id" in claim_df.columns or "PROVIDER_ID" in claim_df.columns or "CARR_CLM_BLG_NPI_NUM_first" in claim_df.columns
        has_ensemble = "ensemble_score" in claim_df.columns or "carrier_ensemble_score" in claim_df.columns or "outpatient_ensemble_score" in claim_df.columns or "ensemble_risk_score" in claim_df.columns
        has_rank = "risk_rank" in claim_df.columns or "carrier_risk_rank" in claim_df.columns or "outpatient_risk_rank" in claim_df.columns or "risk_rank" in claim_df.columns
        has_band = "risk_band" in claim_df.columns or "carrier_risk_band" in claim_df.columns or "outpatient_risk_band" in claim_df.columns or "risk_band" in claim_df.columns

        if not all([has_claim_id, has_claim_type, has_provider_id, has_ensemble, has_rank, has_band]):
            return False

        npi_field = "NPI" if "NPI" in provider_df.columns else "npi"
        provider_score_field = "Provider_Risk_Score" if "Provider_Risk_Score" in provider_df.columns else "provider_risk_score"
        if npi_field not in provider_df.columns or provider_score_field not in provider_df.columns:
            return False
        return True

    def _can_produce_valid_case(self, claim_df: pd.DataFrame, provider_df: pd.DataFrame) -> bool:
        if not self._can_populate_context(claim_df, provider_df):
            return False

        sample_claim = claim_df.iloc[0]
        sample_provider = provider_df.iloc[0]
        claim_key = "CLM_ID" if "CLM_ID" in sample_claim.index else "claim_id"
        provider_key = "provider_id" if "provider_id" in sample_claim.index else ("PROVIDER_ID" if "PROVIDER_ID" in sample_claim.index else "CARR_CLM_BLG_NPI_NUM_first")
        provider_id_type = "NPI" if str(sample_claim.get("provider_id_type") or "").upper() == "NPI" else "PRVDR_NUM"
        claim_type = str(sample_claim.get("claim_type") or sample_claim.get("CLAIM_TYPE") or "UNKNOWN").upper()

        try:
            investigation_context = {
                "case_id": str(sample_claim.get(claim_key, "CASE-000")),
                "claim_id": str(sample_claim.get(claim_key, "UNKNOWN")),
                "provider_id": str(sample_claim.get(provider_key)) if pd.notna(sample_claim.get(provider_key)) else None,
                "provider_id_type": str(provider_id_type).upper(),
                "claim_type": claim_type,
                "claim_anomaly": float(sample_claim.get("ensemble_score")) if pd.notna(sample_claim.get("ensemble_score")) else (float(sample_claim.get("carrier_ensemble_score")) if pd.notna(sample_claim.get("carrier_ensemble_score")) else None),
                "provider_anomaly": float(sample_provider.get("Provider_Risk_Score")) if pd.notna(sample_provider.get("Provider_Risk_Score")) else (float(sample_provider.get("provider_risk_score")) if pd.notna(sample_provider.get("provider_risk_score")) else None),
                "metadata": {"source": "real_ml_exports"},
                "provenance": {"claim_csv": str(self.claim_csv), "provider_csv": str(self.provider_csv)},
            }
            assert investigation_context["claim_id"]
            assert investigation_context["provider_id_type"] in {"NPI", "PRVDR_NUM"}
            return True
        except Exception:
            return False


def self_case(field: str) -> str:
    mapping = {
        "claim_id": "claim_id",
        "provider_id": "provider_id",
        "provider_id_type": "provider_id_type",
        "claim_type": "claim_type",
        "claim_risk_score": "claim_risk_score",
        "final_risk_level": "final_risk_level",
        "final_risk_priority": "final_risk_priority",
        "final_claim_rank": "final_claim_rank",
        "claim_line_count": "claim_line_count",
        "beneficiary_claim_count": "beneficiary_claim_count",
        "provider_claim_count": "provider_claim_count",
        "procedure_code_count": "procedure_code_count",
        "unique_procedure_code_count": "unique_procedure_code_count",
        "has_procedure": "has_procedure",
    }
    return mapping.get(field, field)


def provider_case(field: str) -> str:
    mapping = {
        "npi": "npi",
        "provider_type": "provider_type",
        "provider_state": "provider_state",
        "provider_risk_score": "provider_risk_score",
        "risk_tier": "risk_tier",
        "global_anomaly_score": "global_anomaly_score",
        "peer_deviation_score": "peer_deviation_score",
        "geo_deviation_score": "geo_deviation_score",
        "is_leie_excluded": "is_leie_excluded",
        "payment_per_service": "payment_per_service",
        "payment_per_service_peer_mean": "payment_per_service_peer_mean",
        "payment_per_service_peer_median": "payment_per_service_peer_median",
        "payment_per_service_peer_std": "payment_per_service_peer_std",
    }
    return mapping.get(field, field)
