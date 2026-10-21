"""Formatting helpers: domain data in, readable text/table rows out.

Every function here is pure and defensive. Gradio callbacks receive partially
built projects (a brief without research, a campaign without analysis), so
missing values must render as an explicit dash or explanation instead of
raising. That is also what keeps the interface honest: an unknown number is
shown as unknown, never guessed.
"""
from __future__ import annotations

from typing import Any, Iterable, Optional

DASH = "—"

PRODUCT_HEADERS = ["#", "Product", "Category", "Price", "Est. cost", "Margin", "Score", "Confidence", "Source"]
WORKFLOW_HEADERS = ["Step", "Status", "Detail", "Updated"]
ALLOCATION_HEADERS = ["Budget line", "Amount", "Share", "Purpose"]
CREATIVE_HEADERS = ["Concept", "Angle", "Headline", "Primary text", "CTA"]
SCENARIO_HEADERS = ["Scenario", "Clicks", "Conv. rate", "CPC", "Conversions", "Revenue", "Ad cost", "Net profit", "ROAS"]
PROJECT_HEADERS = ["Project", "Brief", "Budget", "Selected product", "Progress", "Updated"]


# --------------------------------------------------------------------------- #
# Small value helpers
# --------------------------------------------------------------------------- #
def money(value: Any, currency: str = "") -> str:
    """Format a number as money, or a dash when it is unknown."""
    if value is None or value == "":
        return DASH
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return DASH
    prefix = f"{currency} " if currency else ""
    text = f"{amount:,.2f}"
    if text.endswith(".00"):
        text = text[:-3]
    return f"{prefix}{text}"


def percent(value: Any, digits: int = 1) -> str:
    if value is None or value == "":
        return DASH
    try:
        return f"{float(value):.{digits}f}%"
    except (TypeError, ValueError):
        return DASH


def number(value: Any, digits: int = 1) -> str:
    if value is None or value == "":
        return DASH
    try:
        return f"{float(value):,.{digits}f}"
    except (TypeError, ValueError):
        return DASH


def _text(value: Any, fallback: str = "") -> str:
    if value is None:
        return fallback
    return str(value)


def _bullets(items: Iterable[Any], empty: str = "_Nothing yet._") -> str:
    rows = [f"- {_text(item)}" for item in items if _text(item).strip()]
    return "\n".join(rows) if rows else empty


def badge(mode: Optional[str]) -> str:
    """Human wording for a generation mode ("template" vs "llm")."""
    return "AI-generated" if mode == "llm" else "Deterministic template"


# --------------------------------------------------------------------------- #
# Brief / project
# --------------------------------------------------------------------------- #
def brief_markdown(brief: dict, currency: str = "PKR") -> str:
    """One compact block describing the business brief."""
    if not brief:
        return "_No brief yet._"
    audience = brief.get("target_audience") or "not specified"
    niche = brief.get("niche") or brief.get("industry") or "not specified"
    return (
        f"**{_text(brief.get('business_name'), 'Untitled business')}** — {niche}\n\n"
        f"- Market: {_text(brief.get('target_market'), 'not set')}\n"
        f"- Audience: {audience}\n"
        f"- Budget: {money(brief.get('budget'), brief.get('currency') or currency)}\n"
        f"- Brand personality: {_text(brief.get('brand_personality'), 'not specified')}"
    )


def header_markdown(project: Optional[dict], llm_mode: str = "fallback") -> str:
    """Status strip under the page title."""
    mode_line = "AI mode: **live model**" if llm_mode == "llm" else "AI mode: **deterministic templates** (no API key)"
    if not project:
        return f"No project selected. Create one from the **Projects** tab. · {mode_line}"
    brief = project.get("brief") or {}
    done = sum(1 for step in (project.get("steps") or {}).values() if step.get("status") == "success")
    total = len(project.get("steps") or {})
    return (
        f"**{_text(project.get('name'), 'Untitled project')}** · "
        f"{_text(brief.get('niche') or brief.get('industry'), 'no niche')} · "
        f"workflow {done}/{total} steps · {mode_line}"
    )


def overview_markdown(project: Optional[dict]) -> str:
    """The dashboard body: what exists, what is missing, what to do next."""
    if not project:
        return (
            "### Welcome\n\n"
            "Create a project to begin. The **Example project** button on the Projects tab "
            "loads a complete demonstration brief so you can explore every feature in one click."
        )

    brief = project.get("brief") or {}
    research = project.get("research") or {}
    product = project.get("selected_product")
    spec = project.get("store_spec")
    campaign = project.get("campaign")
    analysis = project.get("analysis")

    lines = ["### Business brief", brief_markdown(brief)]

    lines.append("\n### Pipeline")
    checks = [
        ("Research", len(research.get("products") or []), "candidates ranked"),
        ("Product", bool(product), product.get("title") if product else ""),
        ("Storefront", bool(spec), f"{len(spec.get('sections') or [])} sections" if spec else ""),
        ("Campaign", bool(campaign), campaign.get("objective", "") if campaign else ""),
        ("Analysis", bool(analysis), "unit economics + scenarios" if analysis else ""),
    ]
    for label, ok, detail in checks:
        mark = "✅" if ok else "⬜"
        suffix = f" — {_text(detail)}" if detail else ""
        lines.append(f"- {mark} **{label}**{suffix}")

    if research.get("warnings"):
        lines.append("\n### Research notes")
        lines.append(_bullets(research["warnings"]))

    next_steps = []
    if not research.get("products"):
        next_steps.append("Run **Product Hunter** to rank candidates for your niche.")
    elif not product:
        next_steps.append("Choose a product in **Product Hunter**, then generate the storefront.")
    if product and not spec:
        next_steps.append("Generate a storefront in **Store Builder**.")
    if spec and not campaign:
        next_steps.append("Draft an ad campaign in **Marketing Studio**.")
    if campaign and not analysis:
        next_steps.append("Run the numbers in **Business Analytics**.")
    if not next_steps:
        next_steps.append("Everything is generated — review the report below and export your assets.")
    lines.append("\n### Suggested next actions")
    lines.append(_bullets(next_steps))

    lines.append("\n> Data provenance: sample products, simulated campaign metrics and template copy are "
                 "labelled as such throughout. Nothing is published to an ad platform.")
    return "\n".join(lines)


def selected_product_markdown(project: Optional[dict]) -> str:
    """Details of the active product, including the ranking explanation."""
    product = (project or {}).get("selected_product")
    if not product:
        return "No product selected yet."
    currency = (project or {}).get("brief", {}).get("currency") or product.get("currency") or "PKR"
    lines = [
        f"### {_text(product.get('title'))}",
        f"- Price: **{money(product.get('observed_price'), currency)}** · "
        f"estimated cost: **{money(product.get('estimated_cost') or product.get('observed_cost'), currency)}**",
        f"- Category: {_text(product.get('category'), 'uncategorised')} · "
        f"score: **{number(product.get('score'))}** ({_text(product.get('confidence'), 'low')} confidence)",
        f"- Source: {'sample dataset' if product.get('is_sample_data') else 'your input / live research'}",
    ]
    if product.get("source_url"):
        lines.append(f"- Source URL: {product['source_url']}")
    if product.get("ranking_reason"):
        lines.append(f"- Why it ranked here: {product['ranking_reason']}")
    signals = product.get("demand_signals") or []
    if signals:
        lines.append("\n**Evidence**")
        lines.extend(f"- {_text(s.get('label'))}: {_text(s.get('value'))} _{_text(s.get('evidence'))}_" for s in signals)
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Tables
# --------------------------------------------------------------------------- #
def workflow_rows(project: Optional[dict]) -> list[list[str]]:
    """Rows for the workflow table (one per orchestration step)."""
    steps = (project or {}).get("steps") or {}
    order = ["brief", "research", "select", "store", "campaign", "analyze", "report"]
    rows: list[list[str]] = []
    for step_id in order:
        step = steps.get(step_id)
        if not step:
            continue
        rows.append([
            _text(step.get("title"), step_id),
            _text(step.get("status"), "pending"),
            _text(step.get("message")),
            _text(step.get("updated_at"))[11:19] or DASH,
        ])
    return rows


def product_rows(products: Iterable[dict]) -> list[list[str]]:
    """Rows for the research results table."""
    rows: list[list[str]] = []
    for index, product in enumerate(products, start=1):
        currency = product.get("currency") or ""
        cost = product.get("estimated_cost")
        if cost is None:
            cost = product.get("observed_cost")
        rows.append([
            str(index),
            _text(product.get("title")),
            _text(product.get("category")),
            money(product.get("observed_price"), currency),
            money(cost, currency),
            percent(product.get("margin_pct")),
            number(product.get("score")),
            _text(product.get("confidence")),
            "sample" if product.get("is_sample_data") else "live/input",
        ])
    return rows


def allocation_rows(campaign: Optional[dict]) -> list[list[str]]:
    campaign = campaign or {}
    currency = campaign.get("currency") or "PKR"
    total = campaign.get("budget") or 0
    rows: list[list[str]] = []
    for item in campaign.get("allocations") or []:
        amount = item.get("amount") or 0
        share = f"{amount / total * 100:.1f}%" if total else DASH
        rows.append([_text(item.get("label")), money(amount, currency), share, _text(item.get("purpose"))])
    return rows


def creative_rows(campaign: Optional[dict]) -> list[list[str]]:
    rows: list[list[str]] = []
    for creative in (campaign or {}).get("creatives") or []:
        rows.append([
            _text(creative.get("name")),
            _text(creative.get("angle")),
            _text(creative.get("headline")),
            _text(creative.get("primary_text")),
            _text(creative.get("cta")),
        ])
    return rows


def scenario_rows(analysis: Optional[dict]) -> list[list[str]]:
    rows: list[list[str]] = []
    for name, scenario in ((analysis or {}).get("scenarios") or {}).items():
        if not scenario.get("available"):
            rows.append([name.title(), DASH, DASH, DASH, DASH, DASH, DASH, DASH,
                         _text(scenario.get("reason"), "unavailable")])
            continue
        assumptions = scenario.get("assumptions") or {}
        rows.append([
            name.title(),
            number(assumptions.get("clicks"), 0),
            percent(assumptions.get("conversion_rate_pct")),
            money(assumptions.get("cpc")),
            number(scenario.get("conversions"), 1),
            money(scenario.get("revenue")),
            money(scenario.get("ad_cost")),
            money(scenario.get("net_profit")),
            number(scenario.get("roas"), 2),
        ])
    return rows


def project_rows(projects: Iterable[dict]) -> list[list[str]]:
    rows: list[list[str]] = []
    for project in projects:
        brief = project.get("brief") or {}
        steps = project.get("steps") or {}
        done = sum(1 for step in steps.values() if step.get("status") == "success")
        rows.append([
            _text(project.get("name")),
            _text(brief.get("business_name") or brief.get("niche")),
            money(brief.get("budget"), brief.get("currency") or "PKR"),
            _text((project.get("selected_product") or {}).get("title"), DASH),
            f"{done}/{len(steps) or 7}",
            _text(project.get("updated_at"))[:16].replace("T", " "),
        ])
    return rows


# --------------------------------------------------------------------------- #
# Research
# --------------------------------------------------------------------------- #
def research_markdown(result: Optional[dict]) -> str:
    if not result:
        return "No research has been run for this project yet."
    products = result.get("products") or []
    lines = [
        f"### {len(products)} candidates",
        f"- Query: `{_text(result.get('query'), 'n/a')}`",
        f"- Mode: {_text(result.get('mode'))} · "
        f"{'live results included' if result.get('contains_live_results') else 'sample dataset only'}",
        f"- Runtime: {number((result.get('elapsed_ms') or 0) / 1000, 2)}s",
    ]
    if result.get("sources"):
        lines.append(f"- Live sources: {', '.join(result['sources'][:8])}")
    if result.get("warnings"):
        lines.append("\n**Notes**")
        lines.append(_bullets(result["warnings"]))
    lines.append("\n_Scoring is a transparent weighted heuristic, not a market forecast. Unknown "
                 "factors are left unknown and the remaining weights are renormalised._")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Storefront
# --------------------------------------------------------------------------- #
def store_markdown(spec: Optional[dict]) -> str:
    if not spec:
        return "No storefront generated yet."
    design = spec.get("design") or {}
    sections = spec.get("sections") or []
    hero = next((s for s in sections if s.get("type") == "hero"), {})
    return "\n".join([
        f"### {_text(spec.get('brand_name'))}",
        f"_{_text(spec.get('tagline'))}_",
        "",
        f"- Hero: **{_text(hero.get('headline'))}**",
        f"- Sections: {', '.join(_text(s.get('type')) for s in sections)}",
        f"- Design: {_text(design.get('hero_style'))} hero · {_text(design.get('card_style'))} cards · "
        f"{_text(design.get('density'))} spacing · {_text(design.get('radius'))}px radius",
        f"- Colours: `{_text(design.get('primary_color'))}` primary, `{_text(design.get('accent_color'))}` accent",
        f"- Copy: **{badge(spec.get('generation_mode'))}**",
        "",
        "_Reviews are labelled sample content. Nothing is published to a real shop._",
    ])


def store_edits_markdown(applied: list[str], message: str = "") -> str:
    if applied:
        return "**Applied changes**\n" + "\n".join(f"- {change}" for change in applied)
    return f"**No change applied.** {message}" if message else "No change applied."


# --------------------------------------------------------------------------- #
# Campaign
# --------------------------------------------------------------------------- #
def campaign_markdown(campaign: Optional[dict]) -> str:
    if not campaign:
        return "No campaign drafted yet."
    currency = campaign.get("currency") or "PKR"
    lines = [
        f"### {_text(campaign.get('objective')).title()} campaign · {money(campaign.get('budget'), currency)}",
        f"_{_text(campaign.get('objective_detail'))}_",
        "",
        f"- Duration: {number(campaign.get('duration_days'), 0)} days",
        f"- Budget allocation valid: **{'yes' if campaign.get('allocation_valid') else 'no'}**",
        f"- Copy: **{badge(campaign.get('generation_mode'))}**",
        f"- Status: {_text(campaign.get('publication'), 'DEMO — NOT PUBLISHED')}",
        f"- Meta connection: {_text(campaign.get('meta_connection'), 'not_connected').replace('_', ' ')}",
    ]
    if campaign.get("audience_hypotheses"):
        lines += ["", "### Audience hypotheses", _bullets(campaign["audience_hypotheses"])]
    if campaign.get("testing_strategy"):
        lines += ["", "### Testing plan", _bullets(campaign["testing_strategy"])]
    if campaign.get("kpis"):
        lines += ["", f"**KPIs:** {', '.join(map(str, campaign['kpis']))}"]
    if campaign.get("risks_and_assumptions"):
        lines += ["", "### Risks and assumptions", _bullets(campaign["risks_and_assumptions"])]
    return "\n".join(lines)


def simulation_markdown(simulation: Optional[dict]) -> str:
    if not simulation:
        return "No simulation has been run."
    totals = simulation.get("totals") or {}
    assumptions = simulation.get("assumptions") or {}
    rows = simulation.get("rows") or []
    table = ["| Line | Spend | Clicks | Conversions | Revenue |", "|---|---|---|---|---|"]
    for row in rows:
        table.append(
            f"| {_text(row.get('label'))} | {money(row.get('spend'))} | {number(row.get('clicks'))} | "
            f"{number(row.get('conversions'), 2)} | {money(row.get('revenue'))} |"
        )
    return "\n".join([
        f"### {_text(simulation.get('label'), 'DEMO — NOT PUBLISHED')}",
        f"_{_text(simulation.get('metric_source'))}_",
        "",
        f"Assumptions: {number(assumptions.get('clicks'), 0)} clicks at {money(assumptions.get('cpc'))} CPC, "
        f"{percent(assumptions.get('conversion_rate_pct'))} conversion rate.",
        "",
        *table,
        "",
        f"**Totals — spend {money(totals.get('spend'))}, revenue {money(totals.get('revenue'))}, "
        f"ROAS {number(totals.get('roas'), 2)}**",
        "",
        f"> {_text(simulation.get('disclaimer'))}",
    ])


# --------------------------------------------------------------------------- #
# Analysis
# --------------------------------------------------------------------------- #
def analysis_markdown(analysis: Optional[dict]) -> str:
    if not analysis:
        return "No analysis has been run yet."
    unit = analysis.get("unit_economics") or {}
    currency = analysis.get("currency") or "PKR"
    kpis = analysis.get("kpis") or {}
    contribution = analysis.get("contribution_economics") or {}
    budget = analysis.get("budget_summary") or {}

    lines = [
        "### Unit economics",
        "| Metric | Value |",
        "|---|---|",
        f"| Selling price | {money(unit.get('selling_price'), currency)} |",
        f"| Product cost | {money(unit.get('product_cost'), currency)}"
        f"{' (estimate)' if unit.get('cost_is_estimate') else ' (your input)'} |",
        f"| Gross profit / unit | {money(unit.get('gross_profit_per_unit'), currency)} |",
        f"| Gross margin | {percent(unit.get('gross_margin_pct'))} |",
        f"| Break-even ROAS | {number(unit.get('break_even_roas'), 2)} |",
        f"| Contribution / unit | {money(contribution.get('contribution_per_unit'), currency)} |",
        f"| Break-even units | {number(contribution.get('break_even_units'), 0)} |",
    ]
    if budget.get("budget"):
        lines += [
            "",
            "### Budget",
            f"- Campaign budget: {money(budget.get('budget'), currency)}",
            f"- Planned spend: {money(budget.get('planned_spend'), currency)} "
            f"({percent(budget.get('utilization_pct'))} of budget)",
            f"- Reserve held: {money(budget.get('reserve_held'), currency)}",
        ]
    lines += [
        "",
        "### Measured KPIs",
        f"- CPA: {money(kpis.get('cpa'), currency)}",
        f"- Conversion rate: {percent(kpis.get('conversion_rate_pct'))}",
        f"- ROAS: {number(kpis.get('roas'), 2)}",
        f"- Source: {_text(kpis.get('source'), 'no data')}",
    ]
    if analysis.get("recommendations"):
        lines += ["", "### Recommendations", _bullets(analysis["recommendations"])]
    if analysis.get("warnings"):
        lines += ["", "### Warnings", _bullets(analysis["warnings"])]
    if analysis.get("errors"):
        lines += ["", "### Problems", _bullets(analysis["errors"])]
    lines += ["", f"_Break-even ROAS uses gross profit only — {_text((analysis.get('formula_notes') or {}).get('break_even_caveat'))}_"]
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Report / settings
# --------------------------------------------------------------------------- #
def report_markdown(report: Optional[dict]) -> str:
    if not report:
        return "Run the workflow or rebuild the report to see the consolidated summary."
    lines = [f"### Project report · {_text(report.get('project_name'))}"]
    for section in report.get("sections") or []:
        lines.append(f"\n**{_text(section.get('title'))}**")
        lines.append(_bullets(section.get("items") or []))
    if report.get("next_actions"):
        lines += ["", "### Next actions", _bullets(report["next_actions"])]
    if report.get("data_provenance"):
        lines += ["", "### Data provenance", _bullets(report["data_provenance"])]
    if report.get("warnings"):
        lines += ["", "### Warnings", _bullets(report["warnings"])]
    return "\n".join(lines)


def integrations_markdown(status: dict) -> str:
    """Render integration status without ever exposing a credential."""
    lines = ["### Connections"]
    for key in ("llm", "web_search", "meta", "shopify", "storage"):
        block = status.get(key) or {}
        state = _text(block.get("status"), "unknown").replace("_", " ")
        lines.append(f"- **{key.replace('_', ' ').title()}** ({_text(block.get('provider'))}): {state}")
        if block.get("detail"):
            lines.append(f"  {_text(block['detail'])}")
        if block.get("model"):
            lines.append(f"  Model: `{_text(block['model'])}`")
        if block.get("missing_configuration"):
            lines.append("  Missing: " + ", ".join(f"`{item}`" for item in block["missing_configuration"]))
    return "\n".join(lines)


def usage_markdown(summary: dict) -> str:
    """AI spend this month against the configured cap."""
    cap = summary.get("monthly_cap_usd") or 0
    lines = [
        "### AI usage this month",
        f"- Calls: **{number(summary.get('calls'), 0)}** · failures: {number(summary.get('failures'), 0)}",
        f"- Tokens: {number(summary.get('input_tokens'), 0)} in / {number(summary.get('output_tokens'), 0)} out",
        f"- Estimated spend: **${number(summary.get('est_cost_usd'), 4)}** of ${number(cap, 2)} cap",
        f"- Budget used: **{percent(summary.get('percent_used'))}**",
    ]
    if summary.get("warn"):
        lines.append("- ⚠️ **Warning threshold reached** — the assistant falls back to templates at 100%.")
    lines += ["", "_Estimates come from token counts and published per-token prices. "
                  "Groq's free tier means real spend is $0 while within its rate limits._"]
    return "\n".join(lines)
