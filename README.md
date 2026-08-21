# Invoice Intake

Reads Japanese supplier invoices (PDF or scan), turns them into structured data
with an LLM, **verifies** that data with deterministic checks, and registers the
clean ones into the accounting API — routing anything unsafe to a **human review**
queue. Built for the "AI Agent Engineer" take-home.

> The write-up (decisions, trade-offs, cost, risk) is in **[SUBMISSION.md](SUBMISSION.md)** —
> that is the document to read first.

---

## One command to run it

```bash
./run.sh
```

That creates a virtualenv, installs dependencies, starts the mock accounting API
if it isn't already running, and processes every invoice in `invoices/`.

`./run.sh` defaults to **offline mode** — it replays saved, ground-truth
extractions of the 12 samples, so it runs end-to-end with **no API key** and is
fully deterministic. To read the invoices with a real model instead:

```bash
cp .env.example .env      # then put your free GEMINI_API_KEY in .env
./run.sh live
```

Get a free key at <https://aistudio.google.com/apikey>.

### Human-review screen (optional, FastAPI)

```bash
./run.sh serve            # http://127.0.0.1:8000
```

Shows the review queue next to each invoice image, explains why each was held,
and lets a person assign the supplier and register it — through the **same**
verification path as the batch run. The screen also has an **Upload** page
(`/upload`) that converts any new document to JSON on the spot.

---

## What a run does

```
invoices/*.pdf|jpg
      │
      ▼  ingest      render page images (+ PDF text layer as a hint)
      ▼  extract     LLM -> structured JSON (offline: replay fixture)
      ▼  normalize   Japanese/Reiwa dates -> ISO, tax % -> tax_code
      ▼  match        supplier -> partner master (registration_no > name > alias)
      ▼  verify       recompute subtotal / per-code floored tax / total
      ▼  route        auto-register  ─or─  human review (with a reason)
      ▼  register     POST /invoices (idempotent; duplicates held)
      ▼
out/run_report.json   +   out/review_queue.json
```

Outcome on the 12 samples: **10 auto-registered, 1 duplicate held, 1 sent to
review** (supplier not in the master). See `demo/`.

## Commands

```bash
python -m invoice_intake run   --dir invoices --mode offline --reset   # batch
python -m invoice_intake extract invoices/invoice_03.pdf --mode live   # one doc -> JSON
python -m invoice_intake serve                                         # review UI
python -m invoice_intake reset                                         # clear the API
```

## Layout

```
accounting_api.py            the mock API (unchanged, from the assignment §8)
src/invoice_intake/
  ingest.py  extract.py  llm/        read a file, LLM extraction (+ provider adapter)
  normalize.py  partners.py  verify.py   deterministic core (dates, matching, checks)
  register.py  pipeline.py  report.py     API client, orchestration, output
  review.py                              FastAPI human-review + upload screen
tests/                        unit tests + ground-truth fixtures for the 12 samples
invoices/                     the 12 sample invoices
demo/                         run output + review-screen screenshots
```

## Tests

```bash
pip install -e ".[dev]" && pytest        # or: ./.venv/bin/pytest
```

Covers the tax math (single + mixed rate, floor-per-code), the printed-vs-recomputed
rounding case, subtotal-mismatch detection, Reiwa/Japanese date conversion, and
partner matching by registration number / name / alias.

## Requirements

Python 3.9+. Offline mode and the tests use only the standard library; live mode
and the review screen use `google-genai`, `PyMuPDF`, `fastapi`/`uvicorn`
(see `requirements.txt`).
