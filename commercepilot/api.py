"""FastAPI application: the JSON API surface of CommercePilot AI.

This module only concerns itself with HTTP. Request bodies are validated by the
Pydantic models in :mod:`commercepilot.schemas`, and every real action is
performed by the orchestrator in :mod:`commercepilot.workflows.commerce_workflow`.
That keeps the API, the React interface and the automated tests calling exactly
the same business logic.

All routes live under ``/api`` so the built frontend can be served from ``/``
(see ``app.py``).
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import ValidationError

from . import ai, config, integrations
from .agents import product_hunter
from .assistant import handle as assistant_handle
from .runtime import get_store
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
from .workflows import commerce_workflow as wf

app = FastAPI(
    title="CommercePilot AI API",
    version="1.0.0",
    description=(
        "AI-powered e-commerce workspace: product research, storefront generation, "
        "campaign planning, unit economics and a project assistant."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS or ["http://localhost:3000"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _store():
    """The active project store.

    Resolved per call (rather than imported once) so tests can swap in an
    isolated SQLite file without reloading the module.
    """
    return get_store()


def _project_or_404(project_id: str) -> dict[str, Any]:
    project = _store().get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found.")
    return project


def _run_step(project_id: str, fn, *args, **kwargs):
    """Execute an orchestrator step, translating failures into HTTP errors."""
    project = _project_or_404(project_id)
    try:
        return fn(_store(), project, *args, **kwargs)
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
        "llm_mode": ai.mode(),
        "projects": _store().count(),
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
        return wf.create_project(_store(), ProjectCreate(example=True, name=payload.name))
    if payload.brief is None:
        payload.brief = BusinessBrief()
    if not payload.brief.business_name.strip():
        raise HTTPException(status_code=422, detail="business_name is required (or pass example=true).")
    return wf.create_project(_store(), payload)


@app.get("/api/projects")
def list_projects() -> dict:
    rows = []
    for p in _store().list():
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
    if not _store().delete(project_id):
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found.")
    return {"deleted": True, "id": project_id}


@app.post("/api/projects/{project_id}/brief")
def update_brief(project_id: str, payload: BriefUpdate) -> dict:
    """Replace the brief (shared logic with the Projects tab)."""
    return wf.update_brief(_store(), _project_or_404(project_id), payload.brief)


@app.post("/api/projects/{project_id}/select-product")
def select_product(project_id: str, payload: dict = Body(...)) -> dict:
    project = _project_or_404(project_id)
    product_id = payload.get("product_id")
    product_payload = payload.get("product")
    try:
        if product_id:
            wf.step_select_product(_store(), project, product_id, auto_select=True)
        elif product_payload:
            wf.step_select_product(_store(), project, None, auto_select=True)
            project = _project_or_404(project_id)
            from .schemas import Product

            project["selected_product"] = Product(**product_payload).model_dump()
            wf._set_step(_store(), project, "select", "success", f"{product_payload.get('title')} selected")
            wf._save(_store(), project)
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
        wf._set_step(_store(), project, step_id, "pending", "Product reset")
    return wf._save(_store(), project)


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
    result = wf.step_manual_product(_store(), project, payload)
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
        return wf.step_save_product(_store(), project, product_id=product_id)
    except wf.StepFailed as exc:
        raise HTTPException(status_code=422, detail={"step": exc.step, "message": exc.message}) from exc


@app.post("/api/projects/{project_id}/products/{product_id}/reject")
def reject_product(project_id: str, product_id: str) -> dict:
    project = _project_or_404(project_id)
    return wf.step_reject_product(_store(), project, product_id)


@app.post("/api/products/manual-compare")
def manual_compare(payload: ManualProductInput) -> dict:
    """Score a manually entered product WITHOUT saving it: an economics preview."""
    import uuid as _uuid

    from .agents import business_analyst as analyst

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
    _run_step(project_id, wf.step_generate_store, design, payload.get("extra_instructions", ""))
    return _project_or_404(project_id)["store_spec"]


@app.post("/api/projects/{project_id}/edit-store")
def edit_store(project_id: str, payload: StoreEditRequest) -> dict:
    response = _run_step(project_id, wf.step_edit_store, payload.prompt)
    return response.model_dump()


@app.post("/api/projects/{project_id}/reset-store")
def reset_store(project_id: str) -> dict:
    project = _project_or_404(project_id)
    if project.get("selected_product"):
        spec = wf.step_generate_store(_store(), project)
        return {"reset": True, "spec": spec.model_dump()}
    project["store_spec"] = None
    wf._set_step(_store(), project, "store", "pending", "Store reset")
    return wf._save(_store(), project)


@app.get("/api/projects/{project_id}/store/export", response_class=HTMLResponse)
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
    _run_step(project_id, wf.step_generate_campaign, payload)
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
    wf._save(_store(), project)
    return data


@app.post("/api/projects/{project_id}/campaign/simulate")
def simulate_campaign(project_id: str) -> dict:
    """Simulated campaign execution, clearly labelled DEMO - NOT PUBLISHED."""
    project = _project_or_404(project_id)
    try:
        return wf.step_simulate_campaign(_store(), project)
    except wf.StepFailed as exc:
        raise HTTPException(status_code=404, detail=exc.message) from exc


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
            _store(), project_id, auto_select=payload.auto_select, mode=payload.mode, force=payload.force
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found.") from exc


@app.get("/api/projects/{project_id}/report")
def get_report(project_id: str, refresh: bool = Query(False)) -> dict:
    project = _project_or_404(project_id)
    if refresh or not project.get("report"):
        return wf.step_report(_store(), project)
    return project["report"]


@app.post("/api/projects/{project_id}/assistant")
def assistant(project_id: str, payload: dict = Body(...)) -> dict:
    message = str(payload.get("message", "")).strip()
    if not message:
        raise HTTPException(status_code=422, detail="message is required")
    if len(message) > 1000:
        raise HTTPException(status_code=422, detail="message too long (max 1000 chars)")
    return assistant_handle(_store(), project_id, message)


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
