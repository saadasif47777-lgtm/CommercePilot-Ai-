"""Google OIDC identity; one isolated merchant workspace per Google subject."""
import hashlib
from contextvars import ContextVar

from authlib.integrations.starlette_client import OAuth, OAuthError
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from . import config

workspace = ContextVar("workspace", default="")
router = APIRouter(prefix="/api/auth")
oauth = OAuth()
oauth.register("google", client_id=config.GOOGLE_CLIENT_ID, client_secret=config.GOOGLE_CLIENT_SECRET,
               server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
               client_kwargs={"scope": "openid email profile"})


@router.get("/session")
def session(request: Request):
    return {"required": config.AUTH_ENABLED, "authenticated": bool(request.session.get("subject")),
            "name": request.session.get("name", ""), "workspace_id": request.session.get("subject") or None}


@router.get("/login")
async def login(request: Request):
    if not config.AUTH_ENABLED or not config.GOOGLE_CLIENT_ID or not config.GOOGLE_CLIENT_SECRET:
        raise HTTPException(503, "Google sign-in is not configured yet.")
    return await oauth.google.authorize_redirect(request, config.PUBLIC_URL + "/api/auth/callback")


@router.get("/callback")
async def callback(request: Request):
    try:
        token = await oauth.google.authorize_access_token(request)
        user = token.get("userinfo") or {}
        if not user.get("sub") or user.get("email_verified") is not True:
            raise HTTPException(403, "A verified Google account is required.")
    except OAuthError as exc:
        raise HTTPException(401, "Sign-in could not be verified. Please try again.") from exc
    request.session.clear()
    request.session.update(subject=hashlib.sha256(("google:" + user["sub"]).encode()).hexdigest(),
                           name=str(user.get("name", ""))[:120])
    return RedirectResponse("/", status_code=303)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return {"signed_out": True}
