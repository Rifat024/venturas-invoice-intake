"""Extraction stage: produce an `ExtractedInvoice` from a file.

Two backends:
  * live    -> an LLM Provider reads the rendered document.
  * offline -> replay a saved ground-truth fixture (no key, deterministic),
               used for the demo without a key and for tests.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from .ingest import load_document
from .llm.base import Provider
from .models import ExtractedInvoice

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures"


def extract_live(path: str, provider: Provider) -> ExtractedInvoice:
    doc = load_document(path)
    raw = provider.extract(doc)
    return ExtractedInvoice.from_dict(raw, source_file=Path(path).name)


def extract_offline(path: str, fixture_dir: Optional[Path] = None) -> ExtractedInvoice:
    stem = Path(path).stem
    fdir = fixture_dir or FIXTURE_DIR
    fpath = fdir / f"{stem}.json"
    if not fpath.exists():
        raise FileNotFoundError(
            f"No offline fixture for {stem} at {fpath}. Run in --live mode with a key."
        )
    raw = json.loads(fpath.read_text(encoding="utf-8"))
    return ExtractedInvoice.from_dict(raw, source_file=Path(path).name)
