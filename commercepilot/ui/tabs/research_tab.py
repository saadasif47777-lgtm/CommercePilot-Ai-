"""Product Hunter tab: discover, rank and choose products.

Research can run on the local sample catalogue, on live web search, or both.
Live results carry their source URLs; anything that cannot be established from
evidence is shown as unknown rather than estimated.
"""
from __future__ import annotations

import gradio as gr

from ...schemas import ManualProductInput, ResearchRequest
from ...workflows import commerce_workflow as wf
from .. import formatting as fmt
from ..context import UIContext
from ..errors import friendly


def product_choices(project: dict) -> list[tuple[str, str]]:
    """Selector options: research results first, then saved products."""
    options: list[tuple[str, str]] = []
    seen: set[str] = set()
    groups = [
        ("research", (project.get("research") or {}).get("products") or []),
        ("saved", project.get("saved_products") or []),
    ]
    for group, rows in groups:
        for product in rows:
            product_id = product.get("id")
            if not product_id or product_id in seen:
                continue
            seen.add(product_id)
            score = f" · score {product['score']:.1f}" if product.get("score") else ""
            tag = "" if group == "research" else " (saved)"
            options.append((f"{product.get('title')}{score}{tag}", product_id))
    return options


def build(ctx: UIContext) -> dict[str, gr.components.Component]:
    """Create the research form, result table and curation actions."""
    with gr.Tab("Product Hunter"):
        gr.Markdown(
            "## Find a product to sell\n"
            "Rank candidates against your audience, budget and price range. "
            "Scoring is a transparent weighted heuristic — not a market prediction."
        )

        with gr.Row():
            with gr.Column(scale=2):
                niche = gr.Textbox(label="Niche or product idea", placeholder="vitamin C serum")
                audience = gr.Textbox(label="Target audience", placeholder="women 18–34 in urban Pakistan")
                with gr.Row():
                    market = gr.Textbox(label="Market", value="Pakistan")
                    budget = gr.Number(label="Budget", value=30000, minimum=0)
                with gr.Row():
                    price_min = gr.Number(label="Min price", value=None, minimum=0)
                    price_max = gr.Number(label="Max price", value=None, minimum=0)
            with gr.Column(scale=1):
                mode = gr.Radio(
                    choices=[
                        ("Sample + live", "both"),
                        ("Sample only", "sample"),
                        ("Live only", "live"),
                    ],
                    value="both",
                    label="Research mode",
                )
                limit = gr.Slider(4, 30, value=10, step=1, label="Candidates to return")
                prefill = gr.Button("Use project brief")
                run = gr.Button("Run research", variant="primary")

        action_status = gr.Markdown()
        summary = gr.Markdown("No research has been run for this project yet.")
        table = gr.Dataframe(
            headers=fmt.PRODUCT_HEADERS,
            value=[],
            interactive=False,
            wrap=True,
            label="Ranked candidates",
        )

        with gr.Row():
            with gr.Column(scale=2):
                selector = gr.Dropdown(label="Candidate", choices=[], interactive=True)
            with gr.Column(scale=1):
                select_btn = gr.Button("Select for project", variant="primary")
                with gr.Row():
                    save_btn = gr.Button("Save")
                    reject_btn = gr.Button("Reject")

        selected = gr.Markdown("No product selected yet.")

        with gr.Accordion("Enter a product manually (no research needed)", open=False):
            gr.Markdown(
                "Use this when live research is unavailable or you already know your product. "
                "Your figures are treated as **your input**, never as verified market data."
            )
            with gr.Row():
                manual_title = gr.Textbox(label="Product title", placeholder="Hydrating night cream")
                manual_price = gr.Number(label="Selling price", value=None, minimum=0)
                manual_cost = gr.Number(label="Unit cost", value=None, minimum=0)
            with gr.Row():
                manual_currency = gr.Textbox(label="Currency", value="PKR")
                manual_competition = gr.Dropdown(
                    label="Competition", choices=["unknown", "low", "medium", "high"], value="unknown"
                )
                manual_url = gr.Textbox(label="Source URL (optional)")
            manual_description = gr.Textbox(label="Description", lines=2)
            manual_audience = gr.Textbox(label="Target audience", lines=1)
            manual_btn = gr.Button("Save and select this product")
            manual_status = gr.Markdown()

        # ---- callbacks --------------------------------------------------- #
        def on_prefill(project_id):
            try:
                brief = ctx.require(project_id).get("brief") or {}
                return (
                    brief.get("niche") or brief.get("industry") or "",
                    brief.get("target_audience") or "",
                    brief.get("target_market") or "Pakistan",
                    brief.get("budget") or 0,
                    brief.get("preferred_price_min"),
                    brief.get("preferred_price_max"),
                    "Loaded from the project brief.",
                )
            except Exception as exc:
                return "", "", "Pakistan", 0, None, None, friendly(exc)

        def on_run(project_id, niche_value, market_value, audience_value, budget_value,
                   low, high, mode_value, limit_value):
            try:
                project = ctx.require(project_id)
                request = ResearchRequest(
                    niche=(niche_value or "").strip() or None,
                    market=(market_value or "").strip() or None,
                    audience=(audience_value or "").strip() or None,
                    budget=budget_value or None,
                    price_min=low,
                    price_max=high,
                    mode=mode_value,
                    limit=int(limit_value or 10),
                )
                result = wf.step_research(ctx.store, project, request)
                refreshed = ctx.project(project_id) or {}
                choices = product_choices(refreshed)
                note = f"Ranked {len(result.products)} candidates."
                if result.contains_live_results:
                    note += " Live web results are included with their source domains."
                return (
                    note,
                    fmt.research_markdown(result.model_dump()),
                    fmt.product_rows([p.model_dump() for p in result.products]),
                    gr.update(choices=choices, value=choices[0][1] if choices else None),
                )
            except Exception as exc:
                return friendly(exc), gr.update(), gr.update(), gr.update()

        def on_select(project_id, product_id):
            try:
                project = ctx.require(project_id)
                if not product_id:
                    raise ValueError("Choose a candidate from the list first.")
                selected_product = wf.step_select_product(ctx.store, project, product_id, auto_select=False)
                refreshed = ctx.project(project_id)
                return (
                    *ctx.dashboard(project_id),
                    f"Selected **{selected_product.title}** for this project.",
                    fmt.selected_product_markdown(refreshed),
                )
            except Exception as exc:
                return (
                    *ctx.dashboard(project_id),
                    friendly(exc),
                    fmt.selected_product_markdown(ctx.project(project_id)),
                )

        def on_save(project_id, product_id):
            try:
                project = ctx.require(project_id)
                if not product_id:
                    raise ValueError("Choose a candidate first.")
                wf.step_save_product(ctx.store, project, product_id=product_id)
                return "Saved to this project's shortlist."
            except Exception as exc:
                return friendly(exc)

        def on_reject(project_id, product_id):
            try:
                project = ctx.require(project_id)
                if not product_id:
                    raise ValueError("Choose a candidate first.")
                wf.step_reject_product(ctx.store, project, product_id)
                refreshed = ctx.project(project_id) or {}
                choices = product_choices(refreshed)
                return (
                    "Rejected — it will not be auto-selected again.",
                    gr.update(choices=choices, value=choices[0][1] if choices else None),
                )
            except Exception as exc:
                return friendly(exc), gr.update()

        def on_manual(project_id, title, price, cost, currency, competition, url, description, audience_value):
            try:
                project = ctx.require(project_id)
                payload = ManualProductInput(
                    title=(title or "").strip(),
                    observed_price=price,
                    observed_cost=cost,
                    currency=(currency or "PKR").strip() or "PKR",
                    competition=competition or "unknown",
                    source_url=(url or "").strip() or None,
                    description=(description or "").strip(),
                    target_audience=(audience_value or "").strip() or None,
                )
                wf.step_manual_product(ctx.store, project, payload)
                refreshed = ctx.project(project_id) or {}
                choices = product_choices(refreshed)
                return (
                    *ctx.dashboard(project_id),
                    f"Saved and selected **{payload.title}** (your input).",
                    gr.update(choices=choices, value=(refreshed.get("selected_product") or {}).get("id")),
                    fmt.selected_product_markdown(refreshed),
                )
            except Exception as exc:
                return (
                    *ctx.dashboard(project_id),
                    friendly(exc),
                    gr.update(),
                    fmt.selected_product_markdown(ctx.project(project_id)),
                )

        prefill.click(
            on_prefill,
            inputs=[ctx.project_dd],
            outputs=[niche, audience, market, budget, price_min, price_max, action_status],
        )
        run.click(
            on_run,
            inputs=[ctx.project_dd, niche, market, audience, budget, price_min, price_max, mode, limit],
            outputs=[action_status, summary, table, selector],
        )
        select_btn.click(
            on_select,
            inputs=[ctx.project_dd, selector],
            outputs=[*ctx.dashboard_outputs(), action_status, selected],
        )
        save_btn.click(on_save, inputs=[ctx.project_dd, selector], outputs=[action_status])
        reject_btn.click(
            on_reject,
            inputs=[ctx.project_dd, selector],
            outputs=[action_status, selector],
        )
        manual_btn.click(
            on_manual,
            inputs=[
                ctx.project_dd, manual_title, manual_price, manual_cost, manual_currency,
                manual_competition, manual_url, manual_description, manual_audience,
            ],
            outputs=[*ctx.dashboard_outputs(), manual_status, selector, selected],
        )

    return {
        "selector": selector,
        "summary": summary,
        "table": table,
        "selected": selected,
    }
