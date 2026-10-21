"""Assistant tab: a chat that performs real work.

The assistant is an intent router. Each recognised request runs the matching
agent over the current project and returns its actual output, so a reply is
always backed by a real action (or an honest explanation of what it can do).
"""
from __future__ import annotations

import gradio as gr

from ...assistant import handle as assistant_handle
from ..context import UIContext
from ..errors import friendly


def build(ctx: UIContext) -> dict[str, gr.components.Component]:
    """Create the chat surface and its handlers."""
    with gr.Tab("Assistant"):
        gr.Markdown(
            "## Ask in plain English\n"
            "Requests are routed to the real agents. Try “find products for my niche”, "
            "“build the storefront”, “draft a campaign within my budget” or "
            "“show me the break-even point”. Multi-step requests run in order."
        )
        chatbot = gr.Chatbot(
            label="CommercePilot assistant",
            type="messages",
            height=460,
            elem_id="cp-chat",
            show_label=False,
        )
        with gr.Row():
            message = gr.Textbox(
                show_label=False,
                placeholder="Type a request…",
                scale=5,
                lines=1,
                container=False,
            )
            send = gr.Button("Send", variant="primary", scale=1)
            clear = gr.Button("Clear", scale=1)

        gr.Examples(
            examples=[
                ["Find products for a skincare brand in Pakistan"],
                ["Select #1 and build the storefront"],
                ["Make the store more luxurious"],
                ["Draft a campaign within my budget and show the break-even point"],
            ],
            inputs=[message],
            label="Example requests",
        )

        def respond(project_id, text, history):
            history = list(history or [])
            if not (text or "").strip():
                return history, ""
            history.append({"role": "user", "content": text.strip()})
            try:
                result = assistant_handle(ctx.store, project_id, text.strip())
                reply = result.get("reply") or "I could not complete that request."
                intent = result.get("intent")
                if intent and intent != "unknown":
                    reply += f"\n\n_handled as `{intent}`_"
            except Exception as exc:
                reply = friendly(exc)
            history.append({"role": "assistant", "content": reply})
            return history, ""

        def reset():
            return [], ""

        send.click(respond, inputs=[ctx.project_dd, message, chatbot], outputs=[chatbot, message])
        message.submit(respond, inputs=[ctx.project_dd, message, chatbot], outputs=[chatbot, message])
        clear.click(reset, inputs=None, outputs=[chatbot, message])

    return {"chatbot": chatbot}
