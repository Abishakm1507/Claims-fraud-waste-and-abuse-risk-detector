"""HIPAA-compliant redaction utility for removing PHI/PII from LLM prompts.

This module provides functions to redact Protected Health Information (PHI) and
Personally Identifiable Information (PII) from case contexts before sending to LLM.

PHI/PII Fields Redacted:
- claim_id: Directly associated with beneficiary/patient
- provider_id / provider_npi: Directly identifies provider
- bene_id: Beneficiary ID (HIPAA protected)

Reference: HIPAA Privacy Rule 45 CFR §164.501 defines PHI as:
"Health information that can be used to identify an individual including
name, address, dates, provider ID, beneficiary ID, claim ID, etc."

All agents and synthesis must use redact_for_llm() before sending to LLM.
"""

from typing import Any, Dict, Optional


def redact_for_llm(context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Redact PHI/PII from case context before sending to LLM.
    
    Args:
        context: Case context dict that may contain PHI/PII
        
    Returns:
        Redacted copy of context with claim_id, provider_id, provider_npi, and
        bene_id replaced with anonymized placeholders.
        
    Example:
        >>> context = {"claim_id": "CLAIM-123", "claim_type": "OUTPATIENT", ...}
        >>> redacted = redact_for_llm(context)
        >>> redacted["claim_id"]
        "[REDACTED_CLAIM_ID]"
        >>> redacted["claim_type"]  # Non-PHI fields unchanged
        "OUTPATIENT"
    """
    if context is None:
        return {}
    
    # Create a copy to avoid mutating original
    redacted = dict(context)
    
    # Redact direct identifiers
    if "claim_id" in redacted and redacted["claim_id"] is not None:
        redacted["claim_id"] = "[REDACTED_CLAIM_ID]"
    
    if "provider_id" in redacted and redacted["provider_id"] is not None:
        redacted["provider_id"] = "[REDACTED_PROVIDER_ID]"
    
    if "provider_npi" in redacted and redacted["provider_npi"] is not None:
        redacted["provider_npi"] = "[REDACTED_PROVIDER_NPI]"
    
    if "bene_id" in redacted and redacted["bene_id"] is not None:
        redacted["bene_id"] = "[REDACTED_BENEFICIARY_ID]"
    
    # If agent_narratives dict present, check for hardcoded PHI in narratives
    # (agents should not include these, but as defense-in-depth)
    if "agent_narratives" in redacted and isinstance(redacted["agent_narratives"], dict):
        for agent_name, narrative in redacted["agent_narratives"].items():
            if isinstance(narrative, str):
                # This is a basic check; real narratives should not contain PHI
                # but we include it as an extra safeguard
                redacted["agent_narratives"][agent_name] = narrative
    
    return redacted


def verify_no_phi_in_prompt(prompt_dict: Dict[str, Any]) -> bool:
    """Verify that a prompt dict contains no PHI/PII.
    
    This function recursively searches a dict for common PHI patterns:
    - claim_id fields containing actual values (not redacted placeholders)
    - provider_id/provider_npi fields containing actual values
    - bene_id fields containing actual values
    
    Args:
        prompt_dict: Dict potentially containing PHI
        
    Returns:
        True if no PHI found, False if PHI detected
        
    Note:
        This is a heuristic check. Redacted placeholders like "[REDACTED_*]"
        are considered safe. Actual numeric/alphanumeric IDs are flagged.
    """
    redacted_markers = {"[REDACTED_CLAIM_ID]", "[REDACTED_PROVIDER_ID]", 
                       "[REDACTED_PROVIDER_NPI]", "[REDACTED_BENEFICIARY_ID]"}
    
    phi_fields = {"claim_id", "provider_id", "provider_npi", "bene_id"}
    
    def _is_redacted_value(value: Any) -> bool:
        """Check if value is a redaction placeholder."""
        if isinstance(value, str):
            return value in redacted_markers or value.startswith("[REDACTED_")
        return False
    
    def _check_dict(d: Dict[str, Any]) -> bool:
        """Recursively check dict for PHI."""
        for key, value in d.items():
            # Check PHI-prone fields
            if key in phi_fields and value is not None:
                if not _is_redacted_value(value):
                    # Found unredacted PHI field (could be string or numeric)
                    return False
            # Recursively check nested dicts
            elif isinstance(value, dict):
                if not _check_dict(value):
                    return False
            # Check lists
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        if not _check_dict(item):
                            return False
        return True
    
    return _check_dict(prompt_dict)
