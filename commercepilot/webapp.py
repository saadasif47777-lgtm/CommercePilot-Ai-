"""The deployable application: JSON API and Gradio UI in one process.

Why one process?
  * One port, one health check, one log stream to watch.
  * The UI can call the orchestrator directly, so no internal HTTP round trips.
  * The API stays available for scripts and future integrations at ``/api``.

Gradio is mounted at ``/`` after the API routes, so ``/api/*`` takes priority
and every other path is served by the interface.
"""
from __future__ import annotations

import gradio as gr
from fastapi import FastAPI

from .api import app as api_app
from .ui import build_ui


def create_app() -> FastAPI:
    """Mount the interface onto the API application."""
    return gr.mount_gradio_app(api_app, build_ui(), path="/")


app = create_app()
