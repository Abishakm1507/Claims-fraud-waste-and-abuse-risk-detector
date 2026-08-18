"""
Latency metrics for the generation layer.

Three standard LLM serving measurements, and only these three:

  TTFT  Time To First Token
        Wall-clock from sending the request to receiving the first token of the
        answer. This is what the user experiences as responsiveness. It covers
        network round-trip, prompt processing (prefill), and queueing.

  ITL   Inter-Token Latency
        Time between consecutive tokens once generation is underway. Reported
        as mean and p95, because the tail is what makes output feel uneven.
        p95 matters more than the mean here: a stall is more noticeable than a
        slightly slower average.

  TPOT  Time Per Output Token
        (total generation time - TTFT) / (output tokens - 1). The steady-state
        cost of producing one token, with the prefill cost removed.

TPOT and mean ITL measure the same interval and normally agree closely. They are
both reported because TPOT is the conventional serving metric while ITL exposes
the distribution, and a divergence between them indicates stalls.

Retrieval time is measured separately, since it precedes generation and is not
part of TTFT for the LLM itself - but it IS part of what the user waits for, so
end-to-end time is reported alongside.
"""

from __future__ import annotations

import statistics
import time
from dataclasses import dataclass, field
from typing import Callable, Iterable


@dataclass
class LatencyResult:
    """Timings for one generation."""

    question: str
    ttft_ms: float | None = None
    itl_mean_ms: float | None = None
    itl_p50_ms: float | None = None
    itl_p95_ms: float | None = None
    tpot_ms: float | None = None
    total_ms: float | None = None
    retrieval_ms: float | None = None
    end_to_end_ms: float | None = None
    output_chunks: int = 0
    output_chars: int = 0
    error: str | None = None
    _gaps: list[float] = field(default_factory=list, repr=False)

    def to_dict(self) -> dict:
        return {
            "question": self.question,
            "ttft_ms": round(self.ttft_ms, 1) if self.ttft_ms else None,
            "itl_mean_ms": round(self.itl_mean_ms, 2) if self.itl_mean_ms else None,
            "itl_p50_ms": round(self.itl_p50_ms, 2) if self.itl_p50_ms else None,
            "itl_p95_ms": round(self.itl_p95_ms, 2) if self.itl_p95_ms else None,
            "tpot_ms": round(self.tpot_ms, 2) if self.tpot_ms else None,
            "total_ms": round(self.total_ms, 1) if self.total_ms else None,
            "retrieval_ms": round(self.retrieval_ms, 1) if self.retrieval_ms else None,
            "end_to_end_ms": round(self.end_to_end_ms, 1) if self.end_to_end_ms else None,
            "output_chunks": self.output_chunks,
            "output_chars": self.output_chars,
            "error": self.error,
        }


def measure_stream(question: str, stream_factory: Callable[[], Iterable[str]],
                   retrieval_ms: float | None = None) -> LatencyResult:
    """
    Time a streaming generation.

    `stream_factory` is called to start the stream, so the clock starts at the
    moment of the request rather than at the moment the generator was created.
    """
    result = LatencyResult(question=question, retrieval_ms=retrieval_ms)
    gaps: list[float] = []
    started = time.perf_counter()
    last = None
    chars = 0

    try:
        for piece in stream_factory():
            now = time.perf_counter()
            if last is None:
                result.ttft_ms = (now - started) * 1000.0
            else:
                gaps.append((now - last) * 1000.0)
            last = now
            chars += len(piece)
            result.output_chunks += 1
    except Exception as exc:                                # noqa: BLE001
        result.error = f"{type(exc).__name__}: {exc}"
        return result

    total = (time.perf_counter() - started) * 1000.0
    result.total_ms = total
    result.output_chars = chars
    result._gaps = gaps

    if gaps:
        result.itl_mean_ms = statistics.fmean(gaps)
        result.itl_p50_ms = statistics.median(gaps)
        srt = sorted(gaps)
        # Nearest-rank p95; with few samples this is the max, which is correct.
        idx = max(0, min(len(srt) - 1, int(round(0.95 * len(srt))) - 1))
        result.itl_p95_ms = srt[idx]

    if result.ttft_ms is not None and result.output_chunks > 1:
        result.tpot_ms = (total - result.ttft_ms) / (result.output_chunks - 1)

    if retrieval_ms is not None:
        result.end_to_end_ms = retrieval_ms + total

    return result


def summarise(results: list[LatencyResult]) -> dict:
    """Aggregate across runs. Failed runs are counted but excluded from stats."""
    ok = [r for r in results if r.error is None and r.ttft_ms is not None]
    if not ok:
        return {"runs": len(results), "successful": 0,
                "errors": [r.error for r in results if r.error][:3]}

    def agg(vals: list[float]) -> dict:
        srt = sorted(vals)
        idx = max(0, min(len(srt) - 1, int(round(0.95 * len(srt))) - 1))
        return {
            "mean": round(statistics.fmean(vals), 1),
            "p50": round(statistics.median(vals), 1),
            "p95": round(srt[idx], 1),
            "min": round(min(vals), 1),
            "max": round(max(vals), 1),
        }

    all_gaps = [g for r in ok for g in r._gaps]
    out = {
        "runs": len(results),
        "successful": len(ok),
        "TTFT_ms": agg([r.ttft_ms for r in ok]),
        "TPOT_ms": agg([r.tpot_ms for r in ok if r.tpot_ms]),
        "total_generation_ms": agg([r.total_ms for r in ok if r.total_ms]),
    }
    if all_gaps:
        out["ITL_ms"] = agg(all_gaps)
        out["ITL_sample_count"] = len(all_gaps)
    rt = [r.retrieval_ms for r in ok if r.retrieval_ms is not None]
    if rt:
        out["retrieval_ms"] = agg(rt)
        out["end_to_end_ms"] = agg([r.end_to_end_ms for r in ok if r.end_to_end_ms])
    return out
