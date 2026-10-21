"""CommercePilot AI - an AI e-commerce workspace built entirely in Python.

The package is organised in layers, each with a single responsibility:

    commercepilot.config      configuration and paths
    commercepilot.schemas     Pydantic models shared by every layer
    commercepilot.storage     SQLite persistence for projects
    commercepilot.ai          LLM client: retries, JSON validation, budget guard
    commercepilot.tools       deterministic helpers (maths, web search)
    commercepilot.agents      the four domain agents
    commercepilot.workflows   orchestrator that chains the agents
    commercepilot.assistant   natural-language router over the orchestrator
    commercepilot.api         FastAPI JSON API
    commercepilot.ui          Gradio interface (the human-facing app)
    commercepilot.webapp      mounts the API and the UI in one process

Entry point: ``python app.py``.
"""

__version__ = "1.0.0"
__all__ = ["__version__"]
