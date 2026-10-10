"""AI Commerce Assistant - a real intent router, not a fake chat.

Every recognised intent executes an actual agent/orchestrator function over the
shared project context and returns its real output. Unrecognised messages get an
honest capability list. An LLM (when configured) may re-rank intent choice, but
the work is always done by the deterministic agents.
"""
from __future__ import annotations

import json
import re
from typing import Any, Optional

from . import llm
from .schemas import (
    AnalyzeRequest,
    BusinessBrief,
    CampaignRequest,
    ResearchRequest,
    StoreEditRequest,
)
from .storage import ProjectStore
from .tools import calculations as calc
from .workflows import commerce_workflow as wf

INTENTS = [
    ("research", r"\b(find|search|research|hunt|discover|what should i sell)\b"),
    ("select", r"\b(select|choose|pick)\b.*\bproduct\b|#\d"),
    ("store_edit", r"\b(luxur\w*|editorial|minimal\w*|mobile|animations?|animate|colou?r|palette|serif|fonts?|hero|cards?|radius|spac\w+|compact|dark mode|hide reviews|show faq|bordered|elevated)\b"),
    ("store", r"\b(store|storefront|website|site|shop)\b.*\b(build|generate|create|make|launch)\b|\b(generate|build|create)\b.*\b(store|storefront|website|site)\b"),
    ("campaign", r"\b(campaign\w*|ads?|advert\w*|marketing|budget|allocat\w*|meta|facebook|instagram)\b"),
    ("analyze", r"\b(profit\w*|margin\w*|break[- ]?even|roas|analy[sz]\w*|economics|cpa|conversion\w*)\b"),
    ("report", r"\b(report\w*|summary|overview|consolidat\w*)\b"),
    ("workflow", r"\b(run|start)\b.*\b(workflow|everything|all)\b|\bfull commerce\b"),
]


def _detect_intent(message: str) -> str:
    lowered = message.lower()
    if llm.llm_available():
        text = llm.complete(
            "Classify the user message into one of: research, select, store, store_edit, campaign, "
            "analyze, report, workflow, unknown. Return JSON {'intent': '...'}",
            message,
            as_json=True,
        )
        if text:
            try:
                intent = json.loads(text).get("intent")
                if intent in {i[0] for i in INTENTS} or intent == "unknown":
                    return intent
            except (json.JSONDecodeError, TypeError, ValueError):
                pass
    for intent, pattern in INTENTS:
        if re.search(pattern, lowered):
            return intent
    return "unknown"


def handle(store: ProjectStore, project_id: Optional[str], message: str) -> dict[str, Any]:
    project = store.get(project_id) if project_id else None
    intent = _detect_intent(message)

    if intent == "unknown":
        return {
            "intent": "unknown",
            "reply": (
                "I could not map that to an action. I can: research products for a niche, select a "
                "product, build or restyle the storefront ('make it more luxurious', 'editorial "
                "split-screen hero'), draft a marketing campaign with a budget, analyse profitability "
                "and break-even ROAS, or run the full commerce workflow."
            ),
        }

    needs_project = intent in ("select", "store", "store_edit", "campaign", "analyze", "report")
    if needs_project and not project:
        return {"intent": intent, "reply": "Open or create a project first - I need its shared context."}

    try:
        if intent == "workflow":
            if not project:
                return {"intent": intent, "reply": "Open or create a project first."}
            result = wf.run_full_workflow(store, project["id"], auto_select=True, mode="both")
            if result.get("error"):
                return {"intent": intent, "reply": f"Workflow stopped at '{result['error']['step']}': {result['error']['message']}", "workflow": result}
            return {"intent": intent, "reply": "Full workflow complete: research, product, storefront, campaign and analysis are ready.", "workflow": result}

        if intent == "research":
            brief = BusinessBrief(**(project.get("brief") or {}) if project else {})
            niche = brief.niche or brief.industry
            m = re.search(r"(?:for|about|in)\s+([a-z0-9 &-]{3,60})", message.lower())
            if m and not re.search(r"\b(products?|store|campaign|storefront)\b", m.group(1)):
                niche = m.group(1).strip()
            if project:
                req = ResearchRequest(
                    niche=niche or "trending products",
                    market=brief.target_market,
                    audience=brief.target_audience,
                    budget=brief.budget,
                    price_min=brief.preferred_price_min,
                    price_max=brief.preferred_price_max,
                    mode="both",
                )
                result = wf.step_research(store, project, req)
                top = result.products[0] if result.products else None
                reply = (
                    f"Found {len(result.products)} ranked candidates for '{req.niche}'. "
                    + (f"Top pick: {top.title} (score {top.score}, {top.confidence} confidence)." if top else "")
                )
                return {"intent": intent, "reply": reply, "research": {"count": len(result.products), "warnings": result.warnings}}
            return {"intent": intent, "reply": f"Open a project so I can research '{niche}' with its budget and audience."}

        if intent == "select":
            research = project.get("research") or {}
            products = research.get("products") or []
            if not products:
                return {"intent": intent, "reply": "No research results yet - run Product Hunter first."}
            chosen = None
            m = re.search(r"#(\d+)", message)
            if m:
                idx = int(m.group(1)) - 1
                if 0 <= idx < len(products):
                    chosen = products[idx]["id"]
            if not chosen:
                for row in products:
                    if row["title"].lower()[:12] in message.lower():
                        chosen = row["id"]
                        break
            if not chosen:
                chosen = products[0]["id"]
            for row in products:
                if row["id"] == chosen:
                    project["selected_product"] = row
                    wf._set_step(store, project, "select", "success", f"{row['title']} selected")
                    wf._save(store, project)
                    return {"intent": intent, "reply": f"Selected '{row['title']}'."}
            return {"intent": intent, "reply": "Could not match that to a product - use its number from the Product Hunter list."}

        if intent == "store":
            spec = wf.step_generate_store(store, project)
            return {"intent": intent, "reply": f"Storefront generated for {spec.brand_name} with {len(spec.sections)} sections."}

        if intent == "store_edit":
            if not project.get("store_spec"):
                spec = wf.step_generate_store(store, project)
                return {"intent": intent, "reply": f"No storefront yet, so I generated one first for {spec.brand_name}. Now apply design edits from the Store Architect page."}
            response = wf.step_edit_store(store, project, message)
            if response.unmatched:
                return {"intent": intent, "reply": response.message}
            return {"intent": intent, "reply": "Applied: " + "; ".join(response.applied_changes), "applied": response.applied_changes}

        if intent == "campaign":
            brief = BusinessBrief(**project["brief"])
            plan = wf.step_generate_campaign(store, project, CampaignRequest(objective="sales", budget=brief.budget or 30000))
            return {"intent": intent, "reply": f"Drafted a {plan.objective} campaign with {len(plan.creatives)} creatives and {len(plan.allocations)} budget lines (DEMO - not published)."}

        if intent == "analyze":
            analysis = wf.step_analyze(store, project, AnalyzeRequest())
            unit = analysis["unit_economics"]
            if unit.get("break_even_roas") is None:
                return {"intent": intent, "reply": "Cannot analyse yet: product price or cost is missing, so no values were invented.", "analysis": {"warnings": analysis["warnings"]}}
            return {
                "intent": intent,
                "reply": (
                    f"Gross profit/unit {unit['gross_profit_per_unit']} {analysis['currency']} "
                    f"(margin {unit['gross_margin_pct']}%), break-even ROAS {unit['break_even_roas']}."
                ),
            }

        if intent == "report":
            report = wf.step_report(store, project)
            return {"intent": intent, "reply": "Report rebuilt with the latest data.", "report": report}
    except wf.StepFailed as exc:
        return {"intent": intent, "reply": f"{exc.step} step failed: {exc.message}"}
    except calc.CalculationError as exc:
        return {"intent": intent, "reply": f"Calculation rejected an input: {exc}"}

    return {"intent": intent, "reply": "Action recognised but not completed."}
