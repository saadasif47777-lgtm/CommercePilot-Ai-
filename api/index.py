"""Vercel serverless entry point for the CommercePilot AI backend.

One Vercel project serves both the React frontend (static files) and this
FastAPI app (rewritten from /api/* by vercel.json). Because the browser talks
to a single origin, no CORS configuration and no VITE_API_BASE_URL are needed.

SQLite lives on /tmp — the only writable directory in a Vercel function — so
project data is ephemeral and resets on cold starts or redeploys. That is an
accepted trade-off of the free serverless tier: the app's Example Project
button rebuilds the full demo state in one click.
"""

import os
import sys

# The repository root (one level above api/) must be importable so that
# "backend.main" resolves exactly as it does in local development.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Writable location inside the function sandbox; overridable via env.
os.environ.setdefault("DB_PATH", "/tmp/commercepilot.sqlite3")

from backend.main import app  # noqa: E402  (import after sys.path setup)
