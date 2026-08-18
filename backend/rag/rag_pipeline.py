"""
PHASE 4 - RAG pipeline.

Orchestrates one investigator question end to end:

    question
      -> router            which sources are needed
      -> knowledge (FAISS) if conceptual or investigative
      -> data service      if numeric or investigative      [Phase 8]
      -> risk engine       if model or investigative        [Phase 9]
      -> prompt assembly
      -> LLM
      -> grounded answer + sources + evidence

The pipeline decides WHAT to fetch. The LLM only phrases what came back. Any
source that is not connected is reported as unavailable and never substituted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.config import RETRIEVAL_TOP_K
from backend.data.structured_data_service import get_data_service
from backend.llm.llm_service import get_llm_service
from backend.llm.prompts import build_user_prompt
from backend.model.risk_engine_service import get_risk_engine
from backend.rag.retriever import RetrievedChunk, get_retriever
from backend.router.question_router import QuestionType, route_question

DISCLAIMER = (
    "This assistant explains detections; it does not determine that fraud "
    "occurred. An anomaly or elevated risk score indicates a case warranting "
    "review, not proven fraud."
)


@dataclass
class ChatResult:
    """Everything one question produces. Mirrors the API response contract."""

    answer: str
    question_type: str
    sources: list[dict[str, Any]] = field(default_factory=list)
    data_evidence: dict[str, Any] | None = None
    model_information: dict[str, Any] | None = None
    risk_score: float | None = None
    risk_factors: list[dict[str, Any]] | None = None
    routing: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    disclaimer: str = DISCLAIMER

    def to_dict(self) -> dict[str, Any]:
        return {
            "answer": self.answer,
            "question_type": self.question_type,
            "sources": self.sources,
            "data_evidence": self.data_evidence,
            "model_information": self.model_information,
            "risk_score": self.risk_score,
            "risk_factors": self.risk_factors,
            "routing": self.routing,
            "warnings": self.warnings,
            "disclaimer": self.disclaimer,
        }


def _format_knowledge(chunks: list[RetrievedChunk]) -> list[str]:
    """Render retrieved chunks for the prompt, each labelled with its source."""
    blocks = []
    for i, c in enumerate(chunks, 1):
        blocks.append(
            f"[Knowledge {i}] {c.title} > {c.section}\n"
            f"(source: {c.source}, similarity: {c.score:.3f})\n\n{c.text}"
        )
    return blocks


def _format_data(evidence) -> str | None:
    if not evidence or not evidence.available:
        return None
    lines = [f"Query: {evidence.query_description or 'structured lookup'}"]
    if evidence.entity_id:
        lines.append(f"Entity: {evidence.entity_type} {evidence.entity_id}")
    for k, v in evidence.facts.items():
        lines.append(f"- {k}: {v}")
    if evidence.peer_comparison:
        lines.append("Peer comparison:")
        for k, v in evidence.peer_comparison.items():
            lines.append(f"- {k}: {v}")
    if evidence.records:
        lines.append("Records:")
        for r in evidence.records[:12]:
            lines.append("- " + "; ".join(
                f"{k}: {v}" for k, v in r.items() if v is not None))
    return "\n".join(lines)


def _format_model(info) -> str | None:
    if not info or not info.available:
        return None
    lines = []
    if info.entity_id:
        lines.append(f"Entity: {info.entity_type} {info.entity_id}")
    if info.risk_score is not None:
        lines.append(f"Risk score: {info.risk_score}")
    if info.risk_level:
        lines.append(f"Risk level: {info.risk_level}")
    if info.risk_factors:
        lines.append("Risk factors identified by the model:")
        for f in info.risk_factors:
            bits = [f"- {f.name}"]
            if f.description:
                bits.append(f": {f.description}")
            if f.observed_value is not None:
                bits.append(f" | provider {f.observed_value}")
            if f.peer_reference is not None:
                bits.append(f" vs peer median {f.peer_reference}")
            lines.append("".join(bits))
    if info.detected_anomalies:
        lines.append("Detected anomalies: " + ", ".join(info.detected_anomalies))
    if info.detection_reason:
        lines.append(f"Detection reason: {info.detection_reason}")
    if getattr(info, "score_label", None):
        lines.append(f"Score produced by: {info.score_label}")
    if getattr(info, "priority", None):
        lines.append(f"Priority: {info.priority}")
    if getattr(info, "peer_group", None):
        lines.append(f"Peer group used by the model: {info.peer_group}")
    if getattr(info, "component_scores", None):
        lines.append("Score components (the overall score blends these; the "
                     "provider risk model's own score is one of them):")
        for c in info.component_scores:
            tag = "  [provider risk model]" if c.get("is_provider_model") else ""
            lines.append(f"- {c.get('name')}: {c.get('value')}{tag}")
    if getattr(info, "agents_executed", None) or getattr(info, "agents_skipped", None):
        if info.agents_executed:
            lines.append(f"Agents executed: {', '.join(info.agents_executed)}")
        if info.agents_skipped:
            lines.append(f"Agents SKIPPED (never examined, not a clean result): "
                         f"{', '.join(info.agents_skipped)}")
    for k, v in (getattr(info, "data_availability", None) or {}).items():
        if str(v).upper() not in ("AVAILABLE", "TRUE"):
            lines.append(f"- {k} data unavailable ({v})")
    for lim in (getattr(info, "limitations", None) or []):
        lines.append(f"- limitation: {lim}")
    if getattr(info, "score_components", None):
        lines.append("Score components (each 0-1, percentile-ranked):")
        for k, v in info.score_components.items():
            lines.append(f"- {k}: {v}")
    if info.scored_at:
        lines.append(f"Period observed: {info.scored_at}")
    if info.model_version:
        lines.append(f"Model: {info.model_version}")
    lines.append(
        "NOTE: this model was trained without any fraud ground-truth label. "
        "It identifies statistical anomalies, not confirmed fraud."
    )

    # How much weight the stated evidence can bear. This reads only what the
    # model already reports - it never recomputes or overrides the score.
    try:
        from backend.model.flag_quality import assess_provider_risk

        q = assess_provider_risk(info)
        if q.confidence != "unknown":
            lines.append("\nEVIDENCE QUALITY (assessment of the flag, not a "
                         "second score):")
            lines.append(q.as_prompt_block())
    except Exception:                                          # noqa: BLE001
        pass

    return "\n".join(lines)


class RAGPipeline:
    def __init__(self) -> None:
        self.retriever = get_retriever()
        self.data_service = get_data_service()
        self.risk_engine = get_risk_engine()
        self.llm = get_llm_service()

    def ask(self, question: str, top_k: int = RETRIEVAL_TOP_K) -> ChatResult:
        warnings: list[str] = []

        # ---- 1. Route -------------------------------------------------------
        decision = route_question(question)
        qtype = decision.question_type

        # ---- 2. Knowledge ---------------------------------------------------
        chunks: list[RetrievedChunk] = []
        if decision.needs_knowledge:
            try:
                chunks = self.retriever.retrieve(question, top_k=top_k)
            except FileNotFoundError as exc:
                warnings.append(str(exc))
            except Exception as exc:                       # noqa: BLE001
                warnings.append(f"Knowledge retrieval failed: {exc}")

            if not chunks and not warnings:
                warnings.append(
                    "No knowledge above the similarity threshold for this question."
                )

        # ---- 3. Data (Phase 8) ----------------------------------------------
        data_evidence = None
        if decision.needs_data:
            data_evidence = self.data_service.query(question, decision.entities)
            if not data_evidence.available:
                warnings.append(data_evidence.message)

        # ---- 4. Model (Phase 9) ---------------------------------------------
        model_info = None
        if decision.needs_model:
            model_info = self.risk_engine.get_risk(decision.entities)
            if not model_info.available:
                warnings.append(model_info.message)

        # ---- 5. Prompt ------------------------------------------------------
        user_prompt = build_user_prompt(
            question=question,
            question_type=qtype.value,
            knowledge_blocks=_format_knowledge(chunks),
            data_block=_format_data(data_evidence),
            model_block=_format_model(model_info),
        )

        # ---- 6. Generate ----------------------------------------------------
        llm_response = self.llm.generate(user_prompt)

        if llm_response.available:
            answer = llm_response.text
        else:
            answer = self._fallback_answer(chunks, qtype)
            warnings.append(
                f"Answer generation unavailable ({llm_response.error}). "
                "Showing retrieved knowledge instead."
            )

        return ChatResult(
            answer=answer,
            question_type=qtype.value,
            sources=[c.as_source() for c in chunks],
            data_evidence=data_evidence.to_dict() if data_evidence else None,
            model_information=model_info.to_dict() if model_info else None,
            risk_score=model_info.risk_score if model_info and model_info.available else None,
            risk_factors=(
                [f.to_dict() for f in model_info.risk_factors]
                if model_info and model_info.available and model_info.risk_factors
                else None
            ),
            routing=decision.to_dict(),
            warnings=warnings,
        )

    @staticmethod
    def _fallback_answer(chunks: list[RetrievedChunk],
                         qtype: QuestionType) -> str:
        """
        Used when the LLM is unavailable. Returns retrieved knowledge verbatim
        rather than a generated answer - degraded, but never fabricated.
        """
        if not chunks:
            return (
                "Answer generation is not configured, and no relevant knowledge "
                "was retrieved for this question."
            )
        parts = [
            "Answer generation is not configured, so here is the relevant "
            "knowledge retrieved from the knowledge base:\n"
        ]
        for i, c in enumerate(chunks, 1):
            parts.append(f"**{i}. {c.title} — {c.section}**\n{c.text}")
        return "\n\n".join(parts)


_pipeline: RAGPipeline | None = None


def get_pipeline() -> RAGPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = RAGPipeline()
    return _pipeline
