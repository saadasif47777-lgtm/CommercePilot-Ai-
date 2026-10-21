"""Store Builder tab: generate, preview and restyle a storefront.

The agent returns a structured specification (sections + design tokens), not
arbitrary HTML. That specification is rendered twice: as a live preview in the
browser and as a standalone HTML export you can open or host anywhere.
"""
from __future__ import annotations

import time
from typing import Optional

import gradio as gr

from ...schemas import StoreDesign
from ...workflows import commerce_workflow as wf
from .. import downloads
from .. import formatting as fmt
from ..context import UIContext
from ..errors import friendly


def preview_html(project_id: Optional[str]) -> str:
    """An iframe pointing at the exported storefront for this project."""
    if not project_id:
        return (
            "<div style='padding:40px;text-align:center;color:#5B665F;border:1px dashed #cfd6d1;"
            "border-radius:12px'>Generate a storefront to see the preview here.</div>"
        )
    # The query string busts the browser cache after every regeneration.
    return (
        f"<iframe src='/api/projects/{project_id}/store/export?v={int(time.time())}' "
        "title='Storefront preview' loading='lazy'></iframe>"
    )


def build(ctx: UIContext) -> dict[str, gr.components.Component]:
    """Create design controls, generation, editing and preview."""
    with gr.Tab("Store Builder"):
        gr.Markdown(
            "## Build the storefront\n"
            "One click produces a complete, responsive storefront from your selected product. "
            "Ask for changes in plain English — the specification is edited, not rewritten."
        )

        with gr.Row():
            with gr.Column(scale=1):
                generate = gr.Button("Generate storefront", variant="primary")
                with gr.Accordion("Design overrides", open=False):
                    primary = gr.ColorPicker(label="Primary colour", value="#0F3D2E")
                    accent = gr.ColorPicker(label="Accent colour", value="#2F855A")
                    with gr.Row():
                        radius = gr.Slider(0, 28, value=14, step=1, label="Corner radius")
                        density = gr.Dropdown(
                            label="Spacing", choices=["compact", "comfortable", "airy"], value="comfortable"
                        )
                    with gr.Row():
                        hero_style = gr.Dropdown(
                            label="Hero style",
                            choices=["split", "centered", "editorial_split", "boxed", "minimal"],
                            value="split",
                        )
                        card_style = gr.Dropdown(
                            label="Product cards", choices=["minimal", "bordered", "elevated"], value="bordered"
                        )
                    font_heading = gr.Dropdown(
                        label="Heading font", choices=["serif", "sans", "display"], value="serif"
                    )
                instructions = gr.Textbox(
                    label="Extra instructions (optional)",
                    placeholder="Warm, premium tone; emphasise the 30-day guarantee.",
                    lines=2,
                )

                gr.Markdown("---\n### Refine it")
                edit_prompt = gr.Textbox(
                    label="What should change?",
                    placeholder="make it more luxurious",
                    lines=2,
                )
                edit_btn = gr.Button("Apply change")
                gr.Markdown(
                    "_Examples: “editorial split-screen hero”, “compact spacing”, "
                    "“rounded cards”, “hide the reviews”, “shorter headline”._",
                    elem_classes=["cp-hint"],
                )

                download_btn = gr.Button("Download standalone HTML")
                store_file = gr.File(label="Storefront file", interactive=False, visible=False)

            with gr.Column(scale=2):
                action_status = gr.Markdown()
                summary = gr.Markdown("No storefront generated yet.")
                preview = gr.HTML(preview_html(None), elem_id="cp-preview")
                with gr.Accordion("Full specification (JSON)", open=False):
                    spec_json = gr.JSON(label="Website specification")

        # ---- callbacks --------------------------------------------------- #
        def _design(p, a, r, d, h, c, f) -> Optional[StoreDesign]:
            """Build a design override object from the control values."""
            return StoreDesign(
                primary_color=p or "#0F3D2E",
                accent_color=a or "#2F855A",
                radius=int(r if r is not None else 14),
                density=d or "comfortable",
                hero_style=h or "split",
                card_style=c or "bordered",
                font_heading=f or "serif",
            )

        def on_generate(project_id, primary_color, accent_color, radius_value, density_value,
                        hero_value, card_value, font_value, extra):
            try:
                project = ctx.require(project_id)
                design = _design(primary_color, accent_color, radius_value, density_value,
                                 hero_value, card_value, font_value)
                spec = wf.step_generate_store(ctx.store, project, design, (extra or "").strip())
                return (
                    *ctx.dashboard(project_id),
                    f"Storefront generated for **{spec.brand_name}** "
                    f"({len(spec.sections)} sections, {fmt.badge(spec.generation_mode).lower()} copy).",
                    fmt.store_markdown(spec.model_dump()),
                    preview_html(project_id),
                    spec.model_dump(),
                )
            except Exception as exc:
                project = ctx.project(project_id) or {}
                return (
                    *ctx.dashboard(project_id),
                    friendly(exc),
                    fmt.store_markdown(project.get("store_spec")),
                    preview_html(project_id),
                    project.get("store_spec"),
                )

        def on_edit(project_id, prompt):
            try:
                project = ctx.require(project_id)
                if not (prompt or "").strip():
                    raise ValueError("Describe the change you want first.")
                response = wf.step_edit_store(ctx.store, project, prompt)
                return (
                    *ctx.dashboard(project_id),
                    fmt.store_edits_markdown(response.applied_changes, response.message),
                    fmt.store_markdown(response.spec.model_dump()),
                    preview_html(project_id),
                    response.spec.model_dump(),
                )
            except Exception as exc:
                project = ctx.project(project_id) or {}
                return (
                    *ctx.dashboard(project_id),
                    friendly(exc),
                    fmt.store_markdown(project.get("store_spec")),
                    preview_html(project_id),
                    project.get("store_spec"),
                )

        def on_download(project_id):
            path = downloads.export_storefront(ctx.project(project_id))
            if not path:
                return gr.update(visible=False), "Generate the storefront first."
            return gr.update(value=path, visible=True), "HTML export ready — open it in any browser."

        generate.click(
            on_generate,
            inputs=[ctx.project_dd, primary, accent, radius, density, hero_style, card_style, font_heading, instructions],
            outputs=[*ctx.dashboard_outputs(), action_status, summary, preview, spec_json],
        )
        edit_btn.click(
            on_edit,
            inputs=[ctx.project_dd, edit_prompt],
            outputs=[*ctx.dashboard_outputs(), action_status, summary, preview, spec_json],
        )
        download_btn.click(
            on_download,
            inputs=[ctx.project_dd],
            outputs=[store_file, action_status],
        )

    return {
        "preview": preview,
        "summary": summary,
        "spec_json": spec_json,
        "action_status": action_status,
    }
