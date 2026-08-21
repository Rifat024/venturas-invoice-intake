"""Thin client for the mock accounting API, plus the payload builder.

The API is treated as an immutable external system: we cannot change its rules,
so we adapt to them (integer JPY, ISO dates, tax_code per line, amounts it will
recompute). We surface its documented error codes rather than swallowing them.
"""
from __future__ import annotations

import json
from typing import Dict, List, Optional, Tuple
from urllib import error, request

from .models import ExtractedInvoice
from .normalize import normalize_unit, tax_rate_to_code
from .verify import Canonical


class AccountingClient:
    def __init__(self, base_url: str, api_key: str, timeout: int = 15):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def _request(self, method: str, path: str, body: Optional[dict] = None) -> Tuple[int, dict]:
        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = request.Request(url, data=data, method=method)
        req.add_header("X-API-Key", self.api_key)
        if data is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with request.urlopen(req, timeout=self.timeout) as resp:
                return resp.status, json.loads(resp.read() or b"{}")
        except error.HTTPError as e:  # the API returns JSON envelopes on errors too
            try:
                return e.code, json.loads(e.read() or b"{}")
            except Exception:
                return e.code, {"success": False, "error": {"code": "HTTP_ERROR", "message": str(e)}}
        except error.URLError as e:  # server down / unreachable
            raise ConnectionError(
                f"Cannot reach accounting API at {self.base_url} ({e.reason}). "
                f"Start it with: python3 accounting_api.py"
            ) from e

    # --- reads ---
    def health(self) -> dict:
        return self._request("GET", "/health")[1]

    def get_partners(self) -> List[Dict]:
        return self._request("GET", "/partners")[1]["data"]["partners"]

    def get_tax_codes(self) -> List[Dict]:
        return self._request("GET", "/tax-codes")[1]["data"]["tax_codes"]

    def list_invoices(self) -> List[Dict]:
        return self._request("GET", "/invoices")[1]["data"]["invoices"]

    def delete_all(self) -> int:
        return self._request("DELETE", "/invoices")[1]["data"]["removed"]

    # --- write ---
    def create_invoice(self, payload: dict) -> Tuple[int, dict]:
        return self._request("POST", "/invoices", payload)


def build_payload(inv: ExtractedInvoice, partner_code: str, canonical: Canonical) -> dict:
    """Map an extracted invoice + resolved partner into the API's request shape.

    Amounts come from `canonical` (recomputed from the lines) so they always
    satisfy the API's re-derivation; dates come from `canonical` (already ISO).
    """
    lines = [
        {
            "description": l.description,
            "quantity": l.quantity,
            "unit": normalize_unit(l.unit),
            "unit_price": l.unit_price,
            "amount": l.amount,
            "tax_code": tax_rate_to_code(l.tax_rate),
        }
        for l in inv.lines
    ]
    return {
        "partner_code": partner_code,
        "invoice_number": inv.invoice_number,
        "issue_date": canonical.issue_date,
        "due_date": canonical.due_date,
        "currency": "JPY",
        "lines": lines,
        "subtotal": canonical.subtotal,
        "tax_amount": canonical.tax_amount,
        "total_amount": canonical.total_amount,
    }
