"""Turn exceptions into short, user-facing messages.

A Gradio callback that raises shows a red traceback in the interface. That is
noise for the person using the app, so every tab catches its exceptions and
renders the *reason* instead. The full traceback still reaches the server log
through :func:`report`, so failures stay debuggable.
"""
from __future__ import annotations

import logging

from pydantic import ValidationError

from ..tools.calculations import CalculationError
from ..workflows.commerce_workflow import StepFailed

logger = logging.getLogger("commercepilot.ui")


def report(exc: BaseException) -> None:
    """Log the full failure once, server-side only."""
    logger.exception("UI action failed: %s", exc)


def friendly(exc: BaseException) -> str:
    """A concise explanation that never leaks internals or stack traces."""
    if isinstance(exc, StepFailed):
        return f"**{exc.step.title()} step stopped:** {exc.message}"
    if isinstance(exc, ValidationError):
        first = exc.errors()[0] if exc.errors() else {}
        field = " → ".join(str(part) for part in first.get("loc", ()))
        return f"**Invalid input**{' (' + field + ')' if field else ''}: {first.get('msg', 'check the values')}"
    if isinstance(exc, CalculationError):
        return f"**Check the numbers:** {exc}"
    if isinstance(exc, ValueError):
        return f"**Could not run that:** {exc}"
    report(exc)
    return (
        "**Something went wrong while running that action.** "
        "The server log has the details; no data was lost."
    )
