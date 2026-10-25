import json
import socket

import pytest

from commercepilot.agents import product_hunter as ph
from commercepilot.schemas import ResearchRequest
from commercepilot.tools import product_pages as pages
from commercepilot.tools.web_search import SearchOutcome, SearchResult


def html(node):
    return '<script type="application/ld+json">' + json.dumps(node) + '</script>'


def product(**updates):
    return {"@type": "Product", "name": "Ceramic vase", "description": "<p>Handmade vase</p>",
            "offers": {"@type": "Offer", "price": "2,500.50", "priceCurrency": "PKR", "availability": "https://schema.org/InStock"}, **updates}


def test_extracts_product_graph_and_offer_without_executing_scripts():
    result = pages.extract_page(html({"@graph": [product()]}), "https://shop.example/products/vase")
    assert result.kind == "product" and result.price == 2500.5
    assert result.currency == "PKR" and result.availability == "InStock"
    assert result.description == "Handmade vase"


@pytest.mark.parametrize("offers", [
    {"@type": "AggregateOffer", "lowPrice": "100", "highPrice": "200", "priceCurrency": "PKR"},
    [{"price": "100", "priceCurrency": "PKR"}, {"price": "200", "priceCurrency": "PKR"}],
    {"price": "NaN", "priceCurrency": "PKR"},
    {"price": "-2", "priceCurrency": "PKR"},
])
def test_ranges_variants_and_invalid_prices_are_not_single_prices(offers):
    result = pages.extract_page(html(product(offers=offers)), "https://shop.example/products/vase")
    assert result.price is None


def test_collection_does_not_use_embedded_product_as_its_own_price():
    result = pages.extract_page(html({"@type": "CollectionPage", "mainEntity": product()}) + '<a href="/products/vase">Vase</a>', "https://shop.example/collections/vases")
    assert result.kind == "collection" and result.price is None
    assert result.links == ["https://shop.example/products/vase"]


def test_product_metadata_fallback_requires_product_identity():
    markup = '<meta property="product:price:amount" content="2500"><meta property="product:price:currency" content="PKR">'
    assert pages.extract_page(markup, "https://shop.example/").price is None
    result = pages.extract_page('<meta property="og:type" content="product">' + markup, "https://shop.example/p")
    assert result.price == 2500 and result.currency == "PKR"


def test_shopify_og_price_alias_and_single_variant_product_group():
    markup = '<meta property="og:type" content="product"><meta property="og:title" content="Vase"><meta property="og:price:amount" content="3,450"><meta property="og:price:currency" content="PKR">'
    result = pages.extract_page(markup, "https://shop.example/products/vase")
    assert result.price == 3450 and result.currency == "PKR"
    result = pages.extract_page(html({"@type": "ProductGroup", "name": "Vase", "hasVariant": [product()]}), "https://shop.example/products/vase")
    assert result.title == "Vase" and result.price == 2500.5
    group = {"@type": "ProductGroup", "name": "Variant vase", "hasVariant": [product(), product()]}
    result = pages.extract_page(markup + html(group), "https://shop.example/products/vase")
    assert result.title == "Variant vase" and result.price == 3450
    assert "variant" in result.price_basis and "confirm" in result.note.lower()


def test_marketplace_tag_cannot_claim_product_identity_through_og_type():
    result = pages.extract_page('<meta property="og:type" content="product">', "https://www.daraz.pk/tag/ceramic-vases/")
    assert result.kind == "collection" and result.price is None
    assert pages.is_collection_url("https://www.olx.com.pk/vases_c707170")
    assert not pages.is_collection_url("https://brand.example/collections/vases/products/green-vase")


@pytest.mark.parametrize("url", ["http://shop.example/p", "https://user:secret@shop.example/p", "https://shop.example:444/p"])
def test_rejects_unsafe_url_schemes_credentials_and_ports(url):
    with pytest.raises(pages.PageError):
        pages.public_target(url)


@pytest.mark.parametrize("address", ["127.0.0.1", "10.1.2.3", "169.254.169.254", "::1", "::ffff:127.0.0.1"])
def test_dns_must_resolve_only_to_public_addresses(monkeypatch, address):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(socket.AF_INET, 1, 6, "", (address, 443))])
    with pytest.raises(pages.PageError):
        pages.public_target("https://shop.example/p")


def test_robots_denial_prevents_product_request(monkeypatch):
    seen = []
    def read(url, **kwargs):
        seen.append(url)
        return url, 200, "User-agent: *\nDisallow: /", "text/plain"
    monkeypatch.setattr(pages, "read_public", read)
    assert pages.inspect_page("https://shop.example/products/vase").kind == "needs_review"
    assert seen == ["https://shop.example/robots.txt"]


def test_redirect_target_is_validated_before_another_connection(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda host, *a, **k: [(socket.AF_INET, 1, 6, "", ("127.0.0.1" if host == "private.example" else "8.8.8.8", 443))])
    connected = []
    class Raw:
        def close(self):
            pass
    def connect(address, **kwargs):
        connected.append(address)
        return Raw()
    class TLS:
        def wrap_socket(self, raw, **kwargs):
            return raw
    class Response:
        status = 302
        def getheader(self, name, default=None):
            return "https://private.example/secret" if name == "location" else default
    class Connection:
        def __init__(self, *a, **k):
            pass
        def request(self, *a, **k):
            pass
        def getresponse(self):
            return Response()
        def close(self):
            pass
    monkeypatch.setattr(socket, "create_connection", connect)
    monkeypatch.setattr(pages.ssl, "create_default_context", TLS)
    monkeypatch.setattr(pages.http.client, "HTTPSConnection", Connection)
    with pytest.raises(pages.PageError):
        pages.read_public("https://public.example/p")
    assert connected == [("8.8.8.8", 443)]


def test_currency_mismatch_is_retained_but_not_compared(monkeypatch):
    monkeypatch.setattr(ph, "search", lambda *a, **k: SearchOutcome(results=[SearchResult("Vase USD 10", "https://shop.example/products/vase")]))
    result = ph.run(ResearchRequest(niche="vase", mode="live", currency="PKR", price_min=1500, price_max=5000))
    assert len(result.products) == 1
    factor = next(f for f in result.products[0].score_breakdown if f.factor == "price_suitability")
    assert factor.raw_score is None


def test_research_enriches_then_filters_and_expands_collections(monkeypatch):
    monkeypatch.setattr(ph, "search", lambda *a, **k: SearchOutcome(results=[SearchResult("Vases", "https://shop.example/collections/vases")]))
    def inspect(urls):
        return [pages.PageFacts(kind="collection", url=url, links=["https://shop.example/products/vase"]) if "/collections/" in url else pages.PageFacts(kind="product", url=url, title="Ceramic vase", price=2500, currency="PKR", price_basis="product structured offer") for url in urls]
    monkeypatch.setattr(ph, "inspect_pages", inspect)
    result = ph.run(ResearchRequest(niche="vase", mode="live", currency="PKR", price_min=1500, price_max=5000))
    assert result.products[0].page_kind == "product"
    assert result.products[0].observed_price == 2500
    assert result.products[0].score is not None
    assert any(p.page_kind == "collection" for p in result.products)
