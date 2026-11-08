# November audit implementation

Baseline: `a014a78253b9b10f7226d4ce7be744f856446ab4` (the audited commit).
The older onboarding checkout was fast-forwarded without local source changes.

## Implemented

- Google OpenID Connect authorization-code sign-in via Authlib, verified Google subjects, signed HttpOnly cookies, Secure cookies when authentication is enabled, eight-hour sessions and sign-out. Production defaults to authentication enabled and fails closed when the session key is absent. The client mounts merchant data only after the session check.
- Each Google subject receives an independent merchant workspace. Server-derived namespace prefixes partition projects, encrypted credentials, provider verification, usage records, assistant sessions, support documents, widget sessions and quotas in SQLite and PostgreSQL. There is no client-selectable workspace ID. Existing unnamed legacy tables are preserved, not assigned to the first person who signs in. New tables must be added to the namespace registry in `database.py` and covered by isolation tests.
- Public customer widgets resolve their workspace through a server-owned widget registry created by the authenticated install endpoint. Existing storefront origin, session and quota checks remain in place. Re-copy the embed snippet after migrating a workspace.
- Empty/failed research retains saved research, selection and generated artifacts. Successful reruns retain the current selection and outputs. Failed attempts remain in the execution log.
- GET report is read-only; explicit POST regeneration is used by the frontend. Old `GET ?refresh=true` callers receive 405 with migration guidance.
- Replacement Meta/Shopify credentials are probed before saving; a rejected candidate does not overwrite the previous connection or verification. Authenticated workspaces use encrypted credentials even with SQLite and never inherit the owner's environment Shopify/Meta credentials.
- Selection generations reject stale project loads and late mutation refreshes. Transient load failure retains the last visible project.
- Native delete dialog with explicit Tab wrapping, Escape, initial focus and focus restoration. Container-width-responsive store preview, wrapping header, mobile initial mode, reduced-motion CSS.
- Locally bundled Source Sans 3 replaces the app's Fraunces/Inter pairing; comfortable line heights, restrained weights, existing colors and layout retained.
- Routes load lazily behind loading/error boundaries. Strict TypeScript unused checks enabled. Initial JS entry approximately 418 kB / 135 kB gzip versus the audit's 975 kB / 291 kB gzip. This measures emitted bytes, not observed startup latency.
- Product Hunter preserves server evidence order by default; price sorting is limited to the workspace currency, with missing prices last. Unreachable sample filtering/banner removed.
- Anthropic 529 retry, Retry-After deadline guard, usage-persistence failure logging, request IDs, and a shared 50-second HTTP budget passed to search, page inspection and JSON model calls. Opt-in schema-constrained Claude output via `ANTHROPIC_STRUCTURED_OUTPUT=true`; compatibility mode retains local Pydantic validation and bounded repair.
- Widget completion uses a reservation lease so a late request cannot release a newer request's reservation.

## Activation and migration

1. Back up PostgreSQL and retain the previous deployment. Keep Vercel protection enabled during staging.
2. Create a Google OAuth web client. Register the exact HTTPS redirect URI `PUBLIC_URL/api/auth/callback`. Configure GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, PUBLIC_URL, SESSION_SECRET (at least 32 random characters), DATABASE_URL and CREDENTIAL_ENCRYPTION_KEY (a Fernet key) securely on the backend. Never put these in Vite variables. Do not disable authentication on a client-facing deployment.
3. Keep session and encryption keys stable across replicas. Encryption-key rotation requires re-encrypting saved values; changing it alone makes them unreadable.
4. Run the application in staging and sign in with two real Google accounts. Verify isolation, encrypted integration setup and storefront embeds. Live Google callbacks have not been tested in this environment because credentials are absent.
5. Legacy global projects, credentials and knowledge remain untouched in their original tables. Before moving existing customers, explicitly establish ownership and migrate only the selected records into that verified owner's namespace. No automatic ownership claim is made. A dry-run migration utility is provided below; team membership/invitations are outside this per-account workspace implementation.
6. Rotate the previously exposed Anthropic key in Claude Console, update the deployment securely, verify the replacement, then revoke the old key. This environment has no Claude Console access or injected provider credentials; rotation has not been performed.
7. Use staging keys and test records to verify each Claude module, Shopify scopes and Meta account reporting before rollout. Structured output is opt-in until confirmed against the chosen model. Add exact Shopify store/API destinations to network settings as needed.
8. Roll back the application only behind the existing access gate: the old version has no app-level authorization. Keep a database backup; reverting code does not migrate namespaced records back into legacy tables.

## Remaining activation requirements

Live Google sign-in, provider smoke tests, Anthropic key rotation and provider-side billing limits require operator credentials. Configuration requirements are saved in the cloud draft; they do not configure Vercel or publish this code. No live deployment has been performed.

Model-specific schema support is opt-in until staging validates the configured model. Local tests use controlled responses. Token prices are estimates, so the application allowance is not a guarantee about the provider's invoice. Unknown transport outcomes keep their reservations until month end rather than guessing that a failed call was free.

Existing shared data requires an explicit ownership decision. Use `python -m scripts.migrate_legacy_projects --workspace-id <verified-session-workspace-id> --project-id <id>` to dry-run selected project copies; add `--apply` only after backup and ownership verification. Originals and revisions are preserved. Credentials, conversations and knowledge are deliberately not reassigned automatically. Reconnect integrations and sync under the correct account.

## Additional completed work

- Atomic estimated-spend reservations across replicas and merchant accounts sharing deployment provider keys; per-client usage and module evidence remain isolated.
- Server-owned workflow orchestration, reentrant per-project operation leases and checkpoint-based retries. Concurrent expensive operations return a conflict. Interrupted operations may retain their lease for up to two minutes; completed steps are preserved. A client timeout cannot retract work already accepted by a provider.
- Settings distinguishes connection probes from validated module success/failure, including Market Intelligence. Provider request IDs, model, module and latency are logged without prompt contents. Timeout, authentication, permission and overload errors are distinguished.
- Shopify candidates verify store identity and product scope before activation; Meta candidates verify account identity and reporting access. Catalog/report pagination has explicit continuation controls; later-page Shopify imports re-fetch the corresponding server-side page.
- Shopify sync owns each bounded operation, resumes an existing attempt by default and supports explicit restart. The UI can pause after a committed page. Previous published knowledge remains usable until replacement completes.
- Failed or unreviewed research attempts are stored separately, with previous reviewed results preserved and new source evidence accessible.
- Navigation and cart keyboard focus, Escape and restoration; container-responsive Fit mode plus an explicitly scrollable Desktop frame. Reduced-motion preferences apply to Framer Motion.
- Preview/export use consistent font stacks and visible section content, including catalog entries. Real-product templates do not receive sample shipping, return or review claims. Draft checkout remains disabled.
- Charts distinguish absent values from zero and avoid comparing mixed currencies. Requests have bounded timeouts; obsolete project-selection requests are cancelled.

## Deletion ledger

Reference checks used `rg` plus strict TypeScript and existing backend/browser tests.

| Removed | Evidence / compatibility |
|---|---|
| TopBar navigation wrapper | Navigation was synchronous; removed redundant busy/error state. |
| SimulationChart | No imports/callers; chart dependencies retained for other charts. |
| createBlankProject and BLANK_PROJECT_NAME | No consumers after removing unused destructures; blankBrief retained for Business information. |
| Product Hunter sourceFilter, searchLive/searchSample, sample banner | Sample rows are removed before display; branch unreachable. |
| api.products, api.research, api.assistant, api.storeExportUrl | No frontend callers; corresponding HTTP routes retained. |
| Python model_for and complete_text AI wrappers | No application/test callers; native routing and complete_json retained. |
| Unused imports/bindings in CampaignPlanner, DesignPanel, Layout, WorkflowPanel, HistoryPage, Overview, ProductHunterPage, ui | Compiler diagnostics and reference checks; no behavior removed. |

Preserved the bounded product-page read loop, Shopify support pagination, fixtures,
legacy document migration and database transaction compatibility calls.

## Observed validation

- 285 backend tests passed, including disposable PostgreSQL tests; no skips.
- 14 Chromium browser tests passed, including all 10 routes at 320, 390, 768 and 1440 px, stale selection, keyboard confirmation and the existing mocked full workflow.
- TypeScript strict/unused checks and production build passed; Ruff passed.
- Serverless startup passed against disposable PostgreSQL with authentication explicitly disabled for that startup transport test. Authentication/isolation have separate regression tests.
- Gitleaks 8.24.3 (official release, checksum verified), with output redacted: zero findings across repository history and the built frontend. This does not establish that a key shared outside the repository is safe; rotate that key.
- Tests use provider transports/fixtures. None establishes live Google or provider connectivity.

## Vercel startup recovery

Deployment validation and database initialization failures now leave `/api/auth/session`
available with a safe `setup_error`. The UI explains the missing configuration instead
of reporting an unexplained workspace failure. Merchant routes, OAuth entry/callback,
and health remain unavailable (503) until startup succeeds. Database exception details
and credentials are never returned. This is a diagnostic recovery screen, not a bypass
or a substitute for configuring the deployment.

In Vercel, apply variables to the environment being tested (Preview or Production),
then redeploy. Production validation requires LLM_API_KEY/LLM_MODEL and persistent
DATABASE_URL; sign-in requires SESSION_SECRET, HTTPS PUBLIC_URL and Google client
credentials. Integration storage additionally needs CREDENTIAL_ENCRYPTION_KEY.
Register PUBLIC_URL/api/auth/callback with Google. Use a stable application domain
for PUBLIC_URL. Open the newly created deployment after redeploying; an older
immutable deployment URL continues to serve its old build/configuration.
