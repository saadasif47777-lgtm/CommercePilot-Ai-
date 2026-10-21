# CommercePilot AI

An AI-powered e-commerce workspace — entirely in Python.

Research products, generate a storefront, plan a campaign and validate the unit
economics, with four specialised agents handing work to each other through one
shared project. The interface is **Gradio** (no JavaScript, no build step); the
JSON API is **FastAPI**; the data layer is SQLite via Pydantic models.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
# → http://localhost:7860
```

No API key is required to start. Without one the app runs in **labelled
fallback mode** (deterministic templates) and says so everywhere.

---

## What the app does

| Tab | Purpose | Honest status |
|---|---|---|
| **Dashboard** | Brief, pipeline status, consolidated report, one-click full workflow | Runs the 7 real steps and records each one |
| **Product Hunter** | Rank candidates from live web search and/or a sample catalogue; save, reject or enter a product manually | Live rows keep their source URLs; unknown cost/demand/competition stay **unknown** |
| **Store Builder** | Generate a complete storefront from a validated specification; restyle it with plain-English edits; preview and export | Template copy unless an AI key is configured; reviews are labelled sample content |
| **Marketing Studio** | Campaign draft: allocation, audience hypotheses, creatives, KPIs, testing plan, labelled simulation | **Nothing is published.** Meta is not connected |
| **Business Analytics** | Gross profit, margin, break-even ROAS, contribution margin, break-even units, KPIs, three scenarios | Real arithmetic; missing data reports *no data* instead of guessing |
| **Assistant** | Plain-English requests routed to the real agents, including multi-step chains | Executes actual work or explains what it can do |
| **Projects** | Create the example project, edit the brief, delete projects | Changing the brief resets downstream steps on purpose |
| **Settings** | Connection status, AI usage against the budget, optional Meta/Shopify credentials | Credentials are stored server-side and never echoed back |

Everything is reachable both in the UI and over the API (`/api`, interactive
docs at `/docs`).

---

## How the "AI" is wired

* **One AI client** (`commercepilot/ai/`) speaks any OpenAI-compatible API.
  Default provider: **Groq** free tier (`openai/gpt-oss-20b`), which supports
  strict JSON output and does not train on inference data.
* **Structured output only.** Model responses are validated against Pydantic
  schemas, with exactly one repair attempt; a second failure returns an honest
  error and the caller keeps its deterministic template. Nothing unvalidated is
  rendered.
* **Cost control built in.**
  * `LLM_MODEL` handles every task (cheap model).
  * `LLM_MODEL_STRONG` is optional and used only for storefront and ad copy.
  * A hard monthly cap (`AI_MONTHLY_CAP_USD`, default $25) blocks calls *before*
    the provider is contacted, with a warning at 80%.
  * Every call is logged with model, tokens, estimated cost and latency — never
    prompt contents.
* **Prompt-injection defence.** User text and web snippets are delimited as
  untrusted data with explicit instructions; prompts live in versioned files
  (`commercepilot/ai/prompts/*.v1.txt`) so edits are reviewable.
* **Calculations never use a model.** All money maths is ordinary Python in
  `commercepilot/tools/calculations.py`, unit-tested.

Set `LLM_API_KEY` to activate real model output. The app reports
`llm_mode: "llm"` in `/api/health` when a key is present and `"fallback"`
otherwise — it never claims AI when there is none.

---

## Project structure

```
app.py                          entry point: python app.py
commercepilot/
  config.py                     all environment configuration in one place
  schemas.py                    Pydantic contracts shared by every layer
  storage.py                    SQLite project store (JSON documents, WAL)
  runtime.py                    shared store instance
  api.py                        FastAPI routes under /api
  webapp.py                     mounts the API and the Gradio UI in one process
  assistant.py                  natural-language intent router
  integrations.py               optional Meta / Shopify connections
  store_export.py               renders a specification to standalone HTML
  agents/
    product_hunter.py           research + transparent weighted ranking
    store_architect.py          storefront specification + plain-English edits
    marketing_agent.py          campaign plan + validated budget allocation
    business_analyst.py         unit economics, KPIs and scenarios
  workflows/
    commerce_workflow.py        orchestrator, per-step status, report builder
  tools/
    calculations.py             pure, validated arithmetic
    web_search.py               Serper (if keyed) or DuckDuckGo via ddgs
  ai/
    client.py                   provider client: retries, JSON validation, budget
    prompts.py + prompts/       versioned prompt text
    schemas.py, guard.py, usage.py
  ui/
    app.py                      page shell, project selector, cross-tab refresh
    theme.py, formatting.py, context.py, downloads.py, errors.py
    tabs/                       one module per tab (dashboard, research, store, …)
data/
  sample_products.json          16 clearly-labelled demo products
  commercepilot.sqlite3         created on first run (git-ignored)
tests/                          135 tests: agents, workflow, API, UI, exports
docs/                           architecture, manual test checklist, plan, proposal
scripts/verify_deployment.py    HTTP smoke test for any environment
render.yaml                     Render blueprint (free plan)
```

Layer rule: `ui/` and `api.py` are both thin consumers of
`workflows/` → `agents/` → `tools/`. Business rules live in exactly one place.

---

## Tests

```bash
pip install -r requirements-dev.txt
pytest -q
```

The suite covers:
* calculations, including zero/negative/invalid inputs,
* product ranking with and without evidence,
* the full agent handoff chain and per-step failures,
* API validation, persistence across restarts, credential masking,
* AI client retry/repair/budget behaviour (with a stubbed transport),
* the Gradio layout, formatting helpers, exports, and the mounted app serving
  both UI and API.

Deployment smoke test (works locally or against a deployed URL):

```bash
python scripts/verify_deployment.py --base http://127.0.0.1:7860
```

---

## Deployment (free tier)

The app is one Python process, so it needs a host that can run a long-lived
server (Vercel's serverless functions cannot run Gradio). **Render's free web
service** is the documented target; `render.yaml` contains the exact settings:

| Setting | Value |
|---|---|
| Build command | `pip install -r requirements.txt` |
| Start command | `python app.py` |
| Health check | `/api/health` |
| Environment | `LLM_API_KEY` (optional), `DB_PATH` (optional), `PYTHON_VERSION=3.12` |

Details, limits and troubleshooting: [DEPLOYMENT.md](DEPLOYMENT.md).

**Free-tier caveats, stated plainly:**
* Render free instances sleep after ~15 idle minutes; the first request takes
  about a minute to wake the service.
* The free instance has no persistent disk, so the SQLite database resets on
  restart or redeploy. Click **Create example project** to rebuild the demo in
  one step. Attach a disk (paid) and set `DB_PATH` to keep data.
* LLM usage is $0 while inside Groq's free limits; the monthly cap exists for
  the day you switch to a paid model or add real traffic.

---

## Configuration

Copy `.env.example` to `.env` (git-ignored) or set variables in the host
dashboard. Values are names only here — no secrets are committed.

| Variable | Required | Purpose |
|---|---|---|
| `LLM_API_KEY` | no | Enables real model output; falls back to templates when absent |
| `LLM_PROVIDER`, `LLM_BASE_URL`, `LLM_MODEL`, `LLM_MODEL_STRONG` | no | Provider routing and the cheap/strong model split |
| `AI_MONTHLY_CAP_USD`, `AI_BUDGET_WARN_PCT` | no | Hard spend cap and warning threshold |
| `SERPER_API_KEY` | no | Richer live search; `ddgs` works without a key |
| `DB_PATH` | no | SQLite location (point at a persistent disk in production) |
| `PORT`, `HOST` | no | Bind address, default `0.0.0.0:7860` (Render sets `PORT`) |
| `CORS_ORIGINS` | no | Only needed if a separate client calls the API |
| `META_*`, `SHOPIFY_*` | no | Optional integrations; never sent to the browser |

Secrets saved from the Settings tab go to `.secrets/` (git-ignored, mode 600)
and are masked in every response. Environment variables always take precedence.

---

## Data provenance and honesty

* Sample products, template copy, simulated campaign metrics and the example
  brief are **labelled wherever they appear**.
* "Unknown" beats "invented": missing evidence is excluded from scoring and the
  remaining weights are renormalised; missing KPIs read *no data*.
* The campaign simulation states its assumptions (CPC, conversion rate) and is
  labelled `DEMO — NOT PUBLISHED`.
* The storefront is generated from a validated specification; no model-written
  code is ever executed.
* Generated assets are downloadable: storefront HTML, campaign JSON, analysis
  JSON, report JSON.

---

## Known limitations

* **Single-user, no authentication.** Projects are shared by whoever can reach
  the app; accounts are a later phase.
* **SQLite only.** Fine for a demo and a single instance; Postgres is the
  migration path for multi-instance hosting.
* **Streaming is not implemented.** Current generations are short (≤800 output
  tokens), so there is no UX need yet.
* **Meta/Shopify are read-only or draft-only.** Nothing is published or synced.
* The sample catalogue, example project and campaign simulator are still part of
  the demo and are scheduled for removal in the next product phase.

---

## Docs

* [DEPLOYMENT.md](DEPLOYMENT.md) — hosting, environment variables, limits
* [docs/architecture.md](docs/architecture.md) — layers, agent contracts, data flow
* [docs/manual-testing.md](docs/manual-testing.md) — interactive test checklist
* [docs/proposal.md](docs/proposal.md) — the original competition proposal
* [docs/PRODUCTION_PLAN.md](docs/PRODUCTION_PLAN.md) — historical audit and phase plan
