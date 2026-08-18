"""
Measure generation latency: TTFT, ITL and TPOT.

    python scripts/benchmark.py                 default question set
    python scripts/benchmark.py --runs 3        repeat each question
    python scripts/benchmark.py --json out.json save raw results

Requires a configured LLM (LLM_API_KEY in .env), because TTFT can only be
measured against a real streaming response.

Retrieval time is timed separately and reported alongside, so the split between
retrieval and generation is visible.
"""

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.eval.latency import measure_stream, summarise      # noqa: E402
from backend.llm.llm_service import get_llm_service             # noqa: E402
from backend.llm.prompts import build_user_prompt               # noqa: E402
from backend.rag.rag_pipeline import _format_data, _format_knowledge, _format_model  # noqa: E402
from backend.data.structured_data_service import get_data_service  # noqa: E402
from backend.model.risk_engine_service import get_risk_engine   # noqa: E402
from backend.rag.retriever import get_retriever                 # noqa: E402
from backend.router.question_router import route_question       # noqa: E402

QUESTIONS = [
    "What is upcoding?",
    "Why can unusually high reimbursement be suspicious?",
    "What is phantom billing?",
    "What does a high service concentration (HHI) indicate?",
    "Why was provider 1003056821 flagged?",
    "What is the risk score for 1003056821?",
]


def run_one(question: str):
    """Route, retrieve, build the prompt, then time the streamed generation."""
    t0 = time.perf_counter()
    decision = route_question(question)

    chunks = []
    if decision.needs_knowledge:
        chunks = get_retriever().retrieve(question)

    data_ev = model_info = None
    if decision.needs_data:
        data_ev = get_data_service().query(question, decision.entities)
    if decision.needs_model:
        model_info = get_risk_engine().get_risk(decision.entities)

    prompt = build_user_prompt(
        question=question,
        question_type=decision.question_type.value,
        knowledge_blocks=_format_knowledge(chunks),
        data_block=_format_data(data_ev),
        model_block=_format_model(model_info),
    )
    retrieval_ms = (time.perf_counter() - t0) * 1000.0

    llm = get_llm_service()
    return measure_stream(question, lambda: llm.stream(prompt), retrieval_ms)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=1,
                    help="repetitions per question")
    ap.add_argument("--json", type=str, default=None,
                    help="write raw results to this path")
    args = ap.parse_args()

    llm = get_llm_service()
    if not llm.is_available():
        print("LLM is not configured. Set LLM_API_KEY in .env.")
        print("TTFT cannot be measured without a real streaming response.")
        return 1

    print("=" * 74)
    print("LATENCY BENCHMARK")
    print("=" * 74)
    print(f"model: {llm.model}    questions: {len(QUESTIONS)}    runs: {args.runs}\n")

    results = []
    for r in range(args.runs):
        for q in QUESTIONS:
            res = run_one(q)
            results.append(res)
            if res.error:
                print(f"  ERROR  {q[:46]:<46} {res.error[:40]}")
            else:
                print(f"  TTFT {res.ttft_ms:7.0f}ms | "
                      f"ITL {res.itl_mean_ms or 0:6.1f}ms | "
                      f"TPOT {res.tpot_ms or 0:6.1f}ms | "
                      f"{res.output_chunks:4d} chunks | {q[:34]}")

    print("\n" + "=" * 74)
    print("SUMMARY")
    print("=" * 74)
    s = summarise(results)
    print(f"runs: {s['runs']}   successful: {s['successful']}\n")
    for key in ("TTFT_ms", "ITL_ms", "TPOT_ms", "retrieval_ms",
                "total_generation_ms", "end_to_end_ms"):
        if key in s:
            v = s[key]
            print(f"  {key:<22} mean {v['mean']:>8.1f}   p50 {v['p50']:>8.1f}   "
                  f"p95 {v['p95']:>8.1f}   min {v['min']:>7.1f}   max {v['max']:>8.1f}")
    if "ITL_sample_count" in s:
        print(f"\n  ITL computed over {s['ITL_sample_count']:,} inter-token gaps")

    print("\n  TTFT  time to first token - perceived responsiveness")
    print("  ITL   inter-token latency - smoothness of streaming")
    print("  TPOT  time per output token - steady-state generation cost")

    if args.json:
        Path(args.json).write_text(
            json.dumps({"summary": s, "runs": [r.to_dict() for r in results]},
                       indent=2), encoding="utf-8")
        print(f"\nraw results written to {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
