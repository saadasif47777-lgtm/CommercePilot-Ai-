"""Shared workspace request safeguards and separately scoped public widget guards."""

import time
import uuid

from starlette.responses import JSONResponse

from . import config
from .auth import workspace
from .deadline import expires


async def protect(request, call_next):
    setup_error = getattr(request.app.state, "setup_error", None)
    if setup_error and request.url.path.startswith(("/api/", "/docs", "/openapi.json", "/redoc")):
        return JSONResponse({"detail": setup_error}, status_code=503, headers={"Cache-Control": "no-store"})
    request.state.request_id = uuid.uuid4().hex
    expires.set(time.monotonic() + 50)
    workspace.set("")
    if request.url.path.startswith("/api/support/widget/"):
        from .support.routes import widget_cors
        response = await widget_cors(request, call_next)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Cache-Control"] = "no-store"
        return response
    protected = request.url.path.startswith(("/api/", "/docs", "/openapi.json", "/redoc"))
    if config.production() and protected and request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("origin")
        allowed = set(config.CORS_ORIGINS)
        allowed.add(str(request.base_url).rstrip("/"))
        if config.PUBLIC_URL:
            allowed.add(config.PUBLIC_URL)
        if origin and origin not in allowed:
            return JSONResponse({"detail": "Origin not allowed"}, status_code=403)
        if request.headers.get("sec-fetch-site") == "cross-site":
            return JSONResponse({"detail": "Cross-site writes are not allowed"}, status_code=403)
        if request.headers.get("content-length", "0").isdigit() and int(request.headers.get("content-length", "0")) > 1_000_000:
            return JSONResponse({"detail": "Request too large"}, status_code=413)
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Cache-Control"] = "no-store"
    return response
