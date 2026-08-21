# Demo

Evidence of the pipeline running end-to-end. (Re-create any of this with
`./run.sh`, `./run.sh live`, and `./run.sh serve`.)

| File | What it shows |
|---|---|
| `01_pipeline_run.txt` | Offline batch over all 12 invoices → 10 registered, 1 duplicate held, 1 sent to review. |
| `04_live_run.txt` | The same batch in **live mode** (Gemini 2.5 Flash reading the real invoices) — identical outcome. |
| `05_extract_cli_invoice_03.json` | `extract` CLI output: the mixed-tax invoice_03 converted to JSON by Gemini (per-line 8%/10%). |
| `02_review_queue.png` | Human-review screen: the 2 held invoices with reasons. |
| `03_review_detail.png` | Review detail: the held invoice beside its image, with a supplier-assignment form. |
| `06_upload_extraction.png` | Upload page: drop any document → structured JSON + verification + partner match. |

Key cases to look for: **invoice_07** (duplicate of invoice_01, held to avoid double
payment), **invoice_09** (printed total ¥1 high → registered the recomputed value and
flagged it), **invoice_10** (supplier not in the master → review).
