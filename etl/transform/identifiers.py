"""
Identifier normalisation.

THIS MODULE IS WHY THE JOINS WORK.

Every dataset writes the same identifier differently. An NPI arrives as an int
in one file, a float with a trailing .0 in another, and a zero-padded string in
a third. A facility CCN loses its leading zero the moment a spreadsheet touches
it. Join those raw and you silently get zero matches - not an error, just an
empty result that looks like "no data for this provider".

So every identifier passes through here before any join, and the SAME function
is used on both sides of every join. That is the whole discipline: one
normaliser per identifier type, applied everywhere.

VALIDITY IS RECORDED, NOT ENFORCED
An NPI failing its checksum is flagged rather than dropped. Dropping rows hides
data quality problems; flagging them surfaces the problem while keeping the row
available for investigation.
"""

from __future__ import annotations

import re

import pandas as pd

_NON_DIGIT = re.compile(r"\D")


def _to_text(s: pd.Series) -> pd.Series:
    """
    Convert to string without the float artefacts pandas introduces.

    Reading an ID column as numeric turns 1003000126 into 1003000126.0, and
    naive str() then produces "1003000126.0" which matches nothing. This strips
    a trailing .0 before any other processing.
    """
    out = s.astype("string")
    out = out.str.replace(r"\.0$", "", regex=True)
    return out.str.strip()


def normalise_npi(s: pd.Series) -> pd.Series:
    """
    NPI -> 10-digit zero-padded string, or NA.

    Values that are not 10 digits after cleaning are set to NA rather than
    padded, because a 9-digit value is a different error from a formatting one
    and silently padding it would invent an identifier.
    """
    out = _to_text(s).str.replace(_NON_DIGIT, "", regex=True)
    out = out.where(out.str.len() == 10, pd.NA)
    return out.replace({"0000000000": pd.NA})


def npi_checksum_valid(s: pd.Series) -> pd.Series:
    """
    Luhn check with the NPI prefix 80840, per the NPI standard.

    Returns a boolean Series. Used to FLAG bad identifiers, never to drop rows.
    """
    def check(v) -> bool:
        if not isinstance(v, str) or len(v) != 10 or not v.isdigit():
            return False
        body, check_digit = v[:9], int(v[9])
        digits = [int(c) for c in "80840" + body]
        total = 0
        # Double every second digit from the right of the combined string.
        for i, d in enumerate(reversed(digits)):
            if i % 2 == 0:
                d *= 2
                if d > 9:
                    d -= 9
            total += d
        return (10 - total % 10) % 10 == check_digit

    return s.map(check).astype("boolean")


def normalise_ccn(s: pd.Series) -> pd.Series:
    """
    Medicare facility CCN -> 6 characters, uppercase, zero-padded.

    Leading zeros are the classic failure: '011500' becomes 11500 after a
    spreadsheet round-trip. Padding restores it. CCNs legitimately contain
    letters (e.g. '01S023'), so digits alone are not assumed.
    """
    out = _to_text(s).str.upper().str.replace(r"[^0-9A-Z]", "", regex=True)
    out = out.where(out.str.len().between(1, 6), pd.NA)
    return out.str.zfill(6).where(out.notna(), pd.NA)


def normalise_claim_id(s: pd.Series) -> pd.Series:
    """
    CMS claim id -> canonical signed string.

    Synthetic CMS claim ids are large NEGATIVE integers. Read as float they
    become -1.0000930037832e+13 and lose precision permanently, so this keeps
    them as text and preserves the sign explicitly.
    """
    out = _to_text(s)
    neg = out.str.startswith("-").fillna(False)
    digits = out.str.replace(_NON_DIGIT, "", regex=True)
    digits = digits.where(digits.str.len() > 0, pd.NA)
    return ("-" + digits).where(neg, digits)


def normalise_bene_id(s: pd.Series) -> pd.Series:
    """Beneficiary id - same shape and same hazards as claim id."""
    return normalise_claim_id(s)


def normalise_hcpcs(s: pd.Series) -> pd.Series:
    """
    HCPCS / CPT -> 5 characters, uppercase.

    Numeric CPT codes lose leading zeros the same way CCNs do ('00100' -> 100),
    so short values are re-padded to five characters.
    """
    out = _to_text(s).str.upper().str.replace(r"[^0-9A-Z]", "", regex=True)
    out = out.where(out.str.len().between(1, 5), pd.NA)
    return out.str.zfill(5).where(out.notna(), pd.NA)


_STATES = {
    "ALABAMA": "AL", "ALASKA": "AK", "ARIZONA": "AZ", "ARKANSAS": "AR",
    "CALIFORNIA": "CA", "COLORADO": "CO", "CONNECTICUT": "CT",
    "DELAWARE": "DE", "DISTRICT OF COLUMBIA": "DC", "FLORIDA": "FL",
    "GEORGIA": "GA", "HAWAII": "HI", "IDAHO": "ID", "ILLINOIS": "IL",
    "INDIANA": "IN", "IOWA": "IA", "KANSAS": "KS", "KENTUCKY": "KY",
    "LOUISIANA": "LA", "MAINE": "ME", "MARYLAND": "MD", "MASSACHUSETTS": "MA",
    "MICHIGAN": "MI", "MINNESOTA": "MN", "MISSISSIPPI": "MS", "MISSOURI": "MO",
    "MONTANA": "MT", "NEBRASKA": "NE", "NEVADA": "NV", "NEW HAMPSHIRE": "NH",
    "NEW JERSEY": "NJ", "NEW MEXICO": "NM", "NEW YORK": "NY",
    "NORTH CAROLINA": "NC", "NORTH DAKOTA": "ND", "OHIO": "OH",
    "OKLAHOMA": "OK", "OREGON": "OR", "PENNSYLVANIA": "PA",
    "RHODE ISLAND": "RI", "SOUTH CAROLINA": "SC", "SOUTH DAKOTA": "SD",
    "TENNESSEE": "TN", "TEXAS": "TX", "UTAH": "UT", "VERMONT": "VT",
    "VIRGINIA": "VA", "WASHINGTON": "WA", "WEST VIRGINIA": "WV",
    "WISCONSIN": "WI", "WYOMING": "WY", "PUERTO RICO": "PR",
    "VIRGIN ISLANDS": "VI", "GUAM": "GU",
}
STATE_NAME = {v: k.title() for k, v in _STATES.items()}


def normalise_state(s: pd.Series) -> pd.Series:
    """
    State -> 2-letter uppercase code.

    One dataset stores 'California' and another 'CA'. Joining them raw returns
    nothing, so both forms are collapsed to the code here.
    """
    out = _to_text(s).str.upper().str.strip()
    mapped = out.map(_STATES)
    two = out.where(out.str.len() == 2, pd.NA)
    return mapped.fillna(two)


def state_to_name(code: str | None) -> str | None:
    """Reverse lookup, for joining to CMS geography tables keyed on full name."""
    return STATE_NAME.get((code or "").upper())


def normalise_person_name(s: pd.Series) -> pd.Series:
    """Uppercase, collapse whitespace, strip punctuation. For fuzzy name links."""
    out = _to_text(s).str.upper()
    out = out.str.replace(r"[^A-Z\s'-]", "", regex=True)
    return out.str.replace(r"\s+", " ", regex=True).str.strip()
