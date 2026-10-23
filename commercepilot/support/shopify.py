"""Read public Shopify knowledge into an atomically promoted, paginated snapshot."""
from __future__ import annotations

import json
import re
import uuid
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from urllib.parse import urlsplit

import httpx
from fastapi import HTTPException

from .. import config, integrations
from .models import origin
from .store import digest, now

SHOP_QUERY = """query SupportShop {
  shop { name description currencyCode primaryDomain { url }
    shopPolicies { id title body url type updatedAt }
  }
}"""
CATALOG_QUERY = """query SupportCatalog($after: String) {
  products(first: 100, after: $after, query: "status:active") {
    nodes { id title description handle status onlineStoreUrl vendor productType tags
      featuredMedia { preview { image { url } } }
      priceRangeV2 { minVariantPrice { amount currencyCode } maxVariantPrice { amount currencyCode } }
    }
    pageInfo { hasNextPage endCursor }
  }
}"""


class PlainHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.skip += 1
        elif tag in {"p", "div", "li", "br", "h1", "h2", "h3"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style"} and self.skip:
            self.skip -= 1
        elif tag in {"p", "div", "li"}:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def plain_html(text):
    parser = PlainHTML()
    parser.feed(str(text or ""))
    return re.sub(r"[ \t]+", " ", "".join(parser.parts)).strip()


def connection():
    saved = integrations._saved("shopify")
    domain = (config.SHOPIFY_SHOP_DOMAIN or saved.get("shop_domain", "")).strip().lower()
    domain = domain.removeprefix("https://").rstrip("/")
    token = config.SHOPIFY_ADMIN_TOKEN or saved.get("admin_token", "")
    if not token or not re.fullmatch(r"[a-z0-9][a-z0-9-]*\.myshopify\.com", domain):
        raise HTTPException(422, "Connect Shopify in Settings & Integrations first, using your myshopify.com domain.")
    return domain, token, digest(json.dumps([domain, token]))


def graphql(domain, token, query, variables=None):
    try:
        with httpx.Client(timeout=15, follow_redirects=False) as client:
            response = client.post(f"https://{domain}/admin/api/{config.SHOPIFY_API_VERSION}/graphql.json",
                                   headers={"X-Shopify-Access-Token": token}, json={"query": query, "variables": variables or {}})
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(502, "Shopify could not be reached. Your previous knowledge is unchanged; retry sync.") from exc
    if response.status_code != 200 or payload.get("errors") or not isinstance(payload.get("data"), dict):
        raise HTTPException(502, "Shopify sync was rejected. Check the token's read_products and read_legal_policies scopes, then retry. Your previous knowledge is unchanged.")
    return payload["data"]


def safe_url(value, allowed_origins):
    try:
        if len(str(value or "")) > 2048:
            return ""
        parsed = urlsplit(str(value or ""))
        if parsed.scheme != "https" or parsed.username or parsed.password:
            return ""
        if origin(f"{parsed.scheme}://{parsed.netloc}") not in allowed_origins:
            return ""
        return parsed._replace(fragment="").geturl()
    except ValueError:
        return ""


def start(store):
    domain, token, fingerprint = connection()
    data = graphql(domain, token, SHOP_QUERY)
    try:
        shop = data["shop"]
        storefront = origin(shop["primaryDomain"]["url"])
        origins = list(dict.fromkeys([f"https://{domain}", storefront]))
        docs = []
        for policy in shop["shopPolicies"]:
            body = plain_html(policy["body"])
            url = safe_url(policy["url"], origins)
            if body and url:
                # Preserve complete policy content in SQL; retrieval selects bounded excerpts.
                docs.append({"id": digest(policy["id"]), "kind": "policy", "title": policy["title"][:200],
                             "body": body[:524288], "url": url, "policy_type": policy["type"]})
        metadata = {"name": shop["name"][:200], "description": (shop.get("description") or "")[:2000],
                    "currency": shop["currencyCode"], "domain": domain, "origins": origins}
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(502, "Shopify returned incomplete store or policy information. Retry sync.") from exc
    sync_id = uuid.uuid4().hex
    with store.db:
        store.db.lock_project("support-state")
        state = store.state()
        store.db.execute("DELETE FROM support_documents WHERE generation<>?", (state.get("active", ""),))
        store.insert_documents(sync_id, docs)
        state["pending"] = {"id": sync_id, "cursor": None, "pages": 0, "scanned": 0, "started": now().isoformat(),
                            "fingerprint": fingerprint, "shop": metadata}
        store.write_state(state)
    return {"sync_id": sync_id, "complete": False, "pages": 0, "scanned": 0, "products": 0, "policies": len(docs)}


def product_document(product, shop):
    url = safe_url(product.get("onlineStoreUrl"), shop["origins"])
    if product.get("status") != "ACTIVE" or not url:
        return None  # Draft, archived, or not published to the online store.
    minimum = product["priceRangeV2"]["minVariantPrice"]
    maximum = product["priceRangeV2"]["maxVariantPrice"]
    price = Decimal(minimum["amount"])
    max_price = Decimal(maximum["amount"])
    if not price.is_finite() or not max_price.is_finite() or price < 0 or max_price < price:
        raise ValueError("Invalid price")
    image = (((product.get("featuredMedia") or {}).get("preview") or {}).get("image") or {}).get("url", "")
    if not image.startswith("https://cdn.shopify.com/"):
        image = ""
    return {"id": digest(product["id"]), "kind": "product", "title": product["title"][:200],
            "body": plain_html(product.get("description", ""))[:4000], "url": url,
            "keywords": " ".join([product.get("vendor", ""), product.get("productType", ""), *product.get("tags", [])])[:1000],
            "price": str(price), "max_price": str(max_price), "currency": minimum["currencyCode"], "image": image}


def next_page(store, sync_id):
    state = store.state()
    pending = state.get("pending")
    if not pending or pending["id"] != sync_id:
        raise HTTPException(409, "This sync was replaced or completed. Refresh support status.")
    domain, token, fingerprint = connection()
    if fingerprint != pending["fingerprint"]:
        raise HTTPException(409, "Shopify credentials changed. Start a new sync.")
    data = graphql(domain, token, CATALOG_QUERY, {"after": pending["cursor"]})
    try:
        catalog = data["products"]
        page = catalog["pageInfo"]
        complete = not page["hasNextPage"]
        if not complete and (not page["endCursor"] or page["endCursor"] == pending["cursor"] or pending["pages"] >= 99):
            raise ValueError("Pagination did not advance or exceeded the 10,000-product sync limit")
        docs = [doc for p in catalog["nodes"] if (doc := product_document(p, pending["shop"]))]
    except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
        raise HTTPException(502, "The Shopify catalog page could not be saved completely (limit: 10,000 scanned products). Retry or contact your administrator. Previous knowledge is unchanged.") from exc
    if connection()[2] != fingerprint:
        raise HTTPException(409, "Shopify credentials changed. Start a new sync.")
    with store.db:
        store.db.lock_project("support-state")
        state = store.state()
        current = state.get("pending")
        if not current or current["id"] != sync_id or current["pages"] != pending["pages"]:
            raise HTTPException(409, "Another sync request advanced this page. Refresh status and resume.")
        store.insert_documents(sync_id, docs)
        pending.update(cursor=page["endCursor"], pages=pending["pages"] + 1, scanned=pending["scanned"] + len(catalog["nodes"]))
        state["pending"] = pending
        if complete:
            state.update(active=sync_id, shop=pending["shop"], fingerprint=fingerprint, synced_at=now().isoformat())
            state.pop("pending", None)
            store.db.execute("DELETE FROM support_documents WHERE generation<>?", (sync_id,))
        store.write_state(state)
    counts = store.counts(sync_id)
    return {"sync_id": sync_id, "complete": complete, "pages": pending["pages"], "scanned": pending["scanned"],
            "products": counts.get("product", 0), "policies": counts.get("policy", 0)}
