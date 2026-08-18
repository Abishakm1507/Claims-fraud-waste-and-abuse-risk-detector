from __future__ import annotations

import re
from typing import Any, Iterable, Mapping

CLAIM_FEATURE_ALIASES = {
    "CLM_PMT_AMT_first": "Claim Payment Amount",
    "NCH_CARR_CLM_SBMTD_CHRG_AMT_first": "Submitted Charge Amount",
    "NCH_CARR_CLM_ALOWD_AMT_first": "Allowed Amount",
    "payment_to_charge_ratio": "Payment-to-Charge Ratio",
    "claim_line_count": "Claim Line Count",
    "unique_revenue_center_count": "Unique Revenue Center Count",
    "claim_duration_days": "Claim Duration Days",
    "procedure_code_count": "Procedure Code Count",
    "unique_procedure_code_count": "Unique Procedure Code Count",
    "beneficiary_claim_count": "Beneficiary Claim Count",
    "provider_claim_count": "Provider Claim Count",
    "provider_avg_claim_payment": "Provider Average Claim Payment",
    "provider_total_payment": "Provider Total Payment",
    "provider_payment_std": "Provider Payment Standard Deviation",
}

PROVIDER_FEATURE_ALIASES = {
    "Log_Tot_Benes": "Total Beneficiaries",
    "Log_Tot_Srvcs": "Total Services",
    "Log_Tot_HCPCS_Cds": "Unique HCPCS Codes",
    "Log_Tot_Sbmtd_Chrg": "Submitted Charges",
    "Log_Tot_Mdcr_Pymt_Amt": "Medicare Payments",
    "Log_Drug_Tot_Srvcs": "Drug Services",
    "Log_Drug_Sbmtd_Chrg": "Drug Submitted Charges",
    "Payment_to_Charge_Ratio": "Payment-to-Charge Ratio",
    "Allowed_to_Charge_Ratio": "Allowed-to-Charge Ratio",
    "Standardized_to_Payment_Ratio": "Standardized-to-Payment Ratio",
    "Services_per_Beneficiary": "Services per Beneficiary",
    "HCPCS_per_Beneficiary": "HCPCS Codes per Beneficiary",
    "Payment_per_Service": "Payment per Service",
    "Charge_per_Service": "Charge per Service",
    "Drug_Service_Share": "Drug Service Share",
    "Drug_Payment_Share": "Drug Payment Share",
    "Medical_Payment_Share": "Medical Payment Share",
    "Bene_Avg_Risk_Scre": "Average Beneficiary Risk Score",
    "Dual_Eligible_Ratio": "Dual Eligible Ratio",
    "Overall_Condition_Risk": "Overall Condition Risk",
    "Svc_N_Unique_HCPCS": "Unique HCPCS Services",
    "Svc_Top_Service_Share": "Top Service Share",
    "Svc_HCPCS_Concentration_HHI": "HCPCS Concentration HHI",
    "Svc_Drug_Service_Share": "Service Drug Share",
    "Svc_Avg_Payment_to_Charge_Ratio": "Average Payment-to-Charge Ratio",
    "Svc_Min_Payment_to_Charge_Ratio": "Min Payment-to-Charge Ratio",
    "Svc_Max_Beneficiary_Service_Ratio": "Max Beneficiary Service Ratio",
    "Svc_Services_per_HCPCS": "Services per HCPCS",
    "Svc_Std_Charge_Per_Service": "Std Charge per Service",
    "Peer_Mean_Log_Dev_Charge": "Peer Mean Log Charge Deviation",
    "Peer_Max_Log_Dev_Charge": "Peer Max Log Charge Deviation",
    "Peer_Mean_Log_Dev_Payment": "Peer Mean Log Payment Deviation",
    "Peer_Pct_Services_3x_Peer_Charge": "Peer Services >3x Charge Benchmark",
}


def humanize_feature(name: Any) -> str:
    raw = str(name or "").strip()
    if not raw:
        return "Unknown Feature"
    alias = CLAIM_FEATURE_ALIASES.get(raw) or PROVIDER_FEATURE_ALIASES.get(raw)
    if alias:
        return alias
    raw = raw.replace("_missing", " (Missing)")
    raw = raw.replace("_", " ")
    raw = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", raw)
    return raw.strip().title() if raw else "Unknown Feature"


def normalize_feature_vector(feature_vector: Any, expected_names: Iterable[str] | None = None) -> dict[str, float]:
    if feature_vector is None:
        raise ValueError("Feature vector is required.")

    if hasattr(feature_vector, "to_dict"):
        feature_vector = feature_vector.to_dict()

    if isinstance(feature_vector, Mapping):
        candidate = feature_vector
        if expected_names is not None:
            expected_set = {str(name) for name in expected_names}
            candidate = {str(k): v for k, v in feature_vector.items() if str(k) in expected_set}
        normalized = {}
        for k, v in candidate.items():
            if v is None or (isinstance(v, str) and not v.strip()):
                continue
            try:
                numeric = float(v)
            except (TypeError, ValueError):
                continue
            if not (numeric == numeric and abs(numeric) != float('inf')):
                numeric = 0.0
            normalized[str(k)] = numeric
    elif isinstance(feature_vector, (list, tuple)):
        if expected_names is None:
            raise ValueError("A sequence feature vector requires expected feature names in the same order.")
        expected = list(expected_names)
        if len(feature_vector) != len(expected):
            raise ValueError(f"Expected {len(expected)} values but received {len(feature_vector)}.")
        normalized = {str(expected[i]): float(value) for i, value in enumerate(feature_vector)}
    else:
        raise TypeError("Unsupported feature-vector type; pass a mapping or list/ndarray aligned to the model features.")

    if expected_names is not None:
        expected_list = [str(name) for name in expected_names]
        sanitized = {}
        for name in expected_list:
            value = normalized.get(name, 0.0)
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                numeric = 0.0
            if not (numeric == numeric and abs(numeric) != float('inf')):
                numeric = 0.0
            sanitized[name] = float(numeric)
        return sanitized
    return normalized
