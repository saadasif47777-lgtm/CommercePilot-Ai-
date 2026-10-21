"""Shared UI context.

All tabs are built by functions that receive one :class:`UIContext`. It carries
the project selector (the single source of truth for "which project am I
looking at") and provides the few helpers every tab needs. Keeping this in one
place means a tab never reaches into another tab's components.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import gradio as gr

from .. import ai
from ..runtime import get_store
from ..storage import ProjectStore
from . import formatting as fmt


@dataclass
class UIContext:
    # Components created by the shell and shared across tabs.
    project_dd: Optional[gr.Dropdown] = None
    header_status: Optional[gr.Markdown] = None
    # Dashboard components, registered by the dashboard tab so that actions in
    # other tabs can refresh the overview in the same event.
    overview_md: Optional[gr.Markdown] = None
    steps_df: Optional[gr.Dataframe] = None
    report_md: Optional[gr.Markdown] = None
    product_md: Optional[gr.Markdown] = None
    project_count: int = field(default=0, init=False)

    def bind_dashboard(self, components: dict) -> None:
        """Register the dashboard widgets created by the overview tab."""
        self.overview_md = components.get("overview")
        self.steps_df = components.get("steps")
        self.report_md = components.get("report")
        self.product_md = components.get("product")

    def dashboard_outputs(self) -> list:
        """Components to use as outputs when an action changes the project."""
        return [self.header_status, self.overview_md, self.steps_df, self.report_md, self.product_md]

    # ------------------------------------------------------------------ #
    # Store access
    # ------------------------------------------------------------------ #
    @property
    def store(self) -> ProjectStore:
        """Resolve the store per call so tests can swap it safely."""
        return get_store()

    def project(self, project_id: Optional[str]) -> Optional[dict]:
        """Return the project document, or None when nothing is selected."""
        if not project_id:
            return None
        return self.store.get(project_id)

    def require(self, project_id: Optional[str]) -> dict:
        """Return a project or raise a message the UI can display."""
        project = self.project(project_id)
        if not project:
            raise ValueError("Select a project first, or create one in the Projects tab.")
        return project

    def projects(self) -> list[dict]:
        return self.store.list()

    # ------------------------------------------------------------------ #
    # Project selector helpers
    # ------------------------------------------------------------------ #
    def choices(self) -> list[tuple[str, str]]:
        """Dropdown choices as (label, id), newest project first."""
        rows = self.projects()
        self.project_count = len(rows)
        return [
            (f"{row.get('name') or 'Untitled'} · {str(row.get('id'))[-4:]}", str(row["id"]))
            for row in rows
        ]

    def dropdown_update(self, selected: Optional[str] = None):
        """Refresh the selector, keeping ``selected`` if it still exists."""
        choices = self.choices()
        valid = {value for _, value in choices}
        value = selected if selected in valid else (choices[0][1] if choices else None)
        return gr.update(choices=choices, value=value)

    # ------------------------------------------------------------------ #
    # Dashboard payload
    # ------------------------------------------------------------------ #
    def dashboard(self, project_id: Optional[str]):
        """Return the five dashboard outputs for a project selection.

        Order is fixed and mirrored by every caller:
        header status, overview, workflow rows, report, selected product.
        """
        project = self.project(project_id)
        return (
            fmt.header_markdown(project, ai.mode()),
            fmt.overview_markdown(project),
            fmt.workflow_rows(project),
            fmt.report_markdown((project or {}).get("report")),
            fmt.selected_product_markdown(project),
        )
