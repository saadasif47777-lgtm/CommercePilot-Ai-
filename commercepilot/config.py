"""Central configuration, loaded once at import time.

Everything the application can be tuned with lives here instead of being
scattered through the code, so there is one obvious place to look.

Rules:
  * Secrets come from environment variables only (optionally supplied through a
    git-ignored ``.env`` file). They are never written to logs or returned to
    the browser.
  * Every optional integration degrades gracefully when its variables are
    missing: the app still runs and clearly labels the fallback behaviour.
"""
from __future__ import annotations

import os
from pathlib import Path

# commercepilot/config.py -> parents[1] is the repository root.
ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = Path(__file__).resolve().parent


def _load_dotenv() -> None:
    """Load a ``.env`` file without adding a python-dotenv dependency.

    Existing environment variables always win, so platform dashboards (Render,
    Docker, GitHub Actions) can override the local file.
    """
    for candidate in (ROOT / ".env", PACKAGE_DIR / ".env"):
        if not candidate.exists():
            continue
        try:
            lines = candidate.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key:
                os.environ.setdefault(key, value)


_load_dotenv()


def env(name: str, default: str = "") -> str:
    """Read an environment variable, treating blank values as unset."""
    return os.environ.get(name, default) or default


def env_bool(name: str, default: bool = False) -> bool:
    """Read a boolean environment variable (1/true/yes/on are all truthy)."""
    return env(name, "1" if default else "0").strip().lower() in {"1", "true", "yes", "on"}


# --------------------------------------------------------------------------- #
# Filesystem layout
# --------------------------------------------------------------------------- #
DATA_DIR = Path(env("DATA_DIR", str(ROOT / "data"))).expanduser()
# Credentials saved from the Settings tab (git-ignored, never served to clients).
SECRETS_DIR = Path(env("SECRETS_DIR", str(ROOT / ".secrets"))).expanduser()

# One SQLite file holds projects and the AI usage log. Set DB_PATH to a mounted
# disk on a host whose filesystem is ephemeral (Render free tier, containers).
DB_PATH = Path(env("DB_PATH", str(DATA_DIR / "commercepilot.sqlite3"))).expanduser()
DATABASE_URL = env("DATABASE_URL")
CREDENTIAL_ENCRYPTION_KEY = env("CREDENTIAL_ENCRYPTION_KEY")

# --------------------------------------------------------------------------- #
# AI provider (server-side only)
# --------------------------------------------------------------------------- #
# Any OpenAI-compatible endpoint works. Groq is the default because its free
# tier supports strict JSON output and does not train on inference data.
LLM_PROVIDER = env("LLM_PROVIDER", "groq")
LLM_API_KEY = env("LLM_API_KEY") or env("OPENAI_API_KEY")
LLM_BASE_URL = env("LLM_BASE_URL") or env("OPENAI_BASE_URL")
LLM_MODEL = env("LLM_MODEL", env("OPENAI_MODEL", "openai/gpt-oss-20b"))
# Optional stronger model, used ONLY for storefront and ad copy. Blank keeps the
# cheap model for every task, which is the default cost configuration.
LLM_MODEL_STRONG = env("LLM_MODEL_STRONG", "")
LLM_TIMEOUT = float(env("LLM_TIMEOUT", "20"))
LLM_MAX_RETRIES = int(env("LLM_MAX_RETRIES", "2"))
LLM_MAX_OUTPUT_TOKENS = int(env("LLM_MAX_OUTPUT_TOKENS", "800"))
# Hard monthly spend cap in USD (estimated from token counts). 0 disables it.
AI_MONTHLY_CAP_USD = float(env("AI_MONTHLY_CAP_USD", "25"))
# Warn (log line + usage summary flag) once this share of the cap is used.
AI_BUDGET_WARN_PCT = float(env("AI_BUDGET_WARN_PCT", "80"))

# --------------------------------------------------------------------------- #
# Web search (Product Hunter "live" mode)
# --------------------------------------------------------------------------- #
SERPER_API_KEY = env("SERPER_API_KEY")
WEB_SEARCH_TIMEOUT = float(env("WEB_SEARCH_TIMEOUT", "8"))

# --------------------------------------------------------------------------- #
# Optional integrations (server-side only; never echoed to the browser)
# --------------------------------------------------------------------------- #
META_ACCESS_TOKEN = env("META_ACCESS_TOKEN")
META_AD_ACCOUNT_ID = env("META_AD_ACCOUNT_ID")
META_APP_ID = env("META_APP_ID")
META_APP_SECRET = env("META_APP_SECRET")
SHOPIFY_SHOP_DOMAIN = env("SHOPIFY_SHOP_DOMAIN")
SHOPIFY_ADMIN_TOKEN = env("SHOPIFY_ADMIN_TOKEN")

# --------------------------------------------------------------------------- #
# Server
# --------------------------------------------------------------------------- #
HOST = env("HOST", "0.0.0.0")
PORT = int(env("PORT", env("APP_PORT", "8000")))
# The Vite dev server runs on :3000 and proxies /api to this server, so CORS is
# only needed when the API is used directly from another origin.
CORS_ORIGINS = [
    origin.strip()
    for origin in env("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
    if origin.strip()
]
# Public base URL, used when the app links back to itself (optional).
PUBLIC_URL = env("PUBLIC_URL", "").rstrip("/")


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def integration_secrets_path(provider: str) -> Path:
    """Path of the git-ignored JSON file holding credentials for ``provider``."""
    SECRETS_DIR.mkdir(parents=True, exist_ok=True)
    return SECRETS_DIR / f"{provider}.json"

# Production is the default. Demo data requires an explicit local opt-in.
APP_MODE = env("APP_MODE", "production")
SHOPIFY_API_VERSION = env("SHOPIFY_API_VERSION", "2026-10")
META_API_VERSION = env("META_API_VERSION", "v26.0")


def production() -> bool:
    return APP_MODE == "production"


def validate_runtime() -> None:
    if APP_MODE not in {"production", "demo"}:
        raise RuntimeError("APP_MODE must be production or demo")
    if not production():
        return
    if not LLM_API_KEY or not LLM_MODEL:
        raise RuntimeError("Production requires LLM_API_KEY and LLM_MODEL")
    if DATABASE_URL and not DATABASE_URL.startswith(("postgres://", "postgresql://")):
        raise RuntimeError("DATABASE_URL must be a PostgreSQL connection URL")
    if not DATABASE_URL and (env("VERCEL") or str(DB_PATH).startswith("/tmp/")):
        raise RuntimeError("Production requires a persistent disk; ephemeral serverless SQLite is unsupported")
    if "*" in CORS_ORIGINS:
        raise RuntimeError("Production CORS_ORIGINS must contain explicit origins")
