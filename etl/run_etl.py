"""
ETL orchestrator.

    python -m etl.run_etl                    full run
    python -m etl.run_etl --refresh          re-download instead of using cache
    python -m etl.run_etl --skip-download    transform files already in raw/
    python -m etl.run_etl --local DIR        use CSVs from DIR instead of downloading

STAGES
    extract   download from CMS and OIG into data/raw   (never modified)
    clean     normalise ids and types into data/interim (one file per source-year)
    conform   build canonical tables into data/curated  (what modules read)
    report    quality, coverage and crosswalk into data/reports

The pipeline is idempotent: the same inputs always produce the same outputs, and
a rerun is cheap because raw downloads are cached.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import pandas as pd

from etl.config import (
    CURATED_DIR, INTERIM_DIR, RAW_DIR, REPORTS_DIR, YEARS,
)
from etl.transform import clean as C
from etl.transform import conform as CF
from etl.transform import quality as Q

BANNER = "=" * 72


def _read(path: Path, **kw) -> pd.DataFrame:
    """Read a CSV as text, so no identifier is silently coerced to float."""
    sep = "|" if path.suffix == ".psv" else kw.pop("sep", ",")
    return pd.read_csv(path, dtype=str, low_memory=False, sep=sep, **kw)


def _resolve_year(df: pd.DataFrame, path: Path) -> "pd.Series | int":
    """
    Year for each row.

    Prefers a Year column in the data over the filename, because a file may
    contain several years and the filename is only a hint. Returns a Series so
    each row keeps its own year, or an int when the data has no year column.
    """
    ycol = next((c for c in df.columns if c.lower() in ("year", "data_year")), None)
    if ycol is not None:
        yrs = pd.to_numeric(df[ycol], errors="coerce")
        if yrs.notna().any():
            return yrs.astype("Int64")
    from etl.config import YEARS as _Y
    return next((y for y in _Y if str(y) in path.name), 0)


def _write(df: pd.DataFrame, directory: Path, name: str) -> Path:
    """Parquet where available, CSV as fallback."""
    directory.mkdir(parents=True, exist_ok=True)
    try:
        path = directory / f"{name}.parquet"
        df.to_parquet(path, index=False)
    except Exception:                                          # noqa: BLE001
        path = directory / f"{name}.csv"
        df.to_csv(path, index=False)
    print(f"      wrote {path.name:<34} {len(df):>10,} rows")
    return path


# ---------------------------------------------------------------- extract

def stage_extract(refresh: bool, skip: bool) -> dict:
    print(f"\n{BANNER}\n1. EXTRACT\n{BANNER}")
    if skip:
        print("  --skip-download: using files already in data/raw")
        return {}

    import pandas as _pd

    from etl.sources import cms, leie

    found: dict = {}

    # Providers first. The benchmark is then fetched only for the states and
    # procedure codes this sample actually uses, so peer comparison is covered
    # by construction rather than by coincidence.
    try:
        found["provider_service"] = cms.extract("provider_service",
                                                refresh=refresh)
    except Exception as exc:                                   # noqa: BLE001
        print(f"      provider_service extraction failed: "
              f"{type(exc).__name__}: {exc}")
        found["provider_service"] = {}

    restrict = None
    paths = list((found.get("provider_service") or {}).values())
    if paths:
        states: set[str] = set()
        codes: set[str] = set()
        for path in paths:
            try:
                df = _pd.read_csv(path, dtype=str, low_memory=False,
                                  usecols=lambda c: c in (
                                      "Rndrng_Prvdr_State_Abrvtn", "HCPCS_Cd"))
            except Exception:                                  # noqa: BLE001
                continue
            if "Rndrng_Prvdr_State_Abrvtn" in df.columns:
                states |= set(df["Rndrng_Prvdr_State_Abrvtn"].dropna().unique())
            if "HCPCS_Cd" in df.columns:
                codes |= set(df["HCPCS_Cd"].dropna().unique())

        from etl.transform.identifiers import state_to_name
        state_names = {state_to_name(s) for s in states}
        state_names.discard(None)
        restrict = {"states": state_names, "hcpcs": codes}
        print(f"\n      provider sample covers {len(states)} states, "
              f"{len(codes):,} procedure codes")
        print("      benchmark will be restricted to those")

    try:
        found["geo_service"] = cms.extract("geo_service", refresh=refresh,
                                           restrict=restrict)
    except Exception as exc:                                   # noqa: BLE001
        print(f"      geo_service extraction failed: {type(exc).__name__}: {exc}")
        found["geo_service"] = {}
    try:
        found["leie"] = leie.extract(refresh=refresh)
    except Exception as exc:                                   # noqa: BLE001
        print(f"      leie extraction failed: {type(exc).__name__}: {exc}")
        found["leie"] = None
    return found


# ---------------------------------------------------------------- clean

def stage_clean(local: Path | None) -> dict[str, pd.DataFrame]:
    print(f"\n{BANNER}\n2. CLEAN\n{BANNER}")
    src = local or RAW_DIR
    tables: dict[str, pd.DataFrame] = {}

    # provider x service, one file per year
    frames = []
    for path in sorted(src.glob("*provider_service*.csv")):
        df = _read(path)
        # The Year column in the data always wins over the filename. A file
        # named _2020 can legitimately contain several years, and trusting the
        # name would stamp every row with the wrong year and destroy the
        # NPI x HCPCS x year grain.
        cleaned = C.clean_provider_service(
            df, _resolve_year(df, path))
        frames.append(cleaned)
        span = cleaned["year"].dropna()
        label = (f"{int(span.min())}-{int(span.max())}"
                 if not span.empty and span.min() != span.max()
                 else (str(int(span.iloc[0])) if not span.empty else "?"))
        print(f"      provider_service {label}: {len(cleaned):,} rows")
    if frames:
        tables["provider_service"] = pd.concat(frames, ignore_index=True)
        _write(tables["provider_service"], INTERIM_DIR, "provider_service_clean")

    # geography x service
    frames = []
    seen: set[str] = set()
    for path in sorted(list(src.glob("*geo_service*.csv")) + list(src.glob("*Geo*.csv"))):
        if path.name in seen:
            continue
        seen.add(path.name)
        df = _read(path)
        cleaned = C.clean_geo_service(df, _resolve_year(df, path))
        frames.append(cleaned)
        span = cleaned["year"].dropna()
        label = (f"{int(span.min())}-{int(span.max())}"
                 if not span.empty and span.min() != span.max()
                 else (str(int(span.iloc[0])) if not span.empty else "?"))
        print(f"      geo_service {label}: {len(cleaned):,} rows")
    if frames:
        tables["geo_benchmark"] = pd.concat(frames, ignore_index=True)
        _write(tables["geo_benchmark"], INTERIM_DIR, "geo_benchmark_clean")

    # LEIE
    for path in sorted(list(src.glob("*leie*.csv")) + list(src.glob("*LEIE*.csv"))):
        cleaned = C.clean_leie(_read(path))
        tables["leie"] = cleaned
        print(f"      leie: {len(cleaned):,} rows "
              f"({int(cleaned.has_npi.sum()):,} with NPI)")
        _write(cleaned, INTERIM_DIR, "leie_clean")
        break

    # claims
    frames = []
    for pattern, ctype in [("*carrier*.csv", "carrier"),
                           ("*inpatient*.csv", "inpatient"),
                           ("*outpatient*.csv", "outpatient")]:
        for path in sorted(src.glob(pattern)):
            with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                sep = "|" if "|" in fh.readline() else ","
            cleaned = C.clean_claims(_read(path, sep=sep), ctype)
            frames.append(cleaned)
            print(f"      {ctype} ({path.name}): {len(cleaned):,} rows")
            break
    if frames:
        tables["claims"] = pd.concat(frames, ignore_index=True)
        _write(tables["claims"], INTERIM_DIR, "claims_clean")

    if not tables:
        print("      no source files found. Check data/raw or pass --local DIR")
    return tables


# ---------------------------------------------------------------- conform

def stage_conform(tables: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    print(f"\n{BANNER}\n3. CONFORM\n{BANNER}")
    ps = tables.get("provider_service", pd.DataFrame())
    geo = tables.get("geo_benchmark", pd.DataFrame())
    leie = tables.get("leie", pd.DataFrame())
    claims = tables.get("claims", pd.DataFrame())

    curated: dict[str, pd.DataFrame] = {}

    if not ps.empty:
        curated["dim_provider"] = CF.build_dim_provider(ps)
        curated["fact_provider_year"] = CF.build_fact_provider_year(ps)
        curated["fact_provider_service"] = ps
    if not geo.empty:
        curated["fact_geo_benchmark"] = geo
    if not ps.empty or not geo.empty:
        curated["dim_hcpcs"] = CF.build_dim_hcpcs(ps, geo)
    if not leie.empty:
        curated["dim_exclusion"] = leie
    if not claims.empty:
        curated["fact_claim"] = claims

    if "dim_provider" in curated and not leie.empty:
        links = CF.link_exclusions(curated["dim_provider"], leie)
        if not links.empty:
            curated["link_provider_exclusion"] = links

    curated["xwalk_identifier"] = CF.build_xwalk({
        "provider_service": ps, "geo_benchmark": geo,
        "leie": leie, "claims": claims,
    })

    for name, df in curated.items():
        if df is not None and not df.empty:
            _write(df, CURATED_DIR, name)
    return curated


# ---------------------------------------------------------------- report

def stage_report(curated: dict[str, pd.DataFrame]) -> dict:
    print(f"\n{BANNER}\n4. QUALITY REPORT\n{BANNER}")

    keys = {
        "dim_provider": ["npi"],
        "fact_provider_year": ["npi", "year"],
        "fact_provider_service": ["npi", "hcpcs_code", "year", "place_of_service"],
        "fact_geo_benchmark": ["geo_level", "geo_description", "hcpcs_code",
                               "year", "place_of_service"],
        "dim_hcpcs": ["hcpcs_code"],
        "fact_claim": ["claim_id"],
    }

    profiles = [Q.profile_table(n, df, keys.get(n))
                for n, df in curated.items() if df is not None]

    orphans = []
    if "fact_provider_year" in curated and "dim_provider" in curated:
        orphans.append(Q.orphan_check(
            curated["fact_provider_year"], "npi",
            curated["dim_provider"], "npi",
            "fact_provider_year.npi -> dim_provider.npi"))
    if "fact_provider_service" in curated and "dim_hcpcs" in curated:
        orphans.append(Q.orphan_check(
            curated["fact_provider_service"], "hcpcs_code",
            curated["dim_hcpcs"], "hcpcs_code",
            "fact_provider_service.hcpcs_code -> dim_hcpcs.hcpcs_code"))

    coverage = {}
    for name in ("fact_provider_service", "fact_geo_benchmark"):
        if name in curated:
            coverage[name] = Q.coverage_by_year(curated[name])
    if "fact_claim" in curated:
        coverage["fact_claim"] = Q.coverage_by_year(curated["fact_claim"], "claim_year")

    report = {
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "year_scope": [YEARS[0], YEARS[-1]],
        "tables": profiles,
        "referential_integrity": orphans,
        "year_coverage": coverage,
    }
    (REPORTS_DIR / "quality_report.json").write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8")

    for p in profiles:
        if p.get("rows"):
            line = f"  {p['table']:<28} {p['rows']:>10,} rows"
            if "key_is_unique" in p:
                line += "   key unique" if p["key_is_unique"] else \
                        f"   DUPLICATE KEYS: {p['duplicate_keys']:,}"
            print(line)

    if orphans:
        print("\n  referential integrity:")
        for o in orphans:
            if "orphan_pct" in o:
                print(f"    {o['relationship']:<52} {o['orphan_pct']:>6.2f}% orphaned")

    xw = curated.get("xwalk_identifier")
    if xw is not None and not xw.empty:
        print("\n  identifier crosswalk (measured overlap):")
        for _, r in xw.iterrows():
            mark = "OK  " if r.joinable else "WEAK"
            print(f"    [{mark}] {r.left_table}.{r.left_key} -> "
                  f"{r.right_table}.{r.right_key}: {r.overlap:,} "
                  f"({r.pct_of_left}% of left)")

    print(f"\n  full report: {REPORTS_DIR / 'quality_report.json'}")
    return report


# ---------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser(description="UC01 FWA data pipeline")
    ap.add_argument("--refresh", action="store_true",
                    help="re-download even if cached")
    ap.add_argument("--skip-download", action="store_true",
                    help="transform files already in data/raw")
    ap.add_argument("--local", type=str, default=None,
                    help="use CSVs from this directory instead of downloading")
    args = ap.parse_args()

    started = time.time()
    local = Path(args.local).resolve() if args.local else None

    print(BANNER)
    print("UC01 - CLAIMS FWA DATA PIPELINE")
    print(BANNER)
    print(f"years   : {YEARS[0]}-{YEARS[-1]}")
    print(f"source  : {local if local else RAW_DIR}")
    print(f"curated : {CURATED_DIR}")

    if not (args.skip_download or local):
        stage_extract(refresh=args.refresh, skip=False)

    tables = stage_clean(local)
    if not tables:
        print("\nNothing to conform. Pipeline stopped.")
        return 1

    curated = stage_conform(tables)
    stage_report(curated)

    print(f"\n{BANNER}")
    print(f"DONE in {time.time() - started:.0f}s")
    print(f"Curated tables in {CURATED_DIR}")
    print(BANNER)
    return 0


if __name__ == "__main__":
    sys.exit(main())
