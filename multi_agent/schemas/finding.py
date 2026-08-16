from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class Finding:
    """Structured finding produced by a future investigation agent."""

    agent: str
    category: str
    rule: str
    severity: str
    description: str
    evidence: Dict[str, Any] = field(default_factory=dict)
    confidence: Optional[float] = None
