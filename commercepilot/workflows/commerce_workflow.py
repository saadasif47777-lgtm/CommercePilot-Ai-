"""Central orchestrator.

Coordinates the four agents through explicit handoffs over the shared project
context. Every step is recorded (agent, status, timestamps, input/output
summaries, errors/warnings) and can be retried individually.

Why not Agno? Verified in this runtime: with no model credentials, Agno's
Agent.run() returns an errored RunOutput with empty content
("OPENAI_API_KEY not set"), so agents built on it cannot produce results.
The orchestrator below therefore uses plain typed Python functions; if an
LLM key is later configured, commercepilot/ai/client.py activates it inside the agents
without changing this workflow.
"""
from __future__ import annotations

import uuid
from typing import Any, Optional

from .. import ai, config
from ..agents import business_analyst, marketing_agent, product_hunter, store_architect
from ..schemas import (
    WORKFLOW_STEPS,
    AgentExecution,
    AnalyzeRequest,
    BusinessBrief,
    CampaignPlan,
    CampaignRequest,
    Product,
    ProjectCreate,
    ResearchRequest,
    ResearchResult,
    StepState,
    StoreDesign,
    StoreEditResponse,
    WebsiteSpec,
    utcnow,
)
from ..storage import ConcurrentUpdate, ProjectStore


class StepFailed(Exception):
    def __init__(self, step: str, message: str):
        super().__init__(message)
        self.step = step
        self.message = message


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _initial_steps() -> dict[str, StepState]:
    return {s["id"]: StepState(id=s["id"], title=s["title"]) for s in WORKFLOW_STEPS}


# --------------------------------------------------------------------------- #
# Example project
# --------------------------------------------------------------------------- #
EXAMPLE_BRIEF = BusinessBrief(
    business_name="Noor Glow",
    industry="Skincare",
    niche="Vitamin C brightening serum for daily glow",
    target_market="Pakistan",
    target_audience="Women 18-34 in urban Pakistan who follow skincare routines on Instagram",
    currency="PKR",
    budget=30000,
    brand_personality="Premium yet warm and trustworthy",
    preferred_price_min=1000,
    preferred_price_max=4000,
    constraints=[],
    notes="Example project for the CommercePilot AI demo. Fictional brand; sample data.",
)


def create_project(store: ProjectStore, payload: ProjectCreate) -> dict[str, Any]:
    if config.production() and payload.example:
        raise StepFailed("brief", "Example projects are disabled in production")
    brief = payload.brief or (EXAMPLE_BRIEF if payload.example else BusinessBrief())
    name = payload.name or (brief.business_name or "New commerce project")
    project = {
        "id": _id("prj"),
        "name": name,
        "created_at": utcnow(),
        "updated_at": utcnow(),
        "brief": brief.model_dump(),
        "research": None,
        "selected_product": None,
        "saved_products": [],
        "rejected_product_ids": [],
        "store_spec": None,
        "campaign": None,
        "analysis": None,
        "report": None,
        "executions": [],
        "steps": {k: v.model_dump() for k, v in _initial_steps().items()},
        "is_example": payload.example,
        "demo_labels": [],
    }
    if payload.example:
        project["demo_labels"].append("Example project brief is fictional (illustrative demo).")
    return store.save(project)


def update_brief(store: ProjectStore, project: dict, brief: BusinessBrief) -> dict:
    """Save an edited brief and mark dependent steps as needing a re-run.

    The UI and the API share this function so the invalidation rules exist in
    exactly one place. Keeping completed steps green after their source data
    changed would let stale results look current.
    """
    for field in ("research", "selected_product", "store_spec", "campaign", "analysis", "report"):
        project[field] = None
    project["analysis_inputs"] = {}
    project["brief"] = brief.model_dump()
    if brief.business_name:
        project["name"] = brief.business_name
        _set_step(store, project, "brief", "success", "Brief updated")
    _set_step(store, project, "research", "pending", "Brief changed - re-run research")
    for step_id in ("select", "store", "campaign", "analyze", "report"):
        _set_step(store, project, step_id, "pending", "Brief changed - re-run to refresh")
    return _save(store, project)


# --------------------------------------------------------------------------- #
# Project migrations (legacy documents gain new fields on load)
# --------------------------------------------------------------------------- #
def _migrate(project: dict) -> dict:
    project.setdefault("saved_products", [])
    project.setdefault("rejected_product_ids", [])
    return project


# --------------------------------------------------------------------------- #
# Execution bookkeeping
# --------------------------------------------------------------------------- #
def _start(store: ProjectStore, project: dict, agent: str, input_summary: str) -> AgentExecution:
    execution = AgentExecution(id=_id("run"), agent=agent, input_summary=input_summary)
    project["executions"].append(execution.model_dump())
    return execution


def _finish(
    store: ProjectStore,
    project: dict,
    execution_id: str,
    status: str,
    output_summary: str = "",
    errors: Optional[list[str]] = None,
    warnings: Optional[list[str]] = None,
) -> None:
    if isinstance(execution_id, AgentExecution):
        execution_id = execution_id.id
    for row in project["executions"]:
        if row["id"] == execution_id:
            row["status"] = status
            row["finished_at"] = utcnow()
            row["output_summary"] = output_summary
            if errors:
                row["errors"] = errors
            if warnings:
                row["warnings"] = warnings
            return


def _set_step(store: ProjectStore, project: dict, step_id: str, status: str, message: str = "") -> None:
    if step_id in project["steps"]:
        project["steps"][step_id].update({"status": status, "message": message, "updated_at": utcnow()})


def _save(store: ProjectStore, project: dict) -> dict:
    project["updated_at"] = utcnow()
    return store.save(project)


def _brief_of(project: dict) -> BusinessBrief:
    return BusinessBrief(**project.get("brief") or {})


# --------------------------------------------------------------------------- #
# Steps
# --------------------------------------------------------------------------- #
def step_validate_brief(store: ProjectStore, project: dict) -> None:
    brief = _brief_of(project)
    problems = []
    if not brief.business_name.strip():
        problems.append("business_name is required")
    if not (brief.niche.strip() or brief.industry.strip()):
        problems.append("niche or industry is required")
    if brief.budget <= 0:
        problems.append("budget must be greater than 0")
    execution = _start(store, project, "Business Brief Validator", f"brief of '{project['name']}'")
    if problems:
        _set_step(store, project, "brief", "error", "; ".join(problems))
        _finish(store, project, execution.id, "error", errors=problems)
        raise StepFailed("brief", "Business brief incomplete: " + "; ".join(problems))
    _set_step(store, project, "brief", "success", f"Brief valid for {brief.business_name}")
    _finish(
        store, project, execution.id, "success",
        output_summary=(
            f"{brief.business_name} | {brief.niche or brief.industry} | {brief.target_market} | "
            f"{brief.currency} {brief.budget:,.0f} budget"
        ),
    )
    _save(store, project)


def step_research(store: ProjectStore, project: dict, request: ResearchRequest) -> ResearchResult:
    request = request.model_copy(update={"currency": (project.get("brief") or {}).get("currency") or request.currency})
    execution = _start(store, project, "Product Hunter", f"mode={request.mode}, niche={request.niche!r}")
    _set_step(store, project, "research", "running", "Searching candidates...")
    try:
        result = product_hunter.run(request)
    except Exception as exc:  # defensive: agent should not raise, but never lose the step
        _set_step(store, project, "research", "error", str(exc))
        _finish(store, project, execution.id, "error", errors=[str(exc)])
        _save(store, project)
        raise StepFailed("research", f"Product Hunter failed: {exc}") from exc
    # Respect the user's rejected products: keep the underlying research run
    # intact (it holds the evidence) but exclude rejected rows from ranking,
    # auto-selection and the UI list. Applies BEFORE persisting, so the saved
    # document matches the ranked list the user sees.
    original_count = len(result.products)
    if project.get("rejected_product_ids"):
        result.products = [p for p in result.products if p.id not in project["rejected_product_ids"]]
        if original_count > len(result.products):
            result.warnings = [
                *(result.warnings or []),
                f"{original_count - len(result.products)} rejected product(s) hidden from this run.",
            ]
    project["selected_product"] = None
    invalidate_outputs(project)
    project["research"] = result.model_dump()
    if not result.products:
        _set_step(store, project, "research", "error", "No candidates found")
        _finish(store, project, execution.id, "error", errors=result.warnings or ["No products found."])
        _save(store, project)
        raise StepFailed("research", "No product candidates found. Try a different niche or mode.")
    if not request.niche and not (project.get("brief") or {}).get("niche"):
        result.warnings = [*(result.warnings or []), "No niche in the brief - results may be generic."]
    if not result.contains_live_results:
        from .. import config as _cfg

        if _cfg.SERPER_API_KEY:
            pass  # had credentials but got nothing live: the provider warning is already attached
        else:
            result.warnings = [
                *(result.warnings or []),
                "Live search returned nothing this run; results below are the labelled sample "
                "catalogue plus keyless DuckDuckGo when available. Real market data needs "
                "SERPER_API_KEY.",
            ]
    _set_step(
        store, project, "research", "success",
        f"{len(result.products)} candidates ({'live+sample' if result.contains_live_results else 'sample'})",
    )
    _finish(
        store, project, execution.id, "success",
        output_summary=f"{len(result.products)} ranked candidates, query '{result.query}'",
        warnings=result.warnings,
    )
    _save(store, project)
    return result


def _resolve_product(project: dict, product_id: Optional[str], auto_select: bool) -> Product:
    research = project.get("research") or {}
    products = [p for p in research.get("products") or [] if p["id"] not in project.get("rejected_product_ids", [])]
    if product_id:
        for row in products:
            if row["id"] == product_id:
                return _usable_product(row)
        # Fallbacks: saved/compared products, manual entries, then any catalogue product
        for row in (project.get("saved_products") or []):
            if row.get("id") == product_id:
                return _usable_product(row)
        for row in ([] if config.production() else product_hunter.load_sample_products()):
            if row.id == product_id:
                return row
        raise StepFailed("select", f"Product '{product_id}' not found in research results, saved products, or the sample catalogue.")
    if project.get("selected_product"):
        return _usable_product(project["selected_product"])
    if auto_select and products:
        return _usable_product(products[0])
    raise StepFailed("select", "No product selected. Select a product or run with auto_select=true.")


def step_select_product(store: ProjectStore, project: dict, product_id: Optional[str], auto_select: bool) -> Product:
    product = _resolve_product(project, product_id, auto_select)
    if product.page_kind == "collection":
        raise StepFailed("select", "This is a collection page. Open the source and import an individual product URL instead.")
    if config.production() and product.is_sample_data:
        raise StepFailed("select", "Sample products cannot be used in production")
    invalidate_outputs(project)
    project["selected_product"] = product.model_dump()
    execution = _start(store, project, "Product Selection", product.title)
    _set_step(
        store, project, "select", "success",
        f"{product.title} selected{' (auto)' if not product_id else ''}",
    )
    _finish(
        store, project, execution.id, "success",
        output_summary=f"{product.title} | score {product.score} | {product.confidence} confidence",
        warnings=["Selected product uses sample/demo data."] if product.is_sample_data else [],
    )
    _save(store, project)
    return product


# --------------------------------------------------------------------------- #
# Product curation: save / reject / manual entry
# --------------------------------------------------------------------------- #
def step_save_product(store: ProjectStore, project: dict, product_id: Optional[str] = None, product: Optional[Product] = None) -> dict:
    """Save a product for later comparison. Works with research rows, the
    sample catalogue, or a user-supplied manual product."""
    execution = _start(store, project, "Product Curation", "save")
    try:
        if product is not None:
            row = product.model_dump()
            row.setdefault("is_sample_data", False)
            if not row.get("score"):
                row["ranking_reason"] = row.get("ranking_reason") or "Manually entered by the user (not machine-ranked)."
                row["confidence"] = row.get("confidence") or "medium"
        else:
            row = _resolve_product(project, product_id, auto_select=True).model_dump()
        saved = project.setdefault("saved_products", [])
        for existing in saved:
            if existing.get("id") == row["id"]:
                existing.update(row)
                _finish(store, project, execution, "success", "updated")
                _set_step(store, project, "select", "pending", "Saved product updated - re-select to make it active")
                return _save(store, project)
        saved.append(row)
        _finish(store, project, execution, "success", f"saved: {row['title'][:60]}")
        return _save(store, project)
    except (StepFailed, KeyError, ValueError) as exc:
        _finish(store, project, execution, "error", str(exc))
        raise


def step_reject_product(store: ProjectStore, project: dict, product_id: str) -> dict:
    """Reject a research candidate: it is excluded from future auto-selects."""
    if not product_id:
        raise StepFailed("select", "product_id required to reject")
    rejected = project.setdefault("rejected_product_ids", [])
    if product_id not in rejected:
        rejected.append(product_id)
    saved = project.get("saved_products") or []
    kept = [p for p in saved if p.get("id") != product_id]
    project["saved_products"] = kept
    if (project.get("selected_product") or {}).get("id") == product_id:
        project["selected_product"] = None
        invalidate_outputs(project)
        _set_step(store, project, "select", "pending", "Selected product rejected")
    research = project.get("research") or {}
    for row in research.get("products") or []:
        if row.get("id") == product_id:
            row["rejected"] = True
    execution = _start(store, project, "Product Curation", f"reject {product_id[:12]}")
    _finish(store, project, execution, "success", "rejected")
    return _save(store, project)


def step_manual_product(store: ProjectStore, project: dict, payload) -> dict:
    """Create a product manually when live research is unavailable.

    The record carries is_sample_data=False and evidence-only-from-user so
    downstream agents do not pretend it was machine-researched.
    """
    execution = _start(store, project, "Product Hunter", "manual entry")

    raw = payload.model_dump()
    raw["id"] = _id("prd")
    raw["description"] = raw.get("description") or raw.get("notes") or ""
    raw["source"] = "manual"
    raw["is_sample_data"] = False
    raw["cost_is_estimate"] = raw.get("observed_cost") is None
    raw["ranking_reason"] = "Manually entered by the user; economics come from user-supplied figures, not web research."
    raw["confidence"] = "medium"
    if raw.get("observed_cost") is not None:
        raw["estimated_cost"] = raw["observed_cost"]
        if raw.get("observed_price"):
            try:
                from ..tools.calculations import gross_margin_pct
                raw["margin_pct"] = gross_margin_pct(raw["observed_price"], raw["observed_cost"])
            except Exception:
                raw["margin_pct"] = None
    tags = [t for t in (raw.get("target_audience") or "").split(",") if t.strip()][:4]
    raw["audience_tags"] = tags
    # evidence: user supplied, clearly labelled
    raw.setdefault("score_breakdown", [])
    row = Product(**raw).model_dump()
    saved = project.setdefault("saved_products", [])
    saved.append(row)
    research = project.get("research")
    if not research:
        project["research"] = {"products": [row], "warnings": ["User-supplied product - no web research was performed for this entry."], "mode": "manual", "generated_at": utcnow(), "sources": [], "query": "Your products", "elapsed_ms": 0, "is_sample_data": False, "contains_live_results": False}
        research = project["research"]
    else:
        research.setdefault("products", []).append(row)
    invalidate_outputs(project)
    project["selected_product"] = row
    _set_step(store, project, "research", "success", "User supplied product; no search performed")
    _set_step(store, project, "select", "success", f"{row['title']} entered manually and selected")
    _finish(store, project, execution, "success", f"manual product: {row['title'][:60]}")
    return _save(store, project)


def step_generate_store(
    store: ProjectStore, project: dict, design: Optional[StoreDesign] = None, extra_instructions: str = ""
) -> WebsiteSpec:
    brief = _brief_of(project)
    product = _resolve_product(project, None, True)
    execution = _start(store, project, "Store Architect", f"storefront for '{product.title}'")
    _set_step(store, project, "store", "running", "Building storefront specification...")
    catalog = _catalog_for(project, product)
    try:
        spec = store_architect.build_spec(brief, product, design, extra_instructions, catalog)
    except Exception as exc:
        _set_step(store, project, "store", "error", str(exc))
        _finish(store, project, execution.id, "error", errors=[str(exc)])
        _save(store, project)
        raise StepFailed("store", f"Store Architect failed: {exc}") from exc
    project["report"] = None
    project["store_spec"] = spec.model_dump()
    _set_step(store, project, "store", "success", f"Storefront generated for {spec.brand_name}")
    _finish(
        store, project, execution.id, "success",
        output_summary=f"{len(spec.sections)} sections | {spec.design.hero_style} hero | {spec.generation_mode} copy",
    )
    _save(store, project)
    return spec


def _catalog_for(project: dict, product: Product) -> list[Product]:
    """Same-category sample products power the storefront catalog (labelled sample)."""
    research = project.get("research") or {}
    rows = [
        Product(**row)
        for row in research.get("products") or []
        if row.get("category") == product.category and row["id"] != product.id and row.get("observed_price")
    ][:6]
    return rows


def step_edit_store(store: ProjectStore, project: dict, prompt: str) -> StoreEditResponse:
    spec_raw = project.get("store_spec")
    if not spec_raw:
        raise StepFailed("store", "No storefront yet - generate the store before editing it.")
    spec = WebsiteSpec(**spec_raw)
    execution = _start(store, project, "Store Architect", f"edit prompt: {prompt[:120]}")
    response = store_architect.apply_edit(spec, prompt)
    project["store_spec"] = response.spec.model_dump()
    _finish(
        store, project, execution.id, "success" if not response.unmatched else "skipped",
        output_summary="; ".join(response.applied_changes) or response.message,
        warnings=[] if not response.unmatched else [response.message],
    )
    _save(store, project)
    return response


def step_generate_campaign(store: ProjectStore, project: dict, request: CampaignRequest) -> CampaignPlan:
    brief = _brief_of(project)
    product = _resolve_product(project, None, True)
    execution = _start(store, project, "Marketing Strategist", f"objective={request.objective}")
    _set_step(store, project, "campaign", "running", "Drafting campaign plan...")
    try:
        plan = marketing_agent.generate(brief, product, request)
    except Exception as exc:
        _set_step(store, project, "campaign", "error", str(exc))
        _finish(store, project, execution.id, "error", errors=[str(exc)])
        _save(store, project)
        raise StepFailed("campaign", f"Marketing Strategist failed: {exc}") from exc
    project["analysis"] = project["report"] = None
    project["campaign"] = plan.model_dump()
    _set_step(store, project, "campaign", "success", f"{plan.objective} plan, {plan.currency} {plan.budget:,.0f}")
    _finish(
        store, project, execution.id, "success",
        output_summary=(
            f"{len(plan.creatives)} creatives | {len(plan.allocations)} allocations "
            f"({'valid' if plan.allocation_valid else 'invalid'})"
        ),
        warnings=plan.risks_and_assumptions[:2],
    )
    _save(store, project)
    return plan


def step_simulate_campaign(store: ProjectStore, project: dict) -> dict:
    """Produce a clearly-labelled DEMO simulation of the drafted campaign.

    The numbers are arithmetic on two stated assumptions (cost per click and
    conversion rate), applied to the plan's own allocation. They are not
    measurements from Meta and are never presented as such.
    """
    if config.production():
        raise StepFailed("campaign", "Simulation is disabled in production; submit measured campaign actuals")
    if not project.get("campaign"):
        raise StepFailed("campaign", "Draft a campaign first - there is nothing to simulate yet.")
    plan = CampaignPlan(**project["campaign"])
    product = project.get("selected_product") or {}
    price = product.get("observed_price")
    cpc, cvr = 45.0, 2.0  # illustrative assumptions, repeated in the response
    rows = []
    total_spend = 0.0
    total_revenue = 0.0
    for allocation in plan.allocations:
        if "reserve" in allocation.label.lower():
            rows.append({
                "label": allocation.label, "spend": 0.0, "clicks": 0,
                "conversions": 0, "revenue": 0.0, "note": "Reserve unspent by design",
            })
            continue
        clicks = allocation.amount / cpc
        conversions = clicks * cvr / 100
        revenue = conversions * price if price else 0.0
        total_spend += allocation.amount
        total_revenue += revenue
        rows.append({
            "label": allocation.label,
            "spend": round(allocation.amount, 2),
            "clicks": round(clicks, 1),
            "conversions": round(conversions, 2),
            "revenue": round(revenue, 2),
        })
    plan.status = "demo_simulated"
    plan.publication = "DEMO - NOT PUBLISHED"
    simulation = {
        "label": "DEMO - NOT PUBLISHED",
        "metric_source": "SAMPLE DATA - computed from illustrative assumptions, not from Meta",
        "assumptions": {"cpc": cpc, "conversion_rate_pct": cvr, "currency": plan.currency},
        "rows": rows,
        "totals": {
            "spend": round(total_spend, 2),
            "revenue": round(total_revenue, 2),
            "roas": round(total_revenue / total_spend, 2) if total_spend else None,
        },
        "disclaimer": (
            "These are simulated numbers produced by applying the stated assumptions to your budget "
            "allocation. They are not measurements from any ad platform."
        ),
    }
    project["analysis"] = project["report"] = None
    project["campaign"] = plan.model_dump()
    project["campaign"]["simulation"] = simulation
    _save(store, project)
    return simulation


def step_analyze(store: ProjectStore, project: dict, request: Optional[AnalyzeRequest] = None) -> dict:
    inputs = dict(project.get("analysis_inputs") or {})
    for key, value in (request or AnalyzeRequest()).model_dump(exclude_unset=True, exclude_none=True).items():
        inputs[key] = {**inputs.get(key, {}), **value} if isinstance(value, dict) else value
    request = AnalyzeRequest(**inputs)
    brief = _brief_of(project)
    product = _resolve_product(project, None, True)
    campaign = CampaignPlan(**project["campaign"]) if project.get("campaign") else None
    execution = _start(store, project, "Business Analyst", f"economics for '{product.title}'")
    _set_step(store, project, "analyze", "running", "Calculating unit economics...")
    try:
        analysis = business_analyst.analyze(brief, product, campaign, request)
    except Exception as exc:
        _set_step(store, project, "analyze", "error", str(exc))
        _finish(store, project, execution.id, "error", errors=[str(exc)])
        raise StepFailed("analyze", f"Business Analyst failed: {exc}") from exc
    if analysis.get("errors"):
        _set_step(store, project, "analyze", "error", "; ".join(analysis["errors"]))
        _finish(store, project, execution.id, "error", errors=analysis["errors"])
        _save(store, project)
        raise StepFailed("analyze", "; ".join(analysis["errors"]))
    project["report"] = None
    project["analysis"] = analysis
    project["analysis_inputs"] = inputs
    unit = analysis["unit_economics"]
    _set_step(
        store, project, "analyze", "success",
        f"margin {unit.get('margin_pct') or unit.get('gross_margin_pct')}% | break-even ROAS {unit.get('break_even_roas')}",
    )
    _finish(
        store, project, execution.id, "success",
        output_summary=(
            f"gross profit/unit {unit['gross_profit_per_unit']} {analysis['currency']} | "
            f"break-even ROAS {unit['break_even_roas']}"
        ),
        warnings=analysis.get("warnings", []),
    )
    _save(store, project)
    return analysis


def step_report(store: ProjectStore, project: dict) -> dict:
    execution = _start(store, project, "Report Builder", "consolidated project report")
    _set_step(store, project, "report", "running", "Compiling report...")
    report = build_report(project)
    project["report"] = report
    _set_step(store, project, "report", "success", "Report ready")
    _finish(store, project, execution.id, "success", output_summary=f"{len(report['sections'])} sections")
    _save(store, project)
    return report


# --------------------------------------------------------------------------- #
# Full workflow
# --------------------------------------------------------------------------- #
def run_full_workflow(
    store: ProjectStore, project_id: str, auto_select: bool = True, mode: str = "live", force: bool = False
) -> dict[str, Any]:
    project = store.get(project_id)
    if not project:
        raise KeyError(project_id)
    results: dict[str, Any] = {"project_id": project_id, "steps": [], "error": None}
    ran_any = False
    brief_ok = project["steps"]["brief"]["status"] == "success" and not force
    try:
        if not brief_ok:
            step_validate_brief(store, project)
        results["steps"].append({"id": "brief", "status": "success"})

        if project["steps"]["research"]["status"] != "success" or force:
            brief = _brief_of(project)
            request = ResearchRequest(
                niche=brief.niche or brief.industry,
                market=brief.target_market,
                audience=brief.target_audience,
                budget=brief.budget,
                price_min=brief.preferred_price_min,
                price_max=brief.preferred_price_max,
                constraints=brief.constraints,
                mode=mode,  # type: ignore[arg-type]
            )
            project = store.get(project_id) or project
            step_research(store, project, request)
            ran_any = True
        results["steps"].append({"id": "research", "status": "success"})

        if not project.get("selected_product"):
            step_select_product(store, project, None, auto_select)
            ran_any = True
            if project["steps"]["select"]["status"] != "success":
                results["steps"].append({"id": "select", "status": "waiting"})
                results["message"] = "Awaiting product selection"
                return results
        results["steps"].append({"id": "select", "status": "success"})

        brief = _brief_of(project)
        if project["steps"]["store"]["status"] != "success" or force:
            step_generate_store(store, project)
            ran_any = True
        results["steps"].append({"id": "store", "status": "success"})

        if project["steps"]["campaign"]["status"] != "success" or force:
            step_generate_campaign(
                store, project, CampaignRequest(objective="sales", budget=brief.budget or 30000)
            )
            ran_any = True
        results["steps"].append({"id": "campaign", "status": "success"})

        if project["steps"]["analyze"]["status"] != "success" or force:
            step_analyze(store, project)
            ran_any = True
        results["steps"].append({"id": "analyze", "status": "success"})

        if ran_any or force or not project.get("report"):
            step_report(store, project)
        results["steps"].append({"id": "report", "status": "success"})
        results["project"] = store.get(project_id)
        return results
    except StepFailed as exc:
        _save(store, project)
        results["error"] = {"step": exc.step, "message": exc.message}
        results["project"] = store.get(project_id)
        return results
    except (KeyError, ConcurrentUpdate):
        raise
    except Exception as exc:  # unexpected - keep the failure visible and retryable
        _save(store, project)
        results["error"] = {"step": "workflow", "message": f"Unexpected error: {exc}"}
        results["project"] = store.get(project_id)
        return results


# --------------------------------------------------------------------------- #
# Consolidated report
# --------------------------------------------------------------------------- #
def build_report(project: dict) -> dict:
    brief = _brief_of(project)
    product = project.get("selected_product") or {}
    research = project.get("research") or {}
    spec = project.get("store_spec") or {}
    campaign = project.get("campaign") or {}
    analysis = project.get("analysis") or {}
    unit = analysis.get("unit_economics") or {}

    sections: list[dict] = []
    sections.append({
        "title": "Business brief",
        "items": [
            f"{brief.business_name} - {brief.industry or brief.niche}",
            f"Target: {brief.target_audience or 'not set'} ({brief.target_market})",
            f"Budget: {brief.currency} {brief.budget:,.0f}",
        ],
    })
    if product:
        sections.append({
            "title": "Selected product",
            "items": [
                product.get("title", ""),
                f"Price {brief.currency} {product.get('observed_price') or '?'} | "
                f"estimated cost {product.get('estimated_cost') or 'unknown'} | "
                f"ranking score {product.get('score')} ({product.get('confidence')} confidence)",
                "Sample/demo data" if product.get("is_sample_data") else ("User-supplied data" if product.get("source") == "manual" else "Live web evidence"),
            ],
        })
    if spec:
        sections.append({
            "title": "Storefront",
            "items": [
                f"{spec.get('brand_name')} - {len(spec.get('sections') or [])} sections",
                f"{spec.get('design', {}).get('hero_style')} hero, {spec.get('design', {}).get('card_style')} cards",
                f"{len(spec.get('edit_history') or [])} design edits applied",
            ],
        })
    if campaign:
        sections.append({
            "title": "Marketing campaign",
            "items": [
                f"{campaign.get('objective')} | {campaign.get('currency')} {campaign.get('budget', 0):,.0f} over {campaign.get('duration_days')} days",
                f"{len(campaign.get('creatives') or [])} creatives, "
                f"{len(campaign.get('allocations') or [])} budget lines ("
                f"{'valid' if campaign.get('allocation_valid') else 'invalid'})",
                campaign.get("publication", "DEMO - NOT PUBLISHED"),
            ],
        })
    if analysis:
        sections.append({
            "title": "Business analysis",
            "items": [
                f"Gross profit/unit: {unit.get('gross_profit_per_unit')} {analysis.get('currency')} "
                f"(margin {unit.get('gross_margin_pct')}%)",
                f"Break-even ROAS: {unit.get('break_even_roas')}",
                f"CPA: {analysis.get('kpis', {}).get('cpa') or 'no campaign data yet'}",
            ],
        })

    next_actions: list[str] = []
    if not product:
        next_actions.append("Run Product Hunter and select a product.")
    elif not spec:
        next_actions.append("Generate the storefront in Store Architect.")
    elif not campaign:
        next_actions.append("Draft the campaign in Marketing Studio.")
    elif not analysis:
        next_actions.append("Run the Business Analyst.")
    else:
        next_actions.append("Validate supplier cost, then run a small live ad test using the campaign draft.")
    if campaign:
        next_actions.append("Meta is not connected - export the draft manually or add credentials in Settings.")

    provenance = []
    if product.get("is_sample_data"):
        provenance.append("Product economics: SAMPLE demo data.")
    if research.get("contains_live_results"):
        provenance.append("Product discovery: live web search results included (source URLs attached).")
    if spec:
        provenance.append("Storefront: generated from a structured spec, not arbitrary AI code.")
    if campaign:
        provenance.append("Campaign: local draft, not published to Meta. Measured metrics exist only when supplied explicitly.")
    provenance.append(f"LLM: {'configured' if ai.available() else 'not configured (deterministic fallback mode)'}.")

    return {
        "project_id": project["id"],
        "project_name": project["name"],
        "generated_at": utcnow(),
        "sections": sections,
        "next_actions": next_actions,
        "data_provenance": provenance,
        "steps": project.get("steps", {}),
        "executions": project.get("executions", [])[-12:],
        "warnings": sorted({
            w
            for row in project.get("executions", [])
            for w in (row.get("warnings") or [])
        })[:10],
    }


def invalidate_outputs(project: dict) -> None:
    project["analysis_inputs"] = {}
    for field in ("store_spec", "campaign", "analysis", "report"):
        project[field] = None
    for step in ("store", "campaign", "analyze", "report"):
        project["steps"][step].update(status="pending", message="Inputs changed; regenerate output")


def _usable_product(row: dict) -> Product:
    product = Product(**row)
    if product.page_kind == "collection":
        raise StepFailed("select", "Open this collection and import an individual product URL; collections cannot be used as products.")
    if config.production() and product.is_sample_data:
        raise StepFailed("select", "Select a real product; legacy sample products are disabled in production")
    return product
