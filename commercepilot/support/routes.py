"""Merchant setup routes and a separately scoped, origin-restricted widget API."""
from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from starlette.concurrency import run_in_threadpool

from .. import ai, config
from ..runtime import get_support_store
from . import service, shopify
from .models import ChatRequest, NextPage, PreviewRequest, Settings, origin
from .store import digest, now

router = APIRouter(prefix="/api/support", tags=["Customer support"])


@router.get("/status")
def support_status():
    return service.status(get_support_store())


@router.put("/settings")
def support_settings(payload: Settings):
    return service.save_settings(get_support_store(), payload)


@router.post("/sync/start")
def sync_start():
    return shopify.start(get_support_store())


@router.post("/sync/next")
def sync_next(payload: NextPage):
    return shopify.next_page(get_support_store(), payload.sync_id)


@router.post("/preview")
def support_preview(payload: PreviewRequest):
    store = get_support_store()
    _daily_limit(store)
    return service.answer(store, payload.message, [turn.model_dump() for turn in payload.history])


@router.get("/install")
def install(request: Request):
    base = origin(config.PUBLIC_URL or str(request.base_url).rstrip("/"))
    widget_id = get_support_store().state()["widget_id"]
    return {"snippet": f'<script src="{base}/api/support/widget.js" data-widget="{widget_id}" defer></script>',
            "script_url": f"{base}/api/support/widget.js", "widget_id": widget_id}


@router.get("/widget.js", include_in_schema=False)
def widget_script():
    return FileResponse(config.PACKAGE_DIR / "support" / "widget.js", media_type="application/javascript")


def widget_state(widget_id):
    store = get_support_store()
    state = store.state()
    if not re.fullmatch(r"[a-f0-9]{32}", widget_id) or state["widget_id"] != widget_id:
        raise HTTPException(404, "Chat widget not found.")
    if not state["settings"]["enabled"]:
        raise HTTPException(503, "Chat is currently unavailable. Please contact the store.")
    if service.availability(state):
        raise HTTPException(503, "Chat is being updated. Please contact the store or try later.")
    return store, state


async def widget_cors(request, call_next):
    """Permit Shopify origins only for the customer endpoints, never workspace APIs."""
    match = re.fullmatch(r"/api/support/widget/([a-f0-9]{32})/(config|session|chat)", request.url.path)
    response_origin = ""
    try:
        if not match:
            raise HTTPException(404, "Not found")
        _, state = await run_in_threadpool(widget_state, match[1])
        incoming = request.headers.get("origin", "")
        if not incoming and request.headers.get("sec-fetch-site") == "same-origin":
            incoming = str(request.base_url).rstrip("/")
        if incoming not in service.allowed_origins(state):
            raise HTTPException(403, "This store origin is not allowed to use the chat widget.")
        response_origin = incoming
        length = request.headers.get("content-length", "0")
        if not length.isdigit() or int(length) > 8192:
            raise HTTPException(413, "Chat request is too large.")
        if request.method == "OPTIONS":
            response = Response(status_code=204)
        else:
            response = await call_next(request)
    except HTTPException as exc:
        response = JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers=exc.headers)
    if response_origin:
        response.headers["Access-Control-Allow-Origin"] = response_origin
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Vary"] = "Origin"
    return response


def _client_key(request):
    # Do not trust a caller-provided forwarded IP header. A shared reverse-proxy
    # address may conservatively share this bucket; daily/session caps also apply.
    return digest(request.client.host if request.client else "unknown")


def _daily_limit(store):
    store.limit("messages:" + now().date().isoformat(), config.SUPPORT_DAILY_MESSAGES, 86400)


@router.get("/widget/{widget_id}/config")
def widget_config(widget_id: str):
    _, state = widget_state(widget_id)
    return {key: state["settings"][key] for key in ("assistant_name", "welcome", "accent", "support_email")}


@router.post("/widget/{widget_id}/session")
def widget_session(widget_id: str, request: Request):
    store, state = widget_state(widget_id)
    store.limit("sessions:" + _client_key(request), 20, 3600)
    return {"session_token": store.new_session(state), "expires_in": 86400}


@router.post("/widget/{widget_id}/chat")
def widget_chat(widget_id: str, payload: ChatRequest, request: Request):
    store, state = widget_state(widget_id)
    history = store.reserve_session(state, payload.session_token)
    try:
        store.limit("session:" + digest(payload.session_token), 20, 3600)
        store.limit("ip:" + _client_key(request), 60, 3600)
        _daily_limit(store)
        result = service.answer(store, payload.message, history)
        history.extend([{"role": "user", "content": payload.message}, {"role": "assistant", "content": result["answer"]}])
        store.finish_session(payload.session_token, history)
        return result
    except ai.AIError as exc:
        raise HTTPException(503, "Chat is temporarily unavailable. Please try again or contact the store.") from exc
    finally:
        store.finish_session(payload.session_token)
