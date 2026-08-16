"""Shared contracts and data-access foundation for the Multi-Agent investigation layer."""

from .models import (
    CONTRACT_VERSION,
    AgentExecution,
    AgentResult,
    AgentStatus,
    DataAvailability,
    Evidence,
    Finding,
    GenAIExplanation,
    InvestigationCase,
    InvestigationContext,
    RiskCategory,
    RiskPriority,
    RiskSynthesis,
    RuleHit,
)
from .orchestrator import Orchestrator
from .synthesis import InvestigationResult, Synthesis

__all__ = [
    "InvestigationResult",
    "Orchestrator",
    "Synthesis",
    "CONTRACT_VERSION",
    "AgentExecution",
    "AgentResult",
    "AgentStatus",
    "DataAvailability",
    "Evidence",
    "Finding",
    "GenAIExplanation",
    "InvestigationCase",
    "InvestigationContext",
    "RiskCategory",
    "RiskPriority",
    "RiskSynthesis",
    "RuleHit",
]
