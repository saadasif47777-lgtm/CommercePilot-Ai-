"""Unit tests never fetch external product pages. Parser/network tests use fixtures."""
import pytest


@pytest.fixture(autouse=True)
def no_external_page_research(monkeypatch):
    from commercepilot.agents import product_hunter
    monkeypatch.setattr(product_hunter, "inspect_pages", lambda urls: [])
