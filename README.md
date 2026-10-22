# CommercePilot AI

An AI agent crew — Product Hunter, Store Architect, Marketing Strategist and
Business Analyst — that takes a product brief from research to a ranked product
shortlist, a generated storefront, a campaign plan and full unit economics.

**Stack:** Python 3.12 · FastAPI · SQLite — React 19 · Vite · TypeScript ·
Tailwind 4. One backend process serves the JSON API and the built frontend;
there is no second service to deploy.

## Quick start

```bash
# 1. Backend + frontend dependencies
pip install -r requirements.txt
cd frontend && npm install && cd ..

# 2. Configure (optional — the app runs with no keys in labelled demo mode)
cp .env.example .env         # edit if you have keys

# 3. Build the frontend once
npm run build                # runs `npm --prefix frontend run build

# 4. Run
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Open <http://localhost:8000>. API docs at <http://localhost:8000/docs>.

For day-to-day development run the two processes side by side:

```bash
uvicorn backend.main:app --reload --port 8000          # terminal 1
npm --prefix frontend run dev                          # terminal 2 (proxies /api)
```

## Environment variables

All read from `.env` (see `.env.example`):

| Variable | Purpose |
|---|---|
| `DB_PATH` | SQLite file (default `data/commercepilot.sqlite3`) |
| `CORS_ORIGINS` | Comma-separated allow-list for browser origins |
| `SERPER_API_KEY` | Live product/web search (falls back to key-free DDGS, then samples) |
| `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL` / `LLM_MODEL_STRONG` | Optional OpenAI-compatible model access |
| `LLM_MONTHLY_BUDGET` / `LLM_WARN_THRESHOLD` | Monthly spend cap and warning level |
| `SESSION_SECRET` | Signing key for session cookies |

Without model keys the app still works: copy is generated from deterministic
templates and labelled `template`, calculations are always plain Python, and
the Product Hunter degrades live → free search → labeled sample catalogue.

**No secrets are ever committed.** `.env` and `data/` are git-ignored; only
`.env.example` is tracked.

## Tests

```bash
pytest                  # unit + API tests (135 passing)
pytest -m live          # live LLM integration probes (needs keys)
ruff check backend      # lint
python scripts/verify_deployment.py <base-url>   # post-deploy smoke checks
```

## Routes

| Path | What |
|---|---|
| `/` | React SPA (Product Hunter → Store Architect → Marketing → Analytics → History → Settings) |
| `/docs` | OpenAPI explorer |
| `/api/*` | JSON API — same orchestrator functions the UI uses |

## Documentation

* [docs/architecture.md](docs/architecture.md) — layers, agent contracts, AI
  routing, persistence
* [docs/PRODUCTION_PLAN.md](docs/PRODUCTION_PLAN.md) — historical Phase 0 audit
  of the previous Vercel stack (still explains cost policy in section 11)
* [proposal.md](proposal.md) — original project proposal