# Backend review — 2026-10-23

Source baseline: `1c56c5c659f4d4855e82f6eb29505e1c791e8c77`. Frontend source is excluded from this change. Review covers Python API, agents, workflows, AI services/prompts, schemas, persistence, integrations, calculations, exports, entry points, tests, sample data references and operational documentation/configuration.

## Corrected issues

| Area | Finding and correction |
| --- | --- |
| Access | All projects and integration credentials were writable without authentication. Production now requires workspace authentication and rejects cross-site writes. |
| Runtime | README referenced a nonexistent backend module. Current entry point is `app:app`; production startup requires live model settings and persistent storage. |
| AI | Missing credentials and provider failures silently produced templates; store output was always labeled template. Production now fails explicitly, validates required output fields and labels successful model generation correctly. |
| Research | Default mixed sample/live results and unstable `live-N` IDs. Production coerces mixed requests to live-only; URL-based IDs remain stable; zero-weight scoring no longer divides by zero. |
| Manual products | Broken relative import discarded margins; zero costs were treated as missing; manual source was labeled sample; execution records stayed running. Corrected these paths and preserved user-supplied provenance. |
| Workflow | Changed briefs/products left stale reports, stores and campaigns. Derived artifacts are cleared or invalidated and rejected products cannot be auto-selected. |
| Persistence | Concurrent document updates silently overwrote each other. SQLite transactional revision checks now reject stale updates and deleted-document resurrection. |
| Analytics | Zero inputs were lost, allocations rounded to whole currency units, default simulated assumptions populated production results. Explicit scenarios, zero handling, cent allocation and currency mismatch checks added. |
| Campaigns | Budget-only edits bypassed allocation validation. Every changed budget must balance; simulation is disabled in production; generated campaigns remain unpublished drafts. |
| Integrations | Arbitrary Shopify host accepted secret-bearing requests; API version was old; token appeared in Meta query strings; credential writes were non-atomic. Canonical host restriction, versioned Shopify GraphQL, header-based Meta token and atomic credential files added. |
| Export | All products labeled demo and links accepted arbitrary schemes. Export validates the spec, uses accurate provenance and limits link schemes. |
| Operations | Smoke script only tested demo paths and there was no CI/container path. Added authenticated checks, explicit model probe, backend CI and container configuration. |

## Verified locally

Automated suite and Ruff checks pass. Provider responses are mocked in tests. No frontend files were changed. No model credentials, live Shopify/Meta calls, container build, browser acceptance test, deployment or backup restore were verified in this environment.

## Remaining release gates and product limits

- Configure real model credentials privately, then run the explicit model probe and real client workflow. Live provider account/model compatibility is not established by unit tests.
- Use TLS, reverse-proxy rate/body limits, persistent storage and tested encrypted backups. Run one workspace per client. HTTP Basic is operator access, not account registration or per-user permissions.
- The token-cost guard remains approximate, with concurrency/timeout and unknown-model pricing limitations. Provider-side billing limits are required; no hard spend guarantee is claimed.
- Search is snippet-based discovery. Supplier cost and demand remain unknown unless real evidence is supplied. Generated marketing claims require client review.
- Shopify sync is a bounded read-only page, not a full catalog importer. Meta verification is not ad publication or performance sync.
- Storefronts are drafts/HTML exports, not deployed stores with checkout, payment, stock or order management. The unchanged frontend may still show demo controls; production API rejects them. Browser acceptance and removing those controls need a separate frontend pass.
- Multi-tenant SaaS, managed authentication, durable job queues, PostgreSQL migration, automated ad publication and payment processing are not implemented by this change.
