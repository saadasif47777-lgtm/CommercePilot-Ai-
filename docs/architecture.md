# Architecture

`app.py` mounts the existing React build alongside `commercepilot.api`. HTTP routes validate inputs and invoke `workflows/commerce_workflow.py`; the orchestrator coordinates Product Hunter, Store Architect, Marketing Strategist and Business Analyst. Financial arithmetic lives in `tools/calculations.py` and never uses model output.

## Production behavior

Configuration defaults to production. Startup validates required model/authentication settings and rejects ephemeral Vercel/temporary storage. `security.py` protects the application with HTTP Basic authentication, rejects cross-origin browser writes and adds response security headers. `/api/health` is public and reveals no project count or secrets. This is workspace-wide operator access, not per-user authorization.

Research accepts live results only in production. Legacy `both` requests are converted to live-only to preserve compatibility with the existing UI. Explicit samples, example projects and campaign simulation are rejected. Search failures return warnings and no fabricated products. Source URL hashes give listings stable identities across result ordering.

Model calls use OpenAI-compatible JSON requests, bounded retries and schema validation with one repair attempt. Production rejects missing keys, invalid/incomplete responses and provider failures. Copy generation is labeled `llm` only after validated output. Demo mode explicitly permits template fallbacks. Storefront production drafts omit fabricated reviews and hard-coded shipping/benefit/FAQ claims.

## Data and workflow

Each project is a JSON document in SQLite. Writes use `BEGIN IMMEDIATE` and compare document revisions. A stale write fails with HTTP 409 instead of overwriting another request. WAL enables readers during writes. Client deployments use one persistent local volume and one worker. Editing a brief or selecting a new product clears derived artifacts; manual products preserve user-supplied zero costs and provenance. Execution records finish with an outcome.

Analysis distinguishes missing measurements, user-entered actuals, and explicitly supplied scenario assumptions. Production never inserts default illustrative CPC or conversion scenarios. Campaigns remain drafts. Standalone HTML exports are schema-validated, escape text and restrict link schemes; they do not contain checkout functionality.

## Integrations and limits

Shopify reads a bounded GraphQL product page with `read_products`, pinned via `SHOPIFY_API_VERSION`. Only canonical myshopify.com domains are accepted before credentials are sent. Credential files are replaced atomically with owner-only permissions. Meta verifies access but does not buy ads. Configured credentials are reported as unverified until an actual verification request is made.

Usage records contain model/prompt identifiers and token counts, not prompt contents. The monthly threshold uses estimated prices and is not a hard billing cap. Provider limits are the authoritative billing control. Production release requires live credential tests, backup/restore verification, TLS and proxy rate/body limits; see DEPLOYMENT.md.
