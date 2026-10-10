# Manual browser test checklist — CommercePilot AI

Run against the dev server (frontend :3000, backend :8000). Every item below was
exercised over the API during development; this checklist covers the interactive
browser layer.

## 1. First load
- [ ] Sidebar shows all 8 sections; each opens a real section (no dead links).
- [ ] Top bar shows the project selector and a persistent "Demo data labelled" chip.
- [ ] Overview shows the welcome state with **Start a Commerce Project** and **Example Project**.
- [ ] No console errors; page is responsive at 1440px, 1024px, 768px and 390px widths.

## 2. Example project + workflow
- [ ] **Example Project** → Overview shows brief: Noor Glow, Pakistan, PKR 30,000.
- [ ] **Run Full Commerce Workflow** → the 8 steps progress with agent statuses; execution log fills in.
- [ ] Progress bar and per-step badges update live; failures (if any) show a retry for that step only.

## 3. Product Hunter
- [ ] Run research (both modes) → ranked shortlist appears; sample rows labelled *sample data*, live rows *live web result*.
- [ ] **Why this rank?** expands to the scoring breakdown, coverage %, ranking reason and evidence with source links.
- [ ] Filters (category/source), sorting (score/margin/price/confidence) and card/table toggle all work.
- [ ] **Add to Project** marks the product selected; a banner confirms it flows to other agents.

## 4. Store Architect
- [ ] Generate storefront → live preview renders header, hero, product, benefits, reviews (labelled SAMPLE), FAQ, footer.
- [ ] Catalog search + category filter work; empty search shows an empty state.
- [ ] Add to cart → drawer opens; quantity steppers change the subtotal; remove works.
- [ ] Desktop/Mobile toggle re-renders responsively; mobile shows the hamburger nav.
- [ ] Prompts: "Make this store look more luxurious", "Use an editorial split-screen hero", "Improve the mobile layout" → each lists applied changes.
- [ ] Design panel controls (colours, fonts, radius, density, hero/card style, animation) update the preview.
- [ ] **Export HTML** downloads a standalone storefront file that opens correctly.

## 5. Marketing Studio
- [ ] Generate plan → 3 creatives, audience hypotheses, testing strategy, risks appear; Meta shown as not connected.
- [ ] Edit an allocation so it does NOT sum to the budget → save is rejected with a clear message; **Auto-balance** fixes it.
- [ ] **Run simulated execution** → rows appear under a "DEMO — NOT PUBLISHED" banner with the CPC/CVR assumptions stated.
- [ ] Entering real numbers under "Real campaign numbers" updates KPIs (CPA, conversion rate) on Analytics.

## 6. Business Analytics
- [ ] Profitability cards show gross profit/unit, margin, break-even ROAS from stored values.
- [ ] Scenario assumptions (clicks/CVR/CPC) are editable → **Apply assumptions** recalculates charts and numbers.
- [ ] Formula notes explain each calculation, including the gross-profit-only ROAS caveat.
- [ ] Product comparison chart renders when the shortlist has priced products.

## 7. History & Settings
- [ ] History lists projects with step badges; Open/Delete work; delete asks for confirmation.
- [ ] Settings brief edit saves and marks downstream steps pending.
- [ ] Integrations: LLM "not connected (fallback mode)", live search connected, Meta/Shopify "Not connected" with setup instructions.
- [ ] Saving fake Meta credentials: the token is never echoed back and status shows "configured (unverified)".

## 8. Robustness
- [ ] Stop the backend → the UI shows a clear "backend unreachable" error, no white screen.
- [ ] Restart the backend → the project and its results are still there (SQLite).
- [ ] 404 project id in the URL → friendly error, app keeps working.
