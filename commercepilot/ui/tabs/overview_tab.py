"""Dashboard tab: the project at a glance plus the one-click workflow.

This tab is the composition of everything the agents have produced so far. It
also owns the "Run full workflow" action, which is the fastest way to see the
whole pipeline work end to end.
"""
from __future__ import annotations

import gradio as gr

from ...workflows import commerce_workflow as wf
from .. import downloads
from .. import formatting as fmt
from ..context import UIContext
from ..errors import friendly


def build(ctx: UIContext) -> dict[str, gr.components.Component]:
    """Create the dashboard components and wire its actions."""
    with gr.Tab("Dashboard"):
        gr.Markdown(
            "## Project overview\n"
            "Every number below comes from the project's stored data. "
            "Sample and simulated values stay labelled as such."
        )
        overview = gr.Markdown("Select or create a project to begin.")

        with gr.Row():
            run_btn = gr.Button("Run full workflow", variant="primary", scale=2)
            report_btn = gr.Button("Rebuild report", scale=1)
            download_btn = gr.Button("Download report", scale=1)
            mode = gr.Radio(
                choices=[("Sample data (fast)", "sample"), ("Sample + live web search", "both")],
                value="sample",
                label="Research mode",
                scale=1,
            )

        action_status = gr.Markdown()
        product = gr.Markdown("No product selected yet.")

        gr.Markdown("### Workflow")
        steps = gr.Dataframe(
            headers=fmt.WORKFLOW_HEADERS,
            value=[],
            interactive=False,
            wrap=True,
            label="Step status",
        )

        gr.Markdown("### Consolidated report")
        report = gr.Markdown("The report appears here after the workflow runs.")
        report_file = gr.File(label="Report download (JSON)", interactive=False, visible=False)

        # ---- callbacks --------------------------------------------------- #
        dashboard_outputs = [ctx.header_status, overview, steps, report, product]

        def on_run(project_id, research_mode):
            try:
                ctx.require(project_id)
                result = wf.run_full_workflow(
                    ctx.store, project_id, auto_select=True, mode=research_mode or "sample"
                )
                payload = ctx.dashboard(project_id)
                if result.get("error"):
                    error = result["error"]
                    note = f"⚠️ Stopped at **{error['step']}**: {error['message']}"
                else:
                    note = "✅ Workflow finished. All steps completed successfully."
                return (*payload, note)
            except Exception as exc:
                return (*ctx.dashboard(project_id), friendly(exc))

        def on_report(project_id):
            try:
                project = ctx.require(project_id)
                wf.step_report(ctx.store, project)
                return (*ctx.dashboard(project_id), "Report rebuilt from the latest data.")
            except Exception as exc:
                return (*ctx.dashboard(project_id), friendly(exc))

        def on_download(project_id):
            project = ctx.project(project_id)
            path = downloads.export_report(project)
            if not path:
                return gr.update(visible=False), "Run the workflow first — there is no report yet."
            return gr.update(value=path, visible=True), f"Saved `{path.split('/')[-1]}`."

        run_btn.click(
            on_run,
            inputs=[ctx.project_dd, mode],
            outputs=[*dashboard_outputs, action_status],
        )
        report_btn.click(
            on_report,
            inputs=[ctx.project_dd],
            outputs=[*dashboard_outputs, action_status],
        )
        download_btn.click(
            on_download,
            inputs=[ctx.project_dd],
            outputs=[report_file, action_status],
        )

    return {
        "overview": overview,
        "steps": steps,
        "report": report,
        "product": product,
        "action_status": action_status,
    }
