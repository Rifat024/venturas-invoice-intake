"""CLI entry point:  python -m invoice_intake run [options]

Subcommands:
  run     Process a folder of invoices and register the clean ones.
  reset   Delete all invoices from the accounting API (start over).
  serve   Start the FastAPI human-review screen (see review.py).
"""
from __future__ import annotations

import argparse
import json
import sys
from functools import partial

from .config import load_config
from .extract import extract_live, extract_offline
from .pipeline import process_all, process_files
from .register import AccountingClient
from .report import print_summary, print_table, write_json


def _build_extract_fn(mode: str, config):
    if mode == "offline":
        return extract_offline
    # live
    if config.llm_provider == "gemini":
        from .llm.gemini import GeminiProvider

        provider = GeminiProvider(config.gemini_api_key, config.gemini_model)
    else:
        raise SystemExit(f"Unknown LLM_PROVIDER: {config.llm_provider}")
    return partial(extract_live, provider=provider)


def cmd_run(args) -> int:
    config = load_config()
    client = AccountingClient(config.api_url, config.api_key)
    try:
        health = client.health()
    except ConnectionError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    print(f"Accounting API: {config.api_url}  (health: {health['data']['status']})")
    print(f"Mode: {args.mode}   Register: {not args.no_register}")

    if args.reset:
        removed = client.delete_all()
        print(f"Reset: removed {removed} existing invoice(s).")

    extract_fn = _build_extract_fn(args.mode, config)
    results = process_all(
        args.dir, extract_fn, client, config, register=not args.no_register
    )

    print_table(results)
    print_summary(results)
    paths = write_json(results, args.out)
    print(f"\nWrote {paths['run_report']} and {paths['review_queue']}")

    registered = client.list_invoices()
    print(f"Accounting system now holds {len(registered)} invoice(s).")
    return 0


def cmd_extract(args) -> int:
    """Convert a single document into the structured JSON (and optionally register it)."""
    config = load_config()
    extract_fn = _build_extract_fn(args.mode, config)
    inv = extract_fn(args.file)
    print(json.dumps(inv.to_dict(), ensure_ascii=False, indent=2))

    if args.register:
        client = AccountingClient(config.api_url, config.api_key)
        result = process_files([args.file], extract_fn, client, config, register=True)[0]
        print("\n--- pipeline result ---", file=sys.stderr)
        print(f"status={result.status} partner={result.partner_code} "
              f"acct={result.accounting_id}", file=sys.stderr)
        for msg in result.issues + result.notes:
            print(f"  - {msg}", file=sys.stderr)
    return 0


def cmd_reset(args) -> int:
    config = load_config()
    client = AccountingClient(config.api_url, config.api_key)
    removed = client.delete_all()
    print(f"Removed {removed} invoice(s).")
    return 0


def cmd_serve(args) -> int:
    from .review import run_server

    run_server(host=args.host, port=args.port)
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="invoice_intake", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="Process invoices and register clean ones")
    p_run.add_argument("--dir", default="invoices", help="Folder of invoice files")
    p_run.add_argument("--mode", choices=["live", "offline"], default="offline",
                       help="live = call the LLM; offline = replay fixtures (default)")
    p_run.add_argument("--no-register", action="store_true", help="Dry run; do not POST")
    p_run.add_argument("--reset", action="store_true", help="Clear the API first")
    p_run.add_argument("--out", default="out", help="Output folder for JSON reports")
    p_run.set_defaults(func=cmd_run)

    p_extract = sub.add_parser("extract", help="Convert ONE document to structured JSON")
    p_extract.add_argument("file", help="Path to an invoice (PDF or image)")
    p_extract.add_argument("--mode", choices=["live", "offline"], default="live",
                           help="live = call the LLM (default); offline = replay fixture")
    p_extract.add_argument("--register", action="store_true",
                           help="Also match/verify/register via the accounting API")
    p_extract.set_defaults(func=cmd_extract)

    p_reset = sub.add_parser("reset", help="Delete all invoices from the API")
    p_reset.set_defaults(func=cmd_reset)

    p_serve = sub.add_parser("serve", help="Start the human-review web UI (FastAPI)")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8000)
    p_serve.set_defaults(func=cmd_serve)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
