"""Versioned prompt files.

Prompts live in commercepilot/ai/prompts/<name>.<version>.txt and are loaded by name,
so changing a prompt is a reviewable diff and the version used for every call is
recorded in the usage log (prompt contents themselves are never logged).
"""
from __future__ import annotations

from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


def load_prompt(name: str, version: str = "v1") -> tuple[str, str]:
    """Return (prompt text, "name.version"). Raises FileNotFoundError if missing."""
    path = PROMPTS_DIR / f"{name}.{version}.txt"
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise FileNotFoundError(f"Prompt file is empty: {path}")
    return text, f"{name}.{version}"
