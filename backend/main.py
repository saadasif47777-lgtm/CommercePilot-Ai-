"""CommercePilot AI - FastAPI application and route handlers.

Route handlers stay thin: validation is Pydantic, business logic lives in
backend/agents/, backend/workflows/ and backend/tools/.
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import ValidationError

from . import config, integrations, llm
from .agents import product_hunter
from .assistant import handle as assistant_handle
from .schemas import (
    AnalyzeRequest,
    BriefUpdate,
    BusinessBrief,
    CampaignDraftUpdate,
    CampaignPlan,
    CampaignRequest,
    ManualProductInput,
    MetaCredentials,
    Product,
    ProjectCreate,
    ResearchRequest,
    ResearchResult,
    ShopifyCredentials,
    StoreDesign,
    StoreEditRequest,
    WorkflowRequest,
)
from .storage import ProjectStore
from .workflows import commerce_workflow as wf

app = FastAPI(
    title="CommercePilot AI API",
    version="1.0.0",
    description="AI-powered e-commerce workspace backend (competition prototype).",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS or ["http://localhost:3000"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

store = ProjectStore(config.DB_PATH)


def _project_or_404(project_id: str) -> dict[str, Any]:
    project = store.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found.")
    return project


def _run_step(project_id: str, fn, *args, **kwargs):
    """Execute an orchestrator step, translating failures into HTTP errors."""
    project = _project_or_404(project_id)
    try:
        return fn(store, project, *args, **kwargs)
    except wf.StepFailed as exc:
        raise HTTPException(status_code=422, detail={"step": exc.step, "message": exc.message}) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Product '{exc}' not found.") from exc


# --------------------------------------------------------------------------- #
# Health & sample data
# --------------------------------------------------------------------------- #
@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "commercepilot-ai",
        "version": "1.0.0",
        "llm_mode": llm.mode(),
        "projects": store.count(),
    }


@app.get("/api/products")
def list_products(category: Optional[str] = None) -> dict:
    """Local sample catalog (DEMO DATA - clearly labelled in each record)."""
    rows = product_hunter.load_sample_products()
    if category:
        rows = [p for p in rows if p.category.lower() == category.lower()]
    return {
        "is_sample_data": True,
        "disclaimer": "DEMO DATA - illustrative products, prices and costs. Not real market data.",
        "count": len(rows),
        "products": [p.model_dump() for p in rows],
    }


# --------------------------------------------------------------------------- #
# Research (Agent A)
# --------------------------------------------------------------------------- #
@app.post("/api/research", response_model=ResearchResult)
def research(request: ResearchRequest) -> ResearchResult:
    try:
        return product_hunter.run(request)
    except Exception as exc:  # agent never should, but surface a real error if it does
        raise HTTPException(status_code=502, detail=f"Research failed: {exc}") from exc


# --------------------------------------------------------------------------- #
# Projects
# --------------------------------------------------------------------------- #
@app.post("/api/projects", status_code=201)
def create_project(payload: ProjectCreate) -> dict:
    if payload.example:
        return wf.create_project(store, ProjectCreate(example=True, name=payload.name))
    if payload.brief is None:
        payload.brief = BusinessBrief()
    if not payload.brief.business_name.strip():
        raise HTTPException(status_code=422, detail="business_name is required (or pass example=true).")
    return wf.create_project(store, payload)


@app.get("/api/projects")
def list_projects() -> dict:
    rows = []
    for p in store.list():
        rows.append({
            "id": p["id"],
            "name": p.get("name"),
            "created_at": p.get("created_at"),
            "updated_at": p.get("updated_at"),
            "is_example": p.get("is_example", False),
            "brief": p.get("brief"),
            "selected_product": (p.get("selected_product") or {}).get("title"),
            "steps": {k: v.get("status") for k, v in (p.get("steps") or {}).items()},
            "has_campaign": bool(p.get("campaign")),
            "has_analysis": bool(p.get("analysis")),
        })
    return {"count": len(rows), "projects": rows}


@app.get("/api/projects/{project_id}")
def get_project(project_id: str) -> dict:
    return _project_or_404(project_id)


@app.delete("/api/projects/{project_id}")
def delete_project(project_id: str) -> dict:
    if not store.delete(project_id):
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found.")
    return {"deleted": True, "id": project_id}


@app.post("/api/projects/{project_id}/brief")
def update_brief(project_id: str, payload: BriefUpdate) -> dict:
    project = _project_or_404(project_id)
    project["brief"] = payload.brief.model_dump()
    # A changed brief invalidates downstream steps so nothing looks stale-but-green
    if payload.brief.business_name:
        project["steps"]["brief"] = {"id": "brief", "title": "Validate business brief", "status": "success", "message": "Brief updated", "updated_at": wf.utcnow()}
    wf._set_step(store, project, "research", "pending", "Brief changed - re-run research")
    for step_id in ("select", "store", "campaign", "analyze", "report"):
        wf._set_step(store, project, step_id, "pending", "Brief changed - re-run to refresh")
    return wf._save(store, project)


@app.post("/api/projects/{project_id}/select-product")
def select_product(project_id: str, payload: dict = Body(...)) -> dict:
    project = _project_or_404(project_id)
    product_id = payload.get("product_id")
    product_payload = payload.get("product")
    try:
        if product_id:
            product = wf.step_select_product(store, project, product_id, auto_select=True)
        elif product_payload:
            product = wf.step_select_product(store, project, None, auto_select=True)
            project = _project_or_404(project_id)
            from .schemas import Product

            project["selected_product"] = Product(**product_payload).model_dump()
            wf._set_step(store, project, "select", "success", f"{product_payload.get('title')} selected")
            wf._save(store, project)
        else:
            raise HTTPException(status_code=422, detail="Provide product_id or a full product object.")
    except wf.StepFailed as exc:
        raise HTTPException(status_code=422, detail={"step": exc.step, "message": exc.message}) from exc
    return _project_or_404(project_id)


@app.post("/api/projects/{project_id}/reset-product")
def reset_product(project_id: str) -> dict:
    project = _project_or_404(project_id)
    project["selected_product"] = None
    for step_id in ("select", "store", "campaign", "analyze", "report"):
        wf._set_step(store, project, step_id, "pending", "Product reset")
    return wf._save(store, project)


# --------------------------------------------------------------------------- #
# Product curation: manual entry / save / reject
# --------------------------------------------------------------------------- #
@app.post("/api/projects/{project_id}/products/manual")
def add_manual_product(project_id: str, payload: ManualProductInput) -> dict:
    """Manually enter a product when live research is unavailable.

    The record is clearly labelled 'manually entered' everywhere; downstream
    agents treat its economics as user-provided data, never as web-verified.
    """
    project = _project_or_404(project_id)
    result = wf.step_manual_product(store, project, payload)
    return {**result, "manual_entry": True}


@app.get("/api/projects/{project_id}/products/saved")
def list_saved_products(project_id: str) -> dict:
    project = _project_or_404(project_id)
    saved = project.get("saved_products") or []
    rejected = project.get("rejected_product_ids") or []
    return {
        "count": len(saved),
        "rejected_count": len(rejected),
        "products": saved,
        "rejected_product_ids": rejected,
    }


@app.post("/api/projects/{project_id}/products/{product_id}/save")
def save_product(project_id: str, product_id: str) -> dict:
    project = _project_or_404(project_id)
    try:
        return wf.step_save_product(store, project, product_id=product_id)
    except wf.StepFailed as exc:
        raise HTTPException(status_code=422, detail={"step": exc.step, "message": exc.message}) from exc


@app.post("/api/projects/{project_id}/products/{product_id}/reject")
def reject_product(project_id: str, product_id: str) -> dict:
    project = _project_or_404(project_id)
    return wf.step_reject_product(store, project, product_id)


@app.post("/api/products/manual-compare")
def manual_compare(payload: ManualProductInput) -> dict:
    """Score a manually entered product WITHOUT saving it: an economics preview."""
    from .agents import business_analyst as analyst

    import uuid as _uuid

    data = payload.model_dump()
    preview = Product(id=f"preview-{_uuid.uuid4().hex[:8]}", source="sample", **data)
    result = analyst.analyze(BusinessBrief(currency=data["currency"]), preview)
    return {
        "inputs": payload.model_dump(),
        "analysis": {"unit_economics": result["unit_economics"], "contribution_economics": result["contribution_economics"], "warnings": result["warnings"]},
        "disclaimer": "Preview only - this compares your supplied numbers; nothing is saved.",
    }


# --------------------------------------------------------------------------- #
# Store Architect (Agent B)
# --------------------------------------------------------------------------- #
@app.post("/api/projects/{project_id}/generate-store")
def generate_store(project_id: str, payload: Optional[dict] = Body(default=None)) -> dict:
    payload = payload or {}
    try:
        design = StoreDesign(**payload["design"]) if payload.get("design") else None
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid design config: {exc.errors()[0].get('msg')}") from exc
    spec = _run_step(project_id, wf.step_generate_store, design, payload.get("extra_instructions", ""))
    return _project_or_404(project_id)["store_spec"]


@app.post("/api/projects/{project_id}/edit-store")
def edit_store(project_id: str, payload: StoreEditRequest) -> dict:
    response = _run_step(project_id, wf.step_edit_store, payload.prompt)
    return response.model_dump()


@app.post("/api/projects/{project_id}/reset-store")
def reset_store(project_id: str) -> dict:
    project = _project_or_404(project_id)
    if project.get("selected_product"):
        spec = wf.step_generate_store(store, project)
        return {"reset": True, "spec": spec.model_dump()}
    project["store_spec"] = None
    wf._set_step(store, project, "store", "pending", "Store reset")
    return wf._save(store, project)


@app.get("/api/projects/{project_id}/store/export", response_class=PlainTextResponse)
def export_store(project_id: str) -> str:
    """Export the generated storefront as a standalone HTML file."""
    from .store_export import render_standalone_html

    project = _project_or_404(project_id)
    if not project.get("store_spec"):
        raise HTTPException(status_code=404, detail="No storefront generated yet.")
    return render_standalone_html(project["store_spec"])


# --------------------------------------------------------------------------- #
# Marketing Strategist (Agent C)
# --------------------------------------------------------------------------- #
@app.post("/api/projects/{project_id}/generate-campaign")
def generate_campaign(project_id: str, payload: Optional[CampaignRequest] = None) -> dict:
    payload = payload or CampaignRequest()
    plan = _run_step(project_id, wf.step_generate_campaign, payload)
    return _project_or_404(project_id)["campaign"]


@app.put("/api/projects/{project_id}/campaign")
def update_campaign(project_id: str, payload: CampaignDraftUpdate) -> dict:
    project = _project_or_404(project_id)
    if not project.get("campaign"):
        raise HTTPException(status_code=404, detail="No campaign draft yet - generate one first.")
    plan = CampaignPlan(**project["campaign"])
    data = plan.model_dump()
    if payload.objective is not None:
        data["objective"] = payload.objective
    if payload.duration_days is not None:
        data["duration_days"] = payload.duration_days
    if payload.budget is not None:
        data["budget"] = payload.budget
    if payload.status is not None:
        data["status"] = payload.status
    if payload.allocations is not None:
        from .tools import calculations as calc

        try:
            validated = calc.validate_allocation(
                data["budget"], [a.model_dump() for a in payload.allocations]
            )
        except calc.CalculationError as exc:
            raise HTTPException(status_code=422, detail=f"Invalid budget allocation: {exc}") from exc
        data["allocations"] = [
            {"label": a["label"], "amount": a["amount"], "purpose": a["purpose"]}
            for a in validated["allocations"]
        ]
        data["allocation_valid"] = True
    project["campaign"] = data
    wf._save(store, project)
    return data


@app.post("/api/projects/{project_id}/campaign/simulate")
def simulate_campaign(project_id: str) -> dict:
    """Simulated campaign execution. Clearly labelled DEMO - NOT PUBLISHED.

    Sample metrics are computed deterministically from the plan's own
    assumptions (click cost and conversion rate below), never random.
    """
    project = _project_or_404(project_id)
    if not project.get("campaign"):
        raise HTTPException(status_code=404, detail="No campaign draft yet - generate one first.")
    plan = CampaignPlan(**project["campaign"])
    product = project.get("selected_product") or {}
    price = product.get("observed_price")
    cpc, cvr = 45.0, 2.0  # illustrative assumptions, stated in the response
    rows = []
    total_spend = 0.0
    total_revenue = 0.0
    for a in plan.allocations:
        if "reserve" in a.label.lower():
            rows.append({"label": a.label, "spend": 0.0, "clicks": 0, "conversions": 0, "revenue": 0.0, "note": "Reserve unspent by design"})
            continue
        clicks = a.amount / cpc
        conversions = clicks * cvr / 100
        revenue = conversions * price if price else 0.0
        total_spend += a.amount
        total_revenue += revenue
        rows.append({
            "label": a.label,
            "spend": round(a.amount, 2),
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
    project["campaign"] = plan.model_dump()
    project["campaign"]["simulation"] = simulation
    wf._save(store, project)
    return simulation


# --------------------------------------------------------------------------- #
# Business Analyst (Agent D)
# --------------------------------------------------------------------------- #
@app.post("/api/projects/{project_id}/analyze")
def analyze(project_id: str, payload: Optional[AnalyzeRequest] = None) -> dict:
    return _run_step(project_id, wf.step_analyze, payload or AnalyzeRequest())


# --------------------------------------------------------------------------- #
# Workflow & report
# --------------------------------------------------------------------------- #
@app.post("/api/projects/{project_id}/run-workflow")
def run_workflow(project_id: str, payload: Optional[WorkflowRequest] = None) -> dict:
    payload = payload or WorkflowRequest()
    _project_or_404(project_id)
    try:
        return wf.run_full_workflow(
            store, project_id, auto_select=payload.auto_select, mode=payload.mode, force=payload.force
        )
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found.")


@app.get("/api/projects/{project_id}/report")
def get_report(project_id: str, refresh: bool = Query(False)) -> dict:
    project = _project_or_404(project_id)
    if refresh or not project.get("report"):
        return wf.step_report(store, project)
    return project["report"]


@app.post("/api/projects/{project_id}/assistant")
def assistant(project_id: str, payload: dict = Body(...)) -> dict:
    message = str(payload.get("message", "")).strip()
    if not message:
        raise HTTPException(status_code=422, detail="message is required")
    if len(message) > 1000:
        raise HTTPException(status_code=422, detail="message too long (max 1000 chars)")
    return assistant_handle(store, project_id, message)


# --------------------------------------------------------------------------- #
# Integrations
# --------------------------------------------------------------------------- #
@app.get("/api/integrations/status")
def integration_status() -> dict:
    return integrations.all_status()


@app.post("/api/integrations/meta/credentials")
def save_meta_credentials(payload: MetaCredentials) -> dict:
    integrations.save_credentials("meta", payload.model_dump())
    verification = integrations.meta_verify()
    return {
        "saved": True,
        "stored_server_side": True,
        "detail": "Credentials stored server-side (git-ignored). They are never returned to the client.",
        "status": integrations.meta_status()["status"],
        **verification,
    }


@app.post("/api/integrations/meta/verify")
def verify_meta() -> dict:
    return integrations.meta_verify()


@app.post("/api/integrations/shopify/credentials")
def save_shopify_credentials(payload: ShopifyCredentials) -> dict:
    integrations.save_credentials("shopify", payload.model_dump())
    result = integrations.shopify_fetch_products(limit=1)
    return {"saved": True, "verified": bool(result.get("ok")), "detail": result.get("detail", "Token accepted.")}


@app.post("/api/integrations/shopify/sync")
def shopify_sync(limit: int = Query(10, ge=1, le=50)) -> dict:
    return integrations.shopify_fetch_products(limit)


if __name__ == "__main__":
    # Run from the repository root:  python -m backend.main
    # Binds 0.0.0.0 so container/platform routers can reach it, and honours the
    # platform-provided PORT (Render/Heroku-style) before any local override.
    import os

    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host=config.env("BACKEND_HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT") or config.env("BACKEND_PORT", "8000")),
        reload=False,
    )
