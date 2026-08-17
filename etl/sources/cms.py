"""
CMS source: discovery and extraction.

HOW THE CMS CATALOG IS ACTUALLY STRUCTURED
Not one dataset per year. CMS publishes ONE dataset per family - for example
"Medicare Physician & Other Practitioners - by Provider and Service" - carrying
~25 distributions inside it, one pair per year:

    {"format": "CSV", "downloadURL": ".../PHY_..._D24_Prov_Svc.csv",
     "temporal": "2024-01-01/2024-12-31"}
    {"format": "API", "accessURL": ".../dataset/<uuid>/data",
     "temporal": "2024-01-01/2024-12-31"}

So the year lives in the `temporal` field, not the title, and each year offers
both a direct CSV and a paginated API. The CSV is preferred: one request instead
of hundreds, and no pagination to get wrong.

One distribution is also tagged `description: "latest"` and duplicates the most
recent year, so distributions are de-duplicated by year with CSV winning.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

from etl.config import (
    CMS_CATALOG_URL, CMS_DATA_API, CMS_DATASETS, CMS_PAGE_SIZE,
    CMS_STATS_API, RAW_DIR, SAMPLE_MODE, SAMPLE_SEED,
    TARGET_PROVIDERS_PER_YEAR, YEARS,
)
from etl.fetch import download, get_json
from etl.sources.range_sample import sample_csv
from etl.sources.sampling import fetch_benchmark_for, sample_providers

_catalog: list[dict] | None = None


def load_catalog(refresh: bool = False) -> list[dict]:
    """Fetch and cache the CMS DCAT catalog."""
    global _catalog
    if _catalog is not None and not refresh:
        return _catalog

    cache = RAW_DIR / "cms_catalog.json"
    if cache.exists() and not refresh:
        _catalog = json.loads(cache.read_text(encoding="utf-8"))
        print(f"      catalog cached ({len(_catalog):,} datasets)")
        return _catalog

    print(f"      fetching catalog: {CMS_CATALOG_URL}")
    data = get_json(CMS_CATALOG_URL)
    items = data.get("dataset", data) if isinstance(data, dict) else data
    _catalog = items
    cache.write_text(json.dumps(items), encoding="utf-8")
    print(f"      catalog: {len(items):,} datasets")
    return items


def find_dataset(key: str) -> dict | None:
    """Locate one dataset family by title fragments."""
    spec = CMS_DATASETS[key]
    for entry in load_catalog():
        title = (entry.get("title") or "").lower()
        if not all(frag in title for frag in spec["match_all"]):
            continue
        if any(frag in title for frag in spec["match_none"]):
            continue
        return entry
    return None


def _year_of(dist: dict) -> int | None:
    """
    Year for a distribution.

    `temporal` is the reliable source ("2024-01-01/2024-12-31"). The title is a
    fallback, but note its date is the PUBLICATION date, not the data year, so
    temporal is always preferred.
    """
    temporal = dist.get("temporal") or ""
    m = re.match(r"(\d{4})-", temporal)
    if m:
        return int(m.group(1))
    url = dist.get("downloadURL") or ""
    m = re.search(r"_D(\d{2})_", url)          # e.g. ..._D24_Prov_Svc.csv
    if m:
        return 2000 + int(m.group(1))
    return None


def distributions_by_year(entry: dict,
                          years: list[int] | None = None) -> dict[int, dict]:
    """
    Map {year: best distribution}, preferring CSV over API.

    De-duplicates the "latest" alias, which repeats the most recent year.
    """
    want = set(years or YEARS)
    best: dict[int, dict] = {}

    for dist in entry.get("distribution", []) or []:
        year = _year_of(dist)
        if year is None or year not in want:
            continue
        fmt = (dist.get("format") or "").upper()
        current = best.get(year)
        if current is None:
            best[year] = dist
        elif fmt == "CSV" and (current.get("format") or "").upper() != "CSV":
            best[year] = dist                  # CSV always wins

    return dict(sorted(best.items()))


def _dataset_id(dist: dict) -> str | None:
    for field in ("accessURL", "resourcesAPI"):
        m = re.search(r"/(?:dataset|dataset-resources)/([0-9a-f-]{36})",
                      dist.get(field) or "")
        if m:
            return m.group(1)
    return None


def _write_rows(rows: list[dict], dest: Path) -> Path | None:
    """Write API rows to CSV, preserving the source column names."""
    if not rows:
        return None
    header = list(rows[0].keys())
    part = dest.with_suffix(".csv.part")
    with open(part, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=header)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k) for k in header})
    part.replace(dest)
    return dest


def _api_url(dist: dict, entry: dict, year: int) -> str | None:
    """
    API endpoint for a year.

    The chosen distribution may be the CSV one, so the sibling API distribution
    for the same year is looked up here.
    """
    ds_id = _dataset_id(dist)
    if ds_id:
        return CMS_DATA_API.format(dataset_id=ds_id)
    for d in entry.get("distribution", []) or []:
        if _year_of(d) == year and (d.get("format") or "").upper() == "API":
            ds_id = _dataset_id(d)
            if ds_id:
                return CMS_DATA_API.format(dataset_id=ds_id)
    return None


def _filter_benchmark(src: Path, dest: Path, restrict: dict) -> Path | None:
    """
    Reduce a downloaded benchmark file to the sample's states and codes.

    Read in chunks so a large file never has to fit in memory at once.
    """
    import pandas as pd

    states = restrict.get("states") or set()
    codes = restrict.get("hcpcs") or set()
    kept, total = 0, 0
    first = True

    for chunk in pd.read_csv(src, dtype=str, low_memory=False, chunksize=200_000):
        total += len(chunk)
        cols = {c.lower(): c for c in chunk.columns}
        hc = cols.get("hcpcs_cd")
        gd = cols.get("rndrng_prvdr_geo_desc")
        gl = cols.get("rndrng_prvdr_geo_lvl")

        mask = pd.Series(True, index=chunk.index)
        if hc and codes:
            mask &= chunk[hc].isin(codes)
        if gd and states and gl:
            # Keep National rows as the fallback comparison for every code.
            mask &= chunk[gd].isin(states) | chunk[gl].eq("National")

        out = chunk[mask]
        if out.empty:
            continue
        out.to_csv(dest, mode="w" if first else "a", header=first, index=False)
        first = False
        kept += len(out)
        print(f"\r        filtered {kept:,} of {total:,} rows", end="", flush=True)
    print()

    src.unlink(missing_ok=True)          # the full file is not needed again
    return dest if kept else None


def sample_year(key: str, year: int, dist: dict, entry: dict,
                refresh: bool = False,
                restrict: dict | None = None) -> Path | None:
    """
    Fetch a SAMPLE for one year instead of the whole file.

    provider_service is sampled randomly by provider. geo_service is then
    fetched only for the states and procedure codes those providers use, so the
    benchmark covers the sample rather than overlapping it by luck.
    """
    dest = RAW_DIR / f"cms_{key}_{year}.csv"
    if dest.exists() and not refresh and dest.stat().st_size > 0:
        print(f"      {year}: cached sample ({dest.stat().st_size/1e6:,.1f} MB)")
        return dest

    csv_url = dist.get("downloadURL") if \
        (dist.get("format") or "").upper() == "CSV" else None
    if not csv_url:
        for d in entry.get("distribution", []) or []:
            if _year_of(d) == year and (d.get("format") or "").upper() == "CSV":
                csv_url = d.get("downloadURL")
                break

    api = _api_url(dist, entry, year)
    ds_id = api.rstrip("/data").rsplit("/", 1)[-1] if api else None
    stats = CMS_STATS_API.format(dataset_id=ds_id) if ds_id else None

    if key == "provider_service":
        # Byte-range sampling of the static CSV first: the data API times out
        # on deep random offsets into a 10M-row dataset, while a static file
        # serves a byte window instantly.
        rows = []
        if csv_url:
            try:
                rows, method = sample_csv(
                    csv_url,
                    target_providers=TARGET_PROVIDERS_PER_YEAR,
                    seed=SAMPLE_SEED + year,
                )
                print(f"      {year}: sampled via {method}")
            except Exception as exc:                           # noqa: BLE001
                print(f"      {year}: range sampling failed "
                      f"({type(exc).__name__}) - falling back to API")
                rows = []
        if not rows and api and stats:
            rows = sample_providers(
                api, stats,
                target_providers=TARGET_PROVIDERS_PER_YEAR,
                page_size=CMS_PAGE_SIZE,
                seed=SAMPLE_SEED + year,
            )
    elif key == "geo_service":
        if not restrict:
            print(f"      {year}: no provider sample to align to - skipping")
            return None
        # The benchmark file is far smaller than the provider file, so it is
        # downloaded whole and filtered locally to the sample's codes/states.
        if csv_url:
            try:
                path = download(csv_url, dest.with_name(dest.stem + "_full.csv"),
                                use_cache=not refresh)
                return _filter_benchmark(path, dest, restrict)
            except Exception as exc:                           # noqa: BLE001
                print(f"      {year}: benchmark CSV failed "
                      f"({type(exc).__name__}) - trying API")
        if not api:
            return None
        rows = fetch_benchmark_for(
            api,
            states=restrict.get("states", set()),
            hcpcs_codes=restrict.get("hcpcs", set()),
            page_size=CMS_PAGE_SIZE,
        )
    else:
        rows = []

    if not rows:
        print(f"      {year}: sample returned no rows")
        return None

    _write_rows(rows, dest)
    print(f"      {year}: wrote {len(rows):,} sampled rows")
    return dest


def fetch_year(key: str, year: int, dist: dict,
               refresh: bool = False) -> Path | None:
    """Download one dataset-year into raw/. Returns the CSV path."""
    dest = RAW_DIR / f"cms_{key}_{year}.csv"

    url = dist.get("downloadURL")
    if url and (dist.get("format") or "").upper() == "CSV":
        print(f"      {year}: direct CSV")
        return download(url, dest, use_cache=not refresh)

    ds_id = _dataset_id(dist)
    if not ds_id:
        print(f"      {year}: no CSV and no dataset id - skipping")
        return None

    if dest.exists() and not refresh and dest.stat().st_size > 0:
        print(f"      {year}: cached ({dest.stat().st_size/1e6:,.1f} MB)")
        return dest

    print(f"      {year}: paginated API ({ds_id})")
    try:
        stats = get_json(CMS_STATS_API.format(dataset_id=ds_id))
        total = int(stats.get("data", {}).get("total_rows")
                    or stats.get("total_rows") or 0)
    except Exception:                                          # noqa: BLE001
        total = 0

    api = CMS_DATA_API.format(dataset_id=ds_id)
    offset, written, header = 0, 0, None
    part = dest.with_suffix(".csv.part")

    with open(part, "w", newline="", encoding="utf-8") as fh:
        writer = None
        while True:
            rows = get_json(api, params={"size": CMS_PAGE_SIZE, "offset": offset})
            if isinstance(rows, dict):
                rows = rows.get("data", [])
            if not rows:
                break
            if writer is None:
                header = list(rows[0].keys())
                writer = csv.DictWriter(fh, fieldnames=header)
                writer.writeheader()
            for r in rows:
                writer.writerow({k: r.get(k) for k in header})
            written += len(rows)
            offset += CMS_PAGE_SIZE
            msg = f"\r      {written:,} rows"
            if total:
                msg += f" / {total:,} ({written/total*100:5.1f}%)"
            print(msg, end="", flush=True)
            if len(rows) < CMS_PAGE_SIZE:
                break
    print()

    if written == 0:
        part.unlink(missing_ok=True)
        print(f"      {year}: API returned no rows")
        return None

    part.replace(dest)
    return dest


def extract(key: str, refresh: bool = False,
            restrict: dict | None = None) -> dict[int, Path]:
    """
    Discover and fetch every requested year for one dataset family.

    In SAMPLE_MODE the provider dataset is sampled by provider, and the
    benchmark dataset is restricted to that sample's states and codes.
    """
    spec = CMS_DATASETS[key]
    print(f"\n  {key}  ({spec['description']})")

    entry = find_dataset(key)
    if entry is None:
        print(f"      dataset not found in catalog "
              f"(looking for: {', '.join(spec['match_all'])})")
        return {}
    print(f"      found: {entry.get('title')}")

    by_year = distributions_by_year(entry)
    if not by_year:
        available = sorted({y for y in (_year_of(d)
                            for d in entry.get("distribution", []) or [])
                            if y})
        print(f"      no distributions for {YEARS[0]}-{YEARS[-1]}")
        if available:
            print(f"      years available: {available}")
        return {}

    missing = [y for y in YEARS if y not in by_year]
    if missing:
        print(f"      years not published: {missing}")
    print(f"      downloading: {sorted(by_year)}")

    if SAMPLE_MODE:
        print(f"      SAMPLE MODE: ~{TARGET_PROVIDERS_PER_YEAR:,} providers/year"
              if key == "provider_service"
              else "      SAMPLE MODE: benchmark aligned to provider sample")

    out: dict[int, Path] = {}
    for year, dist in by_year.items():
        try:
            if SAMPLE_MODE:
                path = sample_year(key, year, dist, entry,
                                   refresh=refresh, restrict=restrict)
            else:
                path = fetch_year(key, year, dist, refresh=refresh)
            if path:
                out[year] = path
        except Exception as exc:                               # noqa: BLE001
            print(f"      {year}: failed - {type(exc).__name__}: {exc}")
    return out
