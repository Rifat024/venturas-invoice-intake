"""The extraction contract shared by every provider.

`INVOICE_SCHEMA` and `EXTRACTION_PROMPT` live here so the prompt and the JSON
shape are defined once, independent of which model executes them.
"""
from __future__ import annotations

from typing import Protocol

from ..ingest import Document

# JSON shape we ask the model to return. Kept close to how a person reading the
# page would transcribe it: printed percents, printed amounts, printed dates.
INVOICE_SCHEMA = {
    "type": "object",
    "properties": {
        "invoice_number": {"type": "string"},
        "issue_date": {"type": "string", "description": "ISO YYYY-MM-DD"},
        "due_date": {"type": "string", "description": "ISO YYYY-MM-DD"},
        "supplier_name": {"type": "string", "description": "Issuer of the invoice"},
        "supplier_registration_no": {"type": "string", "description": "登録番号, e.g. T1234..."},
        "currency": {"type": "string"},
        "lines": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                    "quantity": {"type": "integer", "nullable": True},
                    "unit": {"type": "string"},
                    "unit_price": {"type": "integer", "nullable": True},
                    "amount": {"type": "integer", "description": "May be negative for discounts"},
                    "tax_rate": {"type": "integer", "description": "Printed percent: 10 or 8"},
                },
                "required": ["description", "amount", "tax_rate"],
            },
        },
        "subtotal": {"type": "integer"},
        "tax_amount": {"type": "integer"},
        "total_amount": {"type": "integer"},
        "confidence": {"type": "number", "description": "0..1 self-rated legibility"},
        "notes": {"type": "string", "description": "Anomalies: handwriting, stamps, unclear digits"},
    },
    "required": [
        "invoice_number", "issue_date", "due_date", "supplier_name",
        "lines", "subtotal", "tax_amount", "total_amount", "confidence",
    ],
}

EXTRACTION_PROMPT = """You are reading one Japanese supplier invoice (請求書 / 御請求書).
Return ONLY structured data matching the schema. Transcribe exactly what is printed.

Rules:
- supplier_name / supplier_registration_no: the ISSUER (the company being paid),
  NOT the addressee 株式会社サンプル商事. The 登録番号 starts with 'T'.
- Amounts are integer yen. Remove commas and the ¥ sign. A leading △ or ▲ means
  NEGATIVE (a discount) -> return a negative integer.
- tax_rate is the printed percent (10 or 8). If a line shows no rate but the
  invoice has a single 消費税 rate, use that rate for every line.
- Dates: convert to ISO YYYY-MM-DD. Japanese-era dates (令和8年 = 2026) must be
  converted, not echoed.
- quantity / unit_price may be null for lump-sum (一式 / 式) lines; amount is always present.
- IGNORE handwriting, stamps and marginal notes (受領, 至急, hand-edited bank
  numbers). Transcribe only the printed invoice, and mention any such marks in `notes`.
- Set `confidence` lower when digits are blurred or the layout is ambiguous.
"""


class Provider(Protocol):
    """Anything that can turn a Document into the raw extraction dict."""

    def extract(self, document: Document) -> dict: ...
