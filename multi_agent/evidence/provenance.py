from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional


class Provenance:
    """Structured provenance metadata for evidence items."""

    @staticmethod
    def build(
        *,
        source: Optional[str] = None,
        source_fields: Optional[Iterable[str]] = None,
        record_key: Optional[str] = None,
        pipeline: Optional[str] = None,
        pipeline_version: Optional[str] = None,
        limitation: Optional[str] = None,
    ) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        if source is not None:
            result["source"] = source
        if source_fields is not None:
            result["source_fields"] = list(source_fields)
        if record_key is not None:
            result["record_key"] = record_key
        if pipeline is not None:
            result["pipeline"] = pipeline
        if pipeline_version is not None:
            result["pipeline_version"] = pipeline_version
        elif pipeline is not None:
            result["pipeline_version"] = None
        if limitation:
            result["limitation"] = limitation
        return result
