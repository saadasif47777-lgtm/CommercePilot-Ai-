"""Settings tab: what is connected, what it costs, and optional credentials.

Credential forms write to a git-ignored server-side file (or prefer environment
variables). Nothing typed here is ever echoed back to the browser: only a
success/failure result and masked identifiers are shown.
"""
from __future__ import annotations

import gradio as gr

from ... import ai, integrations
from .. import formatting as fmt
from ..context import UIContext
from ..errors import friendly


def build(ctx: UIContext) -> dict[str, gr.components.Component]:
    """Create status panels, usage panel and credential forms."""
    with gr.Tab("Settings"):
        gr.Markdown(
            "## Connections and cost\n"
            "The app runs fully without any optional integration. Missing keys simply "
            "switch a feature to its labelled deterministic mode."
        )

        with gr.Row():
            with gr.Column(scale=1):
                usage_btn = gr.Button("Refresh AI usage", variant="primary")
                usage = gr.Markdown(
                    fmt.usage_markdown(ai.usage_summary())
                )
                status_btn = gr.Button("Refresh connections")
            with gr.Column(scale=1):
                status = gr.Markdown(fmt.integrations_markdown(integrations.all_status()))

        action_status = gr.Markdown()

        with gr.Accordion("Meta Marketing API (optional)", open=False):
            gr.Markdown(
                "Credentials are stored server-side only and never displayed again. "
                "Even with credentials, publishing always requires an explicit human approval step, "
                "which this version does not implement — campaigns stay local drafts."
            )
            meta_token = gr.Textbox(label="Access token", type="password")
            meta_account = gr.Textbox(label="Ad account id", placeholder="act_123456789")
            meta_btn = gr.Button("Save and verify")

        with gr.Accordion("Shopify Admin API (optional)", open=False):
            gr.Markdown(
                "Used only to read your catalogue. A Storefront API token does not grant admin access."
            )
            shop_domain = gr.Textbox(label="Shop domain", placeholder="your-store.myshopify.com")
            shop_token = gr.Textbox(label="Admin API token", type="password")
            shop_btn = gr.Button("Save and test")

        gr.Markdown(
            "### How configuration works\n"
            "- **Recommended:** set variables in your host's dashboard (or a local `.env`), never in code.\n"
            "- `LLM_API_KEY` enables real model output; without it every feature uses labelled templates.\n"
            "- `LLM_MODEL` is the cheap model used for all tasks; `LLM_MODEL_STRONG` is optional and used "
            "only for storefront and ad copy.\n"
            "- `AI_MONTHLY_CAP_USD` hard-stops calls at the cap, so the app cannot overspend silently.\n"
            "- `DATABASE_URL` is reserved for the Postgres migration; storage is SQLite today."
        )

        # ---- callbacks --------------------------------------------------- #
        def on_usage():
            return fmt.usage_markdown(ai.usage_summary())

        def on_status():
            return fmt.integrations_markdown(integrations.all_status())

        def on_meta(token, account):
            try:
                if not (token or "").strip() or not (account or "").strip():
                    raise ValueError("Both the access token and the ad account id are required.")
                integrations.save_credentials(
                    "meta", {"access_token": token.strip(), "ad_account_id": account.strip()}
                )
                result = integrations.meta_verify()
                state = "verified" if result.get("verified") else "saved but not verified"
                return f"Meta credentials {state}. {result.get('detail', '')}"
            except Exception as exc:
                return friendly(exc)

        def on_shopify(domain, token):
            try:
                if not (domain or "").strip() or not (token or "").strip():
                    raise ValueError("Both the shop domain and the admin token are required.")
                integrations.save_credentials(
                    "shopify", {"shop_domain": domain.strip(), "admin_token": token.strip()}
                )
                result = integrations.shopify_fetch_products(limit=1)
                if result.get("ok"):
                    return "Shopify connected — the catalogue is readable."
                return f"Shopify saved, but the test call failed: {result.get('detail')}"
            except Exception as exc:
                return friendly(exc)

        usage_btn.click(on_usage, inputs=None, outputs=[usage])
        status_btn.click(on_status, inputs=None, outputs=[status])
        meta_btn.click(on_meta, inputs=[meta_token, meta_account], outputs=[action_status])
        shop_btn.click(on_shopify, inputs=[shop_domain, shop_token], outputs=[action_status])

    return {"usage": usage, "status": status}
