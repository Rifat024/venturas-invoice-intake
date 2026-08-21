"""Orchestration: for each invoice, extract -> match partner -> verify ->
decide (register vs review), and register the clean ones.

The automation boundary is explicit and conservative. An invoice is registered
automatically only when ALL of these hold:
  * the supplier resolves to a row in the partner master,
  * the arithmetic reconciles (within the rounding tolerance),
  * the model's self-rated confidence clears the threshold, and
  * it is not a duplicate of one already seen/registered.
Anything else goes to the review queue with a reason. Duplicate detection is
what protects against the CEO's "paid the same invoice twice" fear.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Dict, List, Set, Tuple

from .config import Config
from .ingest import IMAGE_EXTS
from .models import (
    AUTO_REGISTERED, DUPLICATE, FAILED, NEEDS_REVIEW, ExtractedInvoice, InvoiceResult,
)
from .partners import match_partner
from .register import AccountingClient, build_payload
from .verify import verify

SUPPORTED_EXTS = set(IMAGE_EXTS) | {".pdf"}


def discover_invoices(directory: str) -> List[str]:
    d = Path(directory)
    return [str(p) for p in sorted(d.iterdir()) if p.suffix.lower() in SUPPORTED_EXTS]


def process_files(
    paths: List[str],
    extract_fn: Callable[[str], ExtractedInvoice],
    client: AccountingClient,
    config: Config,
    register: bool = True,
) -> List[InvoiceResult]:
    """Run the pipeline over an explicit list of files (one or many).

    `extract_fn` maps a file path -> ExtractedInvoice (live or offline); the
    pipeline is agnostic to which."""
    partners = client.get_partners()
    # Seed dedup with invoices already in the accounting system (idempotent reruns).
    seen: Set[Tuple[str, str]] = {
        (r["partner_code"], r["invoice_number"]) for r in client.list_invoices()
    }
    return [
        _process_one(path, extract_fn, partners, seen, client, config, register)
        for path in paths
    ]


def process_all(
    directory: str,
    extract_fn: Callable[[str], ExtractedInvoice],
    client: AccountingClient,
    config: Config,
    register: bool = True,
) -> List[InvoiceResult]:
    """Run the whole batch over every invoice in `directory`."""
    return process_files(discover_invoices(directory), extract_fn, client, config, register)


def _process_one(
    path, extract_fn, partners, seen, client, config, register,
) -> InvoiceResult:
    name = Path(path).name
    res = InvoiceResult(source_file=name, status=NEEDS_REVIEW)

    # 1. Extract
    try:
        inv = extract_fn(path)
    except Exception as e:  # extraction blew up entirely
        res.status = FAILED
        res.issues.append(f"Extraction failed: {e}")
        return res
    res.extracted = inv

    # 2. Match supplier to the master
    partner, method = match_partner(partners, inv.supplier_name, inv.supplier_registration_no)
    res.partner_match_method = method
    if partner is None:
        res.status = NEEDS_REVIEW
        res.issues.append(
            f"Supplier '{inv.supplier_name}' (reg {inv.supplier_registration_no}) "
            f"is not in the partner master — cannot be registered."
        )
        return res
    res.partner_code = partner["partner_code"]

    # 3. Verify arithmetic / dates / tax codes
    v = verify(inv, rounding_tolerance_yen=config.rounding_tolerance_yen)
    res.notes.extend(v.notes)
    if not v.passed:
        res.issues.extend(v.issues)
        res.status = NEEDS_REVIEW
        return res

    # 4. Confidence gate
    if inv.confidence < config.confidence_threshold:
        res.issues.append(
            f"Low extraction confidence {inv.confidence:.2f} < {config.confidence_threshold:.2f}."
        )
        res.status = NEEDS_REVIEW
        return res

    # 5. Duplicate gate (batch + already-registered)
    key = (res.partner_code, inv.invoice_number)
    if key in seen:
        res.status = DUPLICATE
        res.issues.append(
            f"Duplicate: invoice {inv.invoice_number} for {res.partner_code} "
            f"was already seen — held to avoid double payment."
        )
        return res

    # 6. Register (unless --no-register)
    payload = build_payload(inv, res.partner_code, v.canonical)
    if not register:
        res.notes.append("Dry run: passed all checks, not submitted.")
        res.status = NEEDS_REVIEW  # not registered, but clean
        res.issues.append("Not registered (dry run).")
        return res

    _status, body = client.create_invoice(payload)
    if body.get("success"):
        res.status = AUTO_REGISTERED
        res.accounting_id = body["data"]["accounting_id"]
        seen.add(key)
    else:
        err = body.get("error") or {}
        res.api_error_code = err.get("code")
        if err.get("code") == "DUPLICATE_INVOICE":
            res.status = DUPLICATE
            res.issues.append("API rejected as duplicate — held to avoid double payment.")
            seen.add(key)
        else:
            res.status = NEEDS_REVIEW
            res.issues.append(
                f"API rejected ({err.get('code')}): {err.get('message')}"
            )
    return res


def summarize(results: List[InvoiceResult]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for r in results:
        counts[r.status] = counts.get(r.status, 0) + 1
    return counts
