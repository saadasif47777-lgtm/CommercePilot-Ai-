"""Integration status and optional credential handling (server-side only).

Nothing here ever returns a secret. Status responses contain booleans and
masked identifiers only. Credentials saved from the Settings UI go to
.secrets/ which is git-ignored; environment variables take precedence.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timedelta, timezone

import httpx

from . import ai, config


def _fingerprint(parts):
    return hashlib.sha256(json.dumps(parts).encode()).hexdigest()


def mark_verified(provider, parts, success=True):
    from .runtime import get_store
    db = get_store()._conn()
    if not success:
        db.execute("DELETE FROM integration_verifications WHERE provider=?", (provider,))
        return
    db.execute("INSERT INTO integration_verifications(provider,fingerprint,checked_at) VALUES (?,?,?) ON CONFLICT(provider) DO UPDATE SET fingerprint=excluded.fingerprint,checked_at=excluded.checked_at",
               (provider, _fingerprint(parts), datetime.now(timezone.utc).isoformat()))


def connection_status(provider, parts):
    if not all(parts):
        return "not_connected"
    from .runtime import get_store
    row = get_store()._conn().execute("SELECT fingerprint,checked_at FROM integration_verifications WHERE provider=?", (provider,)).fetchone()
    if row and row["fingerprint"] == _fingerprint(parts) and datetime.fromisoformat(row["checked_at"]) > datetime.now(timezone.utc) - timedelta(hours=24):
        return "connected"
    return "configured_unverified"


def _mask(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 6:
        return "*" * len(value)
    return f"{value[:3]}…{value[-2:]} (masked, {len(value)} chars)"


def _saved(provider: str) -> dict:
    if config.DATABASE_URL:
        from .credentials import read
        return read(provider)
    path = config.integration_secrets_path(provider)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
    return {}


def save_credentials(provider: str, data: dict) -> None:
    if config.DATABASE_URL:
        from .credentials import save
        save(provider, data)
        return
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
        "status": connection_status("meta", [token, account]),
        "capabilities_when_connected": [
            "Read ad account details and measured spend, clicks and impressions",
        ],
        "current_capabilities": [
            "Local campaign planning and drafts",
            "Read-only Meta account reporting when connected",
        ],
        "ad_account_id": _mask(account) if account else "",
        "token_configured": bool(token),
        "missing_configuration": [] if (token and account) else [
            "META_ACCESS_TOKEN (token with ads_read)",
            "META_AD_ACCOUNT_ID (e.g. act_123456789)",
        ],
        "setup_instructions": [
            "Create a Meta App of type Business and add the Marketing API product.",
            "Generate a System User token with ads_read access to the ad account.",
            "Set META_ACCESS_TOKEN and META_AD_ACCOUNT_ID on the BACKEND only (.env).",
            "Verify the connection from Settings; publishing always requires explicit human approval.",
        ],
        "note": "Connect your ad account for verification and measured reporting. Campaign plans remain drafts; this workspace does not purchase ads.",
    }


def meta_verify() -> dict:
    saved = _saved("meta")
    token = config.META_ACCESS_TOKEN or saved.get("access_token", "")
    account = config.META_AD_ACCOUNT_ID or saved.get("ad_account_id", "")
    if not token or not re.fullmatch(r"act_[0-9]+", account):
        return {"verified": False, "detail": "Configure a token and an ad account id such as act_123456789."}
    try:
        with httpx.Client(timeout=8) as client:
            resp = client.get(
                f"https://graph.facebook.com/{config.META_API_VERSION}/{account}",
                params={"fields": "id,name,currency,account_status"},
                headers={"Authorization": f"Bearer {token}"},
            )
        if resp.status_code == 200:
            data = resp.json()
            mark_verified("meta", [token, account])
            return {"verified": True, "detail": f"Connected to {data.get('name', 'ad account')}.", "account": data}
        mark_verified("meta", [token, account], False)
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
        "status": connection_status("shopify", [domain, token]),
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
            "Catalog access is read-only. Imported products can be selected in your workspace.",
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
                    shop { currencyCode }
                    products(first: $first) { nodes {
                        id title handle description featuredMedia { preview { image { url } } }
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
            mark_verified("shopify", [domain, token])
            return {"ok": True, "currency": (payload["data"].get("shop") or {}).get("currencyCode"), "count": len(rows), "page_info": catalog["pageInfo"], "products": [
                {"id": p.get("id"), "title": p.get("title"), "handle": p.get("handle"), "description": (p.get("description") or "")[:2000], "url": f"https://{clean}/products/{p.get('handle')}",
                 "price": ((p.get("variants") or {}).get("nodes") or [{}])[0].get("price"),
                 "image": (((p.get("featuredMedia") or {}).get("preview") or {}).get("image") or {}).get("url")}
                for p in rows
            ]}
        if resp.status_code == 401:
            return {"ok": False, "detail": "Shopify rejected the token (401). Check scopes: read_products."}
        if resp.status_code == 404:
            return {"ok": False, "detail": "Shop domain not found (404). Check SHOPIFY_SHOP_DOMAIN."}
        return {"ok": False, "detail": f"Shopify returned HTTP {resp.status_code}."}
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        return {"ok": False, "detail": f"Could not reach the Shopify store: {exc.__class__.__name__}"}


def meta_insights(date_preset="last_30d"):
    saved = _saved("meta")
    token = config.META_ACCESS_TOKEN or saved.get("access_token", "")
    account = config.META_AD_ACCOUNT_ID or saved.get("ad_account_id", "")
    if not token or not re.fullmatch(r"act_[0-9]+", account):
        return {"ok": False, "detail": "Connect a Meta ad account first."}
    try:
        with httpx.Client(timeout=15) as client:
            response = client.get(f"https://graph.facebook.com/{config.META_API_VERSION}/{account}/insights",
                                  params={"fields": "account_name,account_currency,spend,clicks,impressions,date_start,date_stop", "date_preset": date_preset, "level": "account"},
                                  headers={"Authorization": f"Bearer {token}"})
        if response.status_code != 200:
            mark_verified("meta", [token, account], False)
            return {"ok": False, "detail": f"Meta reporting returned HTTP {response.status_code}. Check ads_read permission."}
        rows = response.json()["data"]
        mark_verified("meta", [token, account])
        return {"ok": True, "source": "Meta Ads Insights", "date_preset": date_preset, "rows": rows,
                "detail": "No delivery was reported for this period." if not rows else "Measured account totals; attribution to an individual product is not implied."}
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        return {"ok": False, "detail": "Meta reporting is unavailable. Retry or check the account configuration."}


# --------------------------------------------------------------------------- #
# Aggregate
# --------------------------------------------------------------------------- #
def all_status() -> dict:
    search_provider = "Serper API" if config.SERPER_API_KEY else "DuckDuckGo (ddgs, key-free)"
    return {
        "llm": {
            "provider": "OpenAI-compatible API",
            "status": connection_status("llm", [config.LLM_API_KEY, config.LLM_MODEL]),
            "model": config.LLM_MODEL if ai.available() else "",
            "anthropic": {"model": config.ANTHROPIC_MODEL,
                          "status": connection_status("llm_anthropic", [config.ANTHROPIC_API_KEY, config.ANTHROPIC_MODEL])}
                         if config.ANTHROPIC_API_KEY else None,
            "modules": {
                module: {"provider": route.provider, "model": route.model,
                         "status": connection_status("llm_anthropic", [route.api_key, route.model])}
                for prompt, module in {"campaign_creatives": "marketing", "store_copy": "store_architect", "product_research": "product_hunting"}.items()
                if module in config.CLAUDE_MODULES
                for route in [ai.route_for(prompt)]
            },
            "detail": (
                "LLM-assisted copy and intent parsing enabled."
                if ai.available()
                else "Set LLM_API_KEY and LLM_MODEL on the server to enable AI generation."
            ),
        },
        "web_search": {
            "provider": search_provider,
            "status": "configured_unverified",
            "detail": "Live web search for Product Hunter Mode A, with source URLs attached.",
        },
        "meta": meta_status(),
        "shopify": shopify_status(),
        "storage": {"provider": "PostgreSQL" if config.DATABASE_URL else "SQLite", "status": "connected", "detail": "Project history and integration verification persist in the workspace database."},
    }
