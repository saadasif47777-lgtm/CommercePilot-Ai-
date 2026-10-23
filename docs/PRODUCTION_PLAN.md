# CommercePilot AI — Production Plan (Phase 0 audit)

> **Historical document.** This is the audit written before the production
> phases started, kept as a record of what the project looked like and why each
> decision was made. It describes the previous stack (React/TypeScript on
> Vercel). The current application uses React with FastAPI + SQLite
> in one process — see [README](../README.md) and
> [architecture](architecture.md) for the actual implementation. Section 11
> (cost policy and free-tier limits) is still current.

Status: **audit complete, no production code changed**. Every claim below was
verified by reading the repository at commit `deaf75c` and by hitting the live
deployment (<https://commercepilot-ai-one.vercel.app>), not from memory.

---

## 1. Stack (as it exists today)

| Layer | Reality |
|---|---|
| Backend | Python 3.12, FastAPI, 4,443 lines across `backend/` |
| Storage | SQLite, single `projects` table storing each project as a JSON document (`backend/storage.py`). On Vercel `DB_PATH=/tmp/commercepilot.sqlite3` (`api/index.py`) |
| Frontend | React 19 + Vite 7 + TypeScript + Tailwind 4, 4,176 lines, react-router, framer-motion, recharts |
| Hosting | One Vercel project `commerce-pilot1/commercepilot-ai`: static build in `public/` + FastAPI serverless function at `api/index.py`, `/api/*` rewritten to the function |
| CI/CD | none (manual `vercel deploy --prod`); GitHub repo `saadasif47777-lgtm/CommercePilot-Ai-` not yet connected to Vercel for auto-deploy |
| Auth | **none**. No user model, no session, no JWT. Every request sees every project |
| Tests | 111 pytest tests (`tests/`), no E2E |

## 2. Features and their data provenance

| Feature | Where | Real vs demo today |
|---|---|---|
| Product discovery ("Product Hunter") | `backend/agents/product_hunter.py`, `/api/research`, `/api/products` | **Live web search is real** (`ddgs` key-free or Serper when keyed) with source URLs. The default `/api/products` catalogue is **16 hardcoded products** in `backend/data/sample_products.json` (PKR, labelled SAMPLE). Scoring is a documented heuristic over snippets — not a market forecast |
| Manual product entry | `/api/projects/{id}/products/manual`, `manual-compare` | Real user-supplied economics; labelled *manually entered* |
| Storefront generator | `backend/agents/store_architect.py`, `/api/projects/{id}/generate-store|edit-store` | Deterministic templates + optional LLM copy. Produces a **spec/preview and a standalone HTML export** — not a deployed store |
| Campaign planner | `backend/agents/marketing_agent.py`, `/generate-campaign` | Real budget validation + deterministic allocation. LLM can write creative copy when keyed. **Nothing is published**: Meta API is not connected |
| Campaign "simulate" | `/api/projects/{id}/campaign/simulate` | **Fabricated metrics** from fixed assumptions (`cpc=45, cvr=2%`), labelled DEMO - NOT PUBLISHED |
| Profitability analysis | `backend/tools/calculations.py`, `business_analyst.py`, `/analyze` | **Real deterministic arithmetic** (GP/unit, margin %, CPA, CVR, ROAS, break-even ROAS, break-even units, contribution margin). LLM never does math |
| Connected workspace | `/api/projects` (SQLite JSON docs) | Real persistence, but **global and ephemeral on Vercel**: no users, data resets on cold start |
| Assistant | `backend/assistant.py`, `/assistant` | Real intent router executing the actual agent/workflow functions over project state. LLM optional for intent re-ranking |
| History | `/api/projects`, `HistoryPage.tsx` | Real list of stored projects (same global/ephemeral caveats) |
| Settings / integrations | `backend/integrations.py` | Status only. Meta/Shopify tokens are verified against real APIs if provided, but no publishing/sync actions exist |
| Example Project | `POST /api/projects {"example": true}` | **Seeded demo brief** ("Noor Glow", skincare) used by the competition demo |

## 3. Mock / hardcoded / demo inventory (to be removed or made real)

1. `backend/data/sample_products.json` — 16 illustrative products, shown by `/api/products` and in the Product Hunter sample mode.
2. Example Project seeding (`commerce_workflow.py` `EXAMPLE_BRIEF`, `is_example`).
3. Campaign simulation endpoint (fixed CPC/CVR assumptions → fake spend/ROAS).
4. Demo banners in the UI (`App.tsx` footer, demo labels across pages).
5. Product scoring weights and demand/competition labels — heuristic, honest, but only as good as the snippet evidence.

## 4. AI layer — current state

- One module: `backend/llm.py`. OpenAI-compatible `chat/completions` (default `gpt-4o-mini`), **server-side only**, key from `OPENAI_API_KEY`. Never bundled in the frontend.
- Call sites (5): `assistant.py:58` intent classification, `store_architect.py:191` copy, `marketing_agent.py:95` creatives, plus `llm.mode()` exposed by `/api/health` and `/api/integrations/status`.
- Output handling: `json.loads` + ad-hoc key checks. **No schema validation, no retry on malformed output.**
- No streaming, no `maxDuration`, no retries/backoff, no per-request token cap beyond `max_tokens=1200`, no cost logging, no prompt versioning, no prompt-injection defence for search snippets.
- Without a key: deterministic fallback templates, labelled `llm_mode: fallback`.

## 5. Environment variables in use

`OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL`, `LLM_TIMEOUT` · `SERPER_API_KEY`, `WEB_SEARCH_TIMEOUT` · `META_ACCESS_TOKEN`, `META_AD_ACCOUNT_ID`, `META_APP_ID` · `SHOPIFY_SHOP_DOMAIN`, `SHOPIFY_ADMIN_TOKEN` · `DB_PATH`, `CORS_ORIGINS`, `PORT`, `BACKEND_HOST`, `BACKEND_PORT`.

`META_APP_ID` is read into config but never used by any code path.

## 6. Security review (current)

- **No secrets in git history**: pattern scan for `sk-…`, `ghp_…`, `github_pat_…`, `AKIA…`, private keys across all commits → zero hits. Only `.env.example` was ever committed; `.env` and `.vercel` are ignored.
- Secrets are read from env only; integration tokens saved from Settings are written to `backend/.secrets/` — **broken on Vercel** (the deployment directory is read-only; only `/tmp` is writable) and ephemeral where it does work.
- No authn/authz, no per-user isolation, no rate limits, no quotas, no spend cap.
- CORS defaults to `localhost:3000` and is irrelevant in the same-origin deployment; not locked to the production domain.
- Input validation is Pydantic at the route boundary (good); LLM/search output is not sanitised before rendering.
- Stack traces: FastAPI default error responses; no global handler that hides internals.

## 7. Known breakage / risks on the live deployment

| Severity | Issue |
|---|---|
| High | No authentication — any visitor can list, edit and delete every project |
| High | Data loss on cold start: SQLite in `/tmp`, per-instance; `/tmp` may differ between function instances |
| High | Vercel Hobby function limit is 10 s; live search allows 8 s and the LLM allows 20 s → research/generation requests can exceed the limit and 504 |
| Medium | Meta/Shopify credential save writes to a read-only path on Vercel → 500 |
| Medium | No rate limiting or AI spend cap; a public URL with a key is an abuse target |
| Medium | No error monitoring; failures are invisible after deploy |
| Low | `render.yaml` describes the abandoned Render path; `frontend/vercel.json` is unused |
| Low | `verify_deployment.py` still asserts the old split-deployment CORS assumptions |

## 8. Phase plan

**Phase 1 — Real AI layer**
`backend/ai/` service module (provider adapter, timeouts, 2 retries with exponential backoff, per-request token caps, structured JSON output validated by a Pydantic schema with one repair retry), prompts in `backend/ai/prompts/*.v1.md` (versioned), per-user usage logging table, `maxDuration` on the Vercel function, streaming for long generations (SSE) and a background job for anything beyond the limit. Demo/fetched content wrapped as untrusted data in prompts; model output escaped before render. Every non-deterministic claim labelled **AI estimate** with assumptions shown.

**Phase 2 — Real core features**
Discovery (live search + user products only; sample dataset and Example Project removed), storefront (generate → save versions → regenerate/edit → export), campaigns (real allocation + real creative generation; simulation removed; publishing only if a real ad account is connected), analytics (deterministic, unchanged math; LLM explains only), workspace (saved history with edit/regenerate, CSV/PDF export).

**Phase 3 — Accounts and data**
Managed auth (email verification, password reset, Google), Postgres with migrations, `user_id` on every row, authorization enforced server-side on every endpoint, account settings, data export, account deletion.

**Phase 4 — Limits and abuse protection**
Per-user daily/monthly AI quotas, per-IP rate limits, signup bot protection, hard monthly AI spend cap that fails safe (feature degrades, never overspends). Stripe designed, not built.

**Phase 5 — Security**
Secrets only in Vercel env (names documented in `.env.example`), CORS pinned to production origin, input validation everywhere, security headers, generic error responses, dependency audit, credential storage moved to the database (encrypted) instead of the read-only filesystem.

**Phase 6 — Frontend quality**
Loading/empty/error states everywhere, mobile pass, accessibility basics, onboarding, removal of every demo banner and sample row, Privacy/Terms/Contact drafts marked "needs legal review".

**Phase 7 — Reliability**
Health endpoint (extended), structured JSON logs, Sentry, uptime monitor, cost/usage dashboard for the owner.

**Phase 8 — Testing**
Unit tests for business logic, API integration tests with a test database, Playwright E2E (sign up → verify → generate → save → logout → login → data persists), `scripts/verify_deployment.py` rewritten for the real flows and run against production with full output shown.

**Phase 9 — Deployment**
GitHub ↔ Vercel auto-deploy with separate preview/production env vars, GitHub Actions CI, README rewrite, custom-domain instructions.

## 9. Decisions required before Phase 1 (blocking)

1. **LLM provider + key** (set in Vercel env, never in chat).
2. **Auth + database provider** (they ship together in practice).
3. **Rate-limit store** (Redis provider).
4. **Meta / Shopify**: remove the integration UI, or keep it for real accounts you will connect?
5. **Monthly AI spend cap** (a number).
6. **Error monitoring**: enable Sentry now or defer to Phase 7?
7. Billing: confirmed out of scope until you say otherwise.

## 9a. Progress log

### Phase 1 — AI layer: code complete, live in fallback mode

Delivered in commit `9976d9c`:

- `backend/ai/` package: provider-agnostic client (Groq default), retries with
exponential backoff + jitter on timeouts/429/5xx, timeouts, output-token caps,
hard monthly budget (`AI_MONTHLY_CAP_USD`), usage log (`ai_usage` table: prompt
name, tokens, estimated cost, latency, status — never prompt contents).
- Structured output validated with Pydantic (`backend/ai/schemas.py`), with one
repair retry that feeds the validation error back; then an honest failure.
- Prompts are versioned files in `backend/ai/prompts/*.v1.txt`.
- Untrusted input delimited (`<untrusted_*>`) and model text sanitised.
- `maxDuration: 60` set for the Vercel function.
- 8 new unit tests; **119/119 tests pass**. Deployed and verified live
(`/api/health` → `llm_mode: fallback`, workflow 7/7, store copy `generation_mode`
`template` — no false "llm" labels).

**Pending:** real-provider verification requires `LLM_API_KEY` in the Vercel
project (Groq free tier). Until then the app truthfully reports fallback mode.
**Known gap:** streaming (SSE) is not implemented — all current generations are
short (≤800 tokens); the 60 s function limit is set, and streaming will be added
together with the first long-generation feature rather than speculatively.

## 11. Cost policy (owner constraint)

**Paid spend is limited to LLM tokens and, only if ever needed, Vercel Pro.
Everything else must stay inside a free tier.** No credit card is added to any
service unless the owner approves it first.

| Service | Free allowance (checked Oct 2026) | At the limit | Card? |
|---|---|---|---|
| Neon Postgres | 100 CU-hours/project/mo, 1 GB storage/project (20 GB/account), 100 projects, 10 branches | Writes stop at the storage cap; compute already scales to zero after 5 min idle | No |
| Clerk | 50,000 monthly retained users per app; email codes/links + up to 3 social connections (Google) | One-month grace, then upgrade required | No |
| Upstash Redis | 500,000 commands/mo, 250 MB data, 10 GB bandwidth | Notifications; card upgrades the DB (does not preserve free allowances) | No |
| Sentry | 5,000 errors/mo, 1 user, 30-day lookback | Extra events rejected (429) | No (per pricing page) |
| GitHub Actions (private repo) | 2,000 minutes/mo, 500 MB artifacts | Usage blocked without a payment method | No |
| Vercel Hobby (current) | 100 GB transfer, 1M requests, 100 deployments/day | Affected feature pauses until reset | No |
| Vercel Pro (allowed, not needed yet) | $20/mo seat; 60 s → 800 s functions, 1 TB transfer | Billed beyond the $20 credit | Yes |

Sources: Neon docs (plans + 2026-10-02 storage changelog), Clerk pricing, Upstash
pricing/billing, Sentry pricing + quota docs, GitHub Actions billing, Vercel
plan docs.

### Model routing

- `LLM_MODEL` (default `openai/gpt-oss-20b`) handles **every** task: intent
  classification, short rewrites, classification and any future helper calls.
- `LLM_MODEL_STRONG` (empty by default) is used **only** for storefront and ad
  copy generation (`quality=ai.QUALITY_STRONG`). Set it only if the cheap model's
  copy is not good enough; leaving it blank keeps the cheapest configuration.
- No other model is ever called. Every call records its model in `ai_usage`, so
  the split between cheap and strong spend is auditable.

### Spend guards and warnings

- Hard cap: `AI_MONTHLY_CAP_USD` (default 25) blocks calls at 100% and callers
  degrade to clearly-labelled templates.
- Warning: at `AI_BUDGET_WARN_PCT` (default 80%) the server logs a warning line
  and `ai.usage_summary()` reports `warn: true`, `percent_used` and
  `remaining_usd`.
- Other services are monitored through their own dashboards; the owner-facing
  in-app usage/cost dashboard is scheduled for Phase 7.

## 10. Definition of done (mapping)

A stranger signs up → verifies email → uses every feature with real model output
→ returns next day and finds their data → hits limits → nothing sensitive is
exposed; unit + integration + Playwright tests and the rewritten
`verify_deployment.py` pass against production; README explains operation and
maintenance. This document is updated at the end of every phase with actual
results, including anything that could not be made real.
