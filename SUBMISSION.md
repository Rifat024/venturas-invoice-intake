# Submission

- Name: Rifat Bin Siraj
- Submission date (YYYY-MM-DD): 2026-08-21
- Hours actually spent: ~8
- Repository / how to run it: https://github.com/Rifat024/venturas-invoice-intake — `./run.sh` (offline, no key) or `./run.sh live` with a `GEMINI_API_KEY`. Human-review screen: `./run.sh serve`.

## 1. Understanding the request

The client described a **data-entry** problem: staff retype supplier invoices into
the accounting system every month, month-end runs into overtime, and once a typo
"nearly caused us to pay the same invoice twice."

Read literally, the task is "use AI to read invoices and enter them." But the two
sentences that carry the real risk are the *typo* and the *near double payment*.
So the problem I actually set out to solve is narrower and safer than "automate
data entry":

> **Reduce the manual typing, without introducing a wrong or duplicate entry that
> the current manual process would (eventually) have caught.**

That reframing drives every later decision. A model that reads 12 invoices is easy;
the value is in **knowing when not to trust it** and drawing a defensible line
between "register automatically" and "a human must look." I therefore treat the LLM
as the *reader* and put a deterministic **verification + human-review** layer around
it, rather than shipping an autonomous typist.

## 2. What you would have asked the client

| What you wanted to ask | The assumption you made instead | Why |
|---|---|---|
| If an invoice is from a supplier not in the partner master, create it or hold it? | **Hold it for a human** (never auto-create). | The API rejects unknown partners, and onboarding a vendor is an AP/business decision with fraud implications — not something to automate silently. |
| Trust the printed grand total, or the line items? | **Recompute from the line items** and treat the printed total as a cross-check. | The API itself recomputes from lines; printed totals can be off by a yen from tax rounding (invoice_09), so the printed value is not authoritative. |
| What should happen to handwriting on scans (received stamps, hand-edited bank numbers)? | **Ignore handwriting for data entry; flag notable marks.** | The printed invoice is the record. A hand-edited bank number (invoice_08) may be legitimate or fraud — a human decides; it is also not part of what we register. |
| Expected volume, and batch vs. real-time? | **Monthly batch of up to a few hundred; latency not critical.** | The brief says "every month" and shows two months of samples; optimize for correctness and cost, not throughput. |
| Which fields must be exactly right? | **partner, invoice_number, dates, amounts are payment-critical; descriptions are not.** | These four determine who gets paid, how much, and whether it is a duplicate. |
| Same invoice arriving twice (PDF + scan)? | **Deduplicate on (partner_code, invoice_number); hold duplicates.** | Directly addresses the "paid twice" fear; invoice_01 and invoice_07 are exactly this case. |
| Is the tax rule floor-per-code? | **Yes — per tax code, floor(subtotal×rate).** | Confirmed by probing the API's `AMOUNT_MISMATCH` behavior; encoded in `verify.py`. |

## 3. Scoping decisions

**What you built**

- End-to-end pipeline: **ingest → LLM extract → normalize → partner match → verify → register**, with a per-invoice run report and a review queue (`src/invoice_intake/`).
- A **deterministic verification gate** that recomputes subtotal / per-code floored tax / total from the lines (mirrors the API) — the core defence against a bad extraction.
- **Idempotent** registration with duplicate detection (batch + already-registered), so re-running never double-posts.
- A **human-review web screen** (FastAPI) that shows each held invoice beside its image with the reason, lets a person assign the supplier and register it through the same checks, and an **Upload** page that converts any new document to JSON.
- An **offline replay mode** (ground-truth fixtures) so the whole thing runs and is testable with no API key, plus a unit-test suite for the risky logic.

**What you left out, and why** (in priority order of what I *kept*)

1. **Correctness + the two failure modes first** — verification, dedup, partner gating. Non-negotiable given the brief.
2. **Field-level confidence / calibration** — *cut.* I use document-level model self-confidence plus the arithmetic gate. Real per-field confidence (route only the doubtful field to review) is the first thing I'd add (§8).
3. **Durable storage / queue / auth** — *cut.* Output is JSON files and the review UI is unauthenticated. Fine for a demo, not for production; at 12/month it isn't the bottleneck.
4. **Automatic vendor onboarding** — *cut.* Unknown suppliers go to review; creating partners is a business decision.
5. **Aggressive fuzzy supplier matching** — *kept conservative* (registration-no → exact name → alias → cautious containment) to avoid paying the wrong vendor.
6. **Demo video** — *cut* in favour of screenshots + captured run output in `demo/` to save time.

## 4. Design and technology choices

**End-to-end flow.** Each file is rendered to page image(s) with PyMuPDF (one robust
path that also covers scans and the image-only PDF); when a PDF has a text layer it
is passed to the model as an extra hint. The model returns JSON in the invoice's own
vocabulary (printed amounts, tax as a percent, dates). `normalize.py` converts dates
(including **Reiwa** 令和8年→2026) to ISO and tax percents to the API's `tax_code`.
`partners.py` resolves the supplier against the master. `verify.py` recomputes the
amounts and decides pass/fail. `pipeline.py` routes: auto-register only if the
supplier is known, the arithmetic reconciles, confidence clears the threshold, and it
is not a duplicate — otherwise it goes to the review queue with a reason. `register.py`
submits the **recomputed** amounts (never the printed ones) so the payload always
satisfies the API's own re-derivation.

**LLM / OCR: Google Gemini 2.5 Flash (free tier).** Chosen for strong Japanese
vision, native JSON-schema output, and a genuinely usable free tier (the brief
explicitly accepts free tiers; there are only 12 documents). Behind a small provider
adapter (`llm/base.py`), so swapping models — to `gemini-2.5-flash-lite` for lower
cost, or a local model — is a one-line change. The provider retries transient
`503/429`/timeout/DNS failures with exponential backoff; a per-invoice failure is
isolated (that invoice is marked `FAILED`) rather than crashing the batch.

**What I decided against:**
- *A dedicated invoice-parsing cloud service* (Google Document AI, Azure Doc
  Intelligence) — more accurate out of the box, but paid, heavier to set up, and
  overkill for this volume. Worth it at real scale.
- *A local vision model* (e.g. Qwen2-VL via Ollama) — free and private, but weaker
  Japanese accuracy and a heavier setup for the evaluator.
- *An "LLM-as-judge" verification step* — non-deterministic and burns tokens. I used
  **arithmetic reconciliation** instead: deterministic, free, and it directly predicts
  whether the API will accept the invoice.
- *TypeScript* — fine too, but Python matches the API's own runtime and the OCR/PDF
  ecosystem.

## 5. How you used AI, and how you checked it

**What you delegated to AI.** Only the perception step: turning pixels/text into
fields — supplier name + registration number, invoice number, issue/due dates, and the
line items (description, qty, unit, unit price, amount, tax rate) — and *ignoring*
handwriting, stamps, and marginal notes. The prompt (`llm/base.py`) is explicit about
the issuer-vs-addressee trap, △/▲ meaning negative, era-date conversion, and treating
null qty/price on 一式 lines.

**How you verified the output.** I do not trust the model's numbers on their own:

1. **Arithmetic reconciliation** — recompute `subtotal = Σ amounts`, `tax =
   floor(subtotal×rate)` per code, `total = subtotal+tax`, and compare to the printed
   summary. A misread line amount surfaces as a subtotal mismatch *before* any API
   call. This is the primary gate.
2. **Registration-number anchoring** — resolve the supplier by the national tax
   registration number first; if the model garbles the company name, the number still
   resolves it (and vice-versa).
3. **Date + tax sanity** — dates must parse and be ordered (due ≥ issue); tax codes
   must be on the API's whitelist.
4. **Duplicate gate** — dedupe on (partner, invoice_number) to prevent double entry.
5. **Confidence threshold** — the model's self-rated confidence is a soft gate to the
   review queue.

**A case where the AI (or the invoice) got it wrong.** invoice_09's *printed* total is
**¥147,497**, but the line items reconcile to **¥147,496**. Submitting the printed
value returns `AMOUNT_MISMATCH` (I verified this against the API). Because I recompute
from the lines, the pipeline registers the correct ¥147,496 **and** flags the ¥1 gap
in the report rather than silently trusting either the model or the page. A related
case is invoice_08, which carries a **red handwritten note changing the bank account**:
the pipeline ignores it for data entry (the printed invoice is the record) — but that
is exactly the kind of mark a human should see, so it is called out in `notes`.

## 6. Integrating with the accounting system

Handled the constraints by adapting to them, never working around them: integer JPY,
ISO dates, `tax_code` (not rate) per line, amounts the API will recompute, and every
documented error surfaced rather than swallowed. Result over the 12 samples —
**10 auto-registered, 1 duplicate held, 1 sent to review**:

| Invoice | Result | How you handled it |
|---|---|---|
| invoice_01.pdf | Registered (ACC-0001) | Clean; freight line has null qty/unit price. |
| invoice_02.pdf | Registered | Two-page PDF, 26 line items aggregated. |
| invoice_03.pdf | Registered | Mixed 8%/10% tax — floored per code (3,950 + 6,067). |
| invoice_04.jpg | Registered | Ignored handwritten 受領 stamp; slash dates normalized. |
| invoice_05.jpg | Registered | 一式/式 lines → null qty/price; unit defaulted to 式. |
| invoice_06.jpg | Registered | Supplier printed as alias **ヤマダ製作所** → matched P-1001. |
| invoice_07.jpg | **Held — duplicate** | Same (P-1001, YM-2026-0107) as invoice_01 → not paid twice. |
| invoice_08.jpg | Registered | Mixed tax; ignored a red handwritten bank-account edit (flagged). |
| invoice_09.pdf | Registered (ACC-0008) | Image-only PDF; printed total ¥1 high → registered the recomputed 147,496 and flagged it. |
| invoice_10.jpg | **Review** | Supplier 新星ロジスティクス is not in the master → cannot be registered. |
| invoice_11.jpg | Registered | Reiwa **令和8年** → 2026 date conversion. |
| invoice_12.jpg | Registered | Negative discount **△30,000** kept as −30,000. |

Anything that can't be registered is written to `out/review_queue.json` with a reason
and appears on the review screen.

## 7. Cost, limits, and risk in production

Using **Gemini 2.5 Flash** (public pricing ≈ $0.30 / 1M input tokens, $2.50 / 1M output):

- **Cost per invoice:** ~1–2 page images (~1.3k tokens each) + ~0.6k prompt/text hint
  in, ~0.4–0.8k JSON out ≈ **~3k in / ~0.7k out ≈ $0.002–$0.005 per invoice** on the
  paid tier (a little more if the model "thinks"); **$0 on the free tier** for this volume.
  `gemini-2.5-flash-lite` would cut this several-fold.
- **Monthly cost at 1,000 invoices:** **≈ $2–5/month** in model cost (paid), plus
  negligible compute. The free tier likely covers it — the binding limit is
  requests-per-minute/day, not price.
- **Processing time per invoice:** **~3–10 s**, dominated by LLM latency (measured ~5 s
  average here). 1,000 sequentially ≈ 1–3 h; trivially parallelizable to minutes.
- **Where this breaks first:** (1) **new/unknown suppliers** — needs an onboarding
  workflow (already routed to review, not dropped); (2) **rate limits / transient 503s**
  at higher volume — I added retry-with-backoff, but sustained load needs the paid tier
  and real batching/queueing; (3) **low-quality/rotated scans or novel layouts**
  degrading extraction; (4) **verification only catches *internal* inconsistency** — an
  invoice whose lines are self-consistent but wrong (e.g. a vendor overcharge) passes,
  because there is no PO/receipt to 3-way-match against.
- **How you would find out if something was registered incorrectly:** `run_report.json`
  + `review_queue.json` are the audit trail; every API rejection is recorded; a
  periodic sample of auto-registered invoices is re-checked against source; and because
  duplicates and unknown suppliers are gated up front, the highest-impact errors
  (double payment, paying a stranger) are stopped before they reach the ledger.

## 8. What you would do with another 8 hours

1. **Field-level confidence + calibration** — attach confidence per field and route only
   the doubtful field to review (not the whole invoice). Biggest safety/throughput win,
   and it sharpens the automation boundary.
2. **Durable state + auth** — Postgres for records/audit, a job queue for the batch, and
   authentication on the review UI. Required before anyone depends on it in production.
3. **Vendor onboarding from the review screen** — let a reviewer propose/create a partner
   (with fuzzy match suggestions) so the largest "sent to review" bucket (unknown
   suppliers) closes without leaving the tool.
