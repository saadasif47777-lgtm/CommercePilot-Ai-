"""Optional LLM access with graceful fallback.

If an OpenAI-compatible API key is configured the LLM is used for language
tasks (interpretation, copywriting, spec editing). Exact arithmetic is NEVER
delegated to the model - calculations always run in backend/tools/calculations.py.

When no key is configured, every call returns None and callers fall back to
deterministic templates. Results carry generation_mode="template" so the UI can
truthfully label how they were produced.
"""
from __future__ import annotations

import json
from typing import Optional

import httpx

from . import config

_TIMEOUT = config.LLM_TIMEOUT


def llm_available() -> bool:
    return bool(config.OPENAI_API_KEY)


def mode() -> str:
    return "llm" if llm_available() else "fallback"


def complete(system: str, user: str, as_json: bool = False, timeout: float | None = None) -> Optional[str]:
    """Return model text, or None on missing key/timeout/quota/provider error."""
    if not llm_available():
        return None
    payload = {
        "model": config.OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.4,
        "max_tokens": 1200,
    }
    if as_json:
        payload["response_format"] = {"type": "json_object"}
    try:
        with httpx.Client(timeout=timeout or _TIMEOUT) as client:
            resp = client.post(
                f"{config.OPENAI_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {config.OPENAI_API_KEY}"},
                json=payload,
            )
            if resp.status_code != 200:
                return None  # quota / auth / provider error -> caller falls back
            data = resp.json()
            return data["choices"][0]["message"]["content"]
    except (httpx.HTTPError, KeyError, IndexError, json.JSONDecodeError, ValueError):
        return None
