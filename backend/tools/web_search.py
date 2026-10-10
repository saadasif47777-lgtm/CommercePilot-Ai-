"""Live web search for Product Hunter Mode A.

Uses the Serper API when SERPER_API_KEY is configured, otherwise the free
DuckDuckGo backend of the `ddgs` library (no key required). Both paths:

  * attach source URLs to every result
  * enforce a hard timeout
  * convert rate limits / outages into structured warnings instead of raising
  * never throw on empty result sets

No scraping of access-restricted pages is performed: only the search API is
called, and the app reads titles/snippets/URLs it returns.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Optional

import httpx

from .. import config


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str = ""


@dataclass
class SearchOutcome:
    results: list[SearchResult] = field(default_factory=list)
    provider: str = "none"
    warning: Optional[str] = None
    elapsed_ms: int = 0


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def search(query: str, limit: int = 8, timeout: float | None = None) -> SearchOutcome:
    """Run a live web search. Never raises."""
    query = _clean(query)[:300]
    if not query:
        return SearchOutcome(warning="Empty search query.")
    timeout = timeout or config.WEB_SEARCH_TIMEOUT
    started = time.time()
    if config.SERPER_API_KEY:
        outcome = _serper(query, limit, timeout)
    else:
        outcome = _ddgs(query, limit, timeout)
    outcome.elapsed_ms = int((time.time() - started) * 1000)
    return outcome


def _serper(query: str, limit: int, timeout: float) -> SearchOutcome:
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": config.SERPER_API_KEY},
                json={"q": query, "num": limit},
            )
            if resp.status_code == 429:
                return SearchOutcome(provider="serper", warning="Search rate limit reached (429).")
            if resp.status_code != 200:
                return SearchOutcome(
                    provider="serper",
                    warning=f"Search provider returned HTTP {resp.status_code}.",
                )
            data = resp.json()
            results = [
                SearchResult(
                    title=_clean(r.get("title", "")),
                    url=r.get("link", ""),
                    snippet=_clean(r.get("snippet", "")),
                )
                for r in data.get("organic", [])
                if r.get("link")
            ]
            if not results:
                return SearchOutcome(provider="serper", warning="Live search returned no results.")
            return SearchOutcome(results=results[:limit], provider="serper")
    except httpx.TimeoutException:
        return SearchOutcome(provider="serper", warning="Live search timed out.")
    except httpx.HTTPError:
        return SearchOutcome(provider="serper", warning="Live search service unreachable.")


def _ddgs(query: str, limit: int, timeout: float) -> SearchOutcome:
    try:
        from ddgs import DDGS
    except ImportError:
        return SearchOutcome(provider="ddgs", warning="Live search library not installed (ddgs).")
    try:
        with DDGS(timeout=timeout) as ddgs:
            raw = ddgs.text(query, max_results=limit)
        results = [
            SearchResult(
                title=_clean(r.get("title", "")),
                url=r.get("href", "") or r.get("url", ""),
                snippet=_clean(r.get("body", "") or r.get("snippet", "")),
            )
            for r in (raw or [])
            if r.get("href") or r.get("url")
        ]
        if not results:
            return SearchOutcome(provider="ddgs", warning="Live search returned no results.")
        return SearchOutcome(results=results[:limit], provider="ddgs")
    except Exception as exc:  # ddgs raises assorted backend errors on rate limits
        name = type(exc).__name__
        if "timeout" in str(exc).lower() or "Timeout" in name:
            return SearchOutcome(provider="ddgs", warning="Live search timed out.")
        return SearchOutcome(
            provider="ddgs",
            warning=f"Live search unavailable ({name}). Sample data still available.",
        )
