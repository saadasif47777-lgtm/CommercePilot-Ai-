# Architecture

`app.py` mounts the existing React build alongside `commercepilot.api`. HTTP routes validate inputs and invoke `workflows/commerce_workflow.py`; the orchestrator coordinates Product Hunter, Store Architect, Marketing Strategist and Business Analyst. Financial arithmetic lives in `tools/calculations.py` and never uses model output.

## Production behavior

Configuration defaults to production. Startup validates model settings and requires PostgreSQL on ephemeral hosts. The UI and API open directly without authentication; Google sign-in and per-user authorization are future work. Every visitor shares workspace access, including data changes and paid provider actions. `security.py` still rejects cross-origin browser writes, limits declared request sizes and adds response security headers. These guards do not replace authorization; client testing needs an isolated instance or hosting/network access restrictions.

Research accepts live results only in production. Legacy `both` requests are converted to live-only to preserve compatibility with the existing UI. Explicit samples, example projects and campaign simulation are rejected. Search failures return warnings and no fabricated products. Source URL hashes give listings stable identities across result ordering.

Model calls use OpenAI-compatible JSON requests, bounded retries and schema validation with one repair attempt. Production rejects missing keys, invalid/incomplete responses and provider failures. Copy generation is labeled `llm` only after validated output. Demo mode explicitly permits template fallbacks. Storefront production drafts omit fabricated reviews and hard-coded shipping/benefit/FAQ claims.

## Data and workflow

Each project is a JSON document in PostgreSQL or local SQLite. The shared SQL boundary uses pooled PostgreSQL connections and transaction advisory locks, or SQLite write transactions. Both compare document revisions and return HTTP 409 on stale writes. Editing briefs/products clears derived artifacts. Analysis input sections persist so later scenario edits preserve supplied actuals. The UI uses one saved research request and runs workflow stages separately, pausing for product review.

Analysis distinguishes missing measurements, user-entered actuals, and explicitly supplied scenario assumptions. Production never inserts default illustrative CPC or conversion scenarios. Campaigns remain drafts. Standalone HTML exports are schema-validated, escape text and restrict link schemes; they do not contain checkout functionality.

## Integrations and limits

Shopify reads a bounded GraphQL product page with `read_products`, pinned via `SHOPIFY_API_VERSION`, and imports selected server-fetched product records. Only canonical myshopify.com domains receive tokens. PostgreSQL integration tokens are encrypted with Fernet using a server-held key; local credential files remain owner-only. Meta verifies the configured ad account and reads account totals using `ads_read`; it does not buy ads. Verification fingerprints persist, expire after 24 hours, and become invalid when credentials change.

Usage records contain model/prompt identifiers and token counts, not prompt contents. The monthly threshold uses estimated prices and is not a hard billing cap. Provider limits are the authoritative billing control. Production release requires live credential tests, backup/restore verification, TLS and proxy rate/body limits; see DEPLOYMENT.md.
