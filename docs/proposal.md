# CommercePilot AI — Competition Proposal

**Category:** AI in Retail & E-commerce
**Working title:** CommercePilot AI — a unified AI commerce workspace
**Prototype status:** working end-to-end application (not a mock-up)

---

## 1. Problem

Aspiring online sellers in markets like Pakistan face five disconnected tasks:
product research, store design, campaign planning, unit-economics validation and
reporting. Existing tools cover one slice each, price out of reach of beginners,
and bury the few genuinely useful signals (margin, break-even ROAS, evidence
quality) inside dashboards nobody reads.

**CommercePilot AI** collapses that journey into one workspace where four
specialised agents share a single project context — the output of one agent is
the input of the next, automatically.

## 2. Product summary

1. **Product Hunter** ranks candidates from real web search *and* a labelled
   sample catalogue with a transparent, configurable scoring function
   (margin 30%, demand 25%, competition 20%, audience fit 15%, price fit 10%).
2. **Store Architect** turns the brief + selected product into a structured
   website specification and renders a real, responsive storefront page —
   editable through design controls or plain-English prompts, and exportable as
   a standalone HTML file.
3. **Marketing Strategist** drafts a campaign (objective, 3 creative concepts,
   audience hypotheses, KPIs, risks) and an editable budget allocation that must
   sum exactly to the campaign budget.
4. **Business Analyst** computes unit economics, break-even ROAS, CPA,
   conversion rate and three editable scenarios from the values the other
   agents stored.
5. An **orchestrator** runs the full 7-step workflow with per-step retry and an
   auditable execution log.

## 3. What makes the AI honest (and useful)

* **Evidence over guessing.** Live search rows keep their source URLs; anything
  the evidence doesn't support (cost, demand, competition) stays *unknown* and is
  excluded from the score with the remaining weights renormalised. Every product
  shows its evidence coverage and a plain-English ranking reason.
* **Demo labelled as demo.** Sample catalogue data, simulated campaign metrics
  and template-generated copy are labelled on every surface (persistent badges,
  "DEMO — NOT PUBLISHED" on campaign simulation).
* **Deterministic where it matters.** All money maths is real Python with
  validation (negative inputs rejected, zero denominators handled, missing data
  reported as missing) and 135 automated tests.
* **LLM-optional.** With no API key the app runs in fallback mode and says so;
  configure an OpenAI-compatible key to upgrade copywriting and intent parsing
  without changing the calculation layer.

## 4. Technical approach

* **Backend:** Python 3.12, FastAPI, Pydantic v2 (validation), SQLite
  (persistence across refreshes/restarts), `ddgs` for live search.
* **Interface:** Gradio, written in Python — no JavaScript, no build step, no
  second service to deploy. The same process also exposes the JSON API.
* **AI layer:** an OpenAI-compatible client (Groq free tier by default) with
  schema-validated JSON, one repair retry, retries with backoff, a hard monthly
  spend cap and a per-call usage log. Without a key the app runs labelled
  templates; calculations are always plain Python.
* **Agent framework:** verified in-runtime — Agno returns errored/empty runs
  without model credentials, so the orchestrator uses plain typed Python
  functions with explicit handoffs (documented in `docs/architecture.md`).
* **Security:** server-side credential storage outside the repo, masked in all
  responses, CORS-restricted, strict request validation, no `dangerouslySetInnerHTML`.

## 5. Sample scenario (the demo)

**Noor Glow** — a Pakistani skincare brand selling a vitamin C brightening
serum, PKR 30,000 test budget. The workflow researches candidates (real live
results + labelled samples), selects a serum, generates a matching storefront,
drafts a sales campaign (7,500 testing / 19,500 scaling / 3,000 reserve), and
computes a 1.49 break-even ROAS from the stored price and estimated cost — with
every assumption visible and editable.

## 6. Roadmap beyond the prototype

1. **Meta Marketing API** (credential UI and verification already in place) with
   human-approval gates before anything publishes.
2. **Shopify Admin API** catalog sync (status panel and read-only sync implemented;
   activates when credentials are provided).
3. Supplier-quote import to replace estimated costs with real margins.
4. Paid search API (Serper/Brave) for richer structured product data.
5. Multi-user accounts and team workspaces.

## 7. Team & constraints

Two beginner Python developers, ~48 hours, free-tier tooling. The prototype
deliberately depends only on free components: local models optional, key-free
web search, SQLite, self-hosted stack. Everything in this proposal was built and
tested in the runtime it ships in.
