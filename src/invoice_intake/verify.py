"""Verification: does the extracted data hold together, and will the accounting
API accept it?

The check is deliberately the *same arithmetic the API performs* (subtotal =
sum of line amounts; tax = floor(subtotal_for_code * rate) per code; total =
subtotal + tax). Re-deriving it here means:
  * we submit the canonical, API-acceptable numbers rather than the printed
    ones (printed totals can be off by a yen from vendor rounding), and
  * a misread line amount surfaces as a subtotal mismatch *before* we call the
    API, so a human sees it instead of a rejected POST.

This is the primary defence against a wrong LLM extraction. It is chosen over,
say, a second-model "LLM judge" because it is deterministic, free, and directly
predicts API acceptance.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional

from .models import ExtractedInvoice
from .normalize import tax_rate_to_code, to_iso_date

TAX_RATES = {"T10": 0.10, "T08": 0.08}


@dataclass
class Canonical:
    """Amounts recomputed from the line items — what we actually register."""
    subtotal: int
    tax_amount: int
    total_amount: int
    tax_by_code: Dict[str, int]
    issue_date: Optional[str]
    due_date: Optional[str]


@dataclass
class Verification:
    passed: bool
    issues: List[str] = field(default_factory=list)   # blocking -> review
    notes: List[str] = field(default_factory=list)     # non-blocking -> flag
    canonical: Optional[Canonical] = None


def compute_canonical(inv: ExtractedInvoice) -> Canonical:
    subtotal = sum(l.amount for l in inv.lines)
    by_code: Dict[str, int] = {}
    for l in inv.lines:
        code = tax_rate_to_code(l.tax_rate) or f"?{l.tax_rate}"
        by_code[code] = by_code.get(code, 0) + l.amount
    tax_by_code = {
        code: math.floor(sub * TAX_RATES[code])
        for code, sub in by_code.items()
        if code in TAX_RATES
    }
    tax = sum(tax_by_code.values())
    return Canonical(
        subtotal=subtotal,
        tax_amount=tax,
        total_amount=subtotal + tax,
        tax_by_code=tax_by_code,
        issue_date=to_iso_date(inv.issue_date),
        due_date=to_iso_date(inv.due_date),
    )


def verify(inv: ExtractedInvoice, rounding_tolerance_yen: int = 2) -> Verification:
    issues: List[str] = []
    notes: List[str] = []

    if not inv.invoice_number:
        issues.append("Missing invoice number.")
    if not inv.lines:
        issues.append("No line items extracted.")

    # Tax codes must be known to the API.
    unknown = sorted({l.tax_rate for l in inv.lines if tax_rate_to_code(l.tax_rate) is None})
    if unknown:
        issues.append(f"Unknown tax rate(s): {', '.join(str(u) + '%' for u in unknown)}.")

    canon = compute_canonical(inv)

    # Dates: parseable and logically ordered.
    if canon.issue_date is None:
        issues.append(f"Unparseable issue date: {inv.issue_date!r}.")
    if canon.due_date is None:
        issues.append(f"Unparseable due date: {inv.due_date!r}.")
    if canon.issue_date and canon.due_date:
        if date.fromisoformat(canon.due_date) < date.fromisoformat(canon.issue_date):
            issues.append(
                f"Due date {canon.due_date} precedes issue date {canon.issue_date}."
            )

    # Amount reconciliation against the printed summary.
    if inv.subtotal != canon.subtotal:
        issues.append(
            f"Subtotal mismatch: printed {inv.subtotal:,} vs sum of lines "
            f"{canon.subtotal:,} (a line amount was likely misread)."
        )
    else:
        d_tax = inv.tax_amount - canon.tax_amount
        d_total = inv.total_amount - canon.total_amount
        if d_total == 0 and d_tax == 0:
            pass  # clean
        elif abs(d_total) <= rounding_tolerance_yen and abs(d_tax) <= rounding_tolerance_yen:
            notes.append(
                f"Printed total {inv.total_amount:,} differs from recomputed "
                f"{canon.total_amount:,} by ¥{d_total:+d} (vendor tax rounding); "
                f"registered the recomputed value."
            )
        else:
            issues.append(
                f"Tax/total mismatch beyond rounding: printed total "
                f"{inv.total_amount:,} vs recomputed {canon.total_amount:,}."
            )

    if inv.currency and inv.currency != "JPY":
        issues.append(f"Unsupported currency: {inv.currency}.")

    return Verification(passed=not issues, issues=issues, notes=notes, canonical=canon)
