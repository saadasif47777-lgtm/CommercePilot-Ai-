"""Single-client workspace authentication; deploy each client separately over TLS."""
import base64
import binascii
import secrets

from starlette.responses import JSONResponse

from . import config


async def protect(request, call_next):
    if config.production() and request.url.path != "/api/health":
        if len(config.ADMIN_PASSWORD) < 24:
            return JSONResponse({"detail": "Server authentication is not configured"}, status_code=503)
        username = password = ""
        header = request.headers.get("authorization", "")
        try:
            kind, value = header.split(" ", 1)
            if kind.lower() == "basic":
                username, password = base64.b64decode(value, validate=True).decode().split(":", 1)
        except (ValueError, UnicodeError, binascii.Error):
            pass
        valid_user = secrets.compare_digest(username.encode(), config.ADMIN_USERNAME.encode())
        valid_password = secrets.compare_digest(password.encode(), config.ADMIN_PASSWORD.encode())
        if not (valid_user and valid_password):
            return JSONResponse({"detail": "Authentication required"}, status_code=401,
                                headers={"WWW-Authenticate": 'Basic realm="CommercePilot", charset="UTF-8"'})
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin")
            allowed = set(config.CORS_ORIGINS)
            allowed.add(config.PUBLIC_URL or str(request.base_url).rstrip("/"))
            if origin and origin not in allowed:
                return JSONResponse({"detail": "Origin not allowed"}, status_code=403)
            if request.headers.get("sec-fetch-site") == "cross-site":
                return JSONResponse({"detail": "Cross-site writes are not allowed"}, status_code=403)
            if request.headers.get("content-length", "0").isdigit() and int(request.headers.get("content-length", "0")) > 1_000_000:
                return JSONResponse({"detail": "Request too large"}, status_code=413)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Cache-Control"] = "no-store"
    return response
