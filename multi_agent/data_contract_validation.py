from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from multi_agent.models.schemas import CONTRACT_VERSION, InvestigationCase, InvestigationContext

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CLAIM_CSV = PROJECT_ROOT / "data" / "claims" / "final_unified_claim_risk.csv"
PROVIDER_CSV = PROJECT_ROOT / "models" / "provider" / "output" / "provider_risk_scores.csv"


class DataContractValidator:
    """Validate the real upstream ML CSVs against the Investigation Contract v1."""

    CLAIM_REQUIRED_FIELDS = [
        ("claim_id", "CLAIM_ID"),
        ("provider_id", "PROVIDER_ID"),
        ("provider_id_type", "PROVIDER_ID_TYPE"),
        ("claim_type", "CLAIM_TYPE"),
        ("claim_risk_score", "CLAIM_RISK_SCORE"),
        ("final_risk_level", "FINAL_RISK_LEVEL"),
        ("final_risk_priority", "FINAL_RISK_PRIORITY"),
        ("final_claim_rank", "FINAL_CLAIM_RANK"),
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

        claim_type_counts = self._normalize_counts(claim_df, "CLAIM_TYPE")
        limitations: List[str] = []

        required_fields = {
            "claim": self._summarize_field_availability(claim_df, self.CLAIM_REQUIRED_FIELDS),
            "provider": self._summarize_field_availability(provider_df, self.PROVIDER_REQUIRED_FIELDS),
        }

        if not self._field_is_present(claim_df, "CLAIM_ID"):
            limitations.append("Claim export is missing the canonical CLAIM_ID field required by the contract.")
        if not self._field_is_present(claim_df, "PROVIDER_ID_TYPE"):
            limitations.append("Claim export does not include provider_id_type metadata; contract will default to UNKNOWN.")
        if not self._field_is_present(claim_df, "CLAIM_TYPE"):
            limitations.append("Claim export is missing CLAIM_TYPE and cannot reliably classify agent routing.")
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
        return pd.read_csv(self.claim_csv, low_memory=False)

    def _read_providers(self) -> pd.DataFrame:
        if not self.provider_csv.exists():
            raise FileNotFoundError(f"Provider output not found: {self.provider_csv}")
        return pd.read_csv(self.provider_csv, low_memory=False)

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
        required = [
            "CLAIM_ID",
            "PROVIDER_ID",
            "PROVIDER_ID_TYPE",
            "CLAIM_TYPE",
            "CLAIM_RISK_SCORE",
        ]
        if not all(field in claim_df.columns for field in required):
            return False
        if provider_df.empty or claim_df.empty:
            return False
        if "NPI" not in provider_df.columns or "Provider_Risk_Score" not in provider_df.columns:
            return False
        if not claim_df["CLAIM_TYPE"].dropna().isin({"CARRIER", "INPATIENT", "OUTPATIENT"}).all():
            return False
        return True

    def _can_produce_valid_case(self, claim_df: pd.DataFrame, provider_df: pd.DataFrame) -> bool:
        if not self._can_populate_context(claim_df, provider_df):
            return False

        sample_claim = claim_df.iloc[0]
        sample_provider = provider_df.iloc[0]
        case_id = str(sample_claim.get("CLAIM_ID", "CASE-000"))
        provider_id = sample_claim.get("PROVIDER_ID")
        provider_id_type = sample_claim.get("PROVIDER_ID_TYPE") or "UNKNOWN"
        claim_type = sample_claim.get("CLAIM_TYPE")

        try:
            investigation_context = InvestigationContext(
                case_id=case_id,
                claim_id=str(sample_claim.get("CLAIM_ID", "UNKNOWN")),
                provider_id=str(provider_id) if provider_id is not None else None,
                provider_id_type=str(provider_id_type).upper(),
                claim_type=str(claim_type) if claim_type is not None else None,
                claim_anomaly=float(sample_claim.get("CLAIM_RISK_SCORE")) if pd.notna(sample_claim.get("CLAIM_RISK_SCORE")) else None,
                provider_anomaly=float(sample_provider.get("Provider_Risk_Score")) if pd.notna(sample_provider.get("Provider_Risk_Score")) else None,
                claim_features={},
                provider_features={},
                peer_features={},
                leie_evidence={},
                data_availability={},
                metadata={"source": "real_ml_exports"},
                provenance={"claim_csv": str(self.claim_csv), "provider_csv": str(self.provider_csv)},
            )
            InvestigationCase(
                case_id=case_id,
                claim_id=str(sample_claim.get("CLAIM_ID", "UNKNOWN")),
                provider_id=str(provider_id) if provider_id is not None else None,
                provider_id_type=str(provider_id_type).upper(),
                claim_type=str(claim_type) if claim_type is not None else None,
                investigation_context=investigation_context,
                findings=[],
                evidence=[],
                agent_results=[],
                agent_executions=[],
                provenance={"source": "real_ml_exports"},
            )
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
