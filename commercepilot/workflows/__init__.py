"""Orchestration.

`commerce_workflow` sequences the four agents, records every step, invalidates
dependent steps when their inputs change, and builds the consolidated report.
Both the JSON API (and therefore the interface) and the automated tests call
these functions.
"""
