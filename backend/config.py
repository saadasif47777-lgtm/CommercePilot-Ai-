"""Environment configuration.

Credentials are read ONLY from environment variables (or a git-ignored .env
file). Nothing secret is ever returned to the frontend or written to logs.
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = Path(__file__).resolve().parent
SECRETS_DIR = BACKEND_DIR / ".secrets"  # git-ignored, for optional integration credentials


def _load_dotenv() -> None:
    """Minimal .env loader (no external dependency)."""
    path = ROOT / ".env"
    if not path.exists():
        return
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip().strip('"').strip("'")
            if key:
                os.environ.setdefault(key, value)
    except OSError:
        pass


_load_dotenv()


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default) or default


def env_bool(name: str, default: bool = False) -> bool:
    return env(name, "1" if default else "0").strip().lower() in {"1", "true", "yes", "on"}


# --- Storage -------------------------------------------------------------- #
# SQLite location. Override with DB_PATH to use a mounted persistent disk on a
# hosting platform (the default is next to the code, which is ephemeral there).
DB_PATH = Path(env("DB_PATH", str(BACKEND_DIR / "commercepilot.sqlite3"))).expanduser()
if DB_PATH.parent and not DB_PATH.parent.exists():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# --- AI provider (server-side only) -------------------------------------- #
# Any OpenAI-compatible endpoint works. Groq is the default: strict JSON output
# on its free tier and no training on inference data by default.
LLM_PROVIDER = env("LLM_PROVIDER", "groq")
LLM_API_KEY = env("LLM_API_KEY") or env("OPENAI_API_KEY")
LLM_BASE_URL = env("LLM_BASE_URL") or env("OPENAI_BASE_URL")
LLM_MODEL = env("LLM_MODEL", env("OPENAI_MODEL", "openai/gpt-oss-20b"))
# Stronger model, used ONLY for tasks where copy quality matters (storefront and
# ad copy). Empty means "use the cheap model for everything".
LLM_MODEL_STRONG = env("LLM_MODEL_STRONG", "")
LLM_TIMEOUT = float(env("LLM_TIMEOUT", "20"))
LLM_MAX_RETRIES = int(env("LLM_MAX_RETRIES", "2"))
LLM_MAX_OUTPUT_TOKENS = int(env("LLM_MAX_OUTPUT_TOKENS", "800"))
# Hard monthly spend cap (USD, estimated from token usage). 0 disables the cap.
AI_MONTHLY_CAP_USD = float(env("AI_MONTHLY_CAP_USD", "25"))
# Warn (log + usage summary flag) once this percentage of the cap is used.
AI_BUDGET_WARN_PCT = float(env("AI_BUDGET_WARN_PCT", "80"))

# Legacy aliases kept so existing references keep working.
OPENAI_API_KEY = LLM_API_KEY
OPENAI_MODEL = LLM_MODEL

# --- Search --------------------------------------------------------------- #
SERPER_API_KEY = env("SERPER_API_KEY")
WEB_SEARCH_TIMEOUT = float(env("WEB_SEARCH_TIMEOUT", "8"))

# --- Meta / Shopify (server-side only, never echoed to clients) ----------- #
META_ACCESS_TOKEN = env("META_ACCESS_TOKEN")
META_AD_ACCOUNT_ID = env("META_AD_ACCOUNT_ID")
META_APP_ID = env("META_APP_ID")
SHOPIFY_SHOP_DOMAIN = env("SHOPIFY_SHOP_DOMAIN")
SHOPIFY_ADMIN_TOKEN = env("SHOPIFY_ADMIN_TOKEN")

# --- Server --------------------------------------------------------------- #
CORS_ORIGINS = [
    o.strip()
    for o in env(
        "CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
    ).split(",")
    if o.strip()
]


def integration_secrets_path(provider: str) -> Path:
    """Path for credentials saved from the Settings UI (git-ignored)."""
    SECRETS_DIR.mkdir(parents=True, exist_ok=True)
    return SECRETS_DIR / f"{provider}.json"
