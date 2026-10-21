"""One module per tab of the Gradio interface.

Each module exposes ``build(ctx)`` and returns the components the shell needs to
wire shared events (for example the project selector refreshing the dashboard).
"""
