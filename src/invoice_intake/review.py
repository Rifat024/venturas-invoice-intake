"""Optional human-review screen (FastAPI).

The pipeline routes anything it will not auto-register into out/review_queue.json.
This app puts a person in that loop: it shows each held invoice next to its
original image, explains why it was held, and lets the reviewer correct the
supplier / fields and register it — or leave it. It reuses the exact same
verify + build_payload + AccountingClient path as the batch pipeline, so a
human approval goes through identical validation.

Run:  python -m invoice_intake serve      (then open http://127.0.0.1:8000)
"""
from __future__ import annotations

import html
import json
import tempfile
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from .config import load_config
from .extract import extract_live
from .models import ExtractedInvoice
from .partners import match_partner
from .register import AccountingClient, build_payload
from .verify import verify

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"
INVOICES = ROOT / "invoices"


def _load_report() -> dict:
    rp = OUT / "run_report.json"
    if not rp.exists():
        return {"results": []}
    return json.loads(rp.read_text(encoding="utf-8"))


def _held_items(report: dict) -> List[dict]:
    return [r for r in report["results"] if r["status"] in ("needs_review", "duplicate", "failed")]


def create_app():
    app = FastAPI(title="Invoice Intake — Human Review")
    config = load_config()
    client = AccountingClient(config.api_url, config.api_key)
    _provider = {}  # lazy, built on first upload

    def partners():
        return client.get_partners()

    def get_provider():
        if "p" not in _provider:
            from .llm.gemini import GeminiProvider

            _provider["p"] = GeminiProvider(config.gemini_api_key, config.gemini_model)
        return _provider["p"]

    @app.get("/", response_class=HTMLResponse)
    def index():
        report = _load_report()
        held = _held_items(report)
        registered = [r for r in report["results"] if r["status"] == "registered"]
        return _render_index(held, registered)

    @app.get("/image/{filename}")
    def image(filename: str):
        p = INVOICES / filename
        if not p.exists() or p.parent != INVOICES:  # guard against path traversal
            raise HTTPException(404)
        mime = "application/pdf" if p.suffix.lower() == ".pdf" else "image/jpeg"
        return Response(p.read_bytes(), media_type=mime)

    @app.get("/review/{filename}", response_class=HTMLResponse)
    def review_item(filename: str):
        item = _find(filename)
        if not item:
            raise HTTPException(404)
        return _render_detail(item, partners())

    @app.post("/review/{filename}/register")
    def do_register(filename: str, partner_code: str = Form(...)):
        item = _find(filename)
        if not item or not item.get("extracted"):
            raise HTTPException(404)
        inv = ExtractedInvoice.from_dict(item["extracted"], source_file=filename)
        v = verify(inv, rounding_tolerance_yen=config.rounding_tolerance_yen)
        if not v.passed:
            return HTMLResponse(_banner_page(filename, "Still fails verification: " + "; ".join(v.issues)))
        payload = build_payload(inv, partner_code, v.canonical)
        _status, body = client.create_invoice(payload)
        if body.get("success"):
            _mark_registered(filename, partner_code, body["data"]["accounting_id"])
            return RedirectResponse(f"/?registered={filename}", status_code=303)
        err = (body.get("error") or {})
        return HTMLResponse(_banner_page(filename, f"API rejected ({err.get('code')}): {err.get('message')}"))

    # --- "convert any document to JSON" ---
    @app.get("/upload", response_class=HTMLResponse)
    def upload_form():
        return _render_upload()

    @app.post("/upload", response_class=HTMLResponse)
    async def upload(file: UploadFile = File(...)):
        data = await file.read()
        suffix = Path(file.filename or "doc").suffix or ".pdf"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(data)
            tmp_path = tmp.name
        try:
            inv = extract_live(tmp_path, get_provider())
        except Exception as e:
            return HTMLResponse(_render_upload(error=str(e)))
        v = verify(inv, rounding_tolerance_yen=config.rounding_tolerance_yen)
        partner, method = match_partner(
            partners(), inv.supplier_name, inv.supplier_registration_no
        )
        return _render_extraction(inv, v, partner, method)

    return app


# --- persistence of a human decision back into the report ---
def _find(filename: str) -> Optional[dict]:
    for r in _load_report()["results"]:
        if r["source_file"] == filename:
            return r
    return None


def _mark_registered(filename: str, partner_code: str, accounting_id: str) -> None:
    rp = OUT / "run_report.json"
    report = _load_report()
    for r in report["results"]:
        if r["source_file"] == filename:
            r["status"] = "registered"
            r["partner_code"] = partner_code
            r["accounting_id"] = accounting_id
            r["partner_match_method"] = "human_review"
            r.setdefault("notes", []).append("Registered via human review.")
    rp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


# --- tiny server-rendered HTML (no build step, self-contained) ---
_STYLE = """
<style>
 body{font-family:-apple-system,Segoe UI,Roboto,sans-serif;margin:0;background:#f6f7f9;color:#1a1a1a}
 header{background:#0f172a;color:#fff;padding:16px 24px}
 header h1{margin:0;font-size:18px}
 .wrap{max-width:1100px;margin:24px auto;padding:0 24px}
 .card{background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:16px;margin-bottom:14px}
 table{width:100%;border-collapse:collapse}
 th,td{text-align:left;padding:8px 10px;border-bottom:1px solid #eef0f2;font-size:14px}
 .pill{display:inline-block;padding:2px 9px;border-radius:999px;font-size:12px;font-weight:600}
 .review{background:#fef3c7;color:#92400e}.duplicate{background:#e0e7ff;color:#3730a3}
 .failed{background:#fee2e2;color:#991b1b}.registered{background:#dcfce7;color:#166534}
 .grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}
 img,embed{width:100%;border:1px solid #e5e7eb;border-radius:8px;background:#fff}
 a.btn,button{background:#2563eb;color:#fff;border:0;border-radius:8px;padding:9px 14px;font-size:14px;cursor:pointer;text-decoration:none;display:inline-block}
 a{color:#2563eb} .muted{color:#6b7280;font-size:13px} .issue{color:#92400e}
 select,input{padding:8px;border:1px solid #cbd5e1;border-radius:8px;font-size:14px}
</style>
"""


def _page(title: str, body: str) -> str:
    return f"<!doctype html><meta charset='utf-8'><title>{html.escape(title)}</title>{_STYLE}<header><h1>{html.escape(title)}</h1></header><div class='wrap'>{body}</div>"


def _render_index(held: List[dict], registered: List[dict]) -> str:
    rows = ""
    for it in held:
        f = it["source_file"]
        reason = (it["issues"][0] if it.get("issues") else "")
        rows += (
            f"<tr><td><a href='/review/{html.escape(f)}'>{html.escape(f)}</a></td>"
            f"<td><span class='pill {it['status']}'>{it['status']}</span></td>"
            f"<td>{html.escape(str(it.get('supplier_name') or ''))}</td>"
            f"<td>{'{:,}'.format(it['total_amount']) if it.get('total_amount') else '-'}</td>"
            f"<td class='issue'>{html.escape(reason)}</td></tr>"
        )
    body = (
        f"<div class='card'><b>{len(held)}</b> invoice(s) awaiting review · "
        f"<b>{len(registered)}</b> auto-registered. &nbsp; "
        f"<a class='btn' href='/upload'>Convert a new document →</a></div>"
        f"<div class='card'><table><tr><th>File</th><th>Status</th><th>Supplier</th>"
        f"<th>Total</th><th>Why held</th></tr>{rows or '<tr><td colspan=5 class=muted>Nothing to review.</td></tr>'}</table></div>"
    )
    return _page("Invoice Intake — Human Review", body)


def _render_upload(error: Optional[str] = None) -> str:
    err = f"<p class='issue'>Extraction failed: {html.escape(error)}</p>" if error else ""
    body = f"""
    <p><a href='/'>&larr; Back to queue</a></p>
    <div class='card'>
      <h3>Convert any invoice to structured JSON</h3>
      <p class='muted'>Drop a PDF or image; it is read with Gemini and returned as the
         accounting-system JSON, with verification and supplier matching. Requires
         GEMINI_API_KEY (live mode).</p>
      {err}
      <form method='post' action='/upload' enctype='multipart/form-data'>
        <input type='file' name='file' accept='.pdf,.jpg,.jpeg,.png' required>
        <button type='submit'>Extract →</button>
      </form>
    </div>"""
    return _page("Convert document", body)


def _render_extraction(inv: ExtractedInvoice, v, partner, method) -> str:
    payload = json.dumps(inv.to_dict(), ensure_ascii=False, indent=2)
    if v.passed and partner is not None:
        verdict = f"<span class='pill registered'>would auto-register</span> as {html.escape(partner['partner_code'])} ({html.escape(method)})"
    else:
        verdict = "<span class='pill review'>would go to human review</span>"
    reasons = "".join(f"<li class='issue'>{html.escape(i)}</li>" for i in v.issues)
    notes = "".join(f"<li class='muted'>{html.escape(n)}</li>" for n in v.notes)
    canon = v.canonical
    body = f"""
    <p><a href='/upload'>&larr; Convert another</a> · <a href='/'>Queue</a></p>
    <div class='card'>
      <h3>{html.escape(inv.invoice_number)} · {html.escape(inv.supplier_name)}</h3>
      <p>Decision: {verdict}</p>
      <p class='muted'>Recomputed subtotal {canon.subtotal:,} · tax {canon.tax_amount:,} ·
         total {canon.total_amount:,} · confidence {inv.confidence}</p>
      {('<ul>' + reasons + notes + '</ul>') if (reasons or notes) else ''}
    </div>
    <div class='card'><b>Structured JSON</b>
      <pre style='overflow:auto;background:#0f172a;color:#e2e8f0;padding:14px;border-radius:8px'>{html.escape(payload)}</pre>
    </div>"""
    return _page("Extraction result", body)


def _render_detail(item: dict, partner_list: List[dict]) -> str:
    f = item["source_file"]
    ext = item.get("extracted") or {}
    issues = "".join(f"<li class='issue'>{html.escape(i)}</li>" for i in item.get("issues", []))
    options = "".join(
        f"<option value='{html.escape(p['partner_code'])}'"
        f"{' selected' if item.get('partner_code') == p['partner_code'] else ''}>"
        f"{html.escape(p['partner_code'])} — {html.escape(p['name'])}</option>"
        for p in partner_list
    )
    lines = "".join(
        f"<tr><td>{html.escape(str(l.get('description','')))}</td>"
        f"<td>{l.get('quantity') if l.get('quantity') is not None else ''}</td>"
        f"<td>{'{:,}'.format(l['amount'])}</td><td>{l.get('tax_rate')}%</td></tr>"
        for l in ext.get("lines", [])
    )
    viewer = (
        f"<embed src='/image/{html.escape(f)}' type='application/pdf' height='560'>"
        if f.lower().endswith(".pdf")
        else f"<img src='/image/{html.escape(f)}'>"
    )
    body = f"""
    <p><a href='/'>&larr; Back to queue</a></p>
    <div class='grid'>
      <div class='card'>{viewer}</div>
      <div class='card'>
        <h3>{html.escape(ext.get('invoice_number',''))} · {html.escape(ext.get('supplier_name',''))}</h3>
        <p class='muted'>Reg {html.escape(str(ext.get('supplier_registration_no') or '—'))} ·
           issue {html.escape(str(ext.get('issue_date')))} · due {html.escape(str(ext.get('due_date')))} ·
           confidence {ext.get('confidence')}</p>
        <p><b>Held because:</b></p><ul>{issues}</ul>
        <table><tr><th>Description</th><th>Qty</th><th>Amount</th><th>Tax</th></tr>{lines}
          <tr><td colspan=2><b>Total (printed)</b></td><td colspan=2><b>{'{:,}'.format(ext.get('total_amount',0))}</b></td></tr>
        </table>
        <form method='post' action='/review/{html.escape(f)}/register' style='margin-top:14px'>
          <label class='muted'>Assign supplier (partner master):</label><br>
          <select name='partner_code' style='min-width:320px;margin:8px 0'>{options}</select><br>
          <button type='submit'>Approve &amp; register</button>
        </form>
      </div>
    </div>"""
    return _page(f"Review — {f}", body)


def _banner_page(filename: str, message: str) -> str:
    return _page(
        "Review",
        f"<div class='card'><p class='issue'>{html.escape(message)}</p>"
        f"<a href='/review/{html.escape(filename)}'>&larr; Back</a></div>",
    )


def run_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    import uvicorn

    uvicorn.run(create_app(), host=host, port=port)
