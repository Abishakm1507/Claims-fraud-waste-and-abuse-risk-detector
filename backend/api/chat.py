"""
PHASE 5 - Chat API routes.

    POST /api/chat      ask a question
    GET  /api/status    which sources are connected

RESPONSE CONTRACT:
The response shape is fixed from the start and does not change as later phases
land. data_evidence, model_information, risk_score and risk_factors return null
today because those sources are not connected. When Phase 8 and Phase 9 arrive,
the same fields populate - no client change required.

Fields are never filled with placeholder values to make the response look
complete.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.data.structured_data_service import get_data_service
from backend.llm.llm_service import get_llm_service
from backend.model.risk_engine_service import get_risk_engine
from backend.rag.rag_pipeline import get_pipeline

router = APIRouter()


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000,
                          description="The investigator's question")
    top_k: int = Field(8, ge=1, le=20,
                       description="How many knowledge chunks to retrieve")


class ChatResponse(BaseModel):
    answer: str
    question_type: str
    sources: list[dict[str, Any]] = []
    data_evidence: dict[str, Any] | None = None
    model_information: dict[str, Any] | None = None
    risk_score: float | None = None
    risk_factors: list[dict[str, Any]] | None = None
    routing: dict[str, Any] = {}
    warnings: list[str] = []
    disclaimer: str = ""


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    try:
        result = get_pipeline().ask(question, top_k=request.top_k)
    except FileNotFoundError as exc:
        # Index not built yet - actionable message rather than a 500.
        raise HTTPException(
            status_code=503,
            detail=f"Knowledge index not available. {exc}",
        ) from exc
    except Exception as exc:                              # noqa: BLE001
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process question: {type(exc).__name__}: {exc}",
        ) from exc

    return ChatResponse(**result.to_dict())


@router.get("/status")
def status() -> dict[str, Any]:
    """Which of the three sources are connected. Used by the UI on load."""
    from backend.config import FAISS_INDEX_PATH

    knowledge_ready = FAISS_INDEX_PATH.exists()

    from backend.data import warehouse as wh

    data_status = get_data_service().status()
    try:
        data_status["reading_from"] = wh.source()
        from backend.data.curated_loader import find_curated_dir
        d = find_curated_dir()
        data_status["curated_path"] = str(d) if d else None
    except Exception:                                          # noqa: BLE001
        pass

    return {
        "knowledge": {
            "connected": knowledge_ready,
            "phase": 3,
            "message": (
                "Knowledge base indexed and searchable."
                if knowledge_ready
                else "Index not built. Run: python scripts/build_index.py"
            ),
        },
        "data": data_status,
        "model": get_risk_engine().status(),
        "llm": get_llm_service().status(),
    }
