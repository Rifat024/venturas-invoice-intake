"""Google Gemini provider (chosen: strong Japanese vision, usable free tier).

Sends every page image plus any PDF text layer, and asks for JSON matching
INVOICE_SCHEMA. The SDK is imported lazily so nothing here is needed in
--offline mode or in tests.
"""
from __future__ import annotations

import json
import time

from ..ingest import Document
from .base import EXTRACTION_PROMPT, INVOICE_SCHEMA

# Transient conditions worth retrying: model overload (503), rate limit (429),
# server error (500), and flaky network (timeouts / DNS). Substrings are matched
# against the exception text so we don't couple to one SDK's exception classes.
_RETRYABLE = ("503", "429", "500", "UNAVAILABLE", "RESOURCE_EXHAUSTED",
              "timed out", "timeout", "nodename", "temporarily", "connection")


class GeminiProvider:
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash",
                 max_retries: int = 4, base_delay: float = 2.0):
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY is not set. Put it in .env (see .env.example) "
                "or run in --offline mode."
            )
        from google import genai  # lazy import

        self._genai = genai
        self._client = genai.Client(api_key=api_key)
        self.model = model
        self.max_retries = max_retries
        self.base_delay = base_delay

    def extract(self, document: Document) -> dict:
        from google.genai import types

        parts = [types.Part.from_text(text=EXTRACTION_PROMPT)]
        if document.text_layer:
            parts.append(
                types.Part.from_text(
                    text="\n[Embedded PDF text layer, use as a hint]\n" + document.text_layer
                )
            )
        for img in document.page_images:
            parts.append(types.Part.from_bytes(data=img, mime_type=document.mime))

        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=INVOICE_SCHEMA,
            temperature=0.0,
        )
        resp = self._call_with_retry(
            contents=[types.Content(role="user", parts=parts)], config=config
        )
        return json.loads(resp.text)

    def _call_with_retry(self, contents, config):
        # The loop always returns or raises within an iteration.
        for attempt in range(self.max_retries):
            try:
                return self._client.models.generate_content(
                    model=self.model, contents=contents, config=config
                )
            except Exception as e:  # noqa: BLE001 - classify by message, then re-raise
                if not self._retryable(e) or attempt == self.max_retries - 1:
                    raise
                time.sleep(self.base_delay * (2 ** attempt))  # 2s, 4s, 8s…

    @staticmethod
    def _retryable(exc: Exception) -> bool:
        msg = str(exc).lower()
        return any(tok.lower() in msg for tok in _RETRYABLE)
