"""Grounded retrieval with the workspace model; the model never executes SQL."""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta

from fastapi import HTTPException

from .. import config
from ..ai.client import AIConfigError, AIValidationError, complete_json
from ..ai.guard import sanitize_text, wrap_untrusted
from . import shopify
from .models import GroundedAnswer, QueryPlan, Settings
from .store import digest, now


def availability(state):
    if not state.get("active"):
        return "Sync Shopify products and policies first."
    try:
        if shopify.connection()[2] != state.get("fingerprint"):
            return "Shopify connection changed. Sync again before using customer support."
    except HTTPException:
        return "Connect Shopify and sync its products and policies."
    if datetime.fromisoformat(state["synced_at"]) < now() - timedelta(hours=config.SUPPORT_KNOWLEDGE_HOURS):
        return "Store knowledge has expired. Sync Shopify again to resume chat."
    return ""


def allowed_origins(state):
    return list(dict.fromkeys([*state.get("shop", {}).get("origins", []), *state["settings"]["allowed_origins"]]))


def status(store):
    state = store.state()
    reason = availability(state)
    pending = state.get("pending")
    return {"widget_id": state["widget_id"], "settings": state["settings"], "ready": not reason,
            "reason": reason, "shop": state.get("shop"), "synced_at": state.get("synced_at"),
            "knowledge_hours": config.SUPPORT_KNOWLEDGE_HOURS, "daily_message_limit": config.SUPPORT_DAILY_MESSAGES,
            "counts": store.counts(state.get("active", "")), "allowed_origins": allowed_origins(state),
            "pending": {"sync_id": pending["id"], "pages": pending["pages"], "scanned": pending["scanned"]} if pending else None}


def save_settings(store, settings: Settings):
    if settings.enabled and (reason := availability(store.state())):
        raise HTTPException(422, reason)
    store.save_settings(settings)
    return status(store)


def card(doc):
    return {key: doc.get(key, "") for key in ("id", "title", "url", "price", "max_price", "currency", "image")}


def _policy_context(docs, message, terms):
    words = set(re.findall(r"[^\W_]+", (message + " " + " ".join(terms)).casefold()))
    aliases = {"return": {"refund", "return", "exchange"}, "shipping": {"shipping", "delivery", "ship"},
               "refund": {"refund", "return", "money"}, "privacy": {"privacy", "data"}}
    for word, extra in aliases.items():
        if word in words:
            words.update(extra)
    chunks = []
    for doc in docs:
        for start in range(0, len(doc["body"]), 1000):
            excerpt = doc["body"][max(0, start - 150):start + 1300]
            score = sum((doc["title"] + " " + excerpt).casefold().count(word) for word in words if len(word) > 2)
            chunks.append((score, {"id": doc["id"] + ":" + str(start), "title": doc["title"], "body": excerpt, "url": doc["url"], "kind": "policy"}))
    chunks.sort(key=lambda item: item[0], reverse=True)
    return [chunk for _, chunk in chunks[:6]]


def _text(value):
    value = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", value)
    value = re.sub(r"https?://\S+", "", value)
    return sanitize_text(value, 2500)


def _data(value):
    # Keep user-supplied delimiters inside JSON strings, not prompt tag syntax.
    return json.dumps(value, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e")


def answer(store, message, history=None):
    state = store.state()
    if reason := availability(state):
        raise HTTPException(409, reason)
    settings = state["settings"]
    shop = state["shop"]
    history = (history or [])[-8:]
    conversation = {"shop_name": shop["name"], "currency": shop["currency"], "history": history, "message": message}
    user = wrap_untrusted("conversation", _data(conversation), 30000)
    plan = complete_json(prompt_name="support_query", user=user, schema=QueryPlan, max_tokens=300, timeout=10, retries=0)
    if plan is None:
        raise AIConfigError("Configure the workspace AI model before testing customer chat.")
    contact = settings["support_email"]
    base = {"products": [], "sources": [], "support_email": contact, "synced_at": state["synced_at"], "needs_human": False}
    if plan.intent == "handoff":
        return dict(base, answer="Please contact the store's support team for help with your order or account. I can help with product choices and published store policies.", needs_human=True)
    if plan.currency and plan.currency != shop["currency"]:
        return dict(base, answer=f"This catalog lists prices in {shop['currency']}. Please check the product page for your market's currency and final price.", needs_human=True)
    products = store.products(state["active"], plan) if plan.intent == "products" else []
    policies = _policy_context(store.documents(state["active"], "policy"), message, plan.terms) if plan.intent in {"policies", "general"} else []
    faqs = [{"id": "faq:" + digest(faq["question"]), "title": faq["question"], "body": faq["answer"], "kind": "faq", "url": ""} for faq in settings["faqs"]]
    faqs = sorted(faqs, key=lambda doc: sum(word in (doc["title"] + " " + doc["body"]).casefold() for word in re.findall(r"[^\W_]+", message.casefold()) if len(word) > 2), reverse=True)[:4]
    if plan.intent == "products" and not products:
        return dict(base, answer="I couldn't find a matching product in our synced online catalog. Try a different product name or budget, or contact the store for help.", needs_human=True)
    if plan.intent == "policies" and not policies and not faqs:
        return dict(base, answer="I don't have a published policy answering that question. Please contact the store to confirm before ordering.", needs_human=True)
    sources = {doc["id"]: doc for doc in [*policies, *faqs]}
    context = {"shop": shop, "assistant_name": settings["assistant_name"], "support_email": contact,
               "products": [dict(card(doc), description=doc["body"][:1000], keywords=doc.get("keywords", "")[:300]) for doc in products], "sources": list(sources.values())}
    result = complete_json(prompt_name="support_answer", user=user + "\n" + wrap_untrusted("knowledge", _data(context), 60000),
                           schema=GroundedAnswer, max_tokens=750, timeout=10, retries=0)
    if result is None:
        raise AIConfigError("Configure the workspace AI model before testing customer chat.")
    candidates = {doc["id"]: doc for doc in products}
    if any(key not in candidates for key in result.product_ids) or any(key not in sources for key in result.source_ids):
        raise AIValidationError("The support answer referenced unavailable evidence. Please retry.")
    if not result.needs_human and ((plan.intent == "products" and not result.product_ids) or (plan.intent == "policies" and not result.source_ids)):
        raise AIValidationError("The support answer was missing its source. Please retry.")
    if store.state().get("active") != state["active"]:
        raise HTTPException(409, "Store knowledge was refreshed during this answer. Please retry.")
    return dict(base, answer=_text(result.answer), needs_human=result.needs_human,
                products=[card(candidates[key]) for key in dict.fromkeys(result.product_ids)],
                sources=[{"title": sources[key]["title"], "url": sources[key]["url"], "kind": sources[key]["kind"]} for key in dict.fromkeys(result.source_ids)])
