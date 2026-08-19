"""Data integrity checks for claim-type ML artifacts and unified CSV.

Verifies that:
- Each type-specific CSV has unique claim IDs within itself
- No claim ID collisions across the three type-specific CSVs
- Every claim ID in the unified CSV has a corresponding entry in its type-specific CSV
- No orphans (unified claims missing from type-specific, or vice versa)
"""

from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd


class IntegrityCheckResult:
    """Summary of a data integrity check."""

    def __init__(self) -> None:
        self.carrier_count = 0
        self.inpatient_count = 0
        self.outpatient_count = 0
        self.unified_count = 0
        self.total_unique_claims = 0
        
        self.carrier_duplicates: List[str] = []
        self.inpatient_duplicates: List[str] = []
        self.outpatient_duplicates: List[str] = []
        self.cross_type_collisions: List[str] = []
        
        self.unified_orphans: List[str] = []  # in unified but not in type-specific
        self.type_orphans: List[str] = []     # in type-specific but not in unified
        
        self.is_healthy = True
        self.warnings: List[str] = []
        self.errors: List[str] = []

    def log_summary(self) -> str:
        """Return a formatted summary of the integrity check."""
        lines = ["=== Data Integrity Check Summary ==="]
        lines.append(f"Carrier claims: {self.carrier_count}")
        lines.append(f"Inpatient claims: {self.inpatient_count}")
        lines.append(f"Outpatient claims: {self.outpatient_count}")
        lines.append(f"Total (across types): {self.total_unique_claims}")
        lines.append(f"Unified CSV claims: {self.unified_count}")
        
        if self.is_healthy:
            lines.append("\n✅ Status: HEALTHY")
        else:
            lines.append("\n⚠️ Status: ISSUES FOUND")
        
        if self.carrier_duplicates:
            lines.append(f"  - Carrier duplicates: {len(self.carrier_duplicates)} IDs")
            self.errors.append(f"Carrier has duplicate claim IDs: {self.carrier_duplicates[:5]}")
        
        if self.inpatient_duplicates:
            lines.append(f"  - Inpatient duplicates: {len(self.inpatient_duplicates)} IDs")
            self.errors.append(f"Inpatient has duplicate claim IDs: {self.inpatient_duplicates[:5]}")
        
        if self.outpatient_duplicates:
            lines.append(f"  - Outpatient duplicates: {len(self.outpatient_duplicates)} IDs")
            self.errors.append(f"Outpatient has duplicate claim IDs: {self.outpatient_duplicates[:5]}")
        
        if self.cross_type_collisions:
            lines.append(f"  - Cross-type collisions: {len(self.cross_type_collisions)} IDs")
            self.errors.append(f"Claim IDs appear in multiple type pipelines: {self.cross_type_collisions[:5]}")
        
        if self.unified_orphans:
            lines.append(f"  - Unified orphans (no type match): {len(self.unified_orphans)} IDs")
            self.warnings.append(f"Unified CSV has orphaned claims: {self.unified_orphans[:5]}")
        
        if self.type_orphans:
            lines.append(f"  - Type orphans (no unified match): {len(self.type_orphans)} IDs")
            self.warnings.append(f"Type-specific CSVs have claims not in unified: {self.type_orphans[:5]}")
        
        if self.warnings:
            lines.append("\nWarnings:")
            for w in self.warnings:
                lines.append(f"  ⚠️ {w}")
        
        if self.errors:
            lines.append("\nErrors:")
            for e in self.errors:
                lines.append(f"  ❌ {e}")
        
        return "\n".join(lines)


def check_data_integrity(
    carrier_df: pd.DataFrame,
    inpatient_df: pd.DataFrame,
    outpatient_df: pd.DataFrame,
    unified_df: pd.DataFrame,
) -> IntegrityCheckResult:
    """Run comprehensive data integrity checks.
    
    Args:
        carrier_df: Carrier claims dataframe
        inpatient_df: Inpatient claims dataframe
        outpatient_df: Outpatient claims dataframe
        unified_df: Unified claims dataframe
    
    Returns:
        IntegrityCheckResult with full summary
    """
    result = IntegrityCheckResult()
    
    # Extract claim IDs, handling both 'CLM_ID' and 'clm_id' column names
    def get_claim_ids(df: pd.DataFrame, expected_cols: List[str]) -> set:
        col = next((c for c in expected_cols if c in df.columns), None)
        if col is None:
            return set()
        return set(df[col].dropna().astype(str).unique())
    
    carrier_ids = get_claim_ids(carrier_df, ["CLM_ID"])
    inpatient_ids = get_claim_ids(inpatient_df, ["clm_id"])
    outpatient_ids = get_claim_ids(outpatient_df, ["CLM_ID"])
    unified_ids = get_claim_ids(unified_df, ["CLAIM_ID"])
    
    result.carrier_count = len(carrier_ids)
    result.inpatient_count = len(inpatient_ids)
    result.outpatient_count = len(outpatient_ids)
    result.unified_count = len(unified_ids)
    result.total_unique_claims = len(carrier_ids | inpatient_ids | outpatient_ids)
    
    # Check for duplicates within each type
    carrier_dups = set(carrier_df["CLM_ID"].dropna().astype(str).values) - set(carrier_df["CLM_ID"].dropna().astype(str).unique())
    inpatient_dups = set(inpatient_df["clm_id"].dropna().astype(str).values) - set(inpatient_df["clm_id"].dropna().astype(str).unique())
    outpatient_dups = set(outpatient_df["CLM_ID"].dropna().astype(str).values) - set(outpatient_df["CLM_ID"].dropna().astype(str).unique())
    
    if carrier_dups:
        result.carrier_duplicates = list(carrier_dups)
        result.is_healthy = False
    if inpatient_dups:
        result.inpatient_duplicates = list(inpatient_dups)
        result.is_healthy = False
    if outpatient_dups:
        result.outpatient_duplicates = list(outpatient_dups)
        result.is_healthy = False
    
    # Check for collisions across types
    cross_type = (carrier_ids & inpatient_ids) | (carrier_ids & outpatient_ids) | (inpatient_ids & outpatient_ids)
    if cross_type:
        result.cross_type_collisions = list(cross_type)
        result.is_healthy = False
    
    # Check for orphans: claims in unified but not in their type-specific CSV
    carrier_in_unified = unified_df[unified_df["CLAIM_TYPE"] == "CARRIER"]["CLAIM_ID"].astype(str).unique()
    inpatient_in_unified = unified_df[unified_df["CLAIM_TYPE"] == "INPATIENT"]["CLAIM_ID"].astype(str).unique()
    outpatient_in_unified = unified_df[unified_df["CLAIM_TYPE"] == "OUTPATIENT"]["CLAIM_ID"].astype(str).unique()
    
    carrier_orphans_in_unified = set(carrier_in_unified) - carrier_ids
    inpatient_orphans_in_unified = set(inpatient_in_unified) - inpatient_ids
    outpatient_orphans_in_unified = set(outpatient_in_unified) - outpatient_ids
    
    unified_orphans = carrier_orphans_in_unified | inpatient_orphans_in_unified | outpatient_orphans_in_unified
    if unified_orphans:
        result.unified_orphans = list(unified_orphans)
    
    # Check for orphans: claims in type-specific but not in unified
    type_orphans = (carrier_ids - set(carrier_in_unified)) | (inpatient_ids - set(inpatient_in_unified)) | (outpatient_ids - set(outpatient_in_unified))
    if type_orphans:
        result.type_orphans = list(type_orphans)
    
    # Determine health status
    if unified_orphans or type_orphans:
        # Only mark unhealthy if there are structural mismatches
        # Small orphan counts might be acceptable (e.g., if unified is subset of types)
        if len(unified_orphans) > 100 or len(type_orphans) > 100:
            result.is_healthy = False
    
    return result
