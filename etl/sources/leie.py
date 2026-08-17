"""
LEIE source.

OIG publish no API and state they have no plans for one, so this is a plain
monthly CSV download. The file is a SNAPSHOT of currently-effective exclusions:
reinstated parties are removed rather than marked, so the pipeline records which
month's file it pulled. Exclusion status is time-sensitive and a finding made
against one month's file may not hold against another.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from etl.config import LEIE_CSV_CANDIDATES, LEIE_PAGE, RAW_DIR
from etl.fetch import download, session


def discover_csv_url() -> str | None:
    """Scrape the download page for the updated-database CSV link."""
    try:
        r = session().get(LEIE_PAGE, timeout=60)
        r.raise_for_status()
    except Exception as exc:                                   # noqa: BLE001
        print(f"      could not read LEIE page ({type(exc).__name__})")
        return None

    links = re.findall(r'href="([^"]+\.csv)"', r.text, flags=re.IGNORECASE)
    for href in links:
        if "updated" in href.lower():
            if href.startswith("http"):
                return href
            return "https://oig.hhs.gov" + ("" if href.startswith("/") else "/") + href
    return None


def extract(refresh: bool = False) -> Path | None:
    print("\n  leie  (OIG List of Excluded Individuals and Entities)")
    stamp = date.today().strftime("%Y%m")
    dest = RAW_DIR / f"leie_updated_{stamp}.csv"

    if dest.exists() and not refresh and dest.stat().st_size > 0:
        print(f"      cached ({dest.stat().st_size/1e6:,.1f} MB)")
        return dest

    url = discover_csv_url()
    candidates = ([url] if url else []) + LEIE_CSV_CANDIDATES

    for candidate in candidates:
        try:
            print(f"      trying {candidate}")
            return download(candidate, dest, use_cache=not refresh)
        except Exception as exc:                               # noqa: BLE001
            print(f"      failed ({type(exc).__name__})")

    print("      LEIE download failed. The page layout may have changed;")
    print(f"      download manually from {LEIE_PAGE} and save as {dest}")
    return None
