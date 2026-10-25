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

import contextlib
import json
import logging
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

# Cost policy (docs/PRODUCTION_PLAN.md §11): cheap model for classification and
# short tasks, stronger model only for user-facing copy generation.
QUALITY_FAST = "fast"
QUALITY_STRONG = "quality"

logger = logging.getLogger("commercepilot.ai")
_budget_warned = False

RETRYABLE_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}
RETRY_BASE_DELAY = 0.4
RETRY_MAX_DELAY = 4.0

TModel = TypeVar("TModel", bound=BaseModel)

_usage: Optional[UsageLog] = None


def _log() -> UsageLog:
    global _usage
    if _usage is None:
        _usage = UsageLog(config.DATABASE_URL or config.DB_PATH)
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


def model_for(quality: str = QUALITY_FAST) -> str:
    """Model to use for a task: strong only when explicitly requested."""
    if quality == QUALITY_STRONG and config.LLM_MODEL_STRONG:
        return config.LLM_MODEL_STRONG
    return config.LLM_MODEL


def _estimate_cost(input_tokens: int, output_tokens: int, model: str) -> float:
    pin, pout = PRICES.get(model, PRICES["default"])
    return round(input_tokens / 1_000_000 * pin + output_tokens / 1_000_000 * pout, 8)


def _budget_check() -> None:
    global _budget_warned
    cap = config.AI_MONTHLY_CAP_USD
    if cap <= 0:
        return
    spent = _log().month_cost()
    pct = spent / cap * 100
    if not _budget_warned and pct >= config.AI_BUDGET_WARN_PCT:
        _budget_warned = True
        logger.warning(
            "AI budget %.0f%% used (estimated $%.2f of $%.2f this month)",
            pct,
            spent,
            cap,
        )
    if spent >= cap:
        raise AIBudgetExceeded(
            f"Monthly AI budget of ${cap:.2f} has been reached (estimated spend ${spent:.2f})."
        )


def usage_summary() -> dict[str, Any]:
    summary = _log().summary()
    cap = config.AI_MONTHLY_CAP_USD
    spent = summary["est_cost_usd"]
    pct = (spent / cap * 100) if cap > 0 else 0.0
    summary["monthly_cap_usd"] = cap
    summary["remaining_usd"] = round(max(0.0, cap - spent), 6) if cap > 0 else None
    summary["percent_used"] = round(pct, 2)
    summary["warn"] = bool(cap > 0 and pct >= config.AI_BUDGET_WARN_PCT)
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
    model: str,
) -> None:
    # Usage logging must never break a request.
    with contextlib.suppress(Exception):
        _log().record(
            provider=_provider(),
            model=model,
            prompt=prompt_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            est_cost_usd=_estimate_cost(input_tokens, output_tokens, model),
            latency_ms=latency_ms,
            status=status,
        )


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
    quality: str = QUALITY_FAST,
    timeout: Optional[float] = None,
    retries: Optional[int] = None,
) -> str:
    """One logical request with retries. Returns the model's text content."""
    if not available():
        raise AIConfigError("No AI provider key configured on the server.")
    _budget_check()
    model = model_for(quality)

    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system + "\n\n" + UNTRUSTED_SYSTEM_NOTE},
            {"role": "user", "content": user},
        ],
        "temperature": 0.3,
        "max_tokens": int(max_tokens or config.LLM_MAX_OUTPUT_TOKENS),
    }
    if as_json:
        payload["response_format"] = {"type": "json_object"}
    if _provider() == "groq" and model in {"openai/gpt-oss-20b", "openai/gpt-oss-120b"}:
        # Groq counts reasoning against the completion limit as well. Reserving
        # only the visible-answer allowance can truncate JSON before it starts.
        payload["reasoning_effort"] = "low"
        payload["max_completion_tokens"] = payload.pop("max_tokens") + 2048

    headers = {
        "Authorization": f"Bearer {config.LLM_API_KEY}",
        "content-type": "application/json",
    }
    url = f"{_base_url()}/chat/completions"
    attempts = max(0, int(config.LLM_MAX_RETRIES if retries is None else retries)) + 1

    for attempt in range(attempts):
        started = time.time()
        try:
            resp = _post(url, headers, payload, config.LLM_TIMEOUT if timeout is None else timeout)
        except (httpx.TimeoutException, httpx.HTTPError) as exc:
            latency = int((time.time() - started) * 1000)
            _record(prompt_name, 0, 0, latency, "failed_transport", model)
            if attempt < attempts - 1:
                time.sleep(
                    min(RETRY_MAX_DELAY, RETRY_BASE_DELAY * (2 ** attempt))
                    + random.uniform(0, 0.2)
                )
                continue
            raise AIRequestError("AI service timed out or was unreachable.") from exc

        latency = int((time.time() - started) * 1000)

        if resp.status_code == 200:
            try:
                data = resp.json()
                content = data["choices"][0]["message"]["content"] or ""
            except (ValueError, KeyError, IndexError, TypeError) as exc:
                _record(prompt_name, 0, 0, latency, "failed_response", model)
                raise AIRequestError("AI service returned an unexpected response.") from exc
            if not isinstance(content, str) or not content.strip():
                raise AIRequestError("AI service returned no usable text.")
            usage = data.get("usage") or {}
            _record(
                prompt_name,
                int(usage.get("prompt_tokens") or 0),
                int(usage.get("completion_tokens") or 0),
                latency,
                "ok",
                model,
            )
            return content

        if resp.status_code in RETRYABLE_STATUS:
            _record(prompt_name, 0, 0, latency, f"retry_{resp.status_code}", model)
            if attempt < attempts - 1:
                retry_after = (resp.headers.get("retry-after") or "").strip()
                delay = (
                    min(RETRY_MAX_DELAY, float(retry_after))
                    if retry_after.isdigit()
                    else min(RETRY_MAX_DELAY, RETRY_BASE_DELAY * (2 ** attempt))
                )
                time.sleep(delay + random.uniform(0, 0.2))
                continue
            raise AIRequestError("AI service is rate limited or unavailable right now.")

        _record(prompt_name, 0, 0, latency, f"failed_{resp.status_code}", model)
        # Log only allowlisted error codes, never provider messages or generated
        # content (which can contain customer input or credentials).
        try:
            error_code = resp.json().get("error", {}).get("code")
        except (ValueError, AttributeError, TypeError):
            error_code = None
        safe_code = error_code if error_code in {
            "json_validate_failed", "model_not_found", "model_decommissioned",
            "invalid_api_key", "context_length_exceeded", "model_permission_blocked",
        } else "unclassified"
        logger.warning("AI provider rejected request: status=%s code=%s", resp.status_code, safe_code)
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
    quality: str = QUALITY_FAST,
    timeout: Optional[float] = None,
    retries: Optional[int] = None,
) -> Optional[TModel]:
    """Return schema-validated output, or None when no provider is configured.

    Raises AIBudgetExceeded / AIRequestError / AIValidationError so callers can
    surface an honest message instead of showing invented data.
    """
    if not available():
        if config.production():
            raise AIConfigError("No AI provider key configured on the server.")
        return None
    system, _version = load_prompt(prompt_name, version)

    text = _call(
        system=system,
        user=user,
        prompt_name=prompt_name,
        as_json=True,
        max_tokens=max_tokens,
        quality=quality,
        timeout=timeout,
        retries=retries,
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
        quality=quality,
        timeout=timeout,
        retries=retries,
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
    quality: str = QUALITY_FAST,
) -> Optional[str]:
    """Free-form completion (short copy). None when no provider is configured."""
    if not available():
        if config.production():
            raise AIConfigError("No AI provider key configured on the server.")
        return None
    system, _version = load_prompt(prompt_name, version)
    return _call(
        system=system,
        user=user,
        prompt_name=prompt_name,
        as_json=False,
        max_tokens=max_tokens,
        quality=quality,
    ).strip()


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
