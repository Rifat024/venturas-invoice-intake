import json
from pathlib import Path

from invoice_intake.models import ExtractedInvoice
from invoice_intake.verify import compute_canonical, verify

FIXTURES = Path(__file__).parent / "fixtures"


def load(name) -> ExtractedInvoice:
    return ExtractedInvoice.from_dict(
        json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8")), f"{name}"
    )


def test_single_rate_canonical():
    inv = load("invoice_01")
    c = compute_canonical(inv)
    assert c.subtotal == 304000
    assert c.tax_amount == 30400
    assert c.total_amount == 334400
    assert verify(inv).passed


def test_mixed_rate_floors_per_code():
    # invoice_03: T10 on 39,500 -> 3,950 ; T08 on 75,840 -> 6,067 (floored).
    c = compute_canonical(load("invoice_03"))
    assert c.tax_by_code == {"T10": 3950, "T08": 6067}
    assert c.tax_amount == 10017
    assert verify(load("invoice_03")).passed


def test_negative_discount_line():
    # invoice_12: 450,000 + 120,000 - 30,000 = 540,000.
    c = compute_canonical(load("invoice_12"))
    assert c.subtotal == 540000
    assert c.total_amount == 594000
    assert verify(load("invoice_12")).passed


def test_printed_total_rounding_is_flagged_not_blocked():
    # invoice_09: printed total 147,497 but lines reconcile to 147,496.
    inv = load("invoice_09")
    v = verify(inv, rounding_tolerance_yen=2)
    assert v.passed                      # within tolerance -> still auto
    assert v.canonical.total_amount == 147496
    assert any("rounding" in n for n in v.notes)


def test_subtotal_mismatch_blocks():
    inv = load("invoice_01")
    inv.lines[0].amount += 5000          # simulate a misread digit
    v = verify(inv)
    assert not v.passed
    assert any("Subtotal mismatch" in i for i in v.issues)


def test_large_total_mismatch_blocks():
    inv = load("invoice_01")
    inv.total_amount += 500              # beyond rounding tolerance
    v = verify(inv, rounding_tolerance_yen=2)
    assert not v.passed


def test_due_before_issue_blocks():
    inv = load("invoice_01")
    inv.due_date = "2025-01-01"
    v = verify(inv)
    assert not v.passed
    assert any("precedes issue" in i for i in v.issues)


def test_unknown_tax_rate_blocks():
    inv = load("invoice_01")
    inv.lines[0].tax_rate = 5
    v = verify(inv)
    assert not v.passed
