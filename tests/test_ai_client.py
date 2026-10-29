"""Tests for commercepilot/ai: retries, schema validation, repair, budget and logging.

The HTTP layer is monkeypatched, so these tests never call a provider.
"""
from __future__ import annotations

import json

import httpx
import pytest

from commercepilot import config
from commercepilot.ai import client as ai_client
from commercepilot.ai.client import AIBudgetExceeded, AIRequestError, AIValidationError
from commercepilot.ai.schemas import AssistantIntent
from commercepilot.ai.usage import UsageLog


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


def test_schema_is_included_on_first_request(ai, monkeypatch):
    payloads = []

    def post(url, headers, payload, timeout):
        payloads.append(payload)
        return _ok()

    monkeypatch.setattr(ai_client, "_post", post)
    _call()
    assert len(payloads) == 1
    assert json.dumps(AssistantIntent.model_json_schema(), separators=(",", ":")) in payloads[0]["messages"][0]["content"]


@pytest.mark.parametrize("provider,model,is_reasoning", [
    ("groq", "openai/gpt-oss-20b", True),
    ("groq", "openai/gpt-oss-120b", True),
    ("openai", "other-model", False),
    ("groq", "other-model", False),
])
def test_reasoning_budget_preserves_visible_answer_allowance(ai, monkeypatch, provider, model, is_reasoning):
    monkeypatch.setattr(config, "LLM_PROVIDER", provider)
    monkeypatch.setattr(config, "LLM_MODEL", model)
    payloads = []

    def post(url, headers, payload, timeout):
        payloads.append(payload)
        return _ok()

    monkeypatch.setattr(ai_client, "_post", post)
    _call()
    payload = payloads[0]
    if is_reasoning:
        assert payload["max_completion_tokens"] == 2248
        assert payload["reasoning_effort"] == "low"
        assert "max_tokens" not in payload
    else:
        assert payload["max_tokens"] == 200
        assert "reasoning_effort" not in payload


def test_provider_diagnostics_never_log_raw_message(ai, monkeypatch, caplog):
    monkeypatch.setattr(ai_client, "_post", lambda *a: _Resp(400, {
        "error": {"code": "json_validate_failed", "message": "private customer input", "failed_generation": "secret"}
    }))
    with pytest.raises(AIRequestError):
        _call()
    assert "json_validate_failed" in caplog.text
    assert "private customer input" not in caplog.text
    assert "secret" not in caplog.text


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


@pytest.fixture()
def claude(ai, monkeypatch):
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "anthropic-test-key")
    monkeypatch.setattr(config, "ANTHROPIC_MODEL", "claude-sonnet-5-5")
    monkeypatch.setattr(config, "CLAUDE_MODULES", {"marketing", "store_architect", "product_hunting"})


def _claude_ok(text='{"intent":"report"}'):
    return _Resp(payload={"content": [{"type": "thinking", "thinking": "not user output"}, {"type": "text", "text": text}],
                          "stop_reason": "end_turn", "usage": {"input_tokens": 100, "output_tokens": 20}})


@pytest.mark.parametrize("prompt", ["campaign_creatives", "store_copy", "product_research"])
def test_selected_modules_use_native_claude_and_separate_credentials(claude, monkeypatch, prompt):
    calls = []
    monkeypatch.setattr(config, "LLM_BASE_URL", "https://default.example/v1")

    def post(url, headers, payload, timeout):
        calls.append((url, headers, payload, timeout))
        return _claude_ok()

    monkeypatch.setattr(ai_client, "_post", post)
    result = ai_client.complete_json(prompt_name=prompt, user="review", schema=AssistantIntent)
    assert result.intent == "report"
    url, headers, payload, timeout = calls[0]
    assert url == "https://api.anthropic.com/v1/messages"
    assert headers["Authorization"] == "Bearer anthropic-test-key"
    assert headers["anthropic-version"] == "2023-06-01"
    assert payload["model"] == "claude-sonnet-5-5"
    assert payload["thinking"] == {"type": "between_tools"}
    assert payload["system"] and payload["messages"][0]["role"] == "user"
    assert not {"response_format", "temperature", "max_completion_tokens"} & payload.keys()
    assert timeout == config.ANTHROPIC_TIMEOUT
    summary = ai_client.usage_summary()
    assert summary["input_tokens"] == 100 and summary["output_tokens"] == 20
    assert summary["est_cost_usd"] == pytest.approx(0.0004)
    row = ai_client._log()._conn().execute("SELECT provider, model FROM ai_usage").fetchone()
    assert row["provider"] == "anthropic" and row["model"] == "claude-sonnet-5-5"


def test_other_modules_keep_default_provider(claude, monkeypatch):
    calls = []
    monkeypatch.setattr(ai_client, "_post", lambda url, headers, payload, timeout: calls.append((url, headers, payload)) or _ok())
    _call()
    assert calls[0][0].startswith("https://api.groq.com/")
    assert calls[0][1]["Authorization"] == "Bearer test-key"
    assert calls[0][2]["model"] == "openai/gpt-oss-20b"


def test_missing_claude_key_never_uses_groq_for_selected_modules(claude, monkeypatch):
    monkeypatch.setattr(config, "APP_MODE", "production")
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "")
    monkeypatch.setattr(ai_client, "_post", lambda *args: pytest.fail("No provider should be called"))
    with pytest.raises(ai_client.AIConfigError):
        ai_client.complete_json(prompt_name="store_copy", user="x", schema=AssistantIntent)


def test_claude_repair_stays_on_claude(claude, monkeypatch):
    replies = iter([_claude_ok("not json"), _claude_ok()])
    urls = []
    monkeypatch.setattr(ai_client, "_post", lambda url, *args: urls.append(url) or next(replies))
    result = ai_client.complete_json(prompt_name="store_copy", user="x", schema=AssistantIntent)
    assert result.intent == "report" and urls == ["https://api.anthropic.com/v1/messages"] * 2


def test_claude_auth_error_is_actionable_and_does_not_leak_secrets(claude, monkeypatch, caplog):
    monkeypatch.setattr(ai_client, "_post", lambda *args: _Resp(401, {"error": {"message": "secret provider detail"}}))
    with pytest.raises(AIRequestError, match="Claude authentication failed"):
        ai_client.verify_anthropic()
    assert "secret provider detail" not in caplog.text
    assert "anthropic-test-key" not in repr(ai_client.route_for("store_copy"))


@pytest.mark.parametrize("reason", ["refusal", "max_tokens"])
def test_claude_incomplete_output_is_not_accepted(claude, monkeypatch, reason):
    response = _claude_ok()
    response._payload["stop_reason"] = reason
    monkeypatch.setattr(ai_client, "_post", lambda *args: response)
    with pytest.raises(AIRequestError, match="could not complete"):
        ai_client.complete_json(prompt_name="store_copy", user="x", schema=AssistantIntent)


def test_claude_probe_can_run_before_modules_are_activated(claude, monkeypatch):
    monkeypatch.setattr(config, "CLAUDE_MODULES", set())
    monkeypatch.setattr(ai_client, "_post", lambda *args: _claude_ok("OK"))
    assert ai_client.verify_anthropic() == {"verified": True, "provider": "anthropic", "model": "claude-sonnet-5-5"}
    assert ai_client.route_for("store_copy").provider == "groq"
