# CommercePilot AI

A commerce planning workspace for product research, AI storefront copy, campaign drafts and deterministic unit economics. Python 3.12, FastAPI, SQLite, and an existing React interface.

**Production mode is the default.** It requires authentication and a real OpenAI-compatible model configuration. Missing keys, provider failures and invalid model output no longer silently produce template results. Production research uses live search only; sample catalogues, example projects, simulated campaign execution and generated customer reviews are disabled.

## Start

```bash
python -m pip install -r requirements.txt
cp .env.example .env
# Set ADMIN_PASSWORD (random, at least 24 characters), LLM_API_KEY and LLM_MODEL.
# Choose the provider/model available in your own provider account.
npm run build
uvicorn app:app --host 0.0.0.0 --port 8000 --workers 1
```

Open the application and enter `ADMIN_USERNAME` / `ADMIN_PASSWORD` in the browser authentication prompt. Serve it through HTTPS before remote access. The API and UI must share an origin. API clients use HTTP Basic authentication; never embed these credentials in frontend code.

For an explicitly local demonstration, set `APP_MODE=demo`. That disables authentication and allows sample data/template fallbacks. Never expose demo mode publicly.

## Real client workflow

1. Create a project with the client's real brief, market, currency and budget.
2. Research with `mode: live`, or enter a real product with its observed selling price and supplier cost. Live search returns source-linked listings, not verified demand or supplier quotes.
3. Select the product. Generate storefront copy and a campaign draft using the configured model.
4. Review generated copy for factual accuracy. Shipping policies, testimonials and unsupported benefits are not automatically added in production.
5. Analyze real prices and costs. Supply actual campaign measurements to compute KPIs. Scenario projections require explicit assumptions in production.
6. Export the storefront draft and project report. Publishing, checkout and ad buying are separate operations that this backend does not implement.

## Scope and isolation

This is a **single-client workspace**, not a multi-tenant SaaS. Every authenticated operator shares all projects and integration settings. Deploy a separate instance, database, credentials and volume for each client. SQLite must be on a persistent local disk. Production startup rejects Vercel and `/tmp` databases; the existing Vercel configuration is demo-only.

Shopify catalog reads use the versioned GraphQL Admin API. Set `SHOPIFY_SHOP_DOMAIN` to the canonical `*.myshopify.com` domain and use a token with `read_products`. Sync returns a bounded page and pagination metadata. Meta integration verifies token access only; it does not publish campaigns or fetch performance metrics.

## Configuration

See [.env.example](.env.example) for all variables. Main settings:

| Variable | Purpose |
| --- | --- |
| `APP_MODE` | `production` (default) or explicitly local `demo` |
| `ADMIN_USERNAME`, `ADMIN_PASSWORD` | Workspace HTTP Basic credentials |
| `LLM_PROVIDER`, `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL` | Model provider configuration |
| `LLM_MODEL_STRONG` | Optional separate model for copy generation |
| `AI_MONTHLY_CAP_USD`, `AI_BUDGET_WARN_PCT` | Estimated usage threshold and warning percentage |
| `SERPER_API_KEY` | Optional paid search; otherwise key-free DDGS |
| `DB_PATH`, `SECRETS_DIR` | Persistent database and integration credential directory |
| `PUBLIC_URL`, `CORS_ORIGINS` | Public origin and explicit browser origin allowlist |
| `SHOPIFY_API_VERSION` | Pinned Shopify API version; review before each version's support ends |

The usage threshold is an estimate, not a billing guarantee: model prices vary, concurrent requests can overshoot, and timed-out requests may still be billed. Set provider-side spending limits too.

## Validation

```bash
python -m pip install -r requirements-dev.txt
python -m pytest
python -m ruff check commercepilot app.py api tests scripts
python scripts/verify_deployment.py --base https://your-host.example
```

Unit tests use an isolated demo environment and mocked provider transports. Production regression tests cover authentication, origin protection, missing keys, model failures, live-only research, stale-write rejection, manual costs and integration host validation. They do not prove that your live credentials work. The deployment probe is read-only by default; `--live-model` explicitly sends a small paid model probe.

See [deployment](DEPLOYMENT.md), [architecture](docs/architecture.md), and [review findings and remaining release gates](docs/BACKEND_REVIEW.md). Historical proposal and production-plan documents describe earlier prototypes, not the current runtime contract.
