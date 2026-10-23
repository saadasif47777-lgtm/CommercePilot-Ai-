"""Vercel serverless entry point for the CommercePilot AI backend.

One Vercel project serves both the React frontend (prebuilt into ``public/``)
and this FastAPI app (rewritten from ``/api/*`` by ``vercel.json``). Because the
browser talks to a single origin, no CORS configuration and no
``VITE_API_BASE_URL`` are needed in production.

Production requires DATABASE_URL pointing to persistent PostgreSQL. The /tmp
SQLite path below is used only by explicitly enabled local/demo operation;
production startup rejects it when DATABASE_URL is missing. Integration tokens
are encrypted in PostgreSQL using CREDENTIAL_ENCRYPTION_KEY.
"""

import os
import sys

# The repository root (one level above api/) must be importable so that
# "commercepilot.api" resolves exactly as it does in local development.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Writable location inside the function sandbox; overridable via env.
os.environ.setdefault("DB_PATH", "/tmp/commercepilot.sqlite3")

from commercepilot.api import app

# Vercel looks for a module-level ASGI application named ``app``.
__all__ = ["app"]
