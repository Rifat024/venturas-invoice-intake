"""Match the supplier printed on an invoice to a row in the accounting API's
partner master.

Only suppliers in the master can be registered, so this is the gate between
"machine can proceed" and "a human must decide". We match on the strongest
signal first — the tax registration number is a national ID and effectively
unique — then fall back to the official name and its aliases.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from .normalize import normalize_supplier_name

# Match methods, strongest first (also used to explain the decision in reports).
BY_REGISTRATION = "registration_no"
BY_NAME = "name"
BY_ALIAS = "alias"
UNMATCHED = "unmatched"


def match_partner(
    partners: List[Dict], supplier_name: Optional[str], registration_no: Optional[str]
) -> Tuple[Optional[Dict], str]:
    """Return (partner_row, method). partner_row is None when nothing matches."""
    reg = (registration_no or "").strip().upper()
    if reg:
        for p in partners:
            if (p.get("registration_no") or "").strip().upper() == reg:
                return p, BY_REGISTRATION

    name = normalize_supplier_name(supplier_name)
    if name:
        for p in partners:
            if normalize_supplier_name(p.get("name")) == name:
                return p, BY_NAME
        for p in partners:
            for alias in p.get("aliases", []):
                if normalize_supplier_name(alias) == name:
                    return p, BY_ALIAS
        # Last resort: containment either direction (e.g. an alias printed with
        # or without the 株式会社 prefix). Deliberately conservative.
        for p in partners:
            candidates = [p.get("name", "")] + list(p.get("aliases", []))
            for cand in candidates:
                c = normalize_supplier_name(cand)
                if c and (c in name or name in c):
                    return p, BY_ALIAS

    return None, UNMATCHED
