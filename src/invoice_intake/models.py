"""Typed data structures passed between pipeline stages.

Kept deliberately small: the raw LLM output (`ExtractedInvoice`) uses the
invoice's own vocabulary (tax_rate as an integer percent, amounts as printed).
Mapping to the accounting API's vocabulary (tax_code, recomputed amounts)
happens later, in verify/register, so the extraction schema stays close to
what a human reading the page would write down.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import List, Optional


@dataclass
class LineItem:
    description: str
    amount: int                      # JPY, integer; may be negative (discounts)
    tax_rate: int                    # percent as printed: 10 or 8
    quantity: Optional[int] = None   # null for lump-sum ("一式") lines
    unit: Optional[str] = None
    unit_price: Optional[int] = None


@dataclass
class ExtractedInvoice:
    """What the LLM read off one invoice, before normalization/verification."""
    invoice_number: str
    issue_date: str                  # as returned by the model (ideally ISO)
    due_date: str
    supplier_name: str
    supplier_registration_no: Optional[str]
    lines: List[LineItem]
    subtotal: int
    tax_amount: int
    total_amount: int
    currency: str = "JPY"
    confidence: float = 0.0
    notes: str = ""
    source_file: str = ""

    @classmethod
    def from_dict(cls, d: dict, source_file: str = "") -> "ExtractedInvoice":
        lines = [
            LineItem(
                description=str(l.get("description", "")).strip(),
                amount=int(l["amount"]),
                tax_rate=int(l["tax_rate"]),
                quantity=(None if l.get("quantity") in (None, "") else int(l["quantity"])),
                unit=(l.get("unit") or None),
                unit_price=(None if l.get("unit_price") in (None, "") else int(l["unit_price"])),
            )
            for l in d.get("lines", [])
        ]
        return cls(
            invoice_number=str(d.get("invoice_number", "")).strip(),
            issue_date=str(d.get("issue_date", "")).strip(),
            due_date=str(d.get("due_date", "")).strip(),
            supplier_name=str(d.get("supplier_name", "")).strip(),
            supplier_registration_no=(d.get("supplier_registration_no") or None),
            lines=lines,
            subtotal=int(d["subtotal"]),
            tax_amount=int(d["tax_amount"]),
            total_amount=int(d["total_amount"]),
            currency=str(d.get("currency", "JPY")),
            confidence=float(d.get("confidence", 0.0)),
            notes=str(d.get("notes", "")),
            source_file=source_file,
        )

    def to_dict(self) -> dict:
        return asdict(self)


# Routing outcomes for a single invoice.
AUTO_REGISTERED = "registered"
DUPLICATE = "duplicate"
NEEDS_REVIEW = "needs_review"
FAILED = "failed"


@dataclass
class InvoiceResult:
    source_file: str
    status: str                      # one of the constants above
    extracted: Optional[ExtractedInvoice] = None
    partner_code: Optional[str] = None
    partner_match_method: Optional[str] = None
    accounting_id: Optional[str] = None
    issues: List[str] = field(default_factory=list)   # human-readable reasons
    notes: List[str] = field(default_factory=list)     # non-blocking flags
    api_error_code: Optional[str] = None
