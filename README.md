# CommercePilot AI

A commerce workspace for product research, AI storefront copy, campaign drafts and deterministic unit economics. Python 3.12, FastAPI, React, and persistent PostgreSQL or local SQLite.

**Production mode is the default.** It requires a real OpenAI-compatible model configuration. Missing keys, provider failures and invalid model output no longer silently produce template results. Production research uses live search only; sample catalogues, example projects, simulated campaign execution and generated customer reviews are disabled.

## Start

```bash
python -m pip install -r requirements.txt
cp .env.example .env
# Set LLM_API_KEY and LLM_MODEL.
# Choose the provider/model available in your own provider account.
npm run build
uvicorn app:app --host 0.0.0.0 --port 8000 --workers 1
```

Open the application directly; no username or password is required. Google sign-in is planned, not implemented. Anyone who can reach this deployment can read and change the shared workspace and trigger provider usage. Use only an isolated client-testing deployment without sensitive client data; restrict access at the hosting/network layer when needed. Serve it through HTTPS. The API and UI must share an origin.

For an explicitly local demonstration, set `APP_MODE=demo`. That allows sample data/template fallbacks. Never expose demo mode publicly. Removing sign-in does not enable demo mode.

## Real client workflow

1. Open **Business information** or **Add New Project** and enter the client's business, audience, market, currency and budget.
2. In **Product Hunter**, search live sources, enter a product manually, or import one from Shopify through **Settings & Integrations**. Your exact search is saved to your project with one request. Live search returns source-linked listings, not verified demand or supplier quotes.
3. Select the product. Generate storefront copy and a campaign draft using the configured model.
4. Review generated copy for factual accuracy. Shipping policies, testimonials and unsupported benefits are not automatically added in production.
5. Save selling price and supplier cost in Products. Analyze real prices and costs, supply campaign measurements, and enter explicit scenario assumptions. Later analysis updates preserve your existing actuals and overhead inputs.
6. Export the storefront draft and project report. Publishing, checkout and ad buying are separate operations that this backend does not implement.

## AI business guide and budget planner

The **AI Commerce Assistant** answers platform questions before a project exists, remembers business details within an expiring conversation, reviews ideas with balanced strengths/risks and guides users to the right workflow. Share your niche, target location/audience, currency and budget, or use the editable Planning details panel. Whole-business and advertising-only plans are distinct; allocations, contribution margins, acquisition break-even and explicit scenarios are calculated in code. Unknown costs remain unknown. Workspace operations are offered for confirmation and campaign drafts use the calculated test share. See the [assistant guide](docs/AI_ADVISOR.md).

## Shopify customer support

Open **Customer Support** to sync Shopify's published catalog and policies, customize the assistant, add store FAQs, test real model answers and copy the customer chat installation code. The widget suggests products with saved prices and verified store links, answers from published policies, and directs personal order questions to your support contact. It uses the existing model and SQL database. See the [Shopify support setup guide](docs/SHOPIFY_SUPPORT.md) for permissions, installation, refresh behavior and limits.

## Scope and isolation

This is a **single-client workspace**, not a multi-tenant SaaS. All visitors share all projects and integration settings; there is currently no user authorization. Deploy a separate instance, database and integration credentials for each client. Use `DATABASE_URL` for persistent PostgreSQL on Vercel; local SQLite requires a persistent disk. Production still rejects temporary SQLite on serverless hosts.

Shopify uses the GraphQL Admin API: connect a canonical `*.myshopify.com` domain and a token with `read_products`, load up to 50 products, and import a product into the active workspace. Supply its supplier cost after importing. Meta verifies access to the actual ad account with `ads_read` and reads account spend, clicks and impressions. Account totals are not automatically attributed to your selected product. Neither integration publishes ads, themes or checkout.

On PostgreSQL deployments, `CREDENTIAL_ENCRYPTION_KEY` encrypts saved integration tokens. Keep the same key across deployments and backups. Verified status is tied to the configured credentials and expires after 24 hours. Connection forms remain accessible even when status loading fails.

## Vercel client testing

Set `APP_MODE=production`, `LLM_API_KEY`, `LLM_PROVIDER`, `LLM_MODEL`, `DATABASE_URL` (including provider TLS parameters), `CREDENTIAL_ENCRYPTION_KEY`, and your real HTTPS `PUBLIC_URL` / `CORS_ORIGINS` in Vercel environment settings, then redeploy. Old `ADMIN_USERNAME` / `ADMIN_PASSWORD` variables are no longer used and can be removed. Do not paste secrets into chat or commit them. Generate the encryption key with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.

The UI runs workflow stages as separate requests to avoid combining research and multiple model calls into one serverless request. It pauses for product review before generation. Individual provider calls can still time out or reach provider limits, and surface retryable errors.

## Configuration

See [.env.example](.env.example) for all variables. Main settings:

| Variable | Purpose |
| --- | --- |
| `APP_MODE` | `production` (default) or explicitly local `demo` |
| `LLM_PROVIDER`, `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL` | Model provider configuration |
| `LLM_MODEL_STRONG` | Optional separate model for copy generation |
| `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` | Server-only Claude credentials and model (default `claude-sonnet-5-5`) |
| `CLAUDE_MODULES` | Comma-separated Claude routes: `marketing,store_architect,product_hunting`; empty preserves the default provider |
| `ANTHROPIC_TIMEOUT`, `ANTHROPIC_MAX_OUTPUT_TOKENS` | Claude request timeout and output cap (35 seconds / 2400 tokens by default) |
| `AI_MONTHLY_CAP_USD`, `AI_BUDGET_WARN_PCT` | Estimated usage threshold and warning percentage |
| `SERPER_API_KEY` | Optional paid search; otherwise key-free DDGS |
| `DB_PATH`, `SECRETS_DIR` | Persistent database and integration credential directory |
| `DATABASE_URL`, `CREDENTIAL_ENCRYPTION_KEY` | PostgreSQL connection and encryption key for durable integration credentials |
| `PUBLIC_URL`, `CORS_ORIGINS` | Public origin and explicit browser origin allowlist |
| `SHOPIFY_API_VERSION` | Pinned Shopify API version; review before each version's support ends |

Claude module setup: save `ANTHROPIC_API_KEY` as a production secret and deploy. Run `POST /api/integrations/llm/verify?provider=anthropic` to check access before setting `CLAUDE_MODULES=marketing,store_architect,product_hunting` and redeploying. Settings shows each module's model and has a separate Claude verification button. Other modules continue using the default `LLM_*` configuration. Product Hunter uses Claude to review retrieved evidence and suggest verification steps; it never lets the model replace observed prices, supplier costs, demand evidence or calculated scores. Failed AI reviews preserve the retrieved results with a visible warning. Switching models affects new generations; existing saved outputs remain available until regenerated.

The usage threshold is an estimate, not a billing guarantee: model prices vary, concurrent requests can overshoot, and timed-out requests may still be billed. Set provider-side spending limits too.

## Validation

```bash
python -m pip install -r requirements-dev.txt
python -m pytest
python -m ruff check commercepilot app.py api tests scripts
python scripts/verify_deployment.py --base https://your-host.example
npm --prefix frontend run build
cd frontend && npx playwright install chromium && npm run test:e2e
```

Unit tests use an isolated demo environment and mocked provider transports. Production regression tests cover direct workspace access without sign-in, origin protection, missing keys, model failures, live-only research, stale-write rejection, manual costs and integration host validation. They do not prove that your live credentials work. The deployment probe is read-only by default; `--live-model` explicitly sends a small paid model probe.

CI additionally runs real PostgreSQL persistence/encryption checks and Chromium browser tests through business setup, research, pricing, generation, reporting and integration forms. Browser providers are mocked only inside the dedicated test server; production uses configured live services.

See [deployment](DEPLOYMENT.md), [architecture](docs/architecture.md), and [review findings and remaining release gates](docs/BACKEND_REVIEW.md). Historical proposal and production-plan documents describe earlier prototypes, not the current runtime contract.
