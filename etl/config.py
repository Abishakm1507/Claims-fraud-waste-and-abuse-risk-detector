"""
ETL configuration.

One place for source definitions, year scope, and output paths. Nothing else in
the pipeline hardcodes a URL or a path.

WHY DATASET IDS ARE NOT HARDCODED
CMS publishes each year of a dataset as a SEPARATE dataset with its own UUID,
and those UUIDs change as new years are released. Hardcoding them guarantees the
pipeline breaks the next time CMS publishes. So the pipeline discovers UUIDs
from the CMS catalog at runtime by matching on dataset title and year.
"""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------- year scope
START_YEAR = int(os.getenv("ETL_START_YEAR", "2020"))
END_YEAR = int(os.getenv("ETL_END_YEAR", "2024"))
YEARS = list(range(START_YEAR, END_YEAR + 1))

# ---------------------------------------------------------------- paths
DATA_DIR = Path(os.getenv("ETL_DATA_DIR", PROJECT_ROOT / "data"))
RAW_DIR = DATA_DIR / "raw"          # exactly as downloaded, never modified
INTERIM_DIR = DATA_DIR / "interim"  # cleaned, one file per source-year
CURATED_DIR = DATA_DIR / "curated"  # conformed tables every module reads
REPORTS_DIR = DATA_DIR / "reports"  # quality and crosswalk reports

for _d in (RAW_DIR, INTERIM_DIR, CURATED_DIR, REPORTS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------- CMS API
CMS_CATALOG_URL = "https://data.cms.gov/data.json"
CMS_DATA_API = "https://data.cms.gov/data-api/v1/dataset/{dataset_id}/data"
CMS_STATS_API = "https://data.cms.gov/data-api/v1/dataset/{dataset_id}/data/stats"
CMS_PAGE_SIZE = 5000

# Title fragments used to find each dataset FAMILY in the CMS catalog. CMS
# publishes one dataset per family with ~25 distributions inside it, one pair
# (CSV + API) per year, so the year is read from each distribution's `temporal`
# field rather than from the dataset title. Matching is on lowercase substrings
# so punctuation changes do not break discovery.
CMS_DATASETS = {
    "provider_service": {
        "match_all": ["medicare physician", "provider and service"],
        "match_none": ["geography"],
        "description": "NPI x HCPCS x year - provider billing detail",
    },
    "geo_service": {
        "match_all": ["medicare physician", "geography and service"],
        "match_none": [],
        "description": "State/National x HCPCS - peer benchmark table",
    },
    "provider_summary": {
        "match_all": ["medicare physician", "by provider"],
        "match_none": ["service", "geography"],
        "description": "NPI x year - provider demographics and totals",
    },
}

# ---------------------------------------------------------------- LEIE
# OIG publish no API; the updated database is a plain monthly CSV.
LEIE_PAGE = "https://oig.hhs.gov/exclusions/leie-database-supplement-downloads/"
LEIE_CSV_CANDIDATES = [
    "https://oig.hhs.gov/exclusions/downloadables/UPDATED.csv",
    "https://oig.hhs.gov/oie/downloadables/UPDATED.csv",
]

# ---------------------------------------------------------------- Synthetic claims
SYNTHETIC_COLLECTION = (
    "https://data.cms.gov/collection/"
    "synthetic-medicare-enrollment-fee-for-service-claims-and-prescription-drug-event"
)
SYNTHETIC_MATCH = ["synthetic"]

# ---------------------------------------------------------------- behaviour
# ---------------------------------------------------------------- sampling
# The full CMS provider file is ~3 GB and ~10M rows PER YEAR. The project needs
# a few thousand providers, so the sample is taken at the API rather than after
# downloading everything. Set SAMPLE_MODE=false to pull complete files.
SAMPLE_MODE = os.getenv("ETL_SAMPLE_MODE", "true").lower() != "false"
TARGET_PROVIDERS_PER_YEAR = int(os.getenv("ETL_TARGET_PROVIDERS", "2000"))
# Fixed so a rerun reproduces the same sample. If this changed between runs the
# ML model and the assistant could end up on different provider sets.
SAMPLE_SEED = int(os.getenv("ETL_SAMPLE_SEED", "42"))

HTTP_TIMEOUT = int(os.getenv("ETL_HTTP_TIMEOUT", "300"))
HTTP_RETRIES = int(os.getenv("ETL_HTTP_RETRIES", "4"))
USE_CACHE = os.getenv("ETL_USE_CACHE", "true").lower() != "false"
USER_AGENT = "UC01-FWA-ETL/1.0 (research pipeline)"
