"""CommercePilot AI - an AI e-commerce workspace with a Python backend.

The Python package is organised in layers, each with a single responsibility:

    commercepilot.config      configuration and paths
    commercepilot.schemas     Pydantic models shared by every layer
    commercepilot.storage     SQLite persistence for projects
    commercepilot.runtime     one shared project store per process
    commercepilot.ai          LLM client: retries, JSON validation, budget guard
    commercepilot.tools       deterministic helpers (maths, web search)
    commercepilot.agents      the four domain agents
    commercepilot.workflows   orchestrator that chains the agents
    commercepilot.assistant   natural-language router over the orchestrator
    commercepilot.api         FastAPI JSON API consumed by the interface

The user interface is the React + TypeScript app in ``frontend/``; it talks to
this package over ``/api``. Entry point for the combined app: ``python app.py``.
"""

__version__ = "1.0.0"
__all__ = ["__version__"]
