"""Provider-agnostic LLM client.

Responsibilities (all server-side):
  * one HTTP shape for any OpenAI-compatible provider (Groq by default);
  * retries with exponential backoff + jitter on timeouts, 429 and 5xx;
  * request timeouts and output-token caps;
  * JSON output validated against a Pydantic schema, with exactly one repair
    attempt that feeds the validation error back to the model;
  * a hard monthly budget checked before every call;
  * a usage log (tokens + estimated cost, never prompt contents).
"""
from __future__ import annotations

import json
import random
import re
import time
from typing import Any, Optional, Type, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from .. import config
from .guard import UNTRUSTED_SYSTEM_NOTE
from .prompts import load_prompt
from .usage import UsageLog


class AIError(Exception):
    """Base class for AI-layer failures. Messages are safe to show users."""


class AIConfigError(AIError):
    """No API key / model configured."""


class AIBudgetExceeded(AIError):
    """Hard monthly spend cap reached; callers must degrade honestly."""


class AIRequestError(AIError):
    """Transport or provider failure after retries."""


class AIValidationError(AIError):
    """Model output failed schema validation even after one repair."""


DEFAULT_BASE_URLS: dict[str, str] = {
    "groq": "https://api.groq.com/openai/v1",
    "openai": "https://api.openai.com/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
    "mistral": "https://api.mistral.ai/v1",
    "openrouter": "https://openrouter.ai/api/v1",
}

# Estimated USD per 1M tokens (input, output). Used only for the spend estimate
# and the monthly cap — verify against the provider's current pricing page.
PRICES: dict[str, tuple[float, float]] = {
    "openai/gpt-oss-20b": (0.10, 0.50),
    "openai/gpt-oss-120b": (0.20, 0.90),
    "default": (0.20, 0.90),
}

RETRYABLE_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}
RETRY_BASE_DELAY = 0.4
RETRY_MAX_DELAY = 4.0

TModel = TypeVar("TModel", bound=BaseModel)

_usage: Optional[UsageLog] = None


def _log() -> UsageLog:
    global _usage
    if _usage is None:
        _usage = UsageLog(config.DB_PATH)
    return _usage


# --------------------------------------------------------------------------- #
# Configuration helpers
# --------------------------------------------------------------------------- #
def available() -> bool:
    return bool(config.LLM_API_KEY)


def mode() -> str:
    return "llm" if available() else "fallback"


def _provider() -> str:
    return (config.LLM_PROVIDER or "groq").strip().lower()


def _base_url() -> str:
    if config.LLM_BASE_URL:
        return config.LLM_BASE_URL.rstrip("/")
    return DEFAULT_BASE_URLS.get(_provider(), DEFAULT_BASE_URLS["groq"])


def _estimate_cost(input_tokens: int, output_tokens: int) -> float:
    pin, pout = PRICES.get(config.LLM_MODEL, PRICES["default"])
    return round(input_tokens / 1_000_000 * pin + output_tokens / 1_000_000 * pout, 8)


def _budget_check() -> None:
    cap = config.AI_MONTHLY_CAP_USD
    if cap <= 0:
        return
    spent = _log().month_cost()
    if spent >= cap:
        raise AIBudgetExceeded(
            f"Monthly AI budget of ${cap:.2f} has been reached (estimated spend ${spent:.2f})."
        )


def usage_summary() -> dict[str, Any]:
    summary = _log().summary()
    summary["monthly_cap_usd"] = config.AI_MONTHLY_CAP_USD
    summary["remaining_usd"] = round(
        max(0.0, config.AI_MONTHLY_CAP_USD - summary["est_cost_usd"]), 6
    )
    return summary


# --------------------------------------------------------------------------- #
# Transport (isolated so tests can monkeypatch it)
# --------------------------------------------------------------------------- #
def _post(url: str, headers: dict[str, str], payload: dict[str, Any], timeout: float):
    with httpx.Client(timeout=timeout) as client:
        return client.post(url, headers=headers, json=payload)


def _record(
    prompt_name: str,
    input_tokens: int,
    output_tokens: int,
    latency_ms: int,
    status: str,
) -> None:
    try:
        _log().record(
            provider=_provider(),
            model=config.LLM_MODEL,
            prompt=prompt_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            est_cost_usd=_estimate_cost(input_tokens, output_tokens),
            latency_ms=latency_ms,
            status=status,
        )
    except Exception:  # logging must never break a request
        pass


def _strip_fences(text: str) -> str:
    t = (text or "").strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*\s*", "", t)
        t = re.sub(r"\s*```$", "", t)
    return t.strip()


def _call(
    *,
    system: str,
    user: str,
    prompt_name: str,
    as_json: bool,
    max_tokens: Optional[int] = None,
) -> str:
    """One logical request with retries. Returns the model's text content."""
    if not available():
        raise AIConfigError("No AI provider key configured on the server.")
    _budget_check()

    payload: dict[str, Any] = {
        "model": config.LLM_MODEL,
        "messages": [
            {"role": "system", "content": system + "\n\n" + UNTRUSTED_SYSTEM_NOTE},
            {"role": "user", "content": user},
        ],
        "temperature": 0.3,
        "max_tokens": int(max_tokens or config.LLM_MAX_OUTPUT_TOKENS),
    }
    if as_json:
        payload["response_format"] = {"type": "json_object"}

    headers = {
        "Authorization": f"Bearer {config.LLM_API_KEY}",
        "content-type": "application/json",
    }
    url = f"{_base_url()}/chat/completions"
    attempts = max(0, int(config.LLM_MAX_RETRIES)) + 1

    for attempt in range(attempts):
        started = time.time()
        try:
            resp = _post(url, headers, payload, config.LLM_TIMEOUT)
        except (httpx.TimeoutException, httpx.HTTPError):
            latency = int((time.time() - started) * 1000)
            _record(prompt_name, 0, 0, latency, "failed_transport")
            if attempt < attempts - 1:
                time.sleep(
                    min(RETRY_MAX_DELAY, RETRY_BASE_DELAY * (2 ** attempt))
                    + random.uniform(0, 0.2)
                )
                continue
            raise AIRequestError("AI service timed out or was unreachable.")

        latency = int((time.time() - started) * 1000)

        if resp.status_code == 200:
            try:
                data = resp.json()
                content = data["choices"][0]["message"]["content"] or ""
            except (ValueError, KeyError, IndexError, TypeError):
                _record(prompt_name, 0, 0, latency, "failed_response")
                raise AIRequestError("AI service returned an unexpected response.")
            usage = data.get("usage") or {}
            _record(
                prompt_name,
                int(usage.get("prompt_tokens") or 0),
                int(usage.get("completion_tokens") or 0),
                latency,
                "ok",
            )
            return content

        if resp.status_code in RETRYABLE_STATUS:
            _record(prompt_name, 0, 0, latency, f"retry_{resp.status_code}")
            if attempt < attempts - 1:
                retry_after = (resp.headers.get("retry-after") or "").strip()
                delay = (
                    float(retry_after)
                    if retry_after.isdigit()
                    else min(RETRY_MAX_DELAY, RETRY_BASE_DELAY * (2 ** attempt))
                )
                time.sleep(delay + random.uniform(0, 0.2))
                continue
            raise AIRequestError("AI service is rate limited or unavailable right now.")

        _record(prompt_name, 0, 0, latency, f"failed_{resp.status_code}")
        raise AIRequestError("AI request was rejected by the provider.")

    raise AIRequestError("AI request failed after retries.")


# --------------------------------------------------------------------------- #
# Public calls
# --------------------------------------------------------------------------- #
def complete_json(
    *,
    prompt_name: str,
    user: str,
    schema: Type[TModel],
    max_tokens: Optional[int] = None,
    version: str = "v1",
) -> Optional[TModel]:
    """Return schema-validated output, or None when no provider is configured.

    Raises AIBudgetExceeded / AIRequestError / AIValidationError so callers can
    surface an honest message instead of showing invented data.
    """
    if not available():
        return None
    system, _version = load_prompt(prompt_name, version)

    text = _call(
        system=system, user=user, prompt_name=prompt_name, as_json=True, max_tokens=max_tokens
    )
    parsed, error = _parse_and_validate(text, schema)
    if parsed is not None:
        return parsed

    repair_note = (
        "\n\nYour previous reply could not be used. Fix it and reply with ONLY valid JSON.\n"
        f"Validation error: {error}\n"
        f"Required JSON schema: {json.dumps(schema.model_json_schema(), separators=(',', ':'))[:4000]}"
    )
    text = _call(
        system=system,
        user=user + repair_note,
        prompt_name=prompt_name,
        as_json=True,
        max_tokens=max_tokens,
    )
    parsed, error = _parse_and_validate(text, schema)
    if parsed is not None:
        return parsed
    raise AIValidationError("AI returned data that did not match the required schema.")


def complete_text(
    *,
    prompt_name: str,
    user: str,
    max_tokens: Optional[int] = None,
    version: str = "v1",
) -> Optional[str]:
    """Free-form completion (short copy). None when no provider is configured."""
    if not available():
        return None
    system, _version = load_prompt(prompt_name, version)
    return _call(system=system, user=user, prompt_name=prompt_name, as_json=False, max_tokens=max_tokens).strip()


def _parse_and_validate(text: str, schema: Type[TModel]) -> tuple[Optional[TModel], str]:
    cleaned = _strip_fences(text)
    try:
        data = json.loads(cleaned)
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        return None, f"invalid JSON ({exc.__class__.__name__})"
    try:
        return schema.model_validate(data), ""
    except ValidationError as exc:
        first = exc.errors()[0] if exc.errors() else {}
        loc = ".".join(str(p) for p in first.get("loc", ())) or "root"
        return None, f"{loc}: {first.get('msg', 'invalid value')}"
