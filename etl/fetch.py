"""
Network layer: retries, resume, and caching.

NAMED fetch.py, NOT http.py, ON PURPOSE.
A module called `http` inside this package shadows Python's own `http` package.
`requests` imports `urllib3`, which imports `http.client`, which then resolves
to this file instead of the standard library and fails with
"No module named 'http.client'". Never name a module after a stdlib package.

WHY CACHING MATTERS HERE
These files are large and the sources are public endpoints with no SLA. Without
caching, every pipeline run re-downloads gigabytes, which is slow and impolite.
A cached file is reused unless --refresh is passed, so reruns are cheap and the
pipeline is safe to iterate on.

WHY RESUME
A partial download is worse than none: it looks like a valid CSV and silently
truncates the data. Downloads write to a .part file and are renamed only on
completion, so an interrupted run can never leave a truncated file in place.
"""

from __future__ import annotations

import time
from pathlib import Path

import requests

from etl.config import HTTP_RETRIES, HTTP_TIMEOUT, USER_AGENT

_session: requests.Session | None = None


def session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update({"User-Agent": USER_AGENT})
    return _session


def get_json(url: str, params: dict | None = None) -> dict | list:
    last: Exception | None = None
    for attempt in range(1, HTTP_RETRIES + 1):
        try:
            r = session().get(url, params=params, timeout=HTTP_TIMEOUT)
            r.raise_for_status()
            return r.json()
        except Exception as exc:                              # noqa: BLE001
            last = exc
            if attempt < HTTP_RETRIES:
                wait = 2 ** attempt
                print(f"      retry {attempt}/{HTTP_RETRIES - 1} in {wait}s "
                      f"({type(exc).__name__})")
                time.sleep(wait)
    raise RuntimeError(f"GET {url} failed after {HTTP_RETRIES} attempts: {last}")


def download(url: str, dest: Path, use_cache: bool = True) -> Path:
    """Download to `dest`, resuming and caching. Returns the path."""
    dest.parent.mkdir(parents=True, exist_ok=True)

    if use_cache and dest.exists() and dest.stat().st_size > 0:
        mb = dest.stat().st_size / 1e6
        print(f"      cached ({mb:,.1f} MB) - {dest.name}")
        return dest

    part = dest.with_suffix(dest.suffix + ".part")
    last: Exception | None = None

    for attempt in range(1, HTTP_RETRIES + 1):
        try:
            with session().get(url, stream=True, timeout=HTTP_TIMEOUT) as r:
                r.raise_for_status()
                total = int(r.headers.get("Content-Length", 0))
                done = 0
                with open(part, "wb") as fh:
                    for block in r.iter_content(chunk_size=1 << 20):
                        if not block:
                            continue
                        fh.write(block)
                        done += len(block)
                        if total:
                            pct = done / total * 100
                            print(f"\r      {done/1e6:7.1f} / {total/1e6:,.1f} MB "
                                  f"({pct:5.1f}%)", end="", flush=True)
                        else:
                            print(f"\r      {done/1e6:7.1f} MB", end="", flush=True)
                print()
            part.replace(dest)          # atomic: never leaves a truncated file
            return dest
        except Exception as exc:                              # noqa: BLE001
            last = exc
            part.unlink(missing_ok=True)
            if attempt < HTTP_RETRIES:
                wait = 2 ** attempt
                print(f"\n      retry {attempt}/{HTTP_RETRIES - 1} in {wait}s "
                      f"({type(exc).__name__})")
                time.sleep(wait)

    raise RuntimeError(f"Download failed: {url}\n  {last}")
