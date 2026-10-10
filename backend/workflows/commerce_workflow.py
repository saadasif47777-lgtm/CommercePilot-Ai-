"""Central orchestrator.

Coordinates the four agents through explicit handoffs over the shared project
context. Every step is recorded (agent, status, timestamps, input/output
summaries, errors/warnings) and can be retried individually.

Why not Agno? Verified in this runtime: with no model credentials, Agno's
Agent.run() returns an errored RunOutput with empty content
("OPENAI_API_KEY not set"), so agents built on it cannot produce results.
The orchestrator below therefore uses plain typed Python functions; if an
LLM key is later configured, backend/llm.py activates it inside the agents
without changing this workflow.
"""
from __future__ import annotations

import uuid
from typing import Any, Optional

from .. import llm
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
from ..storage import ProjectStore
from ..tools import calculations as calc


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
    execution = _start(store, project, "Product Hunter", f"mode={request.mode}, niche={request.niche!r}")
    _set_step(store, project, "research", "running", "Searching candidates...")
    try:
        result = product_hunter.run(request)
    except Exception as exc:  # defensive: agent should not raise, but never lose the step
        _set_step(store, project, "research", "error", str(exc))
        _finish(store, project, execution.id, "error", errors=[str(exc)])
        _save(store, project)
        raise StepFailed("research", f"Product Hunter failed: {exc}") from exc
    project["research"] = result.model_dump()
    if not result.products:
        _set_step(store, project, "research", "error", "No candidates found")
        _finish(store, project, execution.id, "error", errors=result.warnings or ["No products found."])
        _save(store, project)
        raise StepFailed("research", "No product candidates found. Try a different niche or mode.")
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
    products = research.get("products") or []
    if product_id:
        for row in products:
            if row["id"] == product_id:
                return Product(**row)
        # Fallback: any catalogue product (research runs are limited to the top N)
        for row in product_hunter.load_sample_products():
            if row.id == product_id:
                return row
        raise StepFailed("select", f"Product '{product_id}' not found in research results or the sample catalogue.")
    if project.get("selected_product"):
        return Product(**project["selected_product"])
    if auto_select and products:
        return Product(**products[0])
    raise StepFailed("select", "No product selected. Select a product or run with auto_select=true.")


def step_select_product(store: ProjectStore, project: dict, product_id: Optional[str], auto_select: bool) -> Product:
    product = _resolve_product(project, product_id, auto_select)
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


def step_analyze(store: ProjectStore, project: dict, request: Optional[AnalyzeRequest] = None) -> dict:
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
    project["analysis"] = analysis
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
    store: ProjectStore, project_id: str, auto_select: bool = True, mode: str = "both", force: bool = False
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
    except KeyError:
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
                "Sample/demo data" if product.get("is_sample_data") else "Live web evidence",
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
        provenance.append("Campaign: DEMO - not published to Meta; metrics shown are illustrative.")
    provenance.append(f"LLM: {'configured' if llm.llm_available() else 'not configured (deterministic fallback mode)'}.")

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
