# Deployment

## Supported production topology

One client workspace, one ASGI worker, a persistent local volume, and a TLS reverse proxy. Run `uvicorn app:app --host 0.0.0.0 --port 8000 --workers 1` after installing requirements and building the existing UI. `app:app` serves the built UI and JSON API from the same origin; `commercepilot.api:app` serves the API alone.

Set `APP_MODE=production`, a random `ADMIN_PASSWORD` with at least 24 characters, `LLM_API_KEY`, and the provider/model configuration. Set `PUBLIC_URL` and `CORS_ORIGINS` to the HTTPS origin. Use HTTP Basic authentication at that origin; the browser prompts once and sends the credentials to the same-origin API. Protect and rotate the password through your secret manager. All authenticated users are operators of the same workspace.

The reverse proxy must enforce HTTPS, a 1 MB request-body limit, request and login rate limits, and an upstream timeout appropriate for sequential AI steps (up to several minutes). Do not expose the upstream port directly. Do not use wildcard CORS. Supply provider spending limits because application token-price accounting is approximate.

Mount `DB_PATH` and `SECRETS_DIR` on durable local storage, owned only by the service user. Avoid a shared network filesystem for SQLite WAL. One database is one client; do not share it between unrelated clients. Scale-out/multi-user hosting requires a different architecture and authorization model.

## Container

The Dockerfile builds the existing frontend unchanged and starts one Python worker as a non-root user. Build with `docker build -t commercepilot .`. Mount a volume at `/data`, set `DB_PATH=/data/commercepilot.sqlite3` and `SECRETS_DIR=/data/secrets`, and supply environment secrets. Put the container behind the TLS reverse proxy described above. Container build requires access to the package registries.

## Backups and rollback

Use Python's SQLite backup API (or SQLite `.backup`) to take a consistent database snapshot; do not copy just the main database file while WAL writes are active. Encrypt backups and restrict access: project briefs and saved integration tokens are confidential. Back up the credential directory separately. Before an upgrade, test restore on a separate instance and preserve the previous image. Restored old projects gain `_revision` on their next write. Concurrent stale writes return HTTP 409; reload and retry, rather than blindly resubmitting.

## Release checks

1. Run the complete test suite and lint checks.
2. Start against a fresh persistent volume and confirm unauthenticated API requests receive 401.
3. Run `scripts/verify_deployment.py --base https://host` with admin credentials in environment variables. Add `--live-model` for an explicit model request; this may incur provider usage.
4. In the application, test a real client brief and a manually entered product with verified price/cost. Generate copy, campaign, analysis and report. Confirm outputs survive restart.
5. Verify live search and optional Shopify/Meta credentials using your own accounts. Review generated claims and confirm no demo data appears.
6. Verify proxy rate limits, HTTPS, backup/restore and operator credential rotation.

## Unsupported production paths

The existing Vercel configuration writes SQLite to `/tmp`. It remains suitable only for an explicitly enabled demo; production startup rejects it. A static storefront export is a draft, not a functioning checkout. This release does not implement payments, inventory/order processing, ad publication, multi-tenant accounts or OAuth credential onboarding. Do not represent those as deployed capabilities.
