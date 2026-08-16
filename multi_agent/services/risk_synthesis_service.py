"""
MILESTONE 13: Deterministic Risk Synthesis Service

This service implements the AUTHORITATIVE, DETERMINISTIC risk synthesis formula.
It is the single source of truth for calculating the final risk score from agent inputs.

Core Properties:
- Pure deterministic function (same inputs → same output)
- Mathematically transparent and reproducible
- Handles all edge cases explicitly
- Never calls Groq or any LLM
- Integrates with M12 provenance
- Thread-safe
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from multi_agent.config.risk_synthesis_config import (
    CATEGORY_BY_PRIORITY,
    DISPLAY_PRECISION,
    INVALID_SCORE_STRATEGY,
    INTERNAL_PRECISION,
    MISSING_AGENT_STRATEGY,
    PRIORITY_BY_CATEGORY,
    RISK_CATEGORIES,
    RISK_THRESHOLDS,
    ROUND_TO_INTEGER,
    SYNTHESIS_ALGORITHM_VERSION,
    SYNTHESIS_FORMULA_DESCRIPTION,
    SYNTHESIS_METHOD,
    SYNTHESIS_VERSION,
    SYNTHESIS_WEIGHTS,
)


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class ComponentScore:
    """Represents a single component score input."""
    
    component_name: str
    score: Optional[float]
    status: str  # "available", "not_executed", "not_applicable", "error", "invalid"
    error_message: Optional[str] = None
    
    def is_valid(self) -> bool:
        """Check if score is valid for synthesis."""
        if self.status != "available":
            return False
        if self.score is None:
            return False
        if not isinstance(self.score, (int, float)):
            return False
        if math.isnan(self.score) or math.isinf(self.score):
            return False
        return True
    
    def is_valid_range(self) -> bool:
        """Check if score is in valid range [0, 100]."""
        if not self.is_valid():
            return False
        return 0.0 <= self.score <= 100.0


@dataclass
class SynthesisContribution:
    """Represents how one component contributes to final score."""
    
    component_name: str
    input_score: float
    weight: float
    contribution: float  # input_score * weight


@dataclass
class SynthesisResult:
    """Complete risk synthesis result with full breakdown."""
    
    # Inputs
    inputs: Dict[str, Optional[float]]  # component_name → score
    available_components: List[str]  # which components were available
    missing_components: List[str]  # which components were not available
    invalid_components: List[str]  # which components were invalid
    
    # Computation
    method: str  # "weighted_sum"
    weights: Dict[str, float]  # used weights (may be reweighted if components missing)
    contributions: List[SynthesisContribution]  # breakdown of how score was calculated
    
    # Results
    raw_score: float  # 0-100, full precision
    final_score: float  # 0-100, rounded for display
    risk_category: str  # "LOW", "MEDIUM", "HIGH", "CRITICAL"
    priority: str  # "P3", "P2", "P1", "P0"
    
    # Metadata
    is_complete: bool  # True if all components available
    is_usable: bool  # True if enough components for valid synthesis
    version: str  # SYNTHESIS_VERSION
    algorithm_version: str  # SYNTHESIS_ALGORITHM_VERSION
    
    # Errors/warnings
    errors: List[str]  # Critical issues
    warnings: List[str]  # Non-critical issues
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "method": self.method,
            "version": self.version,
            "algorithm_version": self.algorithm_version,
            "inputs": self.inputs,
            "available_components": self.available_components,
            "missing_components": self.missing_components,
            "invalid_components": self.invalid_components,
            "weights": self.weights,
            "contributions": [
                {
                    "component_name": c.component_name,
                    "input_score": round(c.input_score, INTERNAL_PRECISION),
                    "weight": round(c.weight, INTERNAL_PRECISION),
                    "contribution": round(c.contribution, INTERNAL_PRECISION),
                }
                for c in self.contributions
            ],
            "raw_score": round(self.raw_score, INTERNAL_PRECISION),
            "final_score": self.final_score,
            "risk_category": self.risk_category,
            "priority": self.priority,
            "is_complete": self.is_complete,
            "is_usable": self.is_usable,
            "errors": self.errors,
            "warnings": self.warnings,
        }


# ============================================================================
# CORE SYNTHESIS LOGIC
# ============================================================================

class RiskSynthesisService:
    """Deterministic risk synthesis engine."""
    
    @staticmethod
    def synthesize(
        claim_anomaly: Optional[float] = None,
        provider_anomaly: Optional[float] = None,
        peer_score: Optional[float] = None,
        billing_score: Optional[float] = None,
        rule_score: Optional[float] = None,
    ) -> SynthesisResult:
        """
        Calculate final risk score from component scores.
        
        Args:
            claim_anomaly: Upstream claim anomaly score (0-100)
            provider_anomaly: Upstream provider anomaly score (0-100)
            peer_score: Peer benchmark analysis score (0-100)
            billing_score: Billing rule analysis score (0-100)
            rule_score: Clinical rule analysis score (0-100)
        
        Returns:
            SynthesisResult with complete breakdown
        
        Raises:
            ValueError: If input validation fails and INVALID_SCORE_STRATEGY is REJECT_INVALID
        """
        
        # Step 1: Collect and validate component scores
        components = RiskSynthesisService._collect_components(
            claim_anomaly=claim_anomaly,
            provider_anomaly=provider_anomaly,
            peer_score=peer_score,
            billing_score=billing_score,
            rule_score=rule_score,
        )
        
        # Step 2: Validate all components
        errors, warnings = RiskSynthesisService._validate_components(components)
        
        # Step 3: Handle invalid scores based on strategy
        available_components = [c for c in components if c.is_valid_range()]
        invalid_components = [c for c in components if not c.is_valid_range() and c.status == "available"]
        missing_components = [c for c in components if c.status != "available"]
        
        if errors and INVALID_SCORE_STRATEGY == "REJECT_INVALID":
            raise ValueError(f"Invalid component scores: {'; '.join(errors)}")
        
        # Step 4: Reweight if components missing
        weights = RiskSynthesisService._compute_weights(available_components)
        
        # Step 5: Calculate contributions and raw score
        contributions, raw_score = RiskSynthesisService._calculate_contributions(
            available_components, weights
        )
        
        # Step 6: Determine category and priority
        risk_category = RiskSynthesisService._category_for_score(raw_score)
        priority = PRIORITY_BY_CATEGORY[risk_category]
        
        # Step 7: Round for display
        final_score = RiskSynthesisService._round_score(raw_score)
        
        # Step 8: Determine completeness
        is_complete = len(missing_components) == 0
        is_usable = len(available_components) >= 2  # At least 2 components
        
        if not is_usable and len(available_components) == 1:
            warnings.append(f"Only {available_components[0].component_name} available; result may not be reliable")
        
        return SynthesisResult(
            inputs={c.component_name: c.score for c in components},
            available_components=[c.component_name for c in available_components],
            missing_components=[c.component_name for c in missing_components],
            invalid_components=[c.component_name for c in invalid_components],
            method=SYNTHESIS_METHOD,
            weights={c.component_name: weights[c.component_name] for c in available_components},
            contributions=contributions,
            raw_score=raw_score,
            final_score=final_score,
            risk_category=risk_category,
            priority=priority,
            is_complete=is_complete,
            is_usable=is_usable,
            version=SYNTHESIS_VERSION,
            algorithm_version=SYNTHESIS_ALGORITHM_VERSION,
            errors=errors,
            warnings=warnings,
        )
    
    # ========================================================================
    # HELPER METHODS
    # ========================================================================
    
    @staticmethod
    def _collect_components(
        claim_anomaly: Optional[float] = None,
        provider_anomaly: Optional[float] = None,
        peer_score: Optional[float] = None,
        billing_score: Optional[float] = None,
        rule_score: Optional[float] = None,
    ) -> List[ComponentScore]:
        """Collect all component scores with status."""
        
        components = []
        
        # Collect each component with appropriate status
        for name, score in [
            ("claim_anomaly", claim_anomaly),
            ("provider_anomaly", provider_anomaly),
            ("peer_score", peer_score),
            ("billing_score", billing_score),
            ("rule_score", rule_score),
        ]:
            if score is None:
                components.append(ComponentScore(
                    component_name=name,
                    score=None,
                    status="not_executed",
                ))
            else:
                components.append(ComponentScore(
                    component_name=name,
                    score=score,
                    status="available",
                ))
        
        return components
    
    @staticmethod
    def _validate_components(components: List[ComponentScore]) -> Tuple[List[str], List[str]]:
        """Validate all components and return (errors, warnings)."""
        
        errors = []
        warnings = []
        
        for comp in components:
            if comp.status != "available":
                continue  # Skip non-available
            
            if comp.score is None:
                errors.append(f"{comp.component_name}: score is None")
                continue
            
            if not isinstance(comp.score, (int, float)):
                errors.append(f"{comp.component_name}: score must be numeric, got {type(comp.score).__name__}")
                continue
            
            if math.isnan(comp.score):
                errors.append(f"{comp.component_name}: score is NaN")
                continue
            
            if math.isinf(comp.score):
                errors.append(f"{comp.component_name}: score is infinity")
                continue
            
            if comp.score < 0 or comp.score > 100:
                errors.append(f"{comp.component_name}: score {comp.score} outside valid range [0, 100]")
                continue
        
        return errors, warnings
    
    @staticmethod
    def _compute_weights(
        available_components: List[ComponentScore],
    ) -> Dict[str, float]:
        """
        Compute weights for synthesis.
        
        If all components available: use configured weights.
        If some components missing: reweight available components to sum to 1.0.
        """
        
        if not available_components:
            return {}
        
        # If all configured components are available, use configured weights
        available_names = {c.component_name for c in available_components}
        all_configured = set(SYNTHESIS_WEIGHTS.keys())
        
        if available_names == all_configured:
            # All components available, use as-is
            return SYNTHESIS_WEIGHTS.copy()
        
        # Some components missing, reweight
        if MISSING_AGENT_STRATEGY == "REWEIGHT_AVAILABLE_COMPONENTS":
            available_weight = sum(
                SYNTHESIS_WEIGHTS[name] for name in available_names
                if name in SYNTHESIS_WEIGHTS
            )
            
            if available_weight == 0:
                # Edge case: no configured weights for available components
                # Distribute equally
                equal_weight = 1.0 / len(available_components)
                return {c.component_name: equal_weight for c in available_components}
            
            # Rescale weights to sum to 1.0
            reweighted = {}
            for comp in available_components:
                original_weight = SYNTHESIS_WEIGHTS.get(comp.component_name, 0)
                reweighted[comp.component_name] = original_weight / available_weight
            
            return reweighted
        
        else:
            raise RuntimeError(f"Unsupported MISSING_AGENT_STRATEGY: {MISSING_AGENT_STRATEGY}")
    
    @staticmethod
    def _calculate_contributions(
        available_components: List[ComponentScore],
        weights: Dict[str, float],
    ) -> Tuple[List[SynthesisContribution], float]:
        """Calculate contribution of each component and raw score."""
        
        contributions = []
        raw_score = 0.0
        
        for comp in available_components:
            weight = weights.get(comp.component_name, 0.0)
            contribution = comp.score * weight
            contributions.append(SynthesisContribution(
                component_name=comp.component_name,
                input_score=comp.score,
                weight=weight,
                contribution=contribution,
            ))
            raw_score += contribution
        
        # Clamp to [0, 100] (should not be needed with valid weights, but defensive)
        raw_score = max(0.0, min(100.0, raw_score))
        
        return contributions, raw_score
    
    @staticmethod
    def _category_for_score(score: float) -> str:
        """Determine risk category from score."""
        
        # Categories are defined by lower-bound threshold (inclusive)
        for category in reversed(RISK_CATEGORIES):  # Start from highest
            threshold = RISK_THRESHOLDS[category]
            if score >= threshold:
                return category
        
        # Should not reach here, but fallback to first category
        return RISK_CATEGORIES[0]
    
    @staticmethod
    def _round_score(raw_score: float) -> float:
        """Round score for display."""
        
        if ROUND_TO_INTEGER:
            return float(round(raw_score, 0))
        else:
            return round(raw_score, DISPLAY_PRECISION)


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def calculate_risk_score(
    claim_anomaly: Optional[float] = None,
    provider_anomaly: Optional[float] = None,
    peer_score: Optional[float] = None,
    billing_score: Optional[float] = None,
    rule_score: Optional[float] = None,
) -> Tuple[float, str, str]:
    """
    Simple interface: return (final_score, risk_category, priority).
    
    Raises ValueError if invalid inputs and INVALID_SCORE_STRATEGY is REJECT_INVALID.
    """
    
    result = RiskSynthesisService.synthesize(
        claim_anomaly=claim_anomaly,
        provider_anomaly=provider_anomaly,
        peer_score=peer_score,
        billing_score=billing_score,
        rule_score=rule_score,
    )
    
    return result.final_score, result.risk_category, result.priority
