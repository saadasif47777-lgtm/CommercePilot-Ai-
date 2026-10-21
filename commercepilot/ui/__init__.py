"""Gradio front-end for CommercePilot AI.

The UI is intentionally thin: every button callback validates its inputs, calls
the same orchestrator functions the JSON API uses, and renders the returned
Pydantic/dict data. No business rule lives in this package.
"""
from __future__ import annotations

from .app import build_ui

__all__ = ["build_ui"]
