"""Projects tab: the business brief that every agent reads from.

A project is the unit of work: one brief, one selected product, one storefront,
one campaign and one analysis. Editing the brief invalidates the downstream
steps on purpose, so stale results can never look current.
"""
from __future__ import annotations

import gradio as gr

from ...schemas import BusinessBrief, ProjectCreate
from ...workflows import commerce_workflow as wf
from .. import formatting as fmt
from ..context import UIContext
from ..errors import friendly

BRIEF_FIELDS = [
    "business_name", "industry", "niche", "target_market", "target_audience",
    "currency", "budget", "brand_personality", "preferred_price_min",
    "preferred_price_max", "constraints", "notes",
]


def _brief_from_form(values: list) -> BusinessBrief:
    """Build a validated brief from the form values (in BRIEF_FIELDS order)."""
    # strict=True: the form and this tuple must stay in sync.
    data = dict(zip(BRIEF_FIELDS, values, strict=True))
    constraints = data.get("constraints") or ""
    if isinstance(constraints, str):
        constraints = [line.strip() for line in constraints.splitlines() if line.strip()]
    return BusinessBrief(
        business_name=(data.get("business_name") or "").strip(),
        industry=(data.get("industry") or "").strip(),
        niche=(data.get("niche") or "").strip(),
        target_market=(data.get("target_market") or "Pakistan").strip(),
        target_audience=(data.get("target_audience") or "").strip(),
        currency=(data.get("currency") or "PKR").strip(),
        budget=float(data.get("budget") or 0),
        brand_personality=(data.get("brand_personality") or "").strip(),
        preferred_price_min=data.get("preferred_price_min") or None,
        preferred_price_max=data.get("preferred_price_max") or None,
        constraints=constraints,
        notes=(data.get("notes") or "").strip(),
    )


def build(ctx: UIContext) -> dict[str, gr.components.Component]:
    """Create the project list, brief editor and lifecycle buttons."""
    with gr.Tab("Projects"):
        gr.Markdown(
            "## Projects\n"
            "Start with the example to see a complete pipeline, or enter your own brief. "
            "Changing the brief resets downstream steps so nothing stale stays green."
        )

        with gr.Row():
            refresh = gr.Button("Refresh list")
            create_example = gr.Button("Create example project", variant="primary")

        project_table = gr.Dataframe(
            headers=fmt.PROJECT_HEADERS, value=[], interactive=False, wrap=True, label="All projects"
        )
        list_status = gr.Markdown()

        gr.Markdown("### Edit the selected project's brief")
        with gr.Row():
            business_name = gr.Textbox(label="Business name")
            industry = gr.Textbox(label="Industry")
            niche = gr.Textbox(label="Niche / product focus")
        with gr.Row():
            target_market = gr.Textbox(label="Target market", value="Pakistan")
            currency = gr.Textbox(label="Currency", value="PKR")
            budget = gr.Number(label="Budget", value=0, minimum=0)
        target_audience = gr.Textbox(label="Target audience", lines=2)
        brand_personality = gr.Textbox(label="Brand personality", lines=1)
        with gr.Row():
            price_min = gr.Number(label="Preferred price min", value=None, minimum=0)
            price_max = gr.Number(label="Preferred price max", value=None, minimum=0)
        constraints = gr.Textbox(
            label="Constraints (one per line)", lines=2,
            placeholder="no fragile items\nsupplier must ship within 7 days",
        )
        notes = gr.Textbox(label="Notes", lines=2)

        with gr.Row():
            load_brief = gr.Button("Load selected brief")
            save_brief = gr.Button("Save brief", variant="primary")
            create_brief = gr.Button("Create project from this brief")
        brief_status = gr.Markdown()

        gr.Markdown("### Danger zone")
        with gr.Row():
            confirm_delete = gr.Checkbox(label="I understand this permanently deletes the project", value=False)
            delete_btn = gr.Button("Delete selected project", variant="stop")

        # ---- callbacks --------------------------------------------------- #
        form = [business_name, industry, niche, target_market, target_audience, currency,
                budget, brand_personality, price_min, price_max, constraints, notes]

        def rows() -> list[list[str]]:
            return fmt.project_rows(ctx.projects())

        def on_refresh():
            return rows(), f"{ctx.project_count} project(s)."

        def on_create_example():
            try:
                project = wf.create_project(ctx.store, ProjectCreate(example=True))
                return (
                    *ctx.dashboard(project["id"]),
                    ctx.dropdown_update(project["id"]),
                    rows(),
                    f"Created **{project['name']}** (example brief).",
                )
            except Exception as exc:
                return (*ctx.dashboard(None), gr.update(), rows(), friendly(exc))

        def on_load(project_id):
            project = ctx.project(project_id)
            if not project:
                return [""] * len(form) + ["Select a project first."]
            brief = project.get("brief") or {}
            values = [
                brief.get("business_name", ""),
                brief.get("industry", ""),
                brief.get("niche", ""),
                brief.get("target_market", "Pakistan"),
                brief.get("target_audience", ""),
                brief.get("currency", "PKR"),
                brief.get("budget", 0),
                brief.get("brand_personality", ""),
                brief.get("preferred_price_min"),
                brief.get("preferred_price_max"),
                "\n".join(brief.get("constraints") or []),
                brief.get("notes", ""),
            ]
            return [*values, f"Loaded the brief for **{project.get('name')}**."]

        def on_save(project_id, *values):
            try:
                project = ctx.require(project_id)
                brief = _brief_from_form(list(values))
                wf.update_brief(ctx.store, project, brief)
                return (*ctx.dashboard(project_id), rows(), "Brief saved. Downstream steps were reset so you can re-run them.")
            except Exception as exc:
                return (*ctx.dashboard(project_id), rows(), friendly(exc))

        def on_create_from_form(project_id, *values):
            try:
                brief = _brief_from_form(list(values))
                if not brief.business_name:
                    raise ValueError("Give the business a name before creating the project.")
                project = wf.create_project(ctx.store, ProjectCreate(brief=brief))
                return (
                    *ctx.dashboard(project["id"]),
                    ctx.dropdown_update(project["id"]),
                    rows(),
                    f"Created **{project['name']}**.",
                )
            except Exception as exc:
                return (*ctx.dashboard(project_id), gr.update(), rows(), friendly(exc))

        def on_delete(project_id, confirmed):
            try:
                project = ctx.require(project_id)
                if not confirmed:
                    raise ValueError("Tick the confirmation box first.")
                ctx.store.delete(project["id"])
                remaining = ctx.choices()
                next_id = remaining[0][1] if remaining else None
                return (
                    *ctx.dashboard(next_id),
                    ctx.dropdown_update(next_id),
                    rows(),
                    f"Deleted **{project.get('name')}**.",
                )
            except Exception as exc:
                return (*ctx.dashboard(project_id), gr.update(), rows(), friendly(exc))

        refresh.click(on_refresh, inputs=None, outputs=[project_table, list_status])
        create_example.click(
            on_create_example,
            inputs=None,
            outputs=[*ctx.dashboard_outputs(), ctx.project_dd, project_table, list_status],
        )
        load_brief.click(on_load, inputs=[ctx.project_dd], outputs=[*form, brief_status])
        save_brief.click(
            on_save,
            inputs=[ctx.project_dd, *form],
            outputs=[*ctx.dashboard_outputs(), project_table, brief_status],
        )
        create_brief.click(
            on_create_from_form,
            inputs=[ctx.project_dd, *form],
            outputs=[*ctx.dashboard_outputs(), ctx.project_dd, project_table, brief_status],
        )
        delete_btn.click(
            on_delete,
            inputs=[ctx.project_dd, confirm_delete],
            outputs=[*ctx.dashboard_outputs(), ctx.project_dd, project_table, list_status],
        )

    return {
        "table": project_table,
        "create_example": create_example,
        "create_brief": create_brief,
        "delete_btn": delete_btn,
        "save_brief": save_brief,
    }
