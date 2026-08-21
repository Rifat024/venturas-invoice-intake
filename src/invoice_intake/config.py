"""Runtime configuration, read from environment / .env.

Nothing secret is hard-coded. The accounting API's key is fixed by the mock
(it is not a secret in this exercise), but the LLM key must come from the
environment so it never lands in the repo.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

try:  # optional; the pipeline still runs in --offline mode without it
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - dotenv is a convenience only
    pass


@dataclass
class Config:
    # Accounting API (mock)
    api_url: str = os.getenv("ACCOUNTING_API_URL", "http://localhost:8080")
    api_key: str = os.getenv("ACCOUNTING_API_KEY", "demo-key-1234")

    # LLM provider
    llm_provider: str = os.getenv("LLM_PROVIDER", "gemini")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    # Routing thresholds
    confidence_threshold: float = float(os.getenv("CONFIDENCE_THRESHOLD", "0.75"))
    # Printed vs recomputed total may differ by a few yen due to how the vendor
    # rounded consumption tax. Within this tolerance we register the recomputed
    # value and flag the difference; beyond it we send the invoice to review.
    rounding_tolerance_yen: int = int(os.getenv("ROUNDING_TOLERANCE_YEN", "2"))


def load_config() -> Config:
    return Config()
