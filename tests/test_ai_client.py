"""Tests for backend/ai: retries, schema validation, repair, budget and logging.

The HTTP layer is monkeypatched, so these tests never call a provider.
"""
from __future__ import annotations

import json

import httpx
import pytest

from backend import config
from backend.ai import client as ai_client
from backend.ai.client import AIBudgetExceeded, AIRequestError, AIValidationError
from backend.ai.schemas import AssistantIntent
from backend.ai.usage import UsageLog


class _Resp:
    def __init__(self, status_code: int = 200, payload: dict | None = None, headers: dict | None = None):
        self.status_code = status_code
        self._payload = payload or {}
        self.headers = headers or {}

    def json(self):
        return self._payload


def _ok(intent: str = "research", prompt_tokens: int = 10, completion_tokens: int = 5) -> _Resp:
    return _Resp(
        payload={
            "choices": [{"message": {"content": json.dumps({"intent": intent})}}],
            "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens},
        }
    )


def _bad_json(intent: str = "banana") -> _Resp:
    return _Resp(payload={"choices": [{"message": {"content": json.dumps({"intent": intent})}}]})


@pytest.fixture()
def ai(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "LLM_API_KEY", "test-key")
    monkeypatch.setattr(config, "LLM_PROVIDER", "groq")
    monkeypatch.setattr(config, "LLM_MODEL", "openai/gpt-oss-20b")
    monkeypatch.setattr(config, "LLM_MAX_RETRIES", 1)
    monkeypatch.setattr(config, "LLM_TIMEOUT", 5.0)
    monkeypatch.setattr(config, "LLM_MAX_OUTPUT_TOKENS", 200)
    monkeypatch.setattr(config, "AI_MONTHLY_CAP_USD", 25.0)
    monkeypatch.setattr(ai_client.time, "sleep", lambda *_: None)
    monkeypatch.setattr(ai_client, "_usage", UsageLog(tmp_path / "ai.sqlite3"))
    yield
    monkeypatch.setattr(ai_client, "_usage", None)


def _call():
    return ai_client.complete_json(
        prompt_name="intent", schema=AssistantIntent, user="run the whole workflow"
    )


def test_valid_output_is_validated_and_logged(ai, monkeypatch):
    monkeypatch.setattr(ai_client, "_post", lambda *a, **k: _ok("workflow"))
    result = _call()
    assert result is not None and result.intent == "workflow"
    summary = ai_client.usage_summary()
    assert summary["calls"] == 1
    assert summary["input_tokens"] == 10
    assert summary["output_tokens"] == 5
    assert summary["est_cost_usd"] > 0


def test_retries_on_429_then_succeeds(ai, monkeypatch):
    calls = {"n": 0}

    def fake_post(*a, **k):
        calls["n"] += 1
        return _Resp(status_code=429, headers={"retry-after": "0"}) if calls["n"] == 1 else _ok("store")

    monkeypatch.setattr(ai_client, "_post", fake_post)
    result = _call()
    assert result is not None and result.intent == "store"
    assert calls["n"] == 2


def test_exhausted_retries_raise_request_error(ai, monkeypatch):
    calls = {"n": 0}

    def fake_post(*a, **k):
        calls["n"] += 1
        return _Resp(status_code=503)

    monkeypatch.setattr(ai_client, "_post", fake_post)
    with pytest.raises(AIRequestError):
        _call()
    assert calls["n"] == 2  # initial attempt + one retry


def test_transport_error_is_retried_then_raised(ai, monkeypatch):
    def fake_post(*a, **k):
        raise httpx.ConnectError("boom")

    monkeypatch.setattr(ai_client, "_post", fake_post)
    with pytest.raises(AIRequestError):
        _call()


def test_invalid_enum_is_repaired_once_then_accepted(ai, monkeypatch):
    replies = iter([_bad_json(), _ok("analyze")])
    monkeypatch.setattr(ai_client, "_post", lambda *a, **k: next(replies))
    result = _call()
    assert result is not None and result.intent == "analyze"


def test_invalid_output_after_repair_raises(ai, monkeypatch):
    monkeypatch.setattr(ai_client, "_post", lambda *a, **k: _bad_json())
    with pytest.raises(AIValidationError):
        _call()


def test_monthly_budget_blocks_calls(ai, monkeypatch):
    monkeypatch.setattr(config, "AI_MONTHLY_CAP_USD", 0.01)
    ai_client._log().record(
        provider="groq",
        model="openai/gpt-oss-20b",
        prompt="intent.v1",
        input_tokens=1000,
        output_tokens=1000,
        est_cost_usd=1.0,
        status="ok",
    )
    called = {"n": 0}

    def fake_post(*a, **k):
        called["n"] += 1
        return _ok()

    monkeypatch.setattr(ai_client, "_post", fake_post)
    with pytest.raises(AIBudgetExceeded):
        _call()
    assert called["n"] == 0  # never reached the provider


def test_missing_key_returns_none(ai, monkeypatch):
    monkeypatch.setattr(config, "LLM_API_KEY", "")
    monkeypatch.setattr(ai_client, "_post", lambda *a, **k: _ok())
    assert ai_client.available() is False
    assert _call() is None


def test_cost_routing_uses_strong_model_only_when_requested(ai, monkeypatch):
    payloads: list[dict] = []

    def fake_post(url, headers, payload, timeout):
        payloads.append(payload)
        return _ok()

    monkeypatch.setattr(ai_client, "_post", fake_post)
    monkeypatch.setattr(config, "LLM_MODEL", "cheap-model")
    monkeypatch.setattr(config, "LLM_MODEL_STRONG", "strong-model")

    ai_client.complete_json(prompt_name="intent", schema=AssistantIntent, user="x")
    ai_client.complete_json(
        prompt_name="intent",
        schema=AssistantIntent,
        user="x",
        quality=ai_client.QUALITY_STRONG,
    )
    assert payloads[0]["model"] == "cheap-model"
    assert payloads[1]["model"] == "strong-model"


def test_strong_quality_falls_back_to_cheap_model_when_unset(ai, monkeypatch):
    payloads: list[dict] = []

    def fake_post(url, headers, payload, timeout):
        payloads.append(payload)
        return _ok()

    monkeypatch.setattr(ai_client, "_post", fake_post)
    monkeypatch.setattr(config, "LLM_MODEL", "cheap-model")
    monkeypatch.setattr(config, "LLM_MODEL_STRONG", "")
    ai_client.complete_json(
        prompt_name="intent",
        schema=AssistantIntent,
        user="x",
        quality=ai_client.QUALITY_STRONG,
    )
    assert payloads[0]["model"] == "cheap-model"


def test_usage_summary_warns_near_budget(ai, monkeypatch):
    monkeypatch.setattr(config, "AI_MONTHLY_CAP_USD", 10.0)
    monkeypatch.setattr(config, "AI_BUDGET_WARN_PCT", 80.0)
    ai_client._log().record(
        provider="groq", model="m", prompt="p", est_cost_usd=8.5, status="ok"
    )
    summary = ai_client.usage_summary()
    assert summary["warn"] is True
    assert summary["percent_used"] == 85.0
    assert summary["remaining_usd"] == 1.5
