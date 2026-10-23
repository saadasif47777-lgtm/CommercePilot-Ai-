> Historical demo documentation. For current production behavior and release checks, see [DEPLOYMENT.md](../DEPLOYMENT.md).

# Manual test checklist — CommercePilot AI

Run `python app.py` and open <http://localhost:7860>. Every item below was also
exercised programmatically (the UI callbacks and API are covered by tests), so
this checklist focuses on what a person actually sees.

## 1. First load

- [ ] Header renders with the title, description and four pills; the layout is
      centred and readable at 1440 px and 1024 px widths.
- [ ] Eight tabs are present: Dashboard, Product Hunter, Store Builder,
      Marketing Studio, Business Analytics, Assistant, Projects, Settings.
- [ ] With no projects, the selector is empty and the Dashboard shows the
      welcome text.
- [ ] No traceback or red error box appears in the UI (check the terminal log).

## 2. Example project and workflow

- [ ] **Projects → Create example project** selects "Noor Glow" and shows its
      brief (Pakistan, PKR 30,000).
- [ ] **Dashboard → Run full workflow** ends with "All steps completed" and the
      seven step rows read `success`.
- [ ] The report appears with sections, next actions and data-provenance lines.
- [ ] **Reload the page**: the project and its report are still there.
- [ ] Running the workflow a second time does not duplicate the project.

## 3. Product Hunter

- [ ] **Use project brief** fills niche, audience, market and budget.
- [ ] **Run research** returns a ranked table; the summary says whether live
      results were included and lists source domains when they were.
- [ ] Rows show `sample` or `live/input` in the Source column, and unknown
      values render as `—`, never as invented numbers.
- [ ] Selecting a candidate updates the product panel and the Dashboard.
- [ ] **Save** adds it to the shortlist; **Reject** removes it from the selector.
- [ ] **Enter a product manually** with a title, price and cost: it is saved,
      selected and labelled as your input.

## 4. Store Builder

- [ ] **Generate storefront** renders a preview inside the tab and reports the
      number of sections and the copy mode (template or AI-generated).
- [ ] The preview is a real page: scroll it, check the hero, benefits, reviews
      (labelled sample) and footer.
- [ ] Change the primary colour and radius, regenerate — the preview reflects it.
- [ ] Type "make it more luxurious" → applied changes are listed and the preview
      updates. Type gibberish → an honest "no change applied" message.
- [ ] **Download standalone HTML** produces a file that opens correctly in a
      browser with no server running.

## 5. Marketing Studio

- [ ] **Draft campaign** produces a plan; the allocation table sums to the
      budget and says the allocation is valid.
- [ ] Creative table shows three concepts with angle, headline, primary text
      and CTA.
- [ ] **Run demo simulation** shows rows under a `DEMO — NOT PUBLISHED` heading
      with its CPC and conversion-rate assumptions.
- [ ] The Meta connection is shown as not connected and nothing claims to have
      been published.
- [ ] **Download draft (JSON)** saves the plan.

## 6. Business Analytics

- [ ] **Run analysis** shows unit economics, budget, measured KPIs and three
      scenarios.
- [ ] With no measured campaign data, KPIs read *no data* and a warning explains
      why.
- [ ] Add shipping/packaging/fees → contribution per unit and break-even units
      appear.
- [ ] Gross margin below 40% produces a warning; a loss-making product shows a
      negative profit and no break-even ROAS.
- [ ] **Download analysis (JSON)** saves the result.

## 7. Assistant

- [ ] "Find products for my niche" runs research and reports the count.
- [ ] "Make the store more luxurious" applies a storefront edit.
- [ ] "show me the break-even point" returns real numbers.
- [ ] A multi-step request ("find products, build the store, plan the campaign")
      completes the stages it can and stops at the approval gate with an
      instruction.
- [ ] "tell me a joke" returns the capability list, not a fake answer.
- [ ] **Clear** empties the conversation.

## 8. Projects

- [ ] Editing the brief and saving resets research/store/campaign/analysis to
      pending and says so.
- [ ] Creating a project from a filled form selects it immediately.
- [ ] Deleting requires the confirmation checkbox; without it, the delete is
      refused with a clear message.
- [ ] The list table shows budget, selected product, progress and update time.

## 9. Settings

- [ ] AI usage shows calls, tokens, estimated spend, cap and percentage.
- [ ] Connections list the LLM (fallback without a key), web search, Meta,
      Shopify and storage states with missing-variable names.
- [ ] Saving incomplete Meta credentials is refused with a readable message.
- [ ] After saving credentials, the token never appears in the UI or the page
      source, and status becomes "configured unverified" for a fake token.

## 10. Robustness

- [ ] Clicking an action with no project selected shows "Select a project first",
      not a traceback.
- [ ] Invalid input (negative price, blank product title, price maximum below
      minimum) is rejected with a field-level message.
- [ ] Stopping and restarting the server keeps projects (SQLite).
- [ ] `/api/health` returns `status: ok` and the correct `llm_mode`.
- [ ] `/docs` lists every API route.
