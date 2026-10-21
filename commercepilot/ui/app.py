"""Compose the Gradio interface.

This is the only module that knows about every tab. It owns the page header,
the active-project selector, and the rule that switching projects refreshes all
views from stored data (so a project always looks the same however you reach
it).
"""
from __future__ import annotations

import gradio as gr

from .. import ai
from ..runtime import get_store
from . import formatting as fmt
from .context import UIContext
from .tabs import (
    analytics_tab,
    assistant_tab,
    marketing_tab,
    overview_tab,
    projects_tab,
    research_tab,
    settings_tab,
    store_tab,
)
from .tabs.research_tab import product_choices
from .tabs.store_tab import preview_html
from .theme import CSS, theme

HEADER = """
<div id="cp-header">
  <h1>CommercePilot AI</h1>
  <p>One workspace for product research, storefront generation, campaign planning
  and the unit economics behind every decision.</p>
  <span class="cp-pill">Python · FastAPI · Gradio</span>
  <span class="cp-pill">Free-tier AI</span>
  <span class="cp-pill">Local SQLite storage</span>
  <span class="cp-pill">Nothing auto-published</span>
</div>
"""


def build_ui() -> gr.Blocks:
    """Build and return the complete interface (no server is started here)."""
    ctx = UIContext()
    get_store()  # create the database and tables before the first interaction

    initial = ctx.choices()
    with gr.Blocks(
        theme=theme(),
        css=CSS,
        title="CommercePilot AI",
        analytics_enabled=False,
    ) as demo:
        gr.HTML(HEADER)

        with gr.Row(equal_height=True):
            ctx.project_dd = gr.Dropdown(
                label="Active project",
                choices=initial,
                value=initial[0][1] if initial else None,
                scale=5,
                interactive=True,
            )
            refresh = gr.Button("Refresh", scale=1)

        ctx.header_status = gr.Markdown(fmt.header_markdown(None, ai.mode()))

        with gr.Tabs():
            dashboard = overview_tab.build(ctx)
            # Register the dashboard widgets before other tabs are built: their
            # actions refresh this view as part of the same event.
            ctx.bind_dashboard(dashboard)
            research = research_tab.build(ctx)
            store = store_tab.build(ctx)
            marketing = marketing_tab.build(ctx)
            analytics = analytics_tab.build(ctx)
            # The remaining tabs use the shared context only (no cross-tab outputs).
            assistant_tab.build(ctx)
            projects_tab.build(ctx)
            settings_tab.build(ctx)

        gr.Markdown(
            "<div class='cp-hint' style='text-align:center;padding:12px 0'>"
            "Sample data, template copy and simulated metrics are labelled wherever they appear. "
            "This build never publishes to an ad platform or a live shop."
            "</div>"
        )

        # ---- shared refresh behaviour ----------------------------------- #
        sync_outputs = [
            *ctx.dashboard_outputs(),
            research["summary"],
            research["table"],
            research["selector"],
            research["selected"],
            store["summary"],
            store["preview"],
            store["spec_json"],
            marketing["plan"],
            marketing["allocations"],
            marketing["creatives"],
            marketing["simulation"],
            analytics["result"],
            analytics["scenarios"],
        ]

        def on_project_selected(project_id):
            """Refresh every view from the stored project document."""
            project = ctx.project(project_id) or {}
            campaign = project.get("campaign")
            analysis = project.get("analysis")
            options = product_choices(project)
            selected_id = (project.get("selected_product") or {}).get("id")
            return (
                *ctx.dashboard(project_id),
                fmt.research_markdown(project.get("research")),
                fmt.product_rows((project.get("research") or {}).get("products") or []),
                gr.update(choices=options, value=selected_id),
                fmt.selected_product_markdown(project),
                fmt.store_markdown(project.get("store_spec")),
                preview_html(project_id),
                project.get("store_spec"),
                fmt.campaign_markdown(campaign),
                fmt.allocation_rows(campaign),
                fmt.creative_rows(campaign),
                fmt.simulation_markdown((campaign or {}).get("simulation")),
                fmt.analysis_markdown(analysis),
                fmt.scenario_rows(analysis),
            )

        ctx.project_dd.change(on_project_selected, inputs=[ctx.project_dd], outputs=sync_outputs)
        refresh.click(on_project_selected, inputs=[ctx.project_dd], outputs=sync_outputs)

    return demo


__all__ = ["HEADER", "build_ui"]
