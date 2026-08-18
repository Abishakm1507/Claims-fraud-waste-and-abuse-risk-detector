from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, Optional

try:
    from groq import Groq
except ImportError:  # pragma: no cover
    Groq = None


def _load_env_once() -> None:
    try:
        from pathlib import Path
        project_root = Path(__file__).resolve().parents[1]
        env_path = project_root / ".env"
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith("#") or "=" not in stripped:
                    continue
                key, value = stripped.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())
    except Exception:
        pass


class StructuredGroqExplainer:
    """Compact Groq-based explainer that accepts structured evidence only."""

    DEFAULT_MODEL = "llama-3.3-70b-versatile"

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None, timeout: float = 15.0):
        _load_env_once()
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        self.model = model or os.getenv("GROQ_MODEL") or self.DEFAULT_MODEL
        self.timeout = float(os.getenv("GROQ_TIMEOUT", str(timeout)))

    def generate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not payload:
            raise ValueError("Structured explanation payload is required.")
        if not self.api_key:
            raise ValueError("Missing GROQ_API_KEY.")
        if Groq is None:
            raise RuntimeError("Groq SDK is not installed.")

        prompt = self._build_prompt(payload)
        started = time.time()
        client = Groq(api_key=self.api_key, timeout=self.timeout)
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self._system_prompt()},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=500,
        )

        text = response.choices[0].message.content
        usage = getattr(response, "usage", None)
        parsed = json.loads(text)

        latency_ms = round((time.time() - started) * 1000, 2)
        result = {
            "status": "READY",
            "model": self.model,
            "summary": parsed.get("summary") or "No summary available.",
            "key_reasons": parsed.get("key_reasons") or [],
            "supporting_evidence": parsed.get("supporting_evidence") or [],
            "recommended_action": parsed.get("recommended_action") or "Review the available evidence and model output.",
            "input_tokens": getattr(usage, "prompt_tokens", None) if usage is not None else None,
            "output_tokens": getattr(usage, "completion_tokens", None) if usage is not None else None,
            "total_tokens": getattr(usage, "total_tokens", None) if usage is not None else None,
            "latency_ms": latency_ms,
        }
        return result

    def _system_prompt(self) -> str:
        return (
            "You are a cautious investigator-facing explanation assistant. "
            "Use only the structured evidence supplied in the payload. "
            "Never claim fraud or invent facts. "
            "Explain in human-readable language that the entity shows elevated risk based on model and investigation evidence, but requires further review. "
            "Clearly separate model evidence, investigation evidence, and LLM interpretation. "
            "If evidence is missing, say exactly that. "
            "Return only valid JSON with keys: summary, key_reasons, supporting_evidence, recommended_action."
        )

    def _build_prompt(self, payload: Dict[str, Any]) -> str:
        compact = {
            "entity_type": payload.get("entity_type"),
            "entity_id": payload.get("entity_id"),
            "claim_type": payload.get("claim_type"),
            "risk": {
                "score": payload.get("risk_score"),
                "rank": payload.get("risk_rank"),
                "band": payload.get("risk_band"),
            },
            "shap": {
                "status": payload.get("shap_status"),
                "top_features": payload.get("shap_top_features") or [],
                "shap_values": payload.get("shap_values") or [],
            },
            "model_evidence": payload.get("model_evidence") or {},
            "multi_agent_evidence": payload.get("multi_agent_evidence") or {},
            "instructions": [
                "Explain why this entity received its risk score using only the supplied evidence.",
                "Connect the top model features with the investigation findings.",
                "Use cautious language like 'indicates elevated risk', 'shows an anomalous pattern', and 'requires further investigation'.",
                "Do not invent missing facts or claim fraud.",
                "If SHAP or investigation evidence are unavailable, clearly say so.",
            ],
        }
        return json.dumps(compact, sort_keys=True, default=str)
