"""Human- and machine-readable output for a run.

Prints a per-invoice table to the terminal (no third-party deps) and writes two
JSON artifacts: the full run report and the review queue that a human works.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

from .models import (
    AUTO_REGISTERED, DUPLICATE, FAILED, NEEDS_REVIEW, InvoiceResult,
)

_LABEL = {
    AUTO_REGISTERED: "REGISTERED",
    DUPLICATE: "DUPLICATE",
    NEEDS_REVIEW: "REVIEW",
    FAILED: "FAILED",
}


def _row(cols, widths) -> str:
    return "  ".join(str(c).ljust(w)[:w] for c, w in zip(cols, widths))


def print_table(results: List[InvoiceResult]) -> None:
    widths = (16, 11, 9, 8, 13, 40)
    header = _row(["File", "Status", "Partner", "AcctID", "Total(JPY)", "Reason / note"], widths)
    print("\n" + header)
    print("-" * len(header))
    for r in results:
        total = f"{r.extracted.total_amount:,}" if r.extracted else "-"
        reason = ""
        if r.issues:
            reason = r.issues[0]
        elif r.notes:
            reason = r.notes[0]
        print(_row(
            [r.source_file, _LABEL.get(r.status, r.status), r.partner_code or "-",
             r.accounting_id or "-", total, reason],
            widths,
        ))
    print("-" * len(header))


def print_summary(results: List[InvoiceResult]) -> None:
    counts: Dict[str, int] = {}
    for r in results:
        counts[r.status] = counts.get(r.status, 0) + 1
    parts = [f"{_LABEL.get(k, k)}: {v}" for k, v in sorted(counts.items())]
    print("Summary  " + " | ".join(parts) + f"  (total {len(results)})")


def _result_to_dict(r: InvoiceResult) -> dict:
    return {
        "source_file": r.source_file,
        "status": r.status,
        "partner_code": r.partner_code,
        "partner_match_method": r.partner_match_method,
        "accounting_id": r.accounting_id,
        "invoice_number": r.extracted.invoice_number if r.extracted else None,
        "supplier_name": r.extracted.supplier_name if r.extracted else None,
        "total_amount": r.extracted.total_amount if r.extracted else None,
        "confidence": r.extracted.confidence if r.extracted else None,
        "api_error_code": r.api_error_code,
        "issues": r.issues,
        "notes": r.notes,
        # Full extraction, so the review UI can act without re-reading the file.
        "extracted": r.extracted.to_dict() if r.extracted else None,
    }


def write_json(results: List[InvoiceResult], out_dir: str = "out") -> Dict[str, str]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat()

    report = {
        "generated_at": ts,
        "results": [_result_to_dict(r) for r in results],
    }
    review = {
        "generated_at": ts,
        "items": [
            _result_to_dict(r) for r in results
            if r.status in (NEEDS_REVIEW, DUPLICATE, FAILED)
        ],
    }
    rp = out / "run_report.json"
    rq = out / "review_queue.json"
    rp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    rq.write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"run_report": str(rp), "review_queue": str(rq)}
