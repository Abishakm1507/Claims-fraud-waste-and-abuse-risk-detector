from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List, Optional

import pandas as pd

from multi_agent.schemas.claim_context import ClaimContext, EvidenceBundle

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_CLAIM_CSV = PROJECT_ROOT / "data" / "claims" / "final_unified_claim_risk.csv"


class ClaimStore:
    """Loads the authoritative claim ML output and returns typed ClaimContext objects."""

    def __init__(self, csv_path: Optional[str | Path] = None):
        csv_path = Path(csv_path) if csv_path is not None else DEFAULT_CLAIM_CSV
        if not csv_path.exists():
            raise FileNotFoundError(f"Claim output not found: {csv_path}")
        self.csv_path = csv_path
        self._df = pd.read_csv(csv_path, low_memory=False)
        self._by_claim_id: Dict[str, pd.Series] = {}
        self._by_provider: Dict[str, List[str]] = {}
        self._by_beneficiary: Dict[str, List[str]] = {}

        for _, row in self._df.iterrows():
            claim_id = self._canonicalize_claim_id(row.get("CLAIM_ID"))
            if claim_id is None:
                continue
            self._by_claim_id[claim_id] = row
            provider_id = self._coerce_text(row.get("PROVIDER_ID"))
            provider_type = self._coerce_text(row.get("PROVIDER_ID_TYPE"))
            if provider_id is not None:
                key = f"{provider_type or 'UNKNOWN'}::{provider_id}"
                self._by_provider.setdefault(key, []).append(claim_id)
            bene_id = self._coerce_text(row.get("CLAIM_ID")) or claim_id
            self._by_beneficiary.setdefault(bene_id, []).append(claim_id)

    @staticmethod
    def _canonicalize_claim_id(value):
        text = ClaimStore._coerce_text(value)
        if text is None:
            return None
        try:
            number = float(text)
        except (TypeError, ValueError):
            return text

        if number.is_integer():
            return str(int(number))
        return text

    @staticmethod
    def _coerce_text(value):
        if value is None or pd.isna(value):
            return None
        value = str(value).strip()
        return value if value else None

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

    def _build_context(self, row: pd.Series) -> ClaimContext:
        claim_id = self._coerce_text(row.get("CLAIM_ID"))
        if claim_id is None:
            return None

        claim_type = self._coerce_text(row.get("CLAIM_TYPE"))
        provider_id = self._coerce_text(row.get("PROVIDER_ID"))
        provider_id_type = self._coerce_text(row.get("PROVIDER_ID_TYPE"))
        if provider_id_type is not None:
            provider_id_type = provider_id_type.upper()
        bene_id = claim_id

        risk_score = self._to_float(row.get("CLAIM_RISK_SCORE"))
        final_level = self._coerce_text(row.get("FINAL_RISK_LEVEL"))
        final_priority = self._to_int(row.get("FINAL_RISK_PRIORITY"))
        final_rank = self._to_int(row.get("FINAL_CLAIM_RANK"))
        claim_status = self._coerce_text(row.get("CLAIM_STATUS"))

        data_availability = {
            "financial": any(
                k in row.index and pd.notna(row.get(k))
                for k in ["CLM_PMT_AMT_first", "total_claim_payment", "claim_line_payment_difference"]
            ),
            "utilization": any(
                k in row.index and pd.notna(row.get(k))
                for k in ["claim_line_count", "provider_claim_count", "beneficiary_claim_count"]
            ),
            "procedure": any(
                k in row.index and pd.notna(row.get(k))
                for k in ["procedure_code_count", "unique_procedure_code_count", "has_procedure"]
            ),
            "temporal": any(
                k in row.index and pd.notna(row.get(k))
                for k in ["claim_from_dt", "claim_thru_dt", "claim_year", "claim_duration_days"]
            ),
            "peer": any(
                k in row.index and pd.notna(row.get(k))
                for k in ["provider_avg_claim_payment", "provider_total_payment", "provider_payment_std"]
            ),
            "rule": any(
                k in row.index and pd.notna(row.get(k))
                for k in ["final_risk_level", "final_risk_priority"]
            ),
            "model": any(
                k in row.index and pd.notna(row.get(k))
                for k in ["MODEL_SCORE", "CLAIM_RISK_SCORE", "isolation_forest_score", "outpatient_ensemble_score"]
            ),
        }

        financial = None
        if data_availability["financial"]:
            financial = EvidenceBundle(
                available=True,
                values={
                    "claim_payment": self._to_float(row.get("CLM_PMT_AMT_first")),
                    "total_claim_payment": self._to_float(row.get("total_claim_payment")),
                    "payment_to_charge_ratio": self._to_float(row.get("payment_to_charge_ratio")),
                },
            )

        utilization = None
        if data_availability["utilization"]:
            utilization = EvidenceBundle(
                available=True,
                values={
                    "claim_line_count": self._to_int(row.get("claim_line_count")),
                    "beneficiary_claim_count": self._to_int(row.get("beneficiary_claim_count")),
                    "provider_claim_count": self._to_int(row.get("provider_claim_count")),
                },
            )

        procedure = None
        if data_availability["procedure"]:
            procedure = EvidenceBundle(
                available=True,
                values={
                    "procedure_code_count": self._to_int(row.get("procedure_code_count")),
                    "unique_procedure_code_count": self._to_int(row.get("unique_procedure_code_count")),
                    "has_procedure": row.get("has_procedure"),
                },
            )

        temporal = None
        if data_availability["temporal"]:
            temporal = EvidenceBundle(
                available=True,
                values={
                    "claim_from_dt": row.get("claim_from_dt"),
                    "claim_thru_dt": row.get("claim_thru_dt"),
                    "claim_duration_days": self._to_int(row.get("claim_duration_days")),
                    "claim_year": self._to_int(row.get("claim_year")),
                },
            )

        peer = None
        if data_availability["peer"]:
            peer = EvidenceBundle(
                available=True,
                values={
                    "provider_average_claim_payment": self._to_float(row.get("provider_avg_claim_payment")),
                    "provider_total_payment": self._to_float(row.get("provider_total_payment")),
                    "provider_payment_std": self._to_float(row.get("provider_payment_std")),
                },
            )

        rule = None
        if data_availability["rule"]:
            rule = EvidenceBundle(
                available=True,
                values={
                    "final_risk_level": final_level,
                    "final_risk_priority": final_priority,
                    "final_claim_rank": final_rank,
                },
            )

        model = None
        if data_availability["model"]:
            model = EvidenceBundle(
                available=True,
                values={
                    "model_score": self._to_float(row.get("MODEL_SCORE")),
                    "claim_risk_score": risk_score,
                    "risk_rank": self._to_int(row.get("CLAIM_RISK_RANK")),
                    "risk_band": self._coerce_text(row.get("risk_band")),
                },
            )

        return ClaimContext(
            claim_id=claim_id,
            claim_type=claim_type,
            provider_id=provider_id,
            provider_id_type=provider_id_type,
            bene_id=bene_id,
            claim_risk_score=risk_score,
            final_risk_level=final_level,
            final_risk_priority=final_priority,
            final_claim_rank=final_rank,
            claim_status=claim_status,
            financial_evidence=financial,
            utilization_evidence=utilization,
            procedure_evidence=procedure,
            temporal_evidence=temporal,
            peer_evidence=peer,
            rule_evidence=rule,
            model_evidence=model,
            data_availability=data_availability,
        )

    def get_claim(self, claim_id: str) -> Optional[ClaimContext]:
        key = self._canonicalize_claim_id(claim_id)
        if key is None:
            return None
        row = self._by_claim_id.get(key)
        if row is None:
            return None
        return self._build_context(row)

    def get_claims_by_provider(self, provider_id: str, provider_id_type: Optional[str] = None) -> List[ClaimContext]:
        provider_key = self._coerce_text(provider_id)
        if provider_key is None:
            return []
        normalized_type = self._coerce_text(provider_id_type)
        if normalized_type is not None:
            normalized_type = normalized_type.upper()
        if normalized_type is None:
            matches = []
            for key, claim_ids in self._by_provider.items():
                if key.endswith(f"::{provider_key}"):
                    matches.extend(claim_ids)
            unique = []
            seen = set()
            for claim_id in matches:
                if claim_id not in seen:
                    unique.append(claim_id)
                    seen.add(claim_id)
            return [self.get_claim(claim_id) for claim_id in unique if self.get_claim(claim_id) is not None]

        key = f"{normalized_type}::{provider_key}"
        claim_ids = self._by_provider.get(key, [])
        return [self.get_claim(claim_id) for claim_id in claim_ids if self.get_claim(claim_id) is not None]

    def get_claims_by_beneficiary(self, bene_id: str) -> List[ClaimContext]:
        key = self._coerce_text(bene_id)
        if key is None:
            return []
        claim_ids = self._by_beneficiary.get(key, [])
        return [self.get_claim(claim_id) for claim_id in claim_ids if self.get_claim(claim_id) is not None]

    def exists(self, claim_id: str) -> bool:
        return self.get_claim(claim_id) is not None

    def __len__(self):
        return len(self._by_claim_id)
