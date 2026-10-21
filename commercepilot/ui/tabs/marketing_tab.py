"""Marketing Studio tab: budget allocation, creatives and a labelled simulation.

The campaign is always a local draft. Meta is not connected, nothing is
published, and the simulation is arithmetic on stated assumptions rather than a
promise of performance.
"""
from __future__ import annotations

import gradio as gr

from ...schemas import CampaignRequest
from ...workflows import commerce_workflow as wf
from .. import downloads
from .. import formatting as fmt
from ..context import UIContext
from ..errors import friendly


def build(ctx: UIContext) -> dict[str, gr.components.Component]:
    """Create the campaign planner and its result views."""
    with gr.Tab("Marketing Studio"):
        gr.Markdown(
            "## Draft a campaign\n"
            "A plan you can actually run: budget split, audience hypotheses, creative concepts, "
            "KPIs and a testing schedule. **Nothing is published to Meta.**"
        )

        with gr.Row():
            with gr.Column(scale=1):
                objective = gr.Dropdown(
                    label="Objective",
                    choices=[("Sales", "sales"), ("Traffic", "traffic"), ("Leads", "leads"),
                             ("Retargeting", "retargeting")],
                    value="sales",
                )
                budget = gr.Number(label="Campaign budget", value=None, minimum=0,
                                   info="Leave empty to use the project brief budget.")
                duration = gr.Slider(3, 90, value=14, step=1, label="Duration (days)")
                generate = gr.Button("Draft campaign", variant="primary")
                simulate = gr.Button("Run demo simulation")
                download = gr.Button("Download draft (JSON)")
                campaign_file = gr.File(label="Campaign file", interactive=False, visible=False)
                action_status = gr.Markdown()

            with gr.Column(scale=2):
                plan = gr.Markdown("No campaign drafted yet.")
                gr.Markdown("### Budget allocation")
                allocations = gr.Dataframe(
                    headers=fmt.ALLOCATION_HEADERS, value=[], interactive=False, wrap=True
                )
                gr.Markdown("### Creative concepts")
                creatives = gr.Dataframe(
                    headers=fmt.CREATIVE_HEADERS, value=[], interactive=False, wrap=True
                )

        gr.Markdown("### Simulated performance")
        simulation = gr.Markdown(
            "_The simulation applies the stated CPC and conversion-rate assumptions to your allocation. "
            "It is arithmetic on assumptions, not measured ad performance._"
        )

        # ---- callbacks --------------------------------------------------- #
        def on_generate(project_id, objective_value, budget_value, duration_value):
            try:
                project = ctx.require(project_id)
                brief_budget = (project.get("brief") or {}).get("budget") or None
                request = CampaignRequest(
                    objective=objective_value or "sales",
                    budget=budget_value if budget_value not in (None, "") else brief_budget,
                    duration_days=int(duration_value or 14),
                )
                campaign = wf.step_generate_campaign(ctx.store, project, request)
                data = campaign.model_dump()
                note = (
                    f"Drafted a **{data['objective']}** campaign with {len(data['creatives'])} creatives. "
                    "Allocation valid." if data["allocation_valid"]
                    else f"Drafted a **{data['objective']}** campaign, but the allocation needs attention."
                )
                return (
                    *ctx.dashboard(project_id),
                    note,
                    fmt.campaign_markdown(data),
                    fmt.allocation_rows(data),
                    fmt.creative_rows(data),
                )
            except Exception as exc:
                campaign = (ctx.project(project_id) or {}).get("campaign")
                return (
                    *ctx.dashboard(project_id),
                    friendly(exc),
                    fmt.campaign_markdown(campaign),
                    fmt.allocation_rows(campaign),
                    fmt.creative_rows(campaign),
                )

        def on_simulate(project_id):
            try:
                project = ctx.require(project_id)
                if not project.get("campaign"):
                    raise ValueError("Draft a campaign first — there is nothing to simulate yet.")
                result = wf.step_simulate_campaign(ctx.store, project)
                return fmt.simulation_markdown(result)
            except Exception as exc:
                return friendly(exc)

        def on_download(project_id):
            path = downloads.export_campaign(ctx.project(project_id))
            if not path:
                return gr.update(visible=False), "Draft a campaign first."
            return gr.update(value=path, visible=True), "Campaign JSON ready."

        generate.click(
            on_generate,
            inputs=[ctx.project_dd, objective, budget, duration],
            outputs=[*ctx.dashboard_outputs(), action_status, plan, allocations, creatives],
        )
        simulate.click(on_simulate, inputs=[ctx.project_dd], outputs=[simulation])
        download.click(on_download, inputs=[ctx.project_dd], outputs=[campaign_file, action_status])

    return {"plan": plan, "allocations": allocations, "creatives": creatives, "simulation": simulation}
