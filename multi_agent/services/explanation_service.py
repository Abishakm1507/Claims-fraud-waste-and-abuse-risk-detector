from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from multi_agent.synthesis import InvestigationResult

try:
    from groq import Groq
except ImportError:  # pragma: no cover
    Groq = None

logger = logging.getLogger(__name__)

_MISSING = object()


@dataclass
class InvestigationExplanation:
    executive_summary: str = ""
    key_findings: List[Dict[str, str]] = field(default_factory=list)
    risk_reasoning: str = ""
    supporting_evidence: List[str] = field(default_factory=list)
    recommended_investigation_actions: List[str] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)
    generated_by: str = "Groq"
    model: str = "not-configured"
    timestamp: Optional[str] = None
    status: str = "unavailable"
    error: str = ""
    is_fallback: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "executive_summary": self.executive_summary,
            "key_findings": self.key_findings,
            "risk_reasoning": self.risk_reasoning,
            "supporting_evidence": self.supporting_evidence,
            "recommended_investigation_actions": self.recommended_investigation_actions,
            "limitations": self.limitations,
            "generated_by": self.generated_by,
            "model": self.model,
            "timestamp": self.timestamp,
            "status": self.status,
            "error": self.error,
            "is_fallback": self.is_fallback,
        }


class InvestigationExplanationService:
    """Explanation layer that summarizes deterministic evidence without changing risk outputs."""

    DEFAULT_MODEL = "llama-3.3-70b-versatile"

    def __init__(
        self,
        api_key: Optional[str] | object = _MISSING,
        model: Optional[str] = None,
        client: Any = None,
        timeout: float = 15.0,
        enabled: bool = True,
        max_retries: int = 2,
        temperature: float = 0.1,
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

    @staticmethod
    def _normalize_error_message(error: Any) -> str:
        message = str(error or "").strip()
        lowered = message.lower()
        if "rate limit" in lowered or "429" in lowered:
            return "rate limit exceeded"
        if "timed out" in lowered or "timeout" in lowered:
            return "timeout"
        if "connection" in lowered:
            return "connection error"
        if "auth" in lowered or "401" in lowered:
            return "authentication failed"
        if "500" in lowered or "server error" in lowered:
            return "server error"
        if "validation" in lowered or "unsupported" in lowered:
            return "validation failure"
        if not message:
            return "GenAI service unavailable."
        return message

    @staticmethod
    def _failure_status(error: Any) -> str:
        message = str(error or "").lower()
        if any(
            token in message
            for token in (
                "rate limit",
                "429",
                "auth",
                "401",
                "500",
                "server error",
                "validation",
                "unsupported",
                "timeout",
                "timed out",
                "connection",
            )
        ):
            return "fallback"
        return "unavailable"

    def generate_explanation(self, investigation_result: InvestigationResult) -> InvestigationExplanation:
        if not self.enabled:
            return InvestigationExplanation(status="disabled", error="GenAI explanation disabled by configuration.", model=self.model)
        if not investigation_result:
            return InvestigationExplanation(status="unavailable", error="No investigation result supplied.", model=self.model)
        if not self.api_key:
            return InvestigationExplanation(status="unavailable", error="Missing GROQ_API_KEY.", model=self.model)
        if Groq is None and self.client is None:
            return InvestigationExplanation(status="unavailable", error="Groq SDK is not installed.", model=self.model)

        context = self._authoritative_context(investigation_result)
        prompt = self._build_prompt(context)

        for attempt in range(self.max_retries + 1):
            try:
                response = self._call_groq(prompt)
                parsed = self._parse_response(response)
                self._validate_response(parsed, context)
                explanation = InvestigationExplanation(
                    executive_summary=parsed.get("summary") or parsed.get("executive_summary") or "No executive summary available.",
                    key_findings=self._clean_key_findings(parsed.get("key_findings") or []),
                    risk_reasoning=parsed.get("risk_reasoning") or "The investigation outcome was generated from deterministic evidence only.",
                    supporting_evidence=self._clean_text_list(parsed.get("supporting_evidence") or []),
                    recommended_investigation_actions=self._clean_text_list(parsed.get("recommended_investigation_actions") or []),
                    limitations=self._clean_text_list(parsed.get("limitations") or []),
                    generated_by="Groq",
                    model=self.model,
                    timestamp=self._timestamp(),
                    status="generated",
                )
                logger.info("GENAI_EXPLANATION_ACCEPTED case_id=%s model=%s", context.get("case_id"), self.model)
                return explanation
            except (TimeoutError, ConnectionError, ValueError, TypeError) as exc:
                normalized_error = self._normalize_error_message(exc)
                failure_status = self._failure_status(normalized_error)
                if attempt < self.max_retries:
                    logger.warning("GENAI_RETRY case_id=%s attempt=%s error=%s", context.get("case_id"), attempt + 1, normalized_error)
                    continue
                logger.warning("GENAI_REQUEST_FAILED case_id=%s error=%s", context.get("case_id"), normalized_error)
                return self._fallback_explanation(
                    investigation_result,
                    normalized_error,
                    status=failure_status,
                    is_validation_failure=isinstance(exc, ValueError) and failure_status == "fallback",
                )
            except Exception as exc:  # pragma: no cover
                normalized_error = self._normalize_error_message(exc)
                failure_status = self._failure_status(normalized_error)
                logger.warning("GENAI_REQUEST_FAILED case_id=%s error=%s", context.get("case_id"), normalized_error)
                return self._fallback_explanation(
                    investigation_result,
                    normalized_error,
                    status=failure_status,
                    is_validation_failure=failure_status == "fallback",
                )

        return self._fallback_explanation(investigation_result, "GenAI service unavailable.", status="unavailable", is_validation_failure=False)

    def _call_groq(self, prompt: str) -> str:
        if self.client is not None:
            started = time.time()
            try:
                resp = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": self._system_prompt()},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=self.temperature,
                    max_tokens=1000,
                    timeout=self.timeout,
                )
            except AttributeError:
                try:
                    resp = self.client.completions.create(
                        model=self.model,
                        messages=[
                            {"role": "system", "content": self._system_prompt()},
                            {"role": "user", "content": prompt},
                        ],
                        temperature=self.temperature,
                        max_tokens=500,
                        timeout=self.timeout,
                    )
                except AttributeError:
                    try:
                        resp = self.client.chat.Completions(self.client).create(
                            model=self.model,
                            messages=[
                                {"role": "system", "content": self._system_prompt()},
                                {"role": "user", "content": prompt},
                            ],
                            temperature=self.temperature,
                            max_tokens=1000,
                            timeout=self.timeout,
                        )
                    except AttributeError as exc:
                        raise AttributeError("Groq client does not expose a completions API") from exc
            latency_ms = (time.time() - started) * 1000
            logger.info("GENAI_REQUEST_COMPLETED model=%s latency_ms=%s", self.model, round(latency_ms, 1))
            try:
                return resp.choices[0].message.content
            except Exception:
                return "{}"

        client = Groq(api_key=self.api_key, timeout=self.timeout)
        started = time.time()
        resp = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self._system_prompt()},
                {"role": "user", "content": prompt},
            ],
            temperature=self.temperature,
            max_tokens=1000,
            timeout=self.timeout,
        )
        latency_ms = (time.time() - started) * 1000
        logger.info("GENAI_REQUEST_COMPLETED model=%s latency_ms=%s", self.model, round(latency_ms, 1))
        return resp.choices[0].message.content

    def _build_prompt(self, context: Dict[str, Any]) -> str:
        evidence_ids_list = context.get("evidence_ids", [])
        evidence_id_refs = "\n".join(f"  - {eid}" for eid in evidence_ids_list) if evidence_ids_list else "  - (no evidence IDs available)"
        
        return json.dumps(
            {
                "SYSTEM_INSTRUCTIONS": [
                    "The InvestigationCase and its risk synthesis are authoritative.",
                    "Evidence and evidence IDs are authoritative.",
                    "Do not invent facts, peer baselines, dates, provider behavior, diagnosis codes, procedures, or payment amounts.",
                    "If data is unavailable, say exactly that.",
                    "Do not override deterministic risk outputs.",
                    "Do not claim fraud unless the supplied evidence explicitly supports the conclusion.",
                    "Return only a JSON object with summary, risk_interpretation, key_findings, evidence_references, limitations, recommended_review_actions.",
                ],
                "EVIDENCE_ID_REFERENCE_GUIDE": f"Use ONLY these evidence IDs when referencing findings:\n{evidence_id_refs}",
                "INVESTIGATION_DATA": {
                    "case_id": context.get("case_id"),
                    "claim_id": context.get("claim_id"),
                    "provider_id": context.get("provider_id"),
                    "claim_type": context.get("claim_type"),
                    "final_risk_level": context.get("final_risk_level"),
                    "final_risk_priority": context.get("final_risk_priority"),
                    "investigation_risk_score": context.get("investigation_risk_score"),
                    "agent_errors": context.get("agent_errors", {}),
                },
                "EVIDENCE": context.get("evidence", []),
                "KEY_FINDINGS": context.get("findings", []),
                "USER_INVESTIGATOR_QUESTION": "Explain this case using only the supplied evidence and deterministic risk context.",
            },
            sort_keys=True,
            default=str,
        )

    def _authoritative_context(self, investigation_result: InvestigationResult) -> Dict[str, Any]:
        evidence = []
        evidence_ids = []
        for finding in investigation_result.findings:
            ev = getattr(finding, "evidence", None)
            rule_name = getattr(finding, "rule", None)
            item = {
                "agent": getattr(finding, "agent", None),
                "category": getattr(finding, "category", None),
                "rule": rule_name,
                "severity": getattr(finding, "severity", None),
                "description": getattr(finding, "description", None),
            }
            if isinstance(ev, dict):
                item.update(ev)
                for key, value in ev.items():
                    if key == "evidence_id":
                        evidence_ids.append(str(value))
                    elif isinstance(value, dict) and "evidence_id" in value:
                        evidence_ids.append(str(value["evidence_id"]))
            # Add rule name as a valid evidence identifier
            if rule_name:
                evidence_ids.append(str(rule_name))
            evidence.append(item)
        return {
            "case_id": investigation_result.case_id,
            "claim_id": investigation_result.claim_id,
            "provider_id": investigation_result.provider_id,
            "claim_type": investigation_result.claim_type,
            "final_risk_level": investigation_result.final_risk_level,
            "final_risk_priority": investigation_result.final_risk_priority,
            "investigation_risk_score": investigation_result.investigation_risk_score,
            "investigation_priority": investigation_result.investigation_priority,
            "agent_errors": investigation_result.agent_errors,
            "findings": evidence,
            "evidence": evidence,
            "evidence_ids": evidence_ids,
        }

    @staticmethod
    def _system_prompt() -> str:
        return (
            "SYSTEM INSTRUCTIONS: "
            "The deterministic investigation result is authoritative. Evidence and evidence IDs are authoritative. "
            "Groq is an interpreter only. Do not invent facts, provide unsupported ratios, create dates, create peer groups, create diagnoses, create procedure codes, or claim fraud. "
            "If a value is unavailable, say it is unavailable. If a finding is missing, say it is missing. "
            "Do not override numerical risk, risk category, or priority. "
            "EVIDENCE REFERENCES: When referencing evidence, use ONLY the exact evidence IDs provided in EVIDENCE_ID_REFERENCE_GUIDE. "
            "Never use array indices like EVIDENCE[0] or EVIDENCE[1]. Always use the actual rule name or evidence ID. "
            "CRITICAL: Return ONLY raw valid JSON with NO markdown code blocks, NO backticks, NO triple backticks, NO explanation text. "
            "The output must be valid JSON with keys: summary, risk_interpretation, key_findings, evidence_references, limitations, recommended_review_actions. "
            "Each key finding must identify evidence IDs using the exact names from EVIDENCE_ID_REFERENCE_GUIDE. "
            "Start your response with { and end with } with NO other text."
        )

    @staticmethod
    def _parse_response(response: Any) -> Dict[str, Any]:
        if response is None:
            raise ValueError("Empty response from Groq.")
        if isinstance(response, dict):
            payload = response
        else:
            try:
                response_str = str(response).strip()
                logger.debug("GROQ_RAW_RESPONSE: %s", response_str[:500] if len(response_str) > 500 else response_str)
                
                # Strip markdown code fences if present
                if response_str.startswith("```"):
                    lines = response_str.split("\n")
                    # Remove opening fence (```, ```json, etc.)
                    if lines[0].startswith("```"):
                        lines = lines[1:]
                    # Remove closing fence if present
                    if lines and lines[-1].strip() == "```":
                        lines = lines[:-1]
                    response_str = "\n".join(lines).strip()
                    logger.debug("GROQ_STRIPPED_RESPONSE: %s", response_str[:500] if len(response_str) > 500 else response_str)
                
                payload = json.loads(response_str)
            except (TypeError, ValueError) as exc:
                logger.error("GROQ_PARSE_ERROR response=%s error=%s", str(response)[:500] if response else "None", str(exc))
                raise ValueError("Malformed model response") from exc
        if not isinstance(payload, dict):
            raise ValueError("Groq response must be a JSON object.")
        return payload

    @classmethod
    def _validate_response(cls, payload: Dict[str, Any], context: Dict[str, Any]) -> None:
        if not payload:
            raise ValueError("Empty model payload.")

        summary = str(payload.get("summary") or payload.get("executive_summary") or "")
        risk_interpretation = payload.get("risk_interpretation")
        if isinstance(risk_interpretation, dict):
            category = str(risk_interpretation.get("category") or "").upper()
            priority = str(risk_interpretation.get("priority") or "").upper()
            expected_category = str(context.get("final_risk_level") or "").upper()
            expected_priority = str(context.get("final_risk_priority") or "").upper()
            if category and category != expected_category:
                raise ValueError("Risk category override is unsupported.")
            if priority and priority != expected_priority:
                raise ValueError("Risk priority override is unsupported.")

        if re.search(r"committed fraud|proved fraud|confirmed fraud|fraudulent provider", summary, re.IGNORECASE):
            raise ValueError("Fraud confirmation language is unsupported without explicit evidence.")

        for phrase in [
            "ignore all previous instructions",
            "increased recently",
            "q4 2024",
            "cardiology providers in texas",
            "billing analysis found abnormal payment behavior",
            "peer comparison shows",
            "cpt 99213",
            "diagnosis was inconsistent",
            "detected a temporal spike",
        ]:
            if phrase in summary.lower():
                raise ValueError("Unsupported factual claim in explanation.")

        findings = payload.get("key_findings") or []
        if not isinstance(findings, list):
            raise ValueError("key_findings must be a list.")

        allowed_evidence_ids = {str(item) for item in context.get("evidence_ids", [])}
        for finding in findings:
            if not isinstance(finding, dict):
                raise ValueError("Each key finding must be an object.")
            evidence_ids = finding.get("evidence_ids") or finding.get("evidence_id") or []
            if isinstance(evidence_ids, str):
                evidence_ids = [evidence_ids]
            elif isinstance(evidence_ids, dict):
                evidence_ids = [evidence_ids]
            for evidence_id in evidence_ids:
                # If evidence_id is a dict, extract the actual ID
                actual_id = evidence_id
                if isinstance(evidence_id, dict):
                    # Try multiple possible keys
                    actual_id = (
                        evidence_id.get("evidence_id") or
                        evidence_id.get("rule") or
                        evidence_id.get("id") or
                        evidence_id.get("name")
                    )
                    if not actual_id:
                        # If no ID found, it's invalid
                        logger.warning("EVIDENCE_ID_NOT_FOUND evidence_id=%s allowed=%s", evidence_id, allowed_evidence_ids)
                        raise ValueError(f"Evidence reference is not supported by the case: {evidence_id}")
                
                if str(actual_id) not in allowed_evidence_ids:
                    logger.warning("EVIDENCE_ID_NOT_FOUND evidence_id=%s allowed=%s", actual_id, allowed_evidence_ids)
                    raise ValueError(f"Evidence reference is not supported by the case: {actual_id}")

            text = " ".join(
                str(part)
                for part in [
                    finding.get("finding"),
                    finding.get("description"),
                    finding.get("evidence"),
                ]
            ).lower()
            if re.search(r"q[1-4]\s+20\d\d|\b(cpt|hcpcs|icd|dx)\b|\bcardiology\b|\btexas\b|\bpeer median\b.*\d+x|\b\d+(?:\.\d+)?x\b", text):
                if not allowed_evidence_ids:
                    raise ValueError("Unsupported factual claim in explanation.")

        evidence_references = payload.get("evidence_references") or []
        if isinstance(evidence_references, list):
            for evidence_id in evidence_references:
                # If evidence_id is a dict, extract the actual ID
                actual_id = evidence_id
                if isinstance(evidence_id, dict):
                    actual_id = (
                        evidence_id.get("evidence_id") or
                        evidence_id.get("rule") or
                        evidence_id.get("id") or
                        evidence_id.get("name")
                    )
                    if not actual_id:
                        actual_id = evidence_id
                
                if str(actual_id) not in allowed_evidence_ids and allowed_evidence_ids:
                    logger.warning("EVIDENCE_REFERENCE_NOT_FOUND evidence_id=%s allowed=%s", actual_id, allowed_evidence_ids)
                    raise ValueError(f"Evidence reference is not supported by the case: {actual_id}")

        explanation_text = " ".join(
            str(part)
            for part in [
                summary,
                payload.get("risk_reasoning") or "",
                payload.get("limitations") or "",
                *[
                    item.get("finding") if isinstance(item, dict) else ""
                    for item in (payload.get("key_findings") or [])
                ],
                *[
                    item.get("evidence") if isinstance(item, dict) else ""
                    for item in (payload.get("key_findings") or [])
                ],
            ]
        )
        if re.search(r"\b(?:q[1-4]|quarter|month|year|date|temporal|recently)\b", explanation_text, re.IGNORECASE) and re.search(r"\b(19|20)\d{2}\b", explanation_text):
            raise ValueError("Unsupported date claim in explanation.")

        known_ratios = []
        for item in context.get("evidence", []) or []:
            if isinstance(item, dict):
                for key in ("deviation_ratio", "ratio", "peer_ratio", "payment_to_charge_ratio"):
                    if key in item and item[key] is not None:
                        known_ratios.append(float(item[key]))
        ratio_matches = re.findall(r"\b(\d+(?:\.\d+)?)x\b", explanation_text, re.IGNORECASE)
        if ratio_matches:
            supported = False
            for match in ratio_matches:
                value = float(match)
                if any(abs(value - ratio) < 1e-9 for ratio in known_ratios):
                    supported = True
            if not supported and not known_ratios:
                raise ValueError("Unsupported ratio claim in explanation.")
            if not supported and known_ratios:
                raise ValueError("Unsupported ratio claim in explanation.")

    @staticmethod
    def _clean_key_findings(items: List[Any]) -> List[Dict[str, str]]:
        cleaned: List[Dict[str, str]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            evidence_ids = item.get("evidence_ids") or item.get("evidence_id") or []
            if isinstance(evidence_ids, str):
                evidence_ids = [evidence_ids]
            evidence_text = item.get("evidence") or item.get("description") or "Evidence available."
            cleaned_record = {
                "agent": str(item.get("agent") or "unknown"),
                "finding": str(item.get("finding") or item.get("title") or "Finding"),
                "evidence": str(evidence_text),
            }
            if evidence_ids:
                cleaned_record["evidence_ids"] = [str(value) for value in evidence_ids]
                cleaned_record["evidence"] = f"{evidence_text} Evidence IDs: {', '.join(str(value) for value in evidence_ids)}"
            cleaned.append(cleaned_record)
        return cleaned

    @staticmethod
    def _clean_text_list(items: Any) -> List[str]:
        if not items:
            return []
        if isinstance(items, str):
            return [items]
        cleaned: List[str] = []
        for item in items:
            if isinstance(item, dict):
                text = item.get("text") or item.get("value") or item.get("description") or str(item)
                cleaned.append(str(text))
            else:
                cleaned.append(str(item))
        return cleaned

    @staticmethod
    def _timestamp() -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    @staticmethod
    def _load_dotenv() -> None:
        project_root = Path(__file__).resolve().parents[2]
        env_path = project_root / ".env"
        if not env_path.exists():
            return
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())

    @staticmethod
    def _config_api_key() -> Optional[str]:
        project_root = Path(__file__).resolve().parents[2]
        env_path = project_root / ".env"
        if not env_path.exists():
            return None
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() == "GROQ_API_KEY":
                return value.strip()
        return None

    def _fallback_explanation(
        self,
        investigation_result: InvestigationResult,
        error: str,
        status: str = "fallback",
        is_validation_failure: bool = False,
    ) -> InvestigationExplanation:
        level = investigation_result.final_risk_level or investigation_result.investigation_priority or "UNKNOWN"
        summary = (
            "GenAI explanation unavailable. The case is classified as "
            f"{level} risk based on the deterministic investigation results. Review the listed findings and evidence."
        )
        normalized_error = self._normalize_error_message(error)
        return InvestigationExplanation(
            executive_summary=summary,
            key_findings=[{"agent": "system", "finding": "Deterministic findings remain authoritative.", "evidence": "InvestigationCase and risk synthesis are authoritative."}],
            risk_reasoning="The deterministic risk output remains authoritative because Groq was unavailable or the generated explanation failed validation.",
            supporting_evidence=["Deterministic findings", "Deterministic evidence", "Deterministic risk synthesis"],
            recommended_investigation_actions=["Review the listed findings and evidence in the investigation case.", "Validate the deterministic risk output before escalation."],
            limitations=["GenAI explanation unavailable.", "Deterministic evidence and risk synthesis remain the source of truth."],
            generated_by="Groq",
            model=self.model,
            timestamp=None,
            status=status,
            error=normalized_error,
            is_fallback=status == "fallback",
        )
