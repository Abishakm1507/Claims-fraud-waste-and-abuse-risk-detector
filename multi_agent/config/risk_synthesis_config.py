"""
MILESTONE 13: Risk Synthesis Configuration (FROZEN)

This module defines the AUTHORITATIVE, DETERMINISTIC risk synthesis formula
and all associated configuration values. These values are locked for M13 and
any changes require explicit versioning and documentation.

CRITICAL: Do not modify these values without:
1. Incrementing SYNTHESIS_VERSION
2. Creating a new frozen configuration
3. Documenting the change
4. Updating all tests
5. Notifying the RAG/Explainability team
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Literal, Optional


# ============================================================================
# SYNTHESIS VERSION
# ============================================================================
# Increment this whenever weights, thresholds, or priority mapping changes.
SYNTHESIS_VERSION = "1.0.0"

# Increment this when the algorithm or formula fundamentally changes.
SYNTHESIS_ALGORITHM_VERSION = "1.0.0"


# ============================================================================
# COMPONENT SCALES
# ============================================================================
# All input scores are expected on this scale.
# This is CRITICAL for preventing accidental mixing of scales.
COMPONENT_SCALE_MIN = 0.0
COMPONENT_SCALE_MAX = 100.0

# Allowed components in synthesis
ALLOWED_COMPONENTS = {
    "claim_anomaly",
    "provider_anomaly",
    "peer_score",
    "billing_score",
    "rule_score",
}


# ============================================================================
# SYNTHESIS WEIGHTS (FROZEN)
# ============================================================================
# These weights define how each component contributes to final risk.
# Sum of weights should equal 100 (i.e., 1.0 as fraction).
#
# Current allocation:
#  - Claim anomaly (upstream ML):     30% (0.30)
#  - Provider anomaly (upstream ML):  30% (0.30)
#  - Peer benchmark score:             20% (0.20)
#  - Billing analysis score:           10% (0.10)
#  - Rule-based score:                 10% (0.10)
#
# Total: 100%
#
SYNTHESIS_WEIGHTS: Dict[str, float] = {
    "claim_anomaly": 0.30,
    "provider_anomaly": 0.30,
    "peer_score": 0.20,
    "billing_score": 0.10,
    "rule_score": 0.10,
}

# Verify weights sum to 1.0 (within floating-point tolerance)
_weight_sum = sum(SYNTHESIS_WEIGHTS.values())
assert 0.99 <= _weight_sum <= 1.01, f"Weights must sum to 1.0, got {_weight_sum}"


# ============================================================================
# RISK THRESHOLDS (FROZEN)
# ============================================================================
# These thresholds map raw risk scores to risk categories.
# Boundaries are explicitly handled as INCLUSIVE lower bound.
#
# Examples:
#  - Score 39.9 → LOW (< 40)
#  - Score 40.0 → MEDIUM (>= 40 and < 70)
#  - Score 69.9 → MEDIUM (< 70)
#  - Score 70.0 → HIGH (>= 70 and < 85)
#  - Score 84.9 → HIGH (< 85)
#  - Score 85.0 → CRITICAL (>= 85)
#
RISK_THRESHOLDS: Dict[str, float] = {
    "LOW": 0.0,           # 0 <= score < 40
    "MEDIUM": 40.0,       # 40 <= score < 70
    "HIGH": 70.0,         # 70 <= score < 85
    "CRITICAL": 85.0,     # 85 <= score <= 100
}

# Valid risk categories (in order)
RISK_CATEGORIES: List[str] = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

# Threshold validation: ensure in order
_prev = -1.0
for category in RISK_CATEGORIES:
    threshold = RISK_THRESHOLDS[category]
    assert threshold >= _prev, f"Thresholds must be in increasing order, {category}={threshold} but previous={_prev}"
    _prev = threshold


# ============================================================================
# PRIORITY MAPPING (FROZEN)
# ============================================================================
# These map risk categories to investigation priority.
# P0 = highest priority (investigate immediately)
# P3 = lowest priority (informational)
#
PRIORITY_BY_CATEGORY: Dict[str, str] = {
    "CRITICAL": "P0",
    "HIGH": "P1",
    "MEDIUM": "P2",
    "LOW": "P3",
}

# Reverse mapping (for validation)
CATEGORY_BY_PRIORITY: Dict[str, str] = {v: k for k, v in PRIORITY_BY_CATEGORY.items()}


# ============================================================================
# ROUNDING BEHAVIOR (FROZEN)
# ============================================================================
# How to round the final risk score for display.
#
# INTERNAL_PRECISION: 4 decimal places
# DISPLAY_PRECISION: 1 decimal place (or integer, see ROUND_TO_INTEGER)
#
INTERNAL_PRECISION = 4  # Calculations done with this precision
DISPLAY_PRECISION = 1   # Display scores with this precision
ROUND_TO_INTEGER = True  # If True, round to nearest integer for display (88.13 → 88)


# ============================================================================
# MISSING AGENT BEHAVIOR (FROZEN)
# ============================================================================
# When an agent is not executed (skipped), how should we handle it?
#
# Strategy: REWEIGHT_AVAILABLE_COMPONENTS
#   If only some agents ran, reweight the available ones.
#   E.g., if only provider_anomaly and peer_score are available,
#   recalculate weights to sum to 1.0 using only those components.
#
# Alternative strategies (not currently used):
#   USE_ZERO: Treat missing as score=0
#   USE_BASELINE: Treat missing as score=50 (neutral)
#   MARK_INCOMPLETE: Return error/incomplete status
#
MISSING_AGENT_STRATEGY: Literal["REWEIGHT_AVAILABLE_COMPONENTS", "USE_ZERO", "USE_BASELINE", "MARK_INCOMPLETE"] = "REWEIGHT_AVAILABLE_COMPONENTS"

# Description for documentation
MISSING_AGENT_STRATEGY_DESCRIPTION = (
    "If an agent is not executed (e.g., peer agent skipped), "
    "reweight available components so they sum to 1.0. "
    "This prevents artificially lowering the score due to missing data."
)


# ============================================================================
# INVALID SCORE BEHAVIOR (FROZEN)
# ============================================================================
# When a component score is invalid (NaN, <0, >100, etc.), how should we handle it?
#
# Strategy: REJECT_INVALID
#   Raise an error if any component score is invalid.
#   This forces explicit handling of data quality issues.
#
# Alternative (not used):
#   CLAMP: Clamp invalid scores to [0, 100]
#   SKIP_COMPONENT: Treat invalid component as missing and reweight
#
INVALID_SCORE_STRATEGY: Literal["REJECT_INVALID", "CLAMP", "SKIP_COMPONENT"] = "REJECT_INVALID"

INVALID_SCORE_STRATEGY_DESCRIPTION = (
    "Reject any component score outside [0, 100] or non-numeric. "
    "This ensures data quality and prevents silent data corruption."
)


# ============================================================================
# SYNTHESIS METHOD (FROZEN)
# ============================================================================
# The deterministic formula used to calculate final risk.
#
# METHOD: weighted_sum
#   final_score = sum(component_score * component_weight)
#   This is transparent, auditable, and reproducible.
#
SYNTHESIS_METHOD = "weighted_sum"

SYNTHESIS_FORMULA_DESCRIPTION = (
    "final_risk_score = sum(component_score * component_weight "
    "for component in available_components) "
    "normalized to [0, 100]"
)


# ============================================================================
# CONFIGURATION STATE
# ============================================================================
# Snapshot of all configuration values for provenance/audit purposes.
#
def get_configuration_dict() -> Dict[str, Any]:
    """Return current configuration as a dictionary (for provenance recording)."""
    return {
        "version": SYNTHESIS_VERSION,
        "algorithm_version": SYNTHESIS_ALGORITHM_VERSION,
        "method": SYNTHESIS_METHOD,
        "weights": SYNTHESIS_WEIGHTS.copy(),
        "thresholds": RISK_THRESHOLDS.copy(),
        "priority_mapping": PRIORITY_BY_CATEGORY.copy(),
        "rounding": {
            "internal_precision": INTERNAL_PRECISION,
            "display_precision": DISPLAY_PRECISION,
            "round_to_integer": ROUND_TO_INTEGER,
        },
        "missing_agent_strategy": MISSING_AGENT_STRATEGY,
        "invalid_score_strategy": INVALID_SCORE_STRATEGY,
    }


# ============================================================================
# CONFIGURATION VALIDATION
# ============================================================================
# Ensure configuration is internally consistent.
#

def validate_configuration() -> List[str]:
    """Validate configuration and return list of errors (empty if valid)."""
    errors = []
    
    # Weight validation
    weight_sum = sum(SYNTHESIS_WEIGHTS.values())
    if not (0.99 <= weight_sum <= 1.01):
        errors.append(f"Weights must sum to 1.0, got {weight_sum}")
    
    # Threshold validation
    if len(RISK_THRESHOLDS) != len(RISK_CATEGORIES):
        errors.append(f"Threshold count {len(RISK_THRESHOLDS)} != category count {len(RISK_CATEGORIES)}")
    
    for category in RISK_CATEGORIES:
        if category not in RISK_THRESHOLDS:
            errors.append(f"Missing threshold for category {category}")
    
    for category in RISK_THRESHOLDS:
        if category not in RISK_CATEGORIES:
            errors.append(f"Threshold for unknown category {category}")
    
    # Priority mapping validation
    if set(PRIORITY_BY_CATEGORY.keys()) != set(RISK_CATEGORIES):
        errors.append(f"Priority mapping keys don't match risk categories")
    
    # Component weight validation
    for component in SYNTHESIS_WEIGHTS:
        if component not in ALLOWED_COMPONENTS:
            errors.append(f"Weight for unknown component {component}")
    
    return errors


# Validate on import
_config_errors = validate_configuration()
if _config_errors:
    raise RuntimeError(f"Configuration validation failed: {_config_errors}")
