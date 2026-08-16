"""
MILESTONE 13: Risk Synthesis Tests

Comprehensive test suite for the deterministic risk synthesis formula.

Test Categories:
1. Golden test cases (16 deterministic fixtures)
2. Boundary tests (score thresholds)
3. Missing component tests (agent skipped)
4. Invalid input tests
5. Invariant/property tests
6. Determinism tests
7. Rounding tests
8. Configuration tests
"""

from __future__ import annotations

import math
import pytest

from multi_agent.config.risk_synthesis_config import (
    DISPLAY_PRECISION,
    INVALID_SCORE_STRATEGY,
    MISSING_AGENT_STRATEGY,
    PRIORITY_BY_CATEGORY,
    RISK_CATEGORIES,
    RISK_THRESHOLDS,
    ROUND_TO_INTEGER,
    SYNTHESIS_VERSION,
    SYNTHESIS_WEIGHTS,
)
from multi_agent.services.risk_synthesis_service import (
    RiskSynthesisService,
    SynthesisResult,
    calculate_risk_score,
)


# ============================================================================
# GOLDEN TEST CASES
# ============================================================================
# These fixtures define the expected behavior for common scenarios.
# They should be used as regression tests and documentation.

class TestGoldenCases:
    """Deterministic test fixtures with known correct outputs."""
    
    def test_all_components_high(self):
        """TEST 1: All components high (90+)."""
        result = RiskSynthesisService.synthesize(
            claim_anomaly=95.0,
            provider_anomaly=90.0,
            peer_score=92.0,
            billing_score=88.0,
            rule_score=85.0,
        )
        
        # Expected: very high score
        assert result.final_score >= 85
        assert result.risk_category == "CRITICAL"
        assert result.priority == "P0"
        assert result.is_complete
        assert result.is_usable
        assert len(result.errors) == 0
    
    def test_all_components_low(self):
        """TEST 2: All components low (10-20)."""
        result = RiskSynthesisService.synthesize(
            claim_anomaly=15.0,
            provider_anomaly=12.0,
            peer_score=10.0,
            billing_score=18.0,
            rule_score=14.0,
        )
        
        # Expected: very low score
        assert result.final_score < 40
        assert result.risk_category == "LOW"
        assert result.priority == "P3"
        assert result.is_complete
        assert result.is_usable
        assert len(result.errors) == 0
    
    def test_high_claim_low_provider(self):
        """TEST 3: High claim anomaly, low provider anomaly."""
        result = RiskSynthesisService.synthesize(
            claim_anomaly=85.0,
            provider_anomaly=25.0,
            peer_score=30.0,
            billing_score=40.0,
            rule_score=35.0,
        )
        
        # claim_anomaly (85*0.30=25.5) + provider_anomaly (25*0.30=7.5) + ...
        # Expected: medium-high score (around 50-60)
        assert 40 <= result.final_score <= 70
        assert result.risk_category in {"MEDIUM", "HIGH"}
        assert result.is_complete
        assert len(result.errors) == 0
    
    def test_low_claim_high_provider(self):
        """TEST 4: Low claim anomaly, high provider anomaly."""
        result = RiskSynthesisService.synthesize(
            claim_anomaly=20.0,
            provider_anomaly=88.0,
            peer_score=85.0,
            billing_score=30.0,
            rule_score=25.0,
        )
        
        # provider_anomaly (88*0.30=26.4) + peer_score (85*0.20=17) + ...
        # Expected: medium-high score (around 50-60)
        assert 40 <= result.final_score <= 70
        assert result.risk_category in {"MEDIUM", "HIGH"}
        assert result.is_complete
        assert len(result.errors) == 0
    
    def test_high_claim_high_provider(self):
        """TEST 5: Both claim and provider anomaly high."""
        result = RiskSynthesisService.synthesize(
            claim_anomaly=91.0,
            provider_anomaly=88.0,
            peer_score=75.0,
            billing_score=80.0,
            rule_score=70.0,
        )
        
        # Expected: very high score (likely CRITICAL)
        # (91*0.30) + (88*0.30) + (75*0.20) + (80*0.10) + (70*0.10)
        # = 27.3 + 26.4 + 15 + 8 + 7 = 83.7
        expected_raw = 91 * 0.30 + 88 * 0.30 + 75 * 0.20 + 80 * 0.10 + 70 * 0.10
        assert result.raw_score == pytest.approx(expected_raw, abs=0.1)
        assert result.final_score >= 80
        assert result.risk_category in {"HIGH", "CRITICAL"}
        assert result.is_complete
        assert len(result.errors) == 0
    
    def test_boundary_39_low(self):
        """TEST 6: Score exactly 39.0 should be LOW."""
        # Test with a score just below the LOW/MEDIUM boundary
        result = RiskSynthesisService.synthesize(
            claim_anomaly=39.0,
            provider_anomaly=39.0,
            peer_score=39.0,
            billing_score=39.0,
            rule_score=39.0,
        )
        
        # All 39s should give exactly 39
        assert result.raw_score == pytest.approx(39.0, abs=0.1)
        assert result.final_score == 39
        assert result.risk_category == "LOW"
        assert result.priority == "P3"
    
    def test_boundary_40_medium(self):
        """TEST 7: Score exactly 40.0 should be MEDIUM."""
        result = RiskSynthesisService.synthesize(
            claim_anomaly=40.0,
            provider_anomaly=40.0,
            peer_score=40.0,
            billing_score=40.0,
            rule_score=40.0,
        )
        
        # All 40s should give exactly 40
        assert result.raw_score == pytest.approx(40.0, abs=0.1)
        assert result.final_score == 40
        assert result.risk_category == "MEDIUM"
        assert result.priority == "P2"
    
    def test_boundary_69_medium(self):
        """TEST 8: Score exactly 69.0 should be MEDIUM."""
        result = RiskSynthesisService.synthesize(
            claim_anomaly=69.0,
            provider_anomaly=69.0,
            peer_score=69.0,
            billing_score=69.0,
            rule_score=69.0,
        )
        
        # All 69s should give exactly 69
        assert result.raw_score == pytest.approx(69.0, abs=0.1)
        assert result.final_score == 69
        assert result.risk_category == "MEDIUM"
        assert result.priority == "P2"
    
    def test_boundary_70_high(self):
        """TEST 9: Score exactly 70.0 should be HIGH."""
        result = RiskSynthesisService.synthesize(
            claim_anomaly=70.0,
            provider_anomaly=70.0,
            peer_score=70.0,
            billing_score=70.0,
            rule_score=70.0,
        )
        
        # All 70s should give exactly 70
        assert result.raw_score == pytest.approx(70.0, abs=0.1)
        assert result.final_score == 70
        assert result.risk_category == "HIGH"
        assert result.priority == "P1"
    
    def test_boundary_84_high(self):
        """TEST 10: Score exactly 84.0 should be HIGH."""
        result = RiskSynthesisService.synthesize(
            claim_anomaly=84.0,
            provider_anomaly=84.0,
            peer_score=84.0,
            billing_score=84.0,
            rule_score=84.0,
        )
        
        # All 84s should give exactly 84
        assert result.raw_score == pytest.approx(84.0, abs=0.1)
        assert result.final_score == 84
        assert result.risk_category == "HIGH"
        assert result.priority == "P1"
    
    def test_boundary_85_critical(self):
        """TEST 11: Score exactly 85.0 should be CRITICAL."""
        result = RiskSynthesisService.synthesize(
            claim_anomaly=85.0,
            provider_anomaly=85.0,
            peer_score=85.0,
            billing_score=85.0,
            rule_score=85.0,
        )
        
        # All 85s should give exactly 85
        assert result.raw_score == pytest.approx(85.0, abs=0.1)
        assert result.final_score == 85
        assert result.risk_category == "CRITICAL"
        assert result.priority == "P0"


# ============================================================================
# MISSING AGENT TESTS
# ============================================================================

class TestMissingComponents:
    """Test behavior when components are not executed or not available."""
    
    def test_missing_billing_agent(self):
        """TEST 12: Billing agent skipped (not executed)."""
        result = RiskSynthesisService.synthesize(
            claim_anomaly=80.0,
            provider_anomaly=75.0,
            peer_score=85.0,
            billing_score=None,
            rule_score=70.0,
        )
        
        # Should reweight available components
        assert result.missing_components == ["billing_score"]
        assert result.available_components == ["claim_anomaly", "provider_anomaly", "peer_score", "rule_score"]
        assert "billing_score" not in result.weights
        assert result.is_complete is False
        assert result.is_usable is True
        assert len(result.errors) == 0
    
    def test_missing_peer_agent(self):
        """TEST 13: Peer agent skipped."""
        result = RiskSynthesisService.synthesize(
            claim_anomaly=80.0,
            provider_anomaly=75.0,
            peer_score=None,
            billing_score=85.0,
            rule_score=70.0,
        )
        
        # Should reweight available components
        assert result.missing_components == ["peer_score"]
        assert result.available_components == ["claim_anomaly", "provider_anomaly", "billing_score", "rule_score"]
        assert "peer_score" not in result.weights
        assert result.is_complete is False
        assert result.is_usable is True
        assert len(result.errors) == 0
    
    def test_only_one_component_available(self):
        """TEST 14: Only one component available (minimal case)."""
        result = RiskSynthesisService.synthesize(
            claim_anomaly=80.0,
            provider_anomaly=None,
            peer_score=None,
            billing_score=None,
            rule_score=None,
        )
        
        # Should still calculate, but mark as not fully usable
        assert result.available_components == ["claim_anomaly"]
        assert len(result.contributions) == 1
        assert result.contributions[0].input_score == 80.0
        assert result.contributions[0].weight == pytest.approx(1.0)  # 100% of the signal
        assert result.final_score == pytest.approx(80.0, abs=0.1)
        assert result.is_usable is False  # Only 1 component
        assert len(result.warnings) > 0


# ============================================================================
# INVALID INPUT TESTS
# ============================================================================

class TestInvalidInputs:
    """Test handling of invalid component scores."""
    
    def test_score_below_zero(self):
        """TEST 15: Score below valid range."""
        # Should raise ValueError when INVALID_SCORE_STRATEGY is REJECT_INVALID
        with pytest.raises(ValueError):
            RiskSynthesisService.synthesize(
                claim_anomaly=-5.0,
                provider_anomaly=75.0,
                peer_score=80.0,
                billing_score=85.0,
                rule_score=70.0,
            )
    
    def test_score_above_100(self):
        """TEST 16: Score above valid range."""
        # Should raise ValueError when INVALID_SCORE_STRATEGY is REJECT_INVALID
        with pytest.raises(ValueError):
            RiskSynthesisService.synthesize(
                claim_anomaly=105.0,
                provider_anomaly=75.0,
                peer_score=80.0,
                billing_score=85.0,
                rule_score=70.0,
            )
    
    def test_nan_score(self):
        """Test NaN component."""
        # Should raise ValueError when INVALID_SCORE_STRATEGY is REJECT_INVALID
        with pytest.raises(ValueError):
            RiskSynthesisService.synthesize(
                claim_anomaly=float('nan'),
                provider_anomaly=75.0,
                peer_score=80.0,
                billing_score=85.0,
                rule_score=70.0,
            )
    
    def test_infinity_score(self):
        """Test infinity component."""
        # Should raise ValueError when INVALID_SCORE_STRATEGY is REJECT_INVALID
        with pytest.raises(ValueError):
            RiskSynthesisService.synthesize(
                claim_anomaly=float('inf'),
                provider_anomaly=75.0,
                peer_score=80.0,
                billing_score=85.0,
                rule_score=70.0,
            )


# ============================================================================
# INVARIANT / PROPERTY TESTS
# ============================================================================

class TestInvariants:
    """Test mathematical and logical properties of synthesis."""
    
    def test_final_score_in_valid_range(self):
        """Invariant: Final score must always be in [0, 100]."""
        test_cases = [
            (0, 0, 0, 0, 0),
            (100, 100, 100, 100, 100),
            (50, 50, 50, 50, 50),
            (99.5, 75.3, 82.1, 45.2, 88.9),
            (1.0, 2.0, 3.0, 4.0, 5.0),
        ]
        
        for claim, provider, peer, billing, rule in test_cases:
            result = RiskSynthesisService.synthesize(
                claim_anomaly=claim,
                provider_anomaly=provider,
                peer_score=peer,
                billing_score=billing,
                rule_score=rule,
            )
            assert 0.0 <= result.final_score <= 100.0, f"Score {result.final_score} out of range"
    
    def test_increasing_input_increases_output(self):
        """Invariant: Increasing any component should not decrease final score."""
        base = RiskSynthesisService.synthesize(
            claim_anomaly=50.0,
            provider_anomaly=50.0,
            peer_score=50.0,
            billing_score=50.0,
            rule_score=50.0,
        )
        
        # Increase claim_anomaly
        higher = RiskSynthesisService.synthesize(
            claim_anomaly=75.0,
            provider_anomaly=50.0,
            peer_score=50.0,
            billing_score=50.0,
            rule_score=50.0,
        )
        
        assert higher.final_score >= base.final_score, \
            f"Increasing input decreased output: {base.final_score} → {higher.final_score}"
    
    def test_contributions_sum_to_raw_score(self):
        """Invariant: Sum of contributions should equal raw score (within tolerance)."""
        result = RiskSynthesisService.synthesize(
            claim_anomaly=80.0,
            provider_anomaly=75.0,
            peer_score=85.0,
            billing_score=70.0,
            rule_score=65.0,
        )
        
        contrib_sum = sum(c.contribution for c in result.contributions)
        assert contrib_sum == pytest.approx(result.raw_score, abs=0.0001), \
            f"Contributions {contrib_sum} != raw_score {result.raw_score}"
    
    def test_category_matches_thresholds(self):
        """Invariant: Risk category must always match configured thresholds."""
        test_scores = [10, 25, 39, 40, 50, 69, 70, 84, 85, 100]
        
        for score in test_scores:
            result = RiskSynthesisService.synthesize(
                claim_anomaly=score,
                provider_anomaly=score,
                peer_score=score,
                billing_score=score,
                rule_score=score,
            )
            
            # Determine expected category
            if score < 40:
                expected = "LOW"
            elif score < 70:
                expected = "MEDIUM"
            elif score < 85:
                expected = "HIGH"
            else:
                expected = "CRITICAL"
            
            assert result.risk_category == expected, \
                f"Score {score} categorized as {result.risk_category}, expected {expected}"
    
    def test_priority_matches_category(self):
        """Invariant: Priority must match category."""
        test_categories = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
        
        for category in test_categories:
            threshold = RISK_THRESHOLDS[category]
            result = RiskSynthesisService.synthesize(
                claim_anomaly=threshold + 1,
                provider_anomaly=threshold + 1,
                peer_score=threshold + 1,
                billing_score=threshold + 1,
                rule_score=threshold + 1,
            )
            
            expected_priority = PRIORITY_BY_CATEGORY[category]
            assert result.priority == expected_priority, \
                f"Category {category} should have priority {expected_priority}, got {result.priority}"
    
    def test_weights_sum_to_one(self):
        """Invariant: Computed weights must sum to 1.0."""
        result = RiskSynthesisService.synthesize(
            claim_anomaly=80.0,
            provider_anomaly=75.0,
            peer_score=None,
            billing_score=70.0,
            rule_score=65.0,
        )
        
        weight_sum = sum(result.weights.values())
        assert weight_sum == pytest.approx(1.0, abs=0.0001), \
            f"Weights sum to {weight_sum}, expected 1.0"


# ============================================================================
# DETERMINISM TESTS
# ============================================================================

class TestDeterminism:
    """Test that synthesis is deterministic (same input → same output)."""
    
    def test_same_input_same_output(self):
        """Invariant: Same input must always produce same output."""
        inputs = (80.0, 75.0, 85.0, 70.0, 65.0)
        
        result1 = RiskSynthesisService.synthesize(*inputs)
        result2 = RiskSynthesisService.synthesize(*inputs)
        result3 = RiskSynthesisService.synthesize(*inputs)
        
        assert result1.final_score == result2.final_score == result3.final_score
        assert result1.risk_category == result2.risk_category == result3.risk_category
        assert result1.priority == result2.priority == result3.priority
        assert result1.raw_score == result2.raw_score == result3.raw_score
    
    def test_order_independence(self):
        """Test that order of component scores doesn't matter (semantically)."""
        # Both should give same result (order doesn't affect weighted sum)
        result1 = RiskSynthesisService.synthesize(
            claim_anomaly=80.0, provider_anomaly=75.0, peer_score=85.0,
            billing_score=70.0, rule_score=65.0,
        )
        
        result2 = RiskSynthesisService.synthesize(
            rule_score=65.0, billing_score=70.0, peer_score=85.0,
            provider_anomaly=75.0, claim_anomaly=80.0,
        )
        
        assert result1.final_score == result2.final_score
        assert result1.risk_category == result2.risk_category


# ============================================================================
# ROUNDING TESTS
# ============================================================================

class TestRounding:
    """Test rounding behavior of final scores."""
    
    def test_rounding_to_integer(self):
        """Test that scores are rounded to integers (or configured precision)."""
        result = RiskSynthesisService.synthesize(
            claim_anomaly=80.7,
            provider_anomaly=75.3,
            peer_score=85.5,
            billing_score=70.1,
            rule_score=65.9,
        )
        
        # Should be rounded
        if ROUND_TO_INTEGER:
            assert result.final_score == int(result.final_score)
        else:
            assert result.final_score == round(result.final_score, DISPLAY_PRECISION)
    
    def test_raw_vs_final_score(self):
        """Test that raw_score has more precision than final_score."""
        result = RiskSynthesisService.synthesize(
            claim_anomaly=80.7,
            provider_anomaly=75.3,
            peer_score=85.5,
            billing_score=70.1,
            rule_score=65.9,
        )
        
        # raw_score should be higher precision
        assert result.raw_score != result.final_score or (result.raw_score % 1.0) == 0.0


# ============================================================================
# CONVENIENCE FUNCTION TESTS
# ============================================================================

class TestConvenienceFunctions:
    """Test simple interface functions."""
    
    def test_calculate_risk_score_function(self):
        """Test the simple calculate_risk_score() function."""
        score, category, priority = calculate_risk_score(
            claim_anomaly=80.0,
            provider_anomaly=75.0,
            peer_score=85.0,
            billing_score=70.0,
            rule_score=65.0,
        )
        
        assert 0 <= score <= 100
        assert category in RISK_CATEGORIES
        assert priority in PRIORITY_BY_CATEGORY.values()


# ============================================================================
# CONFIGURATION TESTS
# ============================================================================

class TestConfiguration:
    """Test configuration constants and consistency."""
    
    def test_weights_sum_to_one(self):
        """Configuration property: weights must sum to 1.0."""
        weight_sum = sum(SYNTHESIS_WEIGHTS.values())
        assert 0.99 <= weight_sum <= 1.01, f"Weights sum to {weight_sum}"
    
    def test_thresholds_in_order(self):
        """Configuration property: thresholds must be in increasing order."""
        prev = -1.0
        for category in RISK_CATEGORIES:
            threshold = RISK_THRESHOLDS[category]
            assert threshold >= prev, f"Thresholds not in order: {threshold} < {prev}"
            prev = threshold
    
    def test_priority_mapping_complete(self):
        """Configuration property: every category must have a priority."""
        for category in RISK_CATEGORIES:
            assert category in PRIORITY_BY_CATEGORY, f"Missing priority for {category}"
        
        assert len(PRIORITY_BY_CATEGORY) == len(RISK_CATEGORIES)
