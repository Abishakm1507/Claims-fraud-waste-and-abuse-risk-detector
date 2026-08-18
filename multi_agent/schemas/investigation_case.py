from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .claim_context import ClaimContext
from .finding import Finding
from .provider_context import ProviderContext


@dataclass
class InvestigationCase:
    """Unit of work passed into the future Multi-Agent system."""

    case_id: str
    claim_id: str
    claim: Optional[ClaimContext] = None
    provider: Optional[ProviderContext] = None
    findings: List[Finding] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
<<<<<<< HEAD
    llm_routing_plan: Optional[Dict[str, Any]] = None
    llm_agent_context: Dict[str, Any] = field(default_factory=dict)
=======
>>>>>>> b166e40 (removed old data)
