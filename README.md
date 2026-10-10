# CommercePilot AI

**A unified, AI-powered e-commerce workspace** — discover products, generate an
interactive storefront, plan a campaign and validate the economics, with four
specialised agents handing their outputs to each other through one shared
project context.

Built for the *AI in Retail & E-commerce* competition category. Python + FastAPI
backend, React + TypeScript + Tailwind frontend, SQLite persistence.

---

## What actually works (no simulations presented as real)

| Area | What it does | Real vs demo |
|---|---|---|
| **Product Hunter** | Live web search (DuckDuckGo via `ddgs`, Serper if keyed) + a 16-product sample catalogue, merged and de-duplicated, scored by a transparent weighted heuristic | Live results keep source URLs; cost/demand/competition stay **unknown** when not evidenced. Sample rows are labelled *sample data* everywhere |
| **Store Architect** | Parses the brief into a Pydantic-validated website specification and renders a genuinely interactive storefront (catalog search/filter, quantity steppers, add-to-cart, cart drawer with subtotal, mobile nav, FAQ accordion). Natural-language edits update the structured spec; export as standalone HTML | Generated from validated reusable components — **no arbitrary AI code is executed**. Reviews are labelled sample |
| **Marketing Strategist** | Campaign plan (objective, 3 creative concepts, audience hypotheses, testing strategy, KPIs, risks) + budget allocator validated to sum exactly to the budget (PKR 30,000 → 7,500 testing / 19,500 scaling / 3,000 reserve) | Meta Marketing API is **Not Connected**. Simulated execution is labelled **DEMO — NOT PUBLISHED** and computes deterministic projections from stated assumptions (never random) |
| **Business Analyst** | Real Python arithmetic: gross profit/unit, margin %, break-even ROAS, CPA, conversion rate, budget utilisation, three editable scenarios | KPIs without data report **"no data"** rather than estimates. Break-even ROAS is explicitly documented as gross-profit-only |
| **Orchestrator** | 8-step workflow with per-step status, retry, and an execution log (agent, status, timestamps, in/out summaries, warnings) | Runs plain typed Python functions — see *Why not Agno* below |
| **Integrations panel** | Live status for LLM, web search, Meta, Shopify, storage with setup instructions; credentials save server-side only (git-ignored) and are never echoed to the browser | Meta/Shopify default to **not connected**; verification calls the real vendor APIs when configured |

**Fallback mode:** no AI API key is configured, so all copy is template/rule
generated and the app says so (`llm_mode: "fallback"` in `/api/health`). Set
`OPENAI_API_KEY` to activate LLM-assisted copy and intent parsing — calculations
always stay in Python.

## Quick start

```bash
# 1. Backend (Python 3.12+)
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000

# 2. Frontend (Node 20+)
cd frontend && npm install && npm run dev   # http://localhost:3000
```

Open http://localhost:3000 → **Example Project** → **Run Full Commerce Workflow**.

> The Vite dev server proxies `/api` to the backend, so the browser only ever
> talks to one origin. Use `VITE_API_TARGET` if the backend is elsewhere.

### 60-second demo script (for judges)

1. **Example Project** (top-right) — Noor Glow, a Pakistani skincare brand, PKR 30,000 budget.
2. **Run Full Commerce Workflow** — watch the 8 steps complete with agent handoffs.
3. **Product Hunter** — ranked shortlist; expand *Why this rank?* for the scoring breakdown and evidence; live rows link to their sources.
4. **Add to Project** on a different product → **Store** → *Regenerate design* — the storefront rebuilds around it. Try the prompt *"Make this store look more luxurious"*, toggle Mobile preview, add items to the cart.
5. **Marketing Studio** — edit an allocation; an allocation that doesn't sum to the budget is rejected (422). *Run simulated execution* shows the DEMO label and its assumptions.
6. **Analytics** — profitability cards, break-even ROAS from the actual stored price/cost, editable scenarios, formula notes.
7. **Settings** — integration status: LLM fallback, live search connected, Meta/Shopify not connected.

## Tests

```bash
.venv/bin/python -m pytest tests/ -q     # 111 tests: calculations, hunter, workflow, API
cd frontend && npm run build             # type-checks + production build
```

The suite covers: ranking with known and missing data, gross profit/margin,
break-even ROAS, zero-click/zero-profit edges, budget allocation validation,
product → storefront → campaign → analyst handoffs, API validation and
persistence across restarts.

## API

`GET /api/health` · `GET /api/products` · `POST /api/research` ·
`POST /api/projects` · `GET /api/projects/{id}` ·
`POST /api/projects/{id}/select-product` · `generate-store` · `edit-store` ·
`generate-campaign` · `analyze` · `run-workflow` · `GET .../report` ·
`GET /api/integrations/status` (+ interactive docs at `/docs`).

## Project layout

```
backend/
  main.py                FastAPI routes (thin handlers)
  schemas.py             Pydantic contracts (validation backbone)
  storage.py             SQLite project store
  agents/                product_hunter, store_architect, marketing_agent, business_analyst
  workflows/             commerce_workflow.py — orchestrator + report builder
  tools/                 calculations.py (pure math), web_search.py (live search)
  data/                  sample_products.json (16 labelled demo products)
frontend/src/
  pages/ components/     8 app sections + storefront renderer, charts, chat
  state/                 ProjectContext (shared project state)
tests/                   111 automated tests
docs/                    architecture.md, manual-testing.md
```

## Honesty policy

* Every sample record is labelled; live records keep their source URLs.
* "Unknown" beats "invented": missing evidence is excluded from scoring (with weights renormalised and coverage shown), and KPIs without data say *no data*.
* Simulations state their assumptions and are never presented as platform data.
* No secrets in the repo: `.env` is git-ignored; integration credentials save to `backend/.secrets/` (also git-ignored) and are masked in every response.

## Deployment note

This environment's static hosting (Cloudflare Workers) does not run Python, so
the app runs as a local persistent stack (FastAPI + Vite) — the preview URL
above serves the full working application. The backend logic is standard
FastAPI and ports to any Python host (Railway, Render, Fly.io, a VM) unchanged.

## Docs

* [proposal.md](proposal.md) — competition proposal
* [docs/architecture.md](docs/architecture.md) — system design and agent contracts
* [docs/manual-testing.md](docs/manual-testing.md) — browser test checklist
