"""CommercePilot AI — run the whole application.

    python app.py

Serves the Gradio interface at http://localhost:7860 and the JSON API under
/api on the same port. Configuration is read from environment variables (see
.env.example); no key is required to start the app.
"""
from __future__ import annotations

import logging

import uvicorn

from commercepilot import config
from commercepilot.webapp import app


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s %(name)s  %(message)s",
    )
    logging.getLogger("commercepilot").info(
        "Starting CommercePilot AI on %s:%s (AI mode: %s)",
        config.HOST,
        config.PORT,
        "llm" if config.LLM_API_KEY else "fallback",
    )
    uvicorn.run(
        app,
        host=config.HOST,
        port=config.PORT,
        log_level="info",
    )


if __name__ == "__main__":
    main()
