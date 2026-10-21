"""Orchestration.

`commerce_workflow` sequences the four agents, records every step, invalidates
dependent steps when their inputs change, and builds the consolidated report.
Both the Gradio UI and the JSON API call these functions.
"""
