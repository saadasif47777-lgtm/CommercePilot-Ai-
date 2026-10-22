"""CommercePilot AI — one Python process serves the API and the built UI.

    python app.py                 # API + built React app at http://localhost:8000
    uvicorn commercepilot.api:app # API only (used with the Vite dev server)

The React/TypeScript interface lives in ``frontend/``. ``npm run build`` writes
it to ``frontend/dist``; when that directory exists this module mounts it and
falls back to ``index.html`` for client-side routes, so a single server can host
the whole product. During development the Vite server on :3000 proxies ``/api``
here instead, which gives hot reload without rebuilding.

Configuration is read from environment variables (see ``.env.example``); no key
is required to start the app.
"""
from __future__ import annotations

import logging

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from commercepilot import config
from commercepilot.api import app as api_app

# Built frontend (produced by `npm run build` inside frontend/).
FRONTEND_DIST = config.ROOT / "frontend" / "dist"


def create_app() -> FastAPI:
    """Return the API app, with the built frontend mounted when it is present.

    The API routes are registered first, so ``/api/*``, ``/docs`` and
    ``/openapi.json`` always win over the catch-all route below.
    """
    index = FRONTEND_DIST / "index.html"
    if not index.is_file():
        # No build yet: serve the API only. The UI is then served by Vite.
        return api_app

    assets = FRONTEND_DIST / "assets"
    if assets.is_dir():
        api_app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @api_app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str) -> FileResponse:
        """Serve static files, or index.html for client-side routes."""
        if path.startswith(("api/", "docs", "openapi.json")):
            # Unknown API path: answer with JSON, not with the UI shell.
            raise HTTPException(status_code=404, detail="Not found")
        candidate = (FRONTEND_DIST / path).resolve()
        if candidate.is_file() and FRONTEND_DIST in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(index)  # React Router handles the rest

    return api_app


app = create_app()


def main() -> None:
    """Run the development/production server."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s %(name)s  %(message)s",
    )
    logging.getLogger("commercepilot").info(
        "Starting CommercePilot AI on %s:%s (AI mode: %s, UI: %s)",
        config.HOST,
        config.PORT,
        "llm" if config.LLM_API_KEY else "fallback",
        "frontend/dist" if (FRONTEND_DIST / "index.html").is_file() else "not built",
    )
    uvicorn.run(app, host=config.HOST, port=config.PORT, log_level="info")


if __name__ == "__main__":
    main()
