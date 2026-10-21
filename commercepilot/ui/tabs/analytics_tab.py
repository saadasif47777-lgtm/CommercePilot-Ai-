"""Business Analytics tab: unit economics, scenarios and measured KPIs.

Everything is calculated from numbers that exist. When a price, cost or
measured metric is missing the result says so instead of filling the gap with an
estimate.
"""
from __future__ import annotations

import gradio as gr

from ...schemas import (
    AnalyzeRequest,
    CampaignActuals,
    CostOverheadInputs,
    ScenarioAssumptions,
)
from ...workflows import commerce_workflow as wf
from .. import downloads
from .. import formatting as fmt
from ..context import UIContext
from ..errors import friendly


def _overheads(shipping, packaging, fees, fixed) -> CostOverheadInputs:
    return CostOverheadInputs(
        shipping_cost_per_unit=shipping,
        packaging_cost_per_unit=packaging,
        transaction_fee_per_unit=fees,
        fixed_costs=fixed,
    )


def _actuals(spend, clicks, conversions, customers, revenue) -> CampaignActuals | None:
    if all(value in (None, "") for value in (spend, clicks, conversions, customers, revenue)):
        return None
    return CampaignActuals(
        ad_spend=spend,
        clicks=clicks,
        conversions=conversions,
        customers=customers,
        revenue=revenue,
    )


def _scenario(clicks, cvr, cpc) -> ScenarioAssumptions | None:
    if all(value in (None, "") for value in (clicks, cvr, cpc)):
        return None
    return ScenarioAssumptions(
        clicks=clicks if clicks not in (None, "") else 1000,
        conversion_rate_pct=cvr if cvr not in (None, "") else 2.0,
        cpc=cpc if cpc not in (None, "") else 50,
    )


def build(ctx: UIContext) -> dict[str, gr.components.Component]:
    """Create the analysis inputs, results and export."""
    with gr.Tab("Business Analytics"):
        gr.Markdown(
            "## Know the numbers\n"
            "Unit economics, break-even ROAS and scenario projections for the selected product. "
            "Add real campaign results once you have them — measured data replaces assumptions."
        )

        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("### Per-unit costs (optional)")
                shipping = gr.Number(label="Shipping per unit", value=None, minimum=0)
                packaging = gr.Number(label="Packaging per unit", value=None, minimum=0)
                fees = gr.Number(label="Payment fee per unit", value=None, minimum=0)
                fixed = gr.Number(label="Fixed monthly costs", value=None, minimum=0)

                with gr.Accordion("Measured campaign results (optional)", open=False):
                    spend = gr.Number(label="Ad spend", value=None, minimum=0)
                    clicks = gr.Number(label="Clicks", value=None, minimum=0)
                    conversions = gr.Number(label="Conversions", value=None, minimum=0)
                    customers = gr.Number(label="New customers", value=None, minimum=0)
                    revenue = gr.Number(label="Revenue", value=None, minimum=0)

                with gr.Accordion("Scenario assumptions (optional)", open=False):
                    s_clicks = gr.Number(label="Clicks", value=None, minimum=0)
                    s_cvr = gr.Number(label="Conversion rate %", value=None, minimum=0)
                    s_cpc = gr.Number(label="Cost per click", value=None, minimum=0)

                analyze = gr.Button("Run analysis", variant="primary")
                download = gr.Button("Download analysis (JSON)")
                analysis_file = gr.File(label="Analysis file", interactive=False, visible=False)

            with gr.Column(scale=2):
                action_status = gr.Markdown()
                result = gr.Markdown("No analysis has been run yet.")
                gr.Markdown("### Scenario projections")
                scenarios = gr.Dataframe(
                    headers=fmt.SCENARIO_HEADERS, value=[], interactive=False, wrap=True
                )

        # ---- callbacks --------------------------------------------------- #
        def on_analyze(project_id, ship, pack, fee, fixed_cost,
                       ad_spend, click_count, conv_count, customer_count, rev,
                       sc_clicks, sc_cvr, sc_cpc):
            try:
                project = ctx.require(project_id)
                request = AnalyzeRequest(
                    overheads=_overheads(ship, pack, fee, fixed_cost),
                    actuals=_actuals(ad_spend, click_count, conv_count, customer_count, rev),
                    base=_scenario(sc_clicks, sc_cvr, sc_cpc),
                )
                analysis = wf.step_analyze(ctx.store, project, request)
                return (
                    *ctx.dashboard(project_id),
                    "Analysis complete.",
                    fmt.analysis_markdown(analysis),
                    fmt.scenario_rows(analysis),
                )
            except Exception as exc:
                stored = (ctx.project(project_id) or {}).get("analysis")
                return (
                    *ctx.dashboard(project_id),
                    friendly(exc),
                    fmt.analysis_markdown(stored),
                    fmt.scenario_rows(stored),
                )

        def on_download(project_id):
            path = downloads.export_analysis(ctx.project(project_id))
            if not path:
                return gr.update(visible=False), "Run the analysis first."
            return gr.update(value=path, visible=True), "Analysis JSON ready."

        analyze.click(
            on_analyze,
            inputs=[ctx.project_dd, shipping, packaging, fees, fixed,
                    spend, clicks, conversions, customers, revenue,
                    s_clicks, s_cvr, s_cpc],
            outputs=[*ctx.dashboard_outputs(), action_status, result, scenarios],
        )
        download.click(on_download, inputs=[ctx.project_dd], outputs=[analysis_file, action_status])

    return {"result": result, "scenarios": scenarios}
