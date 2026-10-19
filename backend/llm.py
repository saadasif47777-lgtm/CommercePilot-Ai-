"""Backwards-compatible availability shim.

The real AI layer lives in ``backend/ai`` (provider client, retries with
backoff, schema validation, budget guard and usage logging). This module only
answers the two questions existing code asks — is AI configured, and in which
mode are we running — so no caller silently keeps the old unvalidated path.
"""
from __future__ import annotations

from . import ai


def llm_available() -> bool:
    return ai.available()


def mode() -> str:
    return ai.mode()
