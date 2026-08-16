from __future__ import annotations

from math import isfinite
from typing import Any, Optional


def safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        result = float(value)
        return result if isfinite(result) else None
    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned == "" or cleaned.lower() in {"nan", "none", "null", "na"}:
            return None
        try:
            result = float(cleaned)
            return result if isfinite(result) else None
        except ValueError:
            return None
    return None


def safe_divide(numerator: Any, denominator: Any) -> Optional[float]:
    n = safe_float(numerator)
    d = safe_float(denominator)
    if n is None or d is None:
        return None
    if d == 0:
        return None
    result = n / d
    return result if isfinite(result) else None


def deviation(observed: Any, baseline: Any) -> Optional[float]:
    o = safe_float(observed)
    b = safe_float(baseline)
    if o is None or b is None:
        return None
    result = o - b
    return result if isfinite(result) else None


def deviation_ratio(observed: Any, baseline: Any) -> Optional[float]:
    return safe_divide(observed, baseline)


def percentage_deviation(observed: Any, baseline: Any) -> Optional[float]:
    o = safe_float(observed)
    b = safe_float(baseline)
    if o is None or b is None or b == 0:
        return None
    result = ((o - b) / b) * 100.0
    return result if isfinite(result) else None


def threshold_comparison(observed: Any, threshold: Any, *, operator: str = ">") -> Optional[str]:
    o = safe_float(observed)
    t = safe_float(threshold)
    if o is None or t is None:
        return None
    op = (operator or ">").strip()
    if op == ">":
        return "ABOVE" if o > t else "AT_OR_BELOW"
    if op == ">=":
        return "AT_OR_ABOVE" if o >= t else "BELOW"
    if op == "<":
        return "BELOW" if o < t else "AT_OR_ABOVE"
    if op == "<=":
        return "AT_OR_BELOW" if o <= t else "ABOVE"
    if op == "==":
        return "EQUAL" if o == t else "NOT_EQUAL"
    return None
