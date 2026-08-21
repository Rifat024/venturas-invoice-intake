"""Invoice intake pipeline: read supplier invoices with an LLM, verify the
extraction against deterministic rules, and register clean invoices into the
mock accounting API — routing anything unsafe to a human review queue.

See README.md for the one-command start and SUBMISSION.md for the write-up.
"""

__version__ = "1.0.0"
