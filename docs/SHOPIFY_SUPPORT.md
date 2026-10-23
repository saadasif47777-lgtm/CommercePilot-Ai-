# Shopify customer support

CommercePilot's Customer Support page configures a shopper-facing assistant separately from the AI Commerce Assistant that manages business projects. It uses the same `LLM_PROVIDER`, `LLM_MODEL` and server-side key, usage accounting and estimated monthly cap. No extra Groq key, vector database, downloaded embedding model, Streamlit service or imported Flipkart database is required.

## Connect and install

1. Deploy the current repository with the existing production environment: real model configuration, persistent database, credential encryption key on PostgreSQL, and HTTPS. Set `PUBLIC_URL` to the actual API origin. Merchant workspace sign-in is still disabled by the earlier project decision; restrict merchant pages and workspace API routes at your hosting/network layer for confidential operation, allowing the customer widget routes below publicly.
2. Obtain an Admin API access token for the client store with **`read_products` and `read_legal_policies`**. Use your own approved Shopify app/token flow. Storefront API tokens cannot read this Admin API. In Settings & Integrations, connect the canonical `your-store.myshopify.com` domain and token. Environment credentials override saved credentials; remove an obsolete environment token when switching to UI-managed credentials.
3. Open **Customer Support → Sync Shopify knowledge**. Keep the page open while pages are fetched. A failed sync can be resumed with **Resume sync**. Complete snapshots are published atomically, so an incomplete sync cannot replace the previous working catalog. A new sync removes old/deleted products when it finishes.
4. Enter the assistant name, welcome, color and customer support email. Optionally add FAQs about services or product care. Save settings. Test product questions, budget constraints, policies, unknown facts and personal order requests in the preview.
5. Enable storefront chat and save. Copy the installation code. In Shopify's theme editor, add a **Custom Liquid** section to a footer rendered across your store pages, paste the script and save. A theme without Custom Liquid can load the same script once immediately before `</body>` in `layout/theme.liquid`, using Shopify's code editor and a backed-up theme. This is a direct merchant-installed storefront integration; App Store distribution, OAuth installation and Shopify checkout extensions are separate work.
6. Test the actual storefront on desktop and mobile. The synced myshopify.com and primary store origins are allowed automatically. Add any additional exact HTTPS storefront origins in the support page. Do **not** add the storefront to workspace `CORS_ORIGINS`: customer CORS is scoped to the widget routes only.

Shopify policy fields and their required scope are documented in [ShopPolicy](https://shopify.dev/docs/api/admin-graphql/latest/objects/ShopPolicy). Shopify's [theme extension configuration](https://shopify.dev/docs/apps/build/online-store/theme-app-extensions/configuration) documents a future native app-embed installation path; the current copy/paste script does not require deploying a theme extension.

## What is imported

The pinned GraphQL Admin API reads store name, public description, currency, primary domain and configured policy text/links. Products are paginated in batches of 100, up to 10,000 scanned records per sync. Only active products with an actual `onlineStoreUrl` on the connected store are included. Drafts, archived products and unpublished products are excluded. Product data includes title, description, vendor/type/tags, starting and maximum variant prices, currency, Shopify CDN image and the real product link. Policies are converted from HTML to text before retrieval. Private customers, orders, billing details and staff data are not queried.

Products and complete policy text are saved in dedicated SQL tables in the existing PostgreSQL or durable SQLite database. FAQs and branding persist in the same database. No supplied SQLite catalog, generic FAQ answers, personal contact details, `.env` file or credentials from the uploaded project are imported.

## Answering behavior

One bounded model call interprets the current message and the last eight conversation turns as a structured search plan. The server performs parameterized SQL searches with escaped literal terms, currency and starting-price filters. The model cannot execute SQL or invoke merchant actions. Policy retrieval selects relevant excerpts with overlap. A second call writes a concise answer using the retrieved evidence. Each call has a 10-second transport timeout, no transport retries and at most one JSON repair; this bounds the support path for the 60-second serverless function, though infrastructure limits may still cause a retryable timeout.

Product cards and policy links come from stored Shopify records, not model-generated URLs. References outside the retrieved evidence are rejected. Text is rendered as text, with no model HTML execution. Policy answers link to the full policy so customers can review exceptions. Prompt instructions require grounding but do not guarantee factual accuracy; test your store's actual answers before enabling the widget.

Prices are a sync snapshot in the shop's base currency; starting-price filters do not search every individual variant. Current market price, availability, taxes and shipping are confirmed on the product page/checkout. The assistant does not promise stock, invent ratings/discounts or process refunds. Account-specific questions go to the configured support email; it does not read order status or perform cancellations. Email handoff opens the customer's mail app; no ticket or email is sent automatically.

## Refresh and controls

Sync is merchant-triggered, with no webhook or scheduled task provisioned automatically. Re-sync after policy/catalog changes and at least every `SUPPORT_KNOWLEDGE_HOURS` (default 24). Expired knowledge or a different Shopify credential fingerprint pauses chat until another complete sync. A new completed sync expires old chat sessions to prevent stale product references. Disable the widget instantly with the enable switch and save.

Public requests need the current widget ID and an allowed browser Origin. Opaque session tokens are generated by the server, stored only as hashes in SQL, and expire after 24 hours. Only the latest eight text turns are retained; expiration is enforced on access and expired transcripts are deleted when another session starts. The browser holds its token in sessionStorage when available. There is no public transcript-list endpoint. New conversation clears the browser's token; older sessions expire normally. Do not collect sensitive personal/payment information through chat.

Durable SQL counters limit 20 new sessions per observed client IP per hour, 20 messages per session per hour, 60 messages per observed client IP per hour and `SUPPORT_DAILY_MESSAGES` (default 300) customer/preview messages per UTC day for the workspace. The daily guard is checked in addition to the existing estimated AI spending cap. Limits count failed attempts too. Raw IPs are hashed before storage; untrusted forwarding headers are ignored. A shared reverse proxy can make visitors share the IP quota, so test the deployed proxy behavior. Browser origin restrictions and these counters are abuse controls, not customer identity or merchant authorization.

## HTTP routes

| Purpose | Route |
| --- | --- |
| Merchant status/settings | `GET /api/support/status`, `PUT /api/support/settings` |
| Begin/resume paginated snapshot | `POST /api/support/sync/start`, `POST /api/support/sync/next` with `sync_id` |
| Test saved store knowledge | `POST /api/support/preview` with message and bounded history |
| Installation snippet | `GET /api/support/install` |
| Public script | `GET /api/support/widget.js` |
| Public presentation config | `GET /api/support/widget/{widget_id}/config` |
| Start expiring conversation | `POST /api/support/widget/{widget_id}/session` |
| Ask a customer question | `POST /api/support/widget/{widget_id}/chat` with message and session token |

Shopify credentials stay server-side. The public response exposes only branding, support contact, grounded text, approved product cards and source links. Shopify origins cannot use the widget CORS exception to write to workspace APIs. The merchant workspace itself retains its earlier open-access behavior until user authentication is added.

## Acceptance

Automated tests mock external services only and exercise sync pagination, failed/resumed sync, removal of unpublished/deleted records, real SQL filters, source validation, expiry, credential changes, public CORS, separate customer histories, durable limits, PostgreSQL persistence/concurrency and Chromium widget installation across different origins. They do not verify your token scopes, paid model, Shopify theme, hosting access controls or storefront customer experience with real data. Run those checks against your client store after deploying.
