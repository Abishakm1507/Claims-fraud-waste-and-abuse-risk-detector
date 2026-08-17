"""
Source-side sampling.

WHY THIS EXISTS
The full CMS provider file is roughly 3 GB and 10 million rows PER YEAR. The
project needs about 2,000 providers. Downloading 15 GB to keep 50,000 rows is
wasteful and will exhaust memory on an ordinary laptop, so the sample is taken
at the API instead of after the download.

HOW THE SAMPLE STAYS RANDOM
Taking the first N rows would return providers in NPI order - a skewed slice of
whichever NPIs happen to sort first. Instead the pipeline reads the dataset's
total row count, picks random offsets scattered across the whole range, and
pulls a block of rows at each. Blocks land anywhere in the file, so the sample
is spread across the full population.

WHY WHOLE PROVIDERS, NOT WHOLE ROWS
A provider occupies many consecutive rows, one per procedure code. A block
boundary cuts through a provider mid-way, leaving partial billing history that
would understate their totals and corrupt every downstream metric. So the first
and last provider in each block are discarded and only complete providers are
kept.

WHY THE BENCHMARK IS SAMPLED SECOND
Sampling providers and benchmarks independently would produce two slices that
barely overlap, and peer comparison would silently fail. So providers are
sampled first, then the benchmark is fetched ONLY for the states and procedure
codes those providers actually use. Coverage is guaranteed by construction
rather than left to chance.
"""

from __future__ import annotations

import random
from typing import Any

from etl.fetch import get_json


def _rows(payload: Any) -> list[dict]:
    if isinstance(payload, dict):
        return payload.get("data", []) or []
    return payload or []


def total_rows(stats_url: str) -> int:
    try:
        stats = get_json(stats_url)
        if isinstance(stats, dict):
            data = stats.get("data", stats)
            for key in ("total_rows", "found_rows", "total"):
                if key in data:
                    return int(data[key])
    except Exception:                                          # noqa: BLE001
        pass
    return 0


def sample_providers(
    api_url: str,
    stats_url: str,
    target_providers: int = 2000,
    page_size: int = 5000,
    npi_field: str = "Rndrng_NPI",
    seed: int = 42,
) -> list[dict]:
    """
    Random block sample returning rows for ~`target_providers` whole providers.

    `seed` is fixed so a rerun reproduces the same sample. Reproducibility
    matters here: if the sample changed every run, the ML model and the
    assistant could end up trained and grounded on different provider sets.
    """
    rng = random.Random(seed)
    total = total_rows(stats_url)

    if total == 0:
        # Stats unavailable - fall back to sequential paging from the start.
        print("        row count unavailable, paging sequentially")
        rows: list[dict] = []
        offset = 0
        while len({r.get(npi_field) for r in rows}) < target_providers:
            page = _rows(get_json(api_url, params={"size": page_size,
                                                   "offset": offset}))
            if not page:
                break
            rows.extend(page)
            offset += page_size
            print(f"\r        {len(rows):,} rows, "
                  f"{len({r.get(npi_field) for r in rows}):,} providers",
                  end="", flush=True)
        print()
        return _trim_partial(rows, npi_field)

    print(f"        dataset has {total:,} rows")

    # A 5,000-row block holds roughly 200 providers, so aim for enough blocks
    # to reach the target with headroom for the trimmed edges.
    est_per_block = 180
    n_blocks = max(3, min(40, target_providers // est_per_block + 2))
    max_offset = max(0, total - page_size)
    offsets = sorted(rng.sample(range(0, max_offset + 1),
                                k=min(n_blocks, max_offset + 1))) \
        if max_offset > 0 else [0]

    print(f"        sampling {len(offsets)} random blocks of {page_size:,} rows")

    collected: list[dict] = []
    seen: set = set()

    for i, off in enumerate(offsets, 1):
        page = _rows(get_json(api_url, params={"size": page_size, "offset": off}))
        if not page:
            continue
        kept = _trim_partial(page, npi_field)
        collected.extend(kept)
        seen |= {r.get(npi_field) for r in kept if r.get(npi_field)}
        print(f"\r        block {i}/{len(offsets)}: {len(collected):,} rows, "
              f"{len(seen):,} providers", end="", flush=True)
        if len(seen) >= target_providers:
            break
    print()

    # Trim to exactly the requested provider count, keeping every row for each
    # provider retained.
    if len(seen) > target_providers:
        keep = set(list(seen)[:target_providers])
        collected = [r for r in collected if r.get(npi_field) in keep]

    return collected


def _trim_partial(rows: list[dict], npi_field: str) -> list[dict]:
    """
    Drop the first and last provider in a block.

    Both are almost certainly cut off by the block boundary, and a provider
    with missing procedure rows would report understated totals.
    """
    if len(rows) < 3:
        return []
    first = rows[0].get(npi_field)
    last = rows[-1].get(npi_field)
    return [r for r in rows
            if r.get(npi_field) not in (first, last)]


def fetch_benchmark_for(
    api_url: str,
    states: set[str],
    hcpcs_codes: set[str],
    page_size: int = 5000,
    geo_level_field: str = "Rndrng_Prvdr_Geo_Lvl",
    geo_desc_field: str = "Rndrng_Prvdr_Geo_Desc",
    hcpcs_field: str = "HCPCS_Cd",
) -> list[dict]:
    """
    Fetch benchmark rows covering the sampled providers.

    National rows are pulled in full because they are the fallback comparison
    for every code. State rows are pulled per state, filtered server-side, and
    then reduced to the procedure codes the sample actually uses - so the
    benchmark covers the provider sample by construction.
    """
    out: list[dict] = []

    def page_through(params: dict, label: str) -> list[dict]:
        rows, offset = [], 0
        while True:
            p = dict(params)
            p.update({"size": page_size, "offset": offset})
            batch = _rows(get_json(api_url, params=p))
            if not batch:
                break
            rows.extend(batch)
            offset += page_size
            print(f"\r        {label}: {len(rows):,} rows", end="", flush=True)
            if len(batch) < page_size:
                break
        print()
        return rows

    national = page_through({f"filter[{geo_level_field}]": "National"}, "national")
    out.extend(r for r in national
               if not hcpcs_codes or r.get(hcpcs_field) in hcpcs_codes)

    for i, state in enumerate(sorted(s for s in states if s), 1):
        rows = page_through(
            {f"filter[{geo_desc_field}]": state},
            f"state {i}/{len(states)} ({state})")
        out.extend(r for r in rows
                   if not hcpcs_codes or r.get(hcpcs_field) in hcpcs_codes)

    return out
