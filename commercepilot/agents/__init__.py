"""Domain agents.

Each module is a focused worker with one input contract and one output contract:

    product_hunter    research and rank product candidates
    store_architect   turn a brief + product into a website specification
    marketing_agent   draft a campaign plan with a validated budget
    business_analyst  compute unit economics, KPIs and scenarios

Agents never talk to each other directly. The orchestrator passes data between
them through the shared project document.
"""
