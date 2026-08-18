"""LLM-driven agent reasoning service with tool calling support.

Supports two modes:
1. Tool-calling mode (if Groq supports it): LLM directly selects and calls tools.
2. Structured reasoning mode: LLM receives tool descriptions and returns JSON with selected tools.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

try:
    from groq import Groq
except ImportError:  # pragma: no cover
    Groq = None

logger = logging.getLogger(__name__)

_MISSING = object()


@dataclass
class ToolDefinition:
    """Schema for a callable tool available to the agent."""

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
class AgentReasoningResult:
    """Result from agent LLM reasoning."""

    narrative: str
    selected_tools: List[str] = field(default_factory=list)
    tool_calls: Dict[str, Any] = field(default_factory=dict)
    tool_failures: List[Dict[str, str]] = field(default_factory=list)
    status: str = "success"
    error: str = ""
    is_fallback: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "narrative": self.narrative,
            "selected_tools": self.selected_tools,
            "tool_calls": self.tool_calls,
            "tool_failures": self.tool_failures,
            "status": self.status,
            "error": self.error,
            "is_fallback": self.is_fallback,
        }


class LLMAgentService:
    """Service for agent-level LLM reasoning with tool calling."""

    DEFAULT_MODEL = "openai/gpt-oss-120b"

    def __init__(
        self,
        api_key: Optional[str] | object = _MISSING,
        model: Optional[str] = None,
        client: Any = None,
        timeout: float = 15.0,
        enabled: bool = True,
        max_retries: int = 1,
        temperature: float = 0.1,
        max_tokens: int = 800,
    ):
        self._load_dotenv()
        config_key = self._config_api_key()
        self.api_key = config_key if api_key is _MISSING else api_key
        self.model = model or os.getenv("GROQ_MODEL") or self.DEFAULT_MODEL
        self.timeout = float(os.getenv("GROQ_TIMEOUT", timeout))
        self.enabled = enabled
        self.client = client
        self.max_retries = int(os.getenv("GROQ_MAX_RETRIES", max_retries))
        self.temperature = float(os.getenv("GROQ_TEMPERATURE", temperature))
        self.max_tokens = int(os.getenv("GROQ_MAX_TOKENS", max_tokens))

    def reason_with_tools(
        self,
        agent_name: str,
        case_context: Dict[str, Any],
        available_tools: List[ToolDefinition],
        tool_registry: Dict[str, Callable],
        fallback_narrative: str = "",
        focus_hint: Optional[str] = None,
        case: Optional[Any] = None,
    ) -> AgentReasoningResult:
        """Invoke LLM agent reasoning with tool calling.

        Args:
            agent_name: Name of the agent (billing, peer, clinical_rule, synthesis).
            case_context: Case data (claim, provider, risk scores) for LLM context (redacted dict).
            available_tools: List of tools the agent can select and call.
            tool_registry: {tool_name: callable} mapping.
            fallback_narrative: Text to use if LLM is unavailable.
            focus_hint: Optional routing rationale/guidance from orchestrator.
            case: Full InvestigationCase object to pass to tools (not serialized).

        Returns:
            AgentReasoningResult with narrative and selected tool calls.
        """
        if not self.enabled:
            return AgentReasoningResult(
                narrative=fallback_narrative or "Deterministic evidence remains the source of truth.",
                status="disabled",
                is_fallback=True,
            )

        if not self.api_key:
            return AgentReasoningResult(
                narrative=fallback_narrative or "Deterministic evidence remains the source of truth.",
                status="unavailable",
                error="Missing GROQ_API_KEY.",
                is_fallback=True,
            )

        if Groq is None and self.client is None:
            return AgentReasoningResult(
                narrative=fallback_narrative or "Deterministic evidence remains the source of truth.",
                status="unavailable",
                error="Groq SDK not installed.",
                is_fallback=True,
            )

        prompt = self._build_tool_reasoning_prompt(agent_name, case_context, available_tools, focus_hint)

        for attempt in range(self.max_retries + 1):
            try:
                response = self._call_groq(prompt)
                
                # Detect likely truncation (JSON parse error + response near token limit)
                is_likely_truncated = False
                try:
                    parsed = self._parse_reasoning_response(response)
                except Exception as parse_exc:
                    # Check if it looks like truncation (unterminated string in JSON)
                    if "Unterminated string" in str(parse_exc) or "Expecting value" in str(parse_exc):
                        is_likely_truncated = True
                        logger.warning("AGENT_RESPONSE_LIKELY_TRUNCATED agent=%s attempt=%s", agent_name, attempt + 1)
                    if attempt < self.max_retries and is_likely_truncated:
                        # Retry with higher token budget and request for concise response
                        logger.warning("AGENT_REASONING_TRUNCATION_RETRY agent=%s increasing_tokens=%s", agent_name, int(self.max_tokens * 1.3))
                        self.max_tokens = int(self.max_tokens * 1.3)
                        continue
                    raise parse_exc

                # Extract selected tools from LLM response
                selected_tools = parsed.get("selected_tools") or []
                narrative = parsed.get("narrative") or fallback_narrative or "Investigation complete."

                # Call selected tools and collect results
                # Pass the full case object to tools (not just case_context dict) so they have access to claim/provider
                tool_calls = {}
                tool_failures = []
                case_for_tools = case if case is not None else case_context
                for tool_name in selected_tools:
                    if tool_name in tool_registry:
                        try:
                            result = tool_registry[tool_name](case_for_tools)
                            tool_calls[tool_name] = result
                        except Exception as exc:  # pragma: no cover
                            logger.warning("AGENT_TOOL_FAILED agent=%s tool=%s error=%s", agent_name, tool_name, str(exc))
                            tool_failures.append({"tool": tool_name, "error": str(exc)})

                return AgentReasoningResult(
                    narrative=narrative,
                    selected_tools=selected_tools,
                    tool_calls=tool_calls,
                    tool_failures=tool_failures,
                    status="partial" if tool_failures else "success",
                )
            except (TimeoutError, ConnectionError, ValueError) as exc:
                if attempt < self.max_retries:
                    logger.warning("AGENT_REASONING_RETRY agent=%s attempt=%s error=%s", agent_name, attempt + 1, str(exc))
                    continue
                logger.warning("AGENT_REASONING_FAILED agent=%s error=%s", agent_name, str(exc))
                return AgentReasoningResult(
                    narrative=fallback_narrative or "Deterministic evidence remains the source of truth.",
                    status="fallback",
                    error=str(exc),
                    is_fallback=True,
                )
            except Exception as exc:  # pragma: no cover
                logger.warning("AGENT_REASONING_FAILED agent=%s error=%s", agent_name, str(exc))
                return AgentReasoningResult(
                    narrative=fallback_narrative or "Deterministic evidence remains the source of truth.",
                    status="fallback",
                    error=str(exc),
                    is_fallback=True,
                )

        return AgentReasoningResult(
            narrative=fallback_narrative or "Deterministic evidence remains the source of truth.",
            status="unavailable",
            is_fallback=True,
        )

    def _build_tool_reasoning_prompt(
        self, agent_name: str, case_context: Dict[str, Any], available_tools: List[ToolDefinition], focus_hint: Optional[str] = None
    ) -> str:
        """Build a JSON-structured prompt for agent reasoning."""
        tools_schema = [{"name": t.name, "description": t.description} for t in available_tools]

        prompt_data = {
            "TASK": f"Agent: {agent_name}",
            "SYSTEM": [
                "You are a fraud investigation specialist evaluating a claim or provider.",
                "Review the case context and select which tools to run.",
                "Return valid JSON with keys: 'selected_tools' (list of tool names), 'narrative' (string).",
                "Use ONLY the selected tools' results in the narrative.",
                "Do not claim fraud without tool-backed evidence.",
                "Do not invent numbers or risk scores.",
            ],
            "CASE_CONTEXT": case_context,
            "AVAILABLE_TOOLS": tools_schema,
            "RESPONSE_FORMAT": {
                "selected_tools": ["tool_1", "tool_2"],
                "narrative": "Summary of findings based on tool results.",
            },
        }
        
        if focus_hint:
            prompt_data["INVESTIGATION_FOCUS"] = focus_hint

        return json.dumps(prompt_data, sort_keys=True, default=str)

    def _call_groq(self, prompt: str) -> str:
        """Call Groq API and return response text."""
        if self.client is not None:
            try:
                resp = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are a fraud investigation specialist. Return valid JSON only."},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    timeout=self.timeout,
                )
                return resp.choices[0].message.content
            except Exception:
                pass

        if Groq is not None and self.api_key:
            client = Groq(api_key=self.api_key)
            resp = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a fraud investigation specialist. Return valid JSON only."},
                    {"role": "user", "content": prompt},
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                timeout=self.timeout,
            )
            return resp.choices[0].message.content

        raise ValueError("Groq client not available")

    def _parse_reasoning_response(self, response: str) -> Dict[str, Any]:
        """Parse LLM response into structured JSON.
        
        Raises:
            json.JSONDecodeError: If response cannot be parsed and is likely truncated.
        """
        if not response:
            return {"selected_tools": [], "narrative": "No response from LLM."}

        # Try to extract JSON from response
        try:
            return json.loads(response)
        except json.JSONDecodeError as exc:
            # Try to extract JSON block from markdown
            if "```json" in response:
                try:
                    start = response.index("```json") + 7
                    end = response.index("```", start)
                    return json.loads(response[start:end].strip())
                except (ValueError, json.JSONDecodeError):
                    pass
            if "```" in response:
                try:
                    start = response.index("```") + 3
                    end = response.index("```", start)
                    return json.loads(response[start:end].strip())
                except (ValueError, json.JSONDecodeError):
                    pass

            # If JSON parsing failed and response looks truncated, raise to trigger retry
            if len(response) > 100 and response.rstrip().endswith(('"', ",", "[")):
                # Response ends abruptly, likely truncated
                raise json.JSONDecodeError("Response appears truncated", response, len(response) - 1)
            
            # Fallback: extract narrative from malformed response
            logger.warning("GROQ_PARSE_ERROR response=%s error=%s", str(response)[:500] if response else "None", str(exc))
            return {"selected_tools": [], "narrative": response[:500]}

    @staticmethod
    def _load_dotenv():
        try:
            from dotenv import load_dotenv

            load_dotenv()
        except ImportError:  # pragma: no cover
            pass

    @staticmethod
    def _config_api_key() -> Optional[str]:
        """Read Groq API key from environment or config."""
        api_key = os.getenv("GROQ_API_KEY") or os.getenv("GROQ_API_KEY_FILE")
        if api_key and api_key.startswith("/"):
            try:
                with open(api_key) as f:
                    api_key = f.read().strip()
            except Exception:
                pass
        return api_key if api_key else None
