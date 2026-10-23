# Client testing workflow

## Deploy once, configure privately

Use the current branch with the existing Vercel build/rewrite configuration. Set the real server environment values listed in `.env.example`: production mode, model key/provider/model, the PostgreSQL URL, credential encryption key, public HTTPS origin and allowed origin. Redeploy after changing environment values. Old operator username/password variables are no longer used. Do not paste keys into chat or add them to frontend build variables.

The UI and workspace API open without sign-in. Anyone who can reach the deployment shares full workspace access and can trigger provider usage. Google sign-in is not implemented yet. Keep this an isolated client-testing instance without sensitive data, or restrict access through the host/network. This remains one client per deployment. PostgreSQL stores projects, AI usage and verification records; saved Shopify/Meta tokens are encrypted. Integration forms are always visible, including when status retrieval fails.

## Acceptance steps

1. Open the app directly without sign-in. Open Add New Project, complete Business information, and save. Reload and confirm the saved business opens without another prompt.
2. In Product Hunter, enter a specific niche and run research. There should be one research request with your entered values. Review and select a result. Empty live results are an honest empty state, with manual entry and Shopify import available.
3. Enter confirmed selling price and supplier cost in the selected-product economics form. Save. Missing costs stay unknown rather than invented.
4. Generate a storefront, change a supported design setting, and export HTML. It is a design/content draft; checkout is explicitly unavailable until configured in a commerce platform.
5. Generate a campaign plan, change its allocation, and check that totals equal budget. There are no demo simulation actions. No ad is published and no money is spent.
6. Run analytics, enter actual measured figures/overheads, and apply explicit scenario assumptions. Later analysis changes must preserve already-supplied actuals and overheads.
7. On Overview, Prepare remaining results compiles the missing stages and report. It pauses in Products when product selection is required. Project History can reopen or duplicate the real business brief.
8. Open Settings & Integrations. Verify the configured AI model. Connect a canonical Shopify domain with an Admin token, load the catalog, then import and select a product. Imported prices come from the server-fetched catalog; supplier costs must be entered separately.
9. Connect a Meta ad account with ads_read permission. Verify access to that specific account, then read last-30-days account totals. These are account metrics, not automatically product-attributed results.
10. Restart or redeploy. Confirm project history and integration settings persist; verify connections again when their 24-hour verification expires.
11. Open Customer Support. Sync with read_products and read_legal_policies permissions, customize the assistant/contact, save FAQs and test product/policy questions. Enable chat and install the script in the Shopify theme. Confirm the actual storefront widget answers, links to real products/policies, preserves follow-ups and works on mobile. Follow [the complete setup guide](SHOPIFY_SUPPORT.md) for periodic refresh and access boundaries.

## Automated checks and boundaries

Run Python tests, Ruff, frontend build and Playwright as described in README. CI supplies a disposable PostgreSQL service for real persistence and encrypted-credential checks. Browser tests run the actual API, UI and SQLite persistence, replacing only the external model/search/Shopify/Meta transports inside `tests/browser_server.py`. Those test fixtures are not part of production startup.

Live provider verification, client-specific tokens/scopes, deployment configuration and factual review of generated copy require acceptance against your own accounts. Payments, checkout integration, ad publication, OAuth onboarding and multi-tenant user accounts remain separate features.
