# CommercePilot AI — Architecture

## Overview

```
Browser (React 19 + TS + Tailwind 4)
   │  same-origin /api  (Vite dev proxy → FastAPI)
   ▼
FastAPI routes (backend/main.py)         ← thin: validate, delegate, map errors
   ▼
Orchestrator (workflows/commerce_workflow.py)
   ├── Agent A  product_hunter.py   → ranked candidates (live search + samples)
   ├── Agent B  store_architect.py  → structured WebsiteSpec (+ NL edits)
   ├── Agent C  marketing_agent.py  → CampaignPlan (+ validated allocations)
   └── Agent D  business_analyst.py → analysis dict (pure calculations)
   ▼
tools/calculations.py   exact arithmetic (no LLM, fully unit-tested)
tools/web_search.py     live search: Serper (if keyed) or ddgs (key-free)
storage.py              SQLite (projects table, JSON documents, WAL)
```

## Shared project context

A single JSON document per project (validated by Pydantic on the way in and out)
holds: `brief`, `research`, `selected_product`, `store_spec`, `campaign`,
`analysis`, `report`, `executions`, `steps`. Every agent reads and writes this
document — the Product Hunter's top-ranked row becomes the Store Architect's
hero product, the Marketing Strategist's price/cost inputs and the Business
Analyst's economic basis. That is the mechanism that prevents the
"four disconnected chatbots" failure mode.

Step states (`brief → research → select → store → campaign → analyze → report`)
are stored alongside, so the UI can show progress, failures and the next
recommended action, and a failed step can be retried without restarting.

## Why plain Python instead of Agno

Verified in this runtime before building: with no model credentials, Agno's
`Agent.run()` returns an errored `RunOutput` with empty content
(`OPENAI_API_KEY not set`), so agents built on it cannot produce results. The
orchestrator therefore uses normal typed functions with explicit handoffs. If a
key is later supplied, `backend/llm.py` (OpenAI-compatible, timeout + quota
handling) activates LLM-assisted copy/intent parsing *inside* the agents, with
no orchestrator changes.

## Agent contracts

### Agent A — Product Hunter
`run(ResearchRequest) -> ResearchResult`
* modes: `sample` (16 labelled rows) / `live` (web search, source URLs kept) / `both` (merged, de-duplicated by URL + title similarity > 0.86)
* scoring: weighted normalised heuristic; unknown factors excluded, remaining weights renormalised; `score = evidence_score × evidence_coverage` so thin evidence cannot out-rank fully evidenced candidates; every row carries a score breakdown, coverage, confidence and a plain-English reason
* never raises: outages/timeouts/rate limits become warnings in the result

### Agent B — Store Architect
`build_spec(brief, product, design?, extra?, catalog?) -> WebsiteSpec`
`apply_edit(spec, prompt) -> StoreEditResponse`
* the spec is a validated discriminated union of 8 section types + a design system (colours, fonts, radius, density, hero/card style, animation)
* the frontend renders it with reusable React components — no generated code executes anywhere
* NL edits are deterministic rules → structured mutations, each reporting what changed; unmatched prompts return guidance

### Agent C — Marketing Strategist
`generate(brief, product, CampaignRequest) -> CampaignPlan`
* default allocation by objective; custom allocations validated (`sum == budget`, no negatives, no duplicate labels) via `calculations.validate_allocation`
* all estimates flagged illustrative; Meta status embedded (`not_connected`, `DEMO — NOT PUBLISHED`)
* simulation endpoint computes deterministic projections from stated CPC/CVR assumptions

### Agent D — Business Analyst
`analyze(brief, product, campaign?, AnalyzeRequest) -> dict`
* formulas exactly as specified; negative/non-numeric money rejected; zero denominators return `undefined` (None) with an explanation, never a fabricated number
* uses the **campaign** budget when present (that's what is actually spent), else the brief budget; separates allocated spend, reserve held and expected spend
* scenarios take editable assumptions (clicks, CVR, CPC) and display them next to the outputs

## Validation & error handling

* All request bodies are Pydantic models (422 with field-level messages).
* Agent failures set the step to `error`, record the exception in the execution
  log and surface a retryable `StepFailed` — earlier results are kept.
* Search has hard timeouts and degrades to sample data with a visible warning.

## Persistence

SQLite (`backend/commercepilot.sqlite3`, WAL mode, per-thread connections).
Projects therefore survive page refreshes and backend restarts; tests cover
reload-after-restart.

## Security

* Credentials: env vars preferred; UI-saved credentials go to `backend/.secrets/` (git-ignored, chmod 600) and are masked (`abc…yz (masked, N chars)`) in every response.
* No secrets in logs or execution records; no tokens in the frontend bundle.
* User text renders through React's escaping; no `dangerouslySetInnerHTML`.
* CORS restricted to configured origins.

## LLM layer (optional)

`backend/llm.py::complete(system, user, as_json)` → OpenAI-compatible chat
completions with timeout + non-200 handling. Callers fall back to templates and
label the output `generation_mode: "template"`. Arithmetic is never delegated.
