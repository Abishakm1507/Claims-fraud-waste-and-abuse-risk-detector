"""
Live bridge to the multi-agent orchestrator.

WHAT THIS DOES
When this module is deployed inside the main project repo, the multi-agent
package is importable. This bridge calls it directly:

    Orchestrator().investigate_provider(npi)   -> InvestigationResult
    Orchestrator().investigate_claim(claim_id) -> InvestigationResult

then converts the result to the canonical handoff contract via their own
`build_rag_handoff()`, and parses it. So the synthesis score, findings and
evidence come from THEIR code, not from a reimplementation here.

WHY IT IS OPTIONAL
Developed standalone, the multi_agent package is absent. Every entry point
returns None in that case rather than raising, so the assistant degrades to the
provider risk model instead of failing. Their integration guide is explicit that
missing data must be surfaced, not fabricated - so an unavailable orchestrator
is reported, never filled in.

WHY THEIR HANDOFF BUILDER IS USED
Their guide forbids recomputing risk. Calling `build_rag_handoff()` rather than
reading the result object directly means the contract, its validation, and its
limitations are produced by the system that owns them.
"""

from __future__ import annotations

import os
from typing import Any

_orchestrator = None
_import_error: str | None = None
_checked = False

# Investigating a provider runs several agents; caching avoids re-running the
# whole pipeline when an investigator asks a follow-up about the same case.
_cache: dict[str, Any] = {}
CACHE_LIMIT = 64


def _ensure_repo_on_path() -> None:
    """
    Put the repo root on sys.path if it is not already there.

    When this module is deployed at repo/rag/ and the server is started from
    that directory, `multi_agent` (at repo/) is not importable even though it
    is present. That failure looks identical to "not integrated yet", so the
    repo root is located and added explicitly.
    """
    import sys
    from pathlib import Path

    here = Path(__file__).resolve()
    for level in list(here.parents)[:8]:
        if (level / "multi_agent").is_dir() or (level / ".git").exists():
            if str(level) not in sys.path:
                sys.path.insert(0, str(level))
            if (level / "multi_agent").is_dir():
                return


def _load():
    """Import and construct the orchestrator once. Never raises."""
    global _orchestrator, _import_error, _checked
    if _checked:
        return _orchestrator
    _checked = True

    if os.getenv("DISABLE_AGENT_BRIDGE", "").lower() in ("1", "true", "yes"):
        _import_error = "Agent bridge disabled by DISABLE_AGENT_BRIDGE."
        return None

    _ensure_repo_on_path()

    try:
        from multi_agent.orchestrator import Orchestrator

        _orchestrator = Orchestrator()
    except ImportError as exc:
        _import_error = (
            f"The multi_agent package is not importable ({exc}). The assistant "
            "is running outside the main project repo, so agent investigations "
            "are unavailable."
        )
    except Exception as exc:                                   # noqa: BLE001
        _import_error = (
            f"The multi-agent orchestrator could not be initialised "
            f"({type(exc).__name__}: {exc})."
        )
    return _orchestrator


def is_available() -> bool:
    return _load() is not None


def status() -> dict[str, Any]:
    available = is_available()
    return {
        "connected": available,
        "message": ("Multi-agent orchestrator available."
                    if available else (_import_error or "Not initialised.")),
        "cached_cases": len(_cache),
    }


AGENT_TIMEOUT = int(os.getenv("AGENT_TIMEOUT_SECONDS", "45"))


_pool = None


def _with_timeout(fn, *args):
    """
    Run an agent investigation with a ceiling.

    Investigating a provider runs several agents over the claim store. A slow
    or hung run must not hold an investigator's request open indefinitely -
    falling back to the provider risk model is far better than no answer.

    The executor is module-level and deliberately NOT used as a context
    manager: `with ThreadPoolExecutor(...)` blocks on exit until the worker
    finishes, which would make the timeout meaningless - the call would still
    take as long as the hung investigation. Abandoning the future returns
    immediately; the orphaned thread ends on its own.

    Threads rather than signals, so this behaves the same on Windows.
    """
    global _pool
    import concurrent.futures as cf

    if _pool is None:
        _pool = cf.ThreadPoolExecutor(max_workers=4,
                                      thread_name_prefix="agent-bridge")

    future = _pool.submit(fn, *args)
    try:
        return future.result(timeout=AGENT_TIMEOUT)
    except cf.TimeoutError as exc:
        future.cancel()             # best effort; a running task ignores this
        raise TimeoutError(
            f"agent investigation exceeded {AGENT_TIMEOUT}s") from exc


def _to_handoff(result) -> dict | None:
    """Convert an InvestigationResult into the canonical handoff payload."""
    orch = _load()
    if orch is None or result is None:
        return None
    try:
        from multi_agent.rag.handoff import build_rag_handoff

        case = orch.to_investigation_case(result)
        request = build_rag_handoff(case)
        return request.model_dump(mode="json", exclude_none=True)
    except Exception as exc:                                   # noqa: BLE001
        print(f"  ! could not build agent handoff: {type(exc).__name__}: {exc}")
        return None


def investigate_provider(npi: str):
    """
    Run a multi-agent investigation for a provider.

    Returns a parsed HandoffCase, or None when the orchestrator is unavailable
    or the provider is unknown to it.
    """
    orch = _load()
    if orch is None:
        return None

    key = f"provider:{npi}"
    if key in _cache:
        return _cache[key]          # may be None: a cached failure

    try:
        result = _with_timeout(orch.investigate_provider, str(npi))
    except (TimeoutError, Exception) as exc:                   # noqa: BLE001
        # Cache the failure. Without this, a provider the orchestrator cannot
        # investigate is retried on every follow-up question - and a TIMEOUT
        # failure would cost the full timeout again each time.
        print(f"  ! agent investigation unavailable for provider {npi}: "
              f"{type(exc).__name__}: {exc}")
        _remember(key, None)
        return None

    case = _finish(result, key)
    return case


def investigate_claim(claim_id: str):
    """Run a multi-agent investigation for a claim."""
    orch = _load()
    if orch is None:
        return None

    key = f"claim:{claim_id}"
    if key in _cache:
        return _cache[key]          # may be None: a cached failure

    try:
        result = _with_timeout(orch.investigate_claim, str(claim_id))
    except (TimeoutError, Exception) as exc:                   # noqa: BLE001
        print(f"  ! agent investigation unavailable for claim {claim_id}: "
              f"{type(exc).__name__}: {exc}")
        _remember(key, None)
        return None

    case = _finish(result, key)
    return case


def _remember(key, value):
    """Store a result, evicting the oldest entry when full."""
    if len(_cache) >= CACHE_LIMIT:
        _cache.pop(next(iter(_cache)))
    _cache[key] = value


def _finish(result, key):
    """
    Build, parse and cache. Failures are cached as None too, so a provider the
    orchestrator cannot investigate is not retried on every follow-up question.
    """
    payload = _to_handoff(result)
    case = None
    if payload is not None:
        from backend.model.handoff import parse

        parsed = parse(payload)
        case = parsed if parsed.available else None

    _remember(key, case)
    return case


def investigate(entities: dict[str, list[str]]):
    """Investigate whichever entity the question referenced."""
    if entities.get("claim"):
        return investigate_claim(entities["claim"][0])
    if entities.get("provider"):
        return investigate_provider(entities["provider"][0])
    return None
