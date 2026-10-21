# CommercePilot AI — Architecture

## Overview

```
                    ┌──────────────────────────────────────────┐
                    │  commercepilot.webapp (one ASGI process) │
                    │                                          │
   Browser  ───────►│  Gradio UI  (commercepilot/ui)           │
                    │  JSON API   (commercepilot/api.py, /api) │
                    └───────────────┬──────────────────────────┘
                                    │  same functions, no HTTP hop
                                    ▼
                Orchestrator  commercepilot/workflows/commerce_workflow.py
                    ├── Agent A  product_hunter.py    → ranked candidates
                    ├── Agent B  store_architect.py   → WebsiteSpec (+ edits)
                    ├── Agent C  marketing_agent.py   → CampaignPlan
                    └── Agent D  business_analyst.py  → analysis dict
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        ▼                           ▼                           ▼
tools/calculations.py        tools/web_search.py          ai/ (optional)
pure validated arithmetic    Serper or key-free ddgs      client, schemas,
                                                          guard, usage, budget
                                    │
                                    ▼
                        storage.py — SQLite project documents
```

Layer rules:

1. `ui/` and `api.py` contain **no business rules**; they validate input, call
   the orchestrator and render the result.
2. `workflows/` owns sequencing, step status, invalidation and reports.
3. `agents/` own domain logic and call `tools/` and `ai/` only.
4. `tools/` is deterministic and fully unit-tested; money never goes through a
   language model.

## Shared project context

Each project is one JSON document (validated by Pydantic on write and read):

```
brief, research, selected_product, saved_products, rejected_product_ids,
store_spec, campaign, analysis, report, executions, steps
```

The Product Hunter's ranking becomes the Store Architect's hero product and the
Business Analyst's economics. The campaign's budget is what the analyst spends
against. This shared document is what prevents "four disconnected chatbots".

Step states follow `brief → research → select → store → campaign → analyze →
report`. Each step records status, message and timestamp, and can be retried
without discarding earlier results. Editing the brief deliberately resets the
dependent steps so stale results never look current.

## AI layer

`commercepilot/ai/` is the only place that talks to a model provider.

| Module | Responsibility |
|---|---|
| `client.py` | OpenAI-compatible transport, retries with exponential backoff and jitter, 20 s timeout, output-token cap, one schema-repair retry, budget guard, usage recording |
| `schemas.py` | Pydantic models the model's JSON must satisfy (`StoreCopy`, `CampaignCreatives`, `AssistantIntent`) |
| `guard.py` | wraps untrusted text in explicit delimiters, strips control characters, truncates |
| `prompts.py` + `prompts/*.v1.txt` | prompt text as versioned files; the version is recorded with every call |
| `usage.py` | SQLite `ai_usage` table: prompt name, model, tokens, estimated cost, latency, status — never prompt contents |

**Model routing.** `LLM_MODEL` (cheap) serves every task. `LLM_MODEL_STRONG` is
optional and used only for storefront and ad copy. Blank means the cheap model
does everything — the default, lowest-cost configuration.

**Budget guard.** The monthly cap is checked *before* the provider is called.
At the cap, calls raise `AIBudgetExceeded` and callers keep their deterministic
templates, labelled `generation_mode: "template"`. Warning threshold is
configurable (default 80%).

**Failure behaviour.** Provider outage, invalid output twice, or budget
exhaustion all end the same way: a labelled template result, never invented
data or a false "AI-generated" label.

## Agent contracts

### Agent A — Product Hunter
`run(ResearchRequest) -> ResearchResult`
* modes: `sample` (16 labelled products), `live` (web search, source URLs kept),
  `both` (merged and de-duplicated).
* scoring: weighted heuristic (margin, demand, competition, audience, price).
  Unknown factors are excluded and the remaining weights renormalised;
  `score = evidence_score × evidence_coverage` so thin evidence cannot outrank
  fully evidenced candidates.
* never raises: provider problems become warnings in the result.

### Agent B — Store Architect
`build_spec(brief, product, design?, extra?, catalog?) -> WebsiteSpec`
`apply_edit(spec, prompt) -> StoreEditResponse`
* the specification is a discriminated union of eight section types plus design
  tokens (colours, fonts, radius, density, hero/card style).
* `store_export.render_standalone_html(spec)` turns it into a real page; the UI
  previews that exact page and offers it as a download.
* plain-English edits are deterministic rules that mutate the spec and report
  what changed; unmatched prompts say so instead of pretending.

### Agent C — Marketing Strategist
`generate(brief, product, CampaignRequest) -> CampaignPlan`
* default allocation by objective; custom allocations validated to sum exactly
  to the budget, with no negative amounts or duplicate labels.
* all estimates flagged illustrative; status stays `draft` with
  `publication: "DEMO - NOT PUBLISHED"` and `meta_connection: "not_connected"`.
* `step_simulate_campaign` applies two stated assumptions (CPC, conversion rate)
  to the allocation — arithmetic on assumptions, labelled as such.

### Agent D — Business Analyst
`analyze(brief, product, campaign?, AnalyzeRequest) -> dict`
* gross profit/unit, margin %, markup %, break-even ROAS, contribution margin
  with per-unit overheads, break-even units, CPA, conversion rate, budget
  utilisation, three editable scenarios.
* invalid money is rejected; zero denominators return `None` with an
  explanation; missing KPIs report `no data` rather than an estimate.

## Interface layer

```
ui/app.py      page shell, active-project selector, cross-tab refresh
ui/context.py  shared state: store access, project selector, dashboard payload
ui/formatting.py  pure data → markdown/table rows helpers
ui/downloads.py    storefront HTML, campaign/analysis/report JSON
ui/errors.py       exception → short human message (+ server-side log)
ui/tabs/*.py       one module per tab, each exposes build(ctx)
```

Selecting a project refreshes every view from stored data, so the same project
looks identical whichever tab you open. Handler arity matches the component
outputs exactly; tests build the interface and exercise the callbacks.

## Persistence

SQLite (`data/commercepilot.sqlite3` by default), WAL mode, per-thread
connections, one `projects` table holding JSON documents plus an `ai_usage`
table. Projects survive restarts. On a host with an ephemeral filesystem the
database resets with the instance — `DB_PATH` points at a persistent disk when
one is available. Postgres is the migration path for multi-instance hosting.

## Security

* Secrets are read from environment variables or `.secrets/` (git-ignored,
  mode 600); environment variables take precedence.
* Credentials are never returned to the browser: status responses contain
  booleans and a masked identifier only.
* The AI API key is server-side only; the UI never receives it.
* Every request body is validated by Pydantic; invalid input produces a
  field-level message, not a stack trace.
* Model output is validated and sanitised before rendering; user text is wrapped
  as untrusted data for prompts.
* The app is currently single-tenant. Authentication and per-user isolation are
  the next phase, not an existing feature.

## Why plain Python instead of an agent framework

Verified in this runtime before building: with no model credentials, Agno's
`Agent.run()` returns an errored `RunOutput` with empty content, so agents built
on it cannot produce results. Plain typed functions with explicit handoffs are
also easier to test, trace and present — each step is an ordinary function with
one input contract and one output contract.
