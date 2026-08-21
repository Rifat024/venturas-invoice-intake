#!/usr/bin/env bash
# One command to run the whole thing: sets up a venv, starts the mock accounting
# API if it isn't already up, and processes every invoice in ./invoices.
#
#   ./run.sh              # offline mode (replays saved extractions; no API key)
#   ./run.sh live         # live mode: calls Gemini (needs GEMINI_API_KEY in .env)
#   ./run.sh serve        # start the human-review web screen (http://127.0.0.1:8000)
#
set -euo pipefail
cd "$(dirname "$0")"

MODE="${1:-offline}"
PY=python3

# 1. venv + deps
if [ ! -d .venv ]; then
  echo "==> Creating virtualenv (.venv) and installing dependencies…"
  $PY -m venv .venv
  ./.venv/bin/pip install --quiet --upgrade pip
  ./.venv/bin/pip install --quiet -e .   # installs deps (pyproject) + the package
fi
PY=./.venv/bin/python

# 2. start the mock accounting API if it's not already listening
if ! curl -s http://localhost:8080/health >/dev/null 2>&1; then
  echo "==> Starting mock accounting API on :8080…"
  $PY accounting_api.py >/tmp/accounting_api.log 2>&1 &
  API_PID=$!
  trap '[ -n "${API_PID:-}" ] && kill "$API_PID" 2>/dev/null || true' EXIT
  for _ in $(seq 1 20); do curl -s http://localhost:8080/health >/dev/null 2>&1 && break; sleep 0.3; done
fi

# 3. run
if [ "$MODE" = "serve" ]; then
  echo "==> Human-review screen at http://127.0.0.1:8000  (Ctrl+C to stop)"
  exec $PY -m invoice_intake serve
else
  $PY -m invoice_intake run --dir invoices --mode "$MODE" --reset
  echo
  echo "Done. See out/run_report.json and out/review_queue.json."
  echo "Start the human-review screen with:  ./run.sh serve"
fi
