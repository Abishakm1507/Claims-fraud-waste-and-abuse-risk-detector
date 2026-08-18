from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class ToolSchema:
    """Schema for an LLM agent tool."""

    name: str
    description: str
    params: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.params,
        }


@dataclass
class AgentLLMConfig:
    """Per-agent Groq configuration used by the reasoning layer.

    The deterministic risk synthesis configuration remains frozen and unchanged.
    This config only controls the LLM reasoning layer that sits on top of the
    authoritative risk numbers.
    """

    enabled: bool = True
    model: str = "openai/gpt-oss-120b"
    temperature: float = 0.1
    max_tokens: int = 600
    timeout_seconds: float = 15.0
    allowed_tools: List[str] = field(
        default_factory=lambda: [
            "get_payment_charge_ratio",
            "get_peer_utilization_comparison",
            "check_leie_exclusion",
            "get_claim_line_count",
            "get_provider_benchmark_summary",
        ]
    )
    tools: List[ToolSchema] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "timeout_seconds": self.timeout_seconds,
            "allowed_tools": list(self.allowed_tools),
            "tools": [t.to_dict() for t in self.tools],
        }


# Tool schemas for each agent
BILLING_AGENT_TOOLS = [
    ToolSchema(
        name="check_payment_charge_ratio",
        description="Compute the payment-to-charge ratio to detect overbilling.",
    ),
    ToolSchema(
        name="check_payment_deviation",
        description="Compare claim payment to provider benchmark average.",
    ),
    ToolSchema(
        name="check_reconciliation_issue",
        description="Detect payment reconciliation discrepancies.",
    ),
    ToolSchema(
        name="check_claim_volume",
        description="Examine claim line count and utilization patterns.",
    ),
]

PEER_AGENT_TOOLS = [
    ToolSchema(
        name="compare_peer_metrics",
        description="Compare provider metrics (payment per service, utilization) to peer group benchmarks.",
    ),
    ToolSchema(
        name="compare_geographic_metrics",
        description="Compare provider metrics to geographic (state) benchmarks.",
    ),
    ToolSchema(
        name="get_peer_deviation_score",
        description="Retrieve normalized peer deviation score if available.",
    ),
]

CLINICAL_RULE_AGENT_TOOLS = [
    ToolSchema(
        name="check_outpatient_utilization",
        description="Examine outpatient claim utilization patterns, line counts, diagnoses.",
    ),
    ToolSchema(
        name="check_inpatient_consensus",
        description="Check inpatient ML model consensus signals.",
    ),
    ToolSchema(
        name="check_procedure_volume",
        description="Examine procedure code volume and uniqueness.",
    ),
]

SYNTHESIS_AGENT_TOOLS = [
    ToolSchema(
        name="aggregate_agent_concerns",
        description="Aggregate concern levels from all three agents (billing, peer, clinical).",
    ),
    ToolSchema(
        name="detect_conflicts",
        description="Identify disagreements between agents' findings and concern levels.",
    ),
    ToolSchema(
        name="cross_validate_evidence",
        description="Cross-validate evidence across independent data sources.",
    ),
]

DEFAULT_AGENT_LLM_CONFIG = {
    "billing": AgentLLMConfig(
        enabled=True,
        model="openai/gpt-oss-120b",
        allowed_tools=["check_payment_charge_ratio", "check_payment_deviation", "check_reconciliation_issue", "check_claim_volume"],
        tools=BILLING_AGENT_TOOLS,
    ),
    "peer": AgentLLMConfig(
        enabled=True,
        model="openai/gpt-oss-120b",
        max_tokens=1000,
        allowed_tools=["compare_peer_metrics", "compare_geographic_metrics", "get_peer_deviation_score"],
        tools=PEER_AGENT_TOOLS,
    ),
    "clinical_rule": AgentLLMConfig(
        enabled=True,
        model="openai/gpt-oss-120b",
        allowed_tools=["check_outpatient_utilization", "check_inpatient_consensus", "check_procedure_volume"],
        tools=CLINICAL_RULE_AGENT_TOOLS,
    ),
    "synthesis": AgentLLMConfig(
        enabled=True,
        model="openai/gpt-oss-120b",
        max_tokens=900,
        allowed_tools=["aggregate_agent_concerns", "detect_conflicts", "cross_validate_evidence"],
        tools=SYNTHESIS_AGENT_TOOLS,
    ),
    "orchestrator": AgentLLMConfig(
        enabled=True,
        model="openai/gpt-oss-120b",
        max_tokens=700,
        allowed_tools=["select_agents", "prioritize_investigation"],
    ),
}
