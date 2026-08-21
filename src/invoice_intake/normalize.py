"""Deterministic normalization of extracted values into what the API accepts.

We ask the LLM to return ISO dates and integer percents, but we never trust
that blindly — these helpers re-derive the canonical form ourselves so a model
slip (or a Reiwa-era date it echoed verbatim) is caught rather than forwarded.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Optional

# tax_rate (printed percent) -> accounting API tax_code
_RATE_TO_CODE = {10: "T10", 8: "T08"}

# Japanese era -> Gregorian year offset (year N of era == base + N).
# e.g. 令和1年 == 2019, so base 2018.
_ERA_BASE = {
    "令和": 2018,
    "R": 2018,
    "平成": 1988,
    "H": 1988,
    "昭和": 1925,
    "S": 1925,
}

_ISO = re.compile(r"^\s*(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})\s*$")
_JP = re.compile(r"^\s*(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日?\s*$")
_ERA = re.compile(r"^\s*(令和|平成|昭和|R|H|S)\s*(\d{1,2}|元)\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日?\s*$")


def to_iso_date(raw: Optional[str]) -> Optional[str]:
    """Convert a printed date into 'YYYY-MM-DD', or None if it can't be parsed.

    Accepts ISO ('2026-02-05'), slashed ('2026/02/05'), Japanese
    ('2026年2月5日') and Japanese-era ('令和8年2月5日') forms.
    """
    if not raw:
        return None
    s = str(raw).strip()

    m = _ISO.match(s) or _JP.match(s)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return _safe(y, mo, d)

    m = _ERA.match(s)
    if m:
        era, yr, mo, d = m.group(1), m.group(2), int(m.group(3)), int(m.group(4))
        year_in_era = 1 if yr == "元" else int(yr)
        return _safe(_ERA_BASE[era] + year_in_era, mo, int(d))

    return None


def _safe(y: int, mo: int, d: int) -> Optional[str]:
    try:
        return date(y, mo, d).isoformat()
    except ValueError:
        return None


def tax_rate_to_code(rate: int) -> Optional[str]:
    return _RATE_TO_CODE.get(int(rate))


def normalize_unit(unit: Optional[str]) -> str:
    """The API requires a non-empty unit; lump-sum lines print none, so default
    to 式 (the common 'one lot / lump sum' unit)."""
    u = (unit or "").strip()
    return u or "式"


def normalize_supplier_name(name: Optional[str]) -> str:
    """Collapse whitespace for robust master matching (full-width kept as-is)."""
    return re.sub(r"\s+", "", (name or "")).strip()
