"""
Random sampling of a remote CSV using HTTP Range requests.

WHY THIS INSTEAD OF THE API
The CMS data API has to compute a result set, and a request for rows at a deep
random offset inside a 10-million-row dataset times out repeatedly. Serving a
static CSV file, by contrast, is cheap for the server and fast.

HOW IT GETS A RANDOM SAMPLE WITHOUT DOWNLOADING 3 GB
HTTP Range requests fetch an arbitrary byte window of a file. The pipeline:

  1. HEADs the file to learn its total size
  2. Fetches the first few KB to read the header row
  3. Picks random byte offsets across the whole file
  4. Fetches a window at each offset

A byte offset lands mid-line, so the first partial line of every window is
discarded. Whole-provider trimming then removes the first and last provider in
each window, because a window boundary cuts a provider's procedure rows in half
and a provider missing rows reports understated totals.

The result is a genuine random sample spread across the entire file, fetched in
a few megabytes rather than gigabytes.

FALLBACK
If the server does not honour Range requests, the pipeline streams the file from
the start and stops once it has enough providers. That sample is NOT random - it
is NPI-ordered, which correlates with enrolment date - so the limitation is
reported rather than hidden.
"""

from __future__ import annotations

import csv
import io
import random

from etl.fetch import session

HEADER_BYTES = 16_384


def file_size(url: str) -> tuple[int, bool]:
    """Return (size_bytes, server_supports_ranges)."""
    try:
        r = session().head(url, timeout=60, allow_redirects=True)
        r.raise_for_status()
        size = int(r.headers.get("Content-Length", 0))
        accepts = r.headers.get("Accept-Ranges", "").lower() == "bytes"
        return size, accepts
    except Exception:                                          # noqa: BLE001
        return 0, False


def _range(url: str, start: int, length: int) -> bytes:
    end = start + length - 1
    r = session().get(url, headers={"Range": f"bytes={start}-{end}"}, timeout=120)
    r.raise_for_status()
    return r.content


def read_header(url: str) -> list[str]:
    """Read the CSV header from the first bytes of the file."""
    chunk = _range(url, 0, HEADER_BYTES)
    line = chunk.split(b"\n", 1)[0].decode("utf-8", errors="replace")
    return next(csv.reader(io.StringIO(line)))


def _parse_window(raw: bytes, header: list[str]) -> list[dict]:
    """
    Parse a byte window into rows.

    The first line is dropped because a byte offset lands mid-line, and the
    last line is dropped because the window ends mid-line too.
    """
    text = raw.decode("utf-8", errors="replace")
    lines = text.split("\n")
    if len(lines) < 3:
        return []
    body = "\n".join(lines[1:-1])
    rows = []
    for values in csv.reader(io.StringIO(body)):
        if len(values) == len(header):
            rows.append(dict(zip(header, values)))
    return rows


def _trim_partial_providers(rows: list[dict], key: str) -> list[dict]:
    """Drop the first and last provider - both cut by the window boundary."""
    if len(rows) < 3:
        return []
    first, last = rows[0].get(key), rows[-1].get(key)
    return [r for r in rows if r.get(key) not in (first, last)]


def sample_csv(
    url: str,
    target_providers: int = 2000,
    key: str = "Rndrng_NPI",
    window_bytes: int = 3_000_000,
    seed: int = 42,
    max_windows: int = 40,
) -> tuple[list[dict], str]:
    """
    Sample whole providers from a remote CSV.

    Returns (rows, method) where method describes how the sample was taken, so
    the pipeline can report honestly whether it is random.
    """
    size, accepts_ranges = file_size(url)
    if size:
        print(f"        remote file: {size/1e9:.2f} GB, "
              f"ranges {'supported' if accepts_ranges else 'NOT supported'}")

    header = read_header(url)
    rng = random.Random(seed)

    if size and accepts_ranges and size > window_bytes * 2:
        collected: list[dict] = []
        seen: set = set()
        # Leave room for a full window at the end of the file.
        offsets = sorted(rng.sample(range(HEADER_BYTES, size - window_bytes),
                                    k=min(max_windows, 40)))
        print(f"        fetching random {window_bytes/1e6:.0f} MB windows")

        for i, off in enumerate(offsets, 1):
            try:
                raw = _range(url, off, window_bytes)
            except Exception as exc:                           # noqa: BLE001
                print(f"\n        window {i} failed ({type(exc).__name__})")
                continue
            rows = _trim_partial_providers(_parse_window(raw, header), key)
            collected.extend(rows)
            seen |= {r.get(key) for r in rows if r.get(key)}
            print(f"\r        window {i}/{len(offsets)}: {len(collected):,} rows, "
                  f"{len(seen):,} providers", end="", flush=True)
            if len(seen) >= target_providers:
                break
        print()

        if collected:
            if len(seen) > target_providers:
                keep = set(list(seen)[:target_providers])
                collected = [r for r in collected if r.get(key) in keep]
            return collected, "random byte-range windows"

    # Fallback: stream from the start and stop early. NOT random.
    print("        ranges unavailable - streaming from start (NOT a random "
          "sample; NPI-ordered)")
    collected, seen, buffer = [], set(), ""
    with session().get(url, stream=True, timeout=300) as r:
        r.raise_for_status()
        first = True
        for chunk in r.iter_content(chunk_size=1 << 20):
            buffer += chunk.decode("utf-8", errors="replace")
            lines = buffer.split("\n")
            buffer = lines.pop()
            if first:
                lines = lines[1:]
                first = False
            for values in csv.reader(io.StringIO("\n".join(lines))):
                if len(values) == len(header):
                    row = dict(zip(header, values))
                    collected.append(row)
                    if row.get(key):
                        seen.add(row[key])
            print(f"\r        {len(collected):,} rows, {len(seen):,} providers",
                  end="", flush=True)
            if len(seen) > target_providers + 1:
                break
    print()
    return _trim_partial_providers(collected, key), "sequential from file start"
