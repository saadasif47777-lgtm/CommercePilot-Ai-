"""Claude web search contract tests: provider call, citations, no fabricated links."""
import json
from types import SimpleNamespace

from commercepilot import config
from commercepilot.schemas import ResearchRequest
from commercepilot.tools import claude_search as cs


class Billing:
    def __init__(self):
        self.entries = []
    def reserve(self, amount, cap):
        return "reservation"
    def record(self, **kwargs):
        self.entries.append(kwargs)


def make_response(product_url="https://retailer.example/products/serum"):
    competitor_url = "https://competitor.example/products/serum"
    data = {
        "content": [
            {"type": "web_search_tool_result", "content": [
                {"type": "web_search_result", "title": "Serum", "url": product_url},
                {"type": "web_search_result", "title": "Competing serum", "url": competitor_url},
            ]},
            {"type": "text", "text": json.dumps({"products": [
                {"title": "Local serum", "url": product_url, "snippet": "Serum for skin care",
                 "competitors": [{"name": "Alternative brand", "url": competitor_url, "positioning": "Same price band, business size unknown"}]},
                {"title": "Fake item", "url": "https://fabricated.example/item", "snippet": "Not cited"},
            ]})},
        ],
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 1000, "output_tokens": 300, "server_tool_use": {"web_search_requests": 2}},
    }
    return SimpleNamespace(status_code=200, json=lambda: data)


def test_claude_search_requires_cited_urls(monkeypatch):
    billing = Billing()
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "unit-test-only")
    monkeypatch.setattr(cs.ai, "_budget_check", lambda: None)
    monkeypatch.setattr(cs.ai, "_billing_log", lambda: billing)
    captured = {}
    def post(url, headers, payload, timeout):
        captured["url"] = url
        captured["payload"] = payload
        assert headers["x-api-key"] == "unit-test-only"
        return make_response()
    monkeypatch.setattr(cs.ai, "_post", post)
    outcome = cs.search_products(ResearchRequest(niche="skincare", market="Pakistan", limit=10))
    assert captured["url"].endswith("/v1/messages")
    assert captured["payload"]["tools"][0]["type"] == "web_search_20250305"
    assert len(outcome.results) == 1
    assert len(outcome.results[0].competitors) == 1
    assert "fabricated.example" not in str(outcome.results)
    assert billing.entries[0]["reservation"] == "reservation"


def test_claude_no_key_returns_clear_warning(monkeypatch):
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "")
    outcome = cs.search_products(ResearchRequest(niche="fashion"))
    assert not outcome.results
    assert "ANTHROPIC_API_KEY" in outcome.warning


def test_non_https_citation_is_rejected():
    assert not cs._valid_https("http://retailer.example/product")
    assert not cs._valid_https("https://user:password@retailer.example/product")
    assert cs._valid_https("https://retailer.example/product")
