# Deployment

## Supported production topology

One client workspace, persistent PostgreSQL (or SQLite on a local volume), and HTTPS. For a long-running server, run `uvicorn app:app --host 0.0.0.0 --port 8000 --workers 1` after installing requirements and building the UI. `app:app` serves UI and API together. Vercel serves static UI with the existing API rewrite and requires `DATABASE_URL` for production.

Set `APP_MODE=production`, `LLM_API_KEY`, and the provider/model configuration. Set `PUBLIC_URL` and `CORS_ORIGINS` to the HTTPS origin. The app opens directly without sign-in; old `ADMIN_USERNAME` / `ADMIN_PASSWORD` values are ignored. Google sign-in is future work. Every visitor can read/change all workspace data and trigger paid provider calls. Use an isolated client-testing instance without sensitive data, or restrict reachability at the hosting/network layer. Origin checks are not user authorization.

The reverse proxy must enforce HTTPS, a 1 MB request-body limit, request rate limits, and an upstream timeout appropriate for sequential AI steps (up to several minutes). Do not expose the upstream port directly. Do not use wildcard CORS. Supply provider spending limits because application token-price accounting is approximate.

Mount `DB_PATH` and `SECRETS_DIR` on durable local storage, owned only by the service user. Avoid a shared network filesystem for SQLite WAL. One database is one client; do not share it between unrelated clients. Scale-out/multi-user hosting requires a different architecture and authorization model.

## Container

The Dockerfile builds the frontend and starts one Python worker as a non-root user. Build with `docker build -t commercepilot .`. Mount a volume at `/data`, set `DB_PATH=/data/commercepilot.sqlite3` and `SECRETS_DIR=/data/secrets`, and supply environment secrets. Put the container behind the TLS reverse proxy described above. Container build requires access to the package registries.

## Backups and rollback

Use Python's SQLite backup API (or SQLite `.backup`) to take a consistent database snapshot; do not copy just the main database file while WAL writes are active. Encrypt backups and restrict access: project briefs and saved integration tokens are confidential. Back up the credential directory separately. Before an upgrade, test restore on a separate instance and preserve the previous image. Restored old projects gain `_revision` on their next write. Concurrent stale writes return HTTP 409; reload and retry, rather than blindly resubmitting.

## Release checks

1. Run the complete test suite and lint checks.
2. Start against a fresh persistent volume and confirm the UI and workspace API open without a sign-in prompt, including after reloading.
3. Run `scripts/verify_deployment.py --base https://host`. Add `--live-model` for an explicit model request; this may incur provider usage.
4. In the application, test a real client brief and a manually entered product with verified price/cost. Generate copy, campaign, analysis and report. Confirm outputs survive restart.
5. Verify live search and optional Shopify/Meta credentials using your own accounts. Review generated claims and confirm no demo data appears.
6. Verify proxy rate limits, HTTPS, backup/restore, integration-secret rotation and the intended hosting/network access restrictions.

## Vercel production setup

Set `DATABASE_URL` to the managed PostgreSQL connection URL, with required TLS settings, before deploying. Schema creation is automatic; pooled connections and transactional revision checks apply to projects and usage. Set a stable `CREDENTIAL_ENCRYPTION_KEY` generated with Fernet for encrypted integration tokens; losing or changing that key requires reconnecting accounts. Keep the URL and encryption key in Vercel secrets. No cloud account is provisioned by this repository.

The `/tmp` fallback in `api/index.py` is never used for production persistence; startup rejects it when PostgreSQL is not configured. Existing SQLite data is not migrated automatically. For an existing client database, plan and verify a separate migration before switching storage.

Business setup and connection forms are available in the UI. The workflow uses separate per-stage requests and stops for product selection; provider-side limits and individual request timeouts still apply. CI exercises PostgreSQL and browser flows with test-only provider responses. Real credentials must be verified after deployment.

A static storefront export is a draft, not a functioning checkout. Payments, inventory/order processing, ad publication, multi-tenant accounts and OAuth onboarding are not implemented. Meta supports read-only account reporting; Shopify supports bounded catalog reads and product import.

The customer support widget uses the existing model and database. Set `PUBLIC_URL` to the actual HTTPS API origin so the installation code points at the right deployment. `SUPPORT_KNOWLEDGE_HOURS=24` and `SUPPORT_DAILY_MESSAGES=300` control knowledge expiry and daily customer/preview usage. The Vercel function includes the Python package's prompt and widget assets. Keep the public script and widget config/session/chat routes reachable from approved storefront origins; use hosting/network restrictions for merchant workspace routes while sign-in is deferred. See [Shopify support setup](docs/SHOPIFY_SUPPORT.md).
