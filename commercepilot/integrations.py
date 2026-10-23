"""Integration status and optional credential handling (server-side only).

Nothing here ever returns a secret. Status responses contain booleans and
masked identifiers only. Credentials saved from the Settings UI go to
.secrets/ which is git-ignored; environment variables take precedence.
"""
from __future__ import annotations

import contextlib
import json
import os
import re
import tempfile

import httpx

from . import ai, config


def _mask(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 6:
        return "*" * len(value)
    return f"{value[:3]}…{value[-2:]} (masked, {len(value)} chars)"


def _saved(provider: str) -> dict:
    path = config.integration_secrets_path(provider)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
    return {}


def save_credentials(provider: str, data: dict) -> None:
    path = config.integration_secrets_path(provider)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".credentials-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    # Best-effort owner-only permissions (some filesystems do not support it).
    with contextlib.suppress(OSError):
        path.chmod(0o600)


# --------------------------------------------------------------------------- #
# Meta Marketing API
# --------------------------------------------------------------------------- #
def meta_status() -> dict:
    saved = _saved("meta")
    token = config.META_ACCESS_TOKEN or saved.get("access_token", "")
    account = config.META_AD_ACCOUNT_ID or saved.get("ad_account_id", "")
    return {
        "provider": "Meta Marketing API",
        "status": "configured_unverified" if (token and account) else "not_connected",
        "capabilities_when_connected": [
            "Create and update campaigns, ad sets and ads",
            "Pull spend, impressions, clicks and conversions",
            "Upload audiences for retargeting",
        ],
        "current_capabilities": [
            "Local campaign planning and drafts",
            "Simulated execution labelled DEMO - NOT PUBLISHED",
        ],
        "ad_account_id": _mask(account) if account else "",
        "token_configured": bool(token),
        "missing_configuration": [] if (token and account) else [
            "META_ACCESS_TOKEN (long-lived token with ads_management)",
            "META_AD_ACCOUNT_ID (e.g. act_123456789)",
        ],
        "setup_instructions": [
            "Create a Meta App of type Business and add the Marketing API product.",
            "Generate a System User token with ads_management on the ad account.",
            "Set META_ACCESS_TOKEN and META_AD_ACCOUNT_ID on the BACKEND only (.env).",
            "Verify the connection from Settings; publishing always requires explicit human approval.",
        ],
        "note": "No campaign has ever been published to Meta from this prototype.",
    }


def meta_verify() -> dict:
    saved = _saved("meta")
    token = config.META_ACCESS_TOKEN or saved.get("access_token", "")
    if not token:
        return {"verified": False, "detail": "No access token configured."}
    try:
        with httpx.Client(timeout=8) as client:
            resp = client.get(
                "https://graph.facebook.com/me",
                params={"fields": "id,name"},
                headers={"Authorization": f"Bearer {token}"},
            )
        if resp.status_code == 200:
            data = resp.json()
            return {"verified": True, "detail": f"Token valid for app user id {data.get('id')}."}
        return {"verified": False, "detail": f"Meta verification failed (HTTP {resp.status_code}). Check token permissions."}
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        return {"verified": False, "detail": f"Could not reach graph.facebook.com: {exc.__class__.__name__}"}


# --------------------------------------------------------------------------- #
# Shopify Admin API
# --------------------------------------------------------------------------- #
def shopify_status() -> dict:
    saved = _saved("shopify")
    domain = config.SHOPIFY_SHOP_DOMAIN or saved.get("shop_domain", "")
    token = config.SHOPIFY_ADMIN_TOKEN or saved.get("admin_token", "")
    return {
        "provider": "Shopify Admin API",
        "status": "configured_unverified" if (domain and token) else "not_connected",
        "store_domain": domain or "",
        "token_configured": bool(token),
        "capabilities_when_connected": [
            "Read product catalog (title, price, stock)",
            "Optional: import products into Product Hunter research",
        ],
        "current_capabilities": [
            "Shopify-inspired storefront preview generated locally (independent of Shopify)",
        ],
        "missing_configuration": [] if (domain and token) else [
            "SHOPIFY_SHOP_DOMAIN (e.g. your-store.myshopify.com)",
            "SHOPIFY_ADMIN_TOKEN (custom app token with read_products)",
        ],
        "setup_instructions": [
            "In Shopify: Settings -> Develop apps -> create a custom app.",
            "Grant read_products (Admin API scopes) and install the app.",
            "Set SHOPIFY_SHOP_DOMAIN and SHOPIFY_ADMIN_TOKEN on the BACKEND only (.env).",
            "Note: a Storefront API token does NOT provide admin access.",
            "This prototype never publishes themes or modifies the live store.",
        ],
    }


def shopify_fetch_products(limit: int = 10) -> dict:
    saved = _saved("shopify")
    domain = config.SHOPIFY_SHOP_DOMAIN or saved.get("shop_domain", "")
    token = config.SHOPIFY_ADMIN_TOKEN or saved.get("admin_token", "")
    if not domain or not token:
        return {"ok": False, "detail": "Shopify is not configured (domain or token missing)."}
    clean = domain.replace("https://", "").replace("http://", "").strip("/")
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9-]*\.myshopify\.com", clean):
        return {"ok": False, "detail": "Invalid store domain format - expected e.g. your-store.myshopify.com"}
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.post(
                f"https://{clean}/admin/api/{config.SHOPIFY_API_VERSION}/graphql.json",
                json={"query": """query Catalog($first: Int!) {
                    products(first: $first) { nodes {
                        id title handle featuredImage { url }
                        variants(first: 1) { nodes { price } }
                    } pageInfo { hasNextPage endCursor } }
                }""", "variables": {"first": max(1, min(limit, 50))}},
                headers={"X-Shopify-Access-Token": token},
            )
        if resp.status_code == 200:
            payload = resp.json()
            if payload.get("errors") or not isinstance(payload.get("data"), dict):
                return {"ok": False, "detail": "Shopify rejected the catalog query. Check read_products scope."}
            catalog = payload["data"]["products"]
            rows = catalog["nodes"]
            return {"ok": True, "count": len(rows), "page_info": catalog["pageInfo"], "products": [
                {"title": p.get("title"), "handle": p.get("handle"),
                 "price": ((p.get("variants") or {}).get("nodes") or [{}])[0].get("price"),
                 "image": (p.get("featuredImage") or {}).get("url")}
                for p in rows
            ]}
        if resp.status_code == 401:
            return {"ok": False, "detail": "Shopify rejected the token (401). Check scopes: read_products."}
        if resp.status_code == 404:
            return {"ok": False, "detail": "Shop domain not found (404). Check SHOPIFY_SHOP_DOMAIN."}
        return {"ok": False, "detail": f"Shopify returned HTTP {resp.status_code}."}
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        return {"ok": False, "detail": f"Could not reach the Shopify store: {exc.__class__.__name__}"}


# --------------------------------------------------------------------------- #
# Aggregate
# --------------------------------------------------------------------------- #
def all_status() -> dict:
    search_provider = "Serper API" if config.SERPER_API_KEY else "DuckDuckGo (ddgs, key-free)"
    return {
        "llm": {
            "provider": "OpenAI-compatible API",
            "status": "configured_unverified" if ai.available() else "not_connected",
            "model": config.LLM_MODEL if ai.available() else "",
            "detail": (
                "LLM-assisted copy and intent parsing enabled."
                if ai.available()
                else "No OPENAI_API_KEY configured - running deterministic FALLBACK MODE "
                "(templates + rules). Results are labelled accordingly; no LLM claims are made."
            ),
        },
        "web_search": {
            "provider": search_provider,
            "status": "configured_unverified",
            "detail": "Live web search for Product Hunter Mode A, with source URLs attached.",
        },
        "meta": meta_status(),
        "shopify": shopify_status(),
        "storage": {"provider": "SQLite", "status": "connected", "detail": "Projects persist across restarts (data/commercepilot.sqlite3)."},
    }
