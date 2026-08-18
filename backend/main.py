"""
PHASE 5 - FastAPI application.

Run from the project root:

    uvicorn backend.main:app --reload --port 8000

Interactive API docs:  http://<host>:<port>/docs
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.chat import router as chat_router
from backend.config import CORS_ALLOWED_ORIGINS

app = FastAPI(
    title="Healthcare FWA - AI Investigation Assistant",
    description=(
        "Investigator-facing assistant for a Claims Fraud, Waste and Abuse "
        "detection platform. Explains existing detections using curated domain "
        "knowledge, structured dataset evidence, and existing risk engine "
        "output. Does not perform fraud detection and does not determine that "
        "fraud occurred."
    ),
    version="0.3.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router, prefix="/api", tags=["chat"])


@app.get("/")
def root() -> dict:
    return {
        "service": "Healthcare FWA Investigation Assistant",
        "version": "0.3.0",
        "docs": "/docs",
        "endpoints": {
            "chat": "POST /api/chat",
            "status": "GET /api/status",
            "health": "GET /health",
        },
    }


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
