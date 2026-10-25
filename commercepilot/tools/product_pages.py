"""Bounded public product-page research. No JavaScript, login or bot bypass.

HTTPS connections are pinned to a validated public IP, including every redirect,
while TLS still verifies the original hostname. No environment proxy or cookies.
"""
import http.client
import ipaddress
import json
import math
import re
import socket
import ssl
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urldefrag, urljoin, urlsplit
from urllib.robotparser import RobotFileParser

AGENT = "CommercePilotResearch/1.0"
MAX_BYTES = 1_500_000


class PageError(Exception):
    pass


def public_target(url):
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password or parts.port not in (None, 443):
        raise PageError("Only public HTTPS product URLs are supported.")
    host = parts.hostname.encode("idna").decode()
    addresses = {row[4][0] for row in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)}
    if not addresses or any(not ipaddress.ip_address(ip).is_global for ip in addresses):
        raise PageError("Private or non-public addresses cannot be researched.")
    return host, sorted(addresses)[0], parts


def read_public(url, redirects=2, max_bytes=MAX_BYTES):
    for _ in range(redirects + 1):
        host, address, parts = public_target(url)
        conn = http.client.HTTPSConnection(host, timeout=4)
        raw = socket.create_connection((address, 443), timeout=4)
        try:
            tls = ssl.create_default_context().wrap_socket(raw, server_hostname=host)
            conn.sock = tls
            conn.request("GET", (parts.path or "/") + ("?" + parts.query if parts.query else ""),
                         headers={"Host": host, "User-Agent": AGENT, "Accept": "text/html,text/plain", "Accept-Encoding": "identity"})
            response = conn.getresponse()
            if response.status in (301, 302, 303, 307, 308):
                url = urljoin(url, response.getheader("location", ""))
                continue
            if response.status == 404:
                return url, 404, "", ""
            if response.status != 200:
                raise PageError(f"Source returned HTTP {response.status}; open it manually or use catalog import.")
            content_type = response.getheader("content-type", "").lower()
            if not any(t in content_type for t in ("text/html", "text/plain", "application/xhtml+xml")):
                raise PageError("Source did not return a readable HTML page.")
            if response.getheader("content-encoding", "identity") != "identity":
                raise PageError("Source encoding is not supported.")
            chunks, size = [], 0
            deadline = time.monotonic() + 6
            while size <= max_bytes:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise PageError("Source exceeded the read deadline.")
                tls.settimeout(min(4, remaining))
                chunk = response.read1(min(65536, max_bytes + 1 - size))
                if not chunk:
                    break
                chunks.append(chunk)
                size += len(chunk)
            data = b"".join(chunks)
            if len(data) > max_bytes:
                raise PageError("Source page exceeded the research size limit.")
            return url, 200, data.decode("utf-8", errors="replace"), content_type
        finally:
            conn.close()
            raw.close()
    raise PageError("Source redirected too many times.")


def read_allowed(url):
    parts = urlsplit(url)
    robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
    final, status, body, _ = read_public(robots_url, max_bytes=100_000)
    if urlsplit(final).netloc != parts.netloc:
        raise PageError("Could not establish the source's crawl permission.")
    if status == 200:
        robots = RobotFileParser()
        robots.parse(body.splitlines())
        if not robots.can_fetch(AGENT, url):
            raise PageError("Source does not permit automated research; open it manually or import your catalog.")
    # Redirects to another product page require its own robots check.
    final, status, body, _ = read_public(url, redirects=0)
    if status != 200:
        raise PageError("Product page is unavailable.")
    return final, body


class PageHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.meta, self.blocks, self.links = {}, [], []
        self.capture, self.buffer = False, []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "meta":
            self.meta[(a.get("property") or a.get("name") or "").lower()] = a.get("content", "")
        if tag == "script" and a.get("type", "").lower() == "application/ld+json":
            self.capture, self.buffer = True, []
        if tag == "a" and a.get("href"):
            self.links.append(a["href"])

    def handle_data(self, data):
        if self.capture:
            self.buffer.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self.capture:
            self.blocks.append("".join(self.buffer))
            self.capture = False


@dataclass
class PageFacts:
    kind: str = "needs_review"
    title: str = ""
    description: str = ""
    price: float | None = None
    currency: str | None = None
    availability: str = "not provided"
    price_basis: str = "not found"
    url: str = ""
    note: str = ""
    links: list[str] = field(default_factory=list)


def _types(node):
    value = node.get("@type", [])
    return {str(t).rsplit("/", 1)[-1] for t in (value if isinstance(value, list) else [value])}


def _nodes(value):
    if isinstance(value, list):
        for node in value:
            yield from _nodes(node)
    elif isinstance(value, dict):
        yield value
        yield from _nodes(value.get("@graph", []))
        yield from _nodes(value.get("mainEntity", []))


def _price(value):
    try:
        number = float(str(value).replace(",", ""))
        return number if math.isfinite(number) and 0 < number < 1_000_000_000 else None
    except (TypeError, ValueError):
        return None


def _text(value, limit=500):
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", str(value or "")))).strip()[:limit]


def extract_page(html, url):
    parser = PageHTML()
    parser.feed(html)
    nodes = []
    for block in parser.blocks[:30]:
        try:
            nodes.extend(_nodes(json.loads(block)))
        except (ValueError, RecursionError):
            continue
    products = [n for n in nodes if "Product" in _types(n)]
    collection = any(_types(n) & {"CollectionPage", "ItemList", "SearchResultsPage"} for n in nodes)
    facts = PageFacts(url=url)
    for href in parser.links:
        link = urldefrag(urljoin(url, href))[0]
        path = urlsplit(link).path
        if urlsplit(link).netloc == urlsplit(url).netloc and re.search(r"/(?:products/[^/]+|[^/]+-i\d+[^/]*)/?$", path) and link != url and link not in facts.links:
            facts.links.append(link)
    if len(products) == 1 and not collection:
        product = products[0]
        facts.kind = "product"
        facts.title = _text(product.get("name"), 200)
        facts.description = _text(product.get("description"))
        offers = product.get("offers", [])
        offers = offers if isinstance(offers, list) else [offers]
        offers = [o for o in offers if isinstance(o, dict)]
        # Multiple variants or AggregateOffer ranges are not a single price.
        prices = {(p, str(o.get("priceCurrency", "")).upper()) for o in offers
                  if "AggregateOffer" not in _types(o) and (p := _price(o.get("price"))) is not None}
        if len(prices) == 1:
            facts.price, currency = next(iter(prices))
            facts.currency = currency if re.fullmatch(r"[A-Z]{3}", currency) else None
            facts.price_basis = "product structured offer"
        elif offers:
            facts.note = "Variant prices or a price range require confirmation on the source."
        if len(offers) == 1:
            facts.availability = str(offers[0].get("availability", "not provided")).rsplit("/", 1)[-1][:60]
    elif not collection and not products and parser.meta.get("og:type", "").lower() == "product":
        facts.kind = "product"
        facts.title = _text(parser.meta.get("og:title"), 200)
        facts.description = _text(parser.meta.get("og:description"))
        facts.price = _price(parser.meta.get("product:price:amount"))
        currency = parser.meta.get("product:price:currency", "").upper()
        facts.currency = currency if re.fullmatch(r"[A-Z]{3}", currency) else None
        facts.price_basis = "product page metadata" if facts.price else "not found"
    else:
        facts.kind = "collection" if collection or len(products) > 1 or facts.links else "needs_review"
        facts.note = "Collection/search page, not an individual product." if facts.kind == "collection" else "No unambiguous product data found; confirm details manually."
    if facts.price is not None and not facts.currency:
        facts.note = "Price found without a reliable currency; confirm before comparing."
    return facts


def inspect_page(url):
    try:
        final, html = read_allowed(url)
        return extract_page(html, final)
    except (PageError, OSError, ValueError, http.client.HTTPException, RecursionError):
        return PageFacts(url=url, note="Page could not be read safely, is restricted, or lacks accessible data. Open the source to confirm or import your catalog.")


def inspect_pages(urls):
    with ThreadPoolExecutor(max_workers=4) as pool:
        return list(pool.map(inspect_page, list(urls)[:8]))
