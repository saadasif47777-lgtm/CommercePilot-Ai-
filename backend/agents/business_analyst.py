"""AGENT D - Business Analyst.

Real deterministic calculations (backend/tools/calculations.py) over the
selected product's stored economics plus any campaign data. Handles missing
values, zero denominators and invalid money inputs explicitly - nothing is
converted into a fabricated measurement.

Break-even ROAS note surfaced to users: ROAS = selling price / gross profit per
unit, which considers gross profit only and EXCLUDES overheads (shipping,
payment fees, returns, labour...) unless those are modelled into product cost.
"""
from __future__ import annotations

from typing import Optional

from .. import llm
from ..schemas import (
    AnalyzeRequest,
    BusinessBrief,
    CampaignPlan,
    CostOverheadInputs,
    Product,
    ScenarioAssumptions,
    utcnow,
)
from ..tools import calculations as calc

DEFAULT_CPC = 45.0  # illustrative PKR click cost used only as a starting assumption
DEFAULT_SCENARIOS = {
    "conservative": ScenarioAssumptions(clicks=0, conversion_rate_pct=1.2, cpc=DEFAULT_CPC),
    "base": ScenarioAssumptions(clicks=0, conversion_rate_pct=2.0, cpc=DEFAULT_CPC),
    "best": ScenarioAssumptions(clicks=0, conversion_rate_pct=3.0, cpc=DEFAULT_CPC),
}


def _fmt_currency(value: Optional[float], currency: str) -> str:
    if value is None:
        return "unknown"
    return f"{currency} {value:,.2f}"


def analyze(
    brief: BusinessBrief,
    product: Product,
    campaign: Optional[CampaignPlan] = None,
    request: Optional[AnalyzeRequest] = None,
) -> dict:
    """Run the full analysis. Returns a dict; warnings explain every gap."""
    request = request or AnalyzeRequest()
    currency = brief.currency or product.currency or "PKR"
    warnings: list[str] = []
    errors: list[str] = []

    # ---- 1. Unit economics ------------------------------------------------ #
    price = product.observed_price
    # Manual/user-entered products store their cost in observed_cost; researched
    # products carry an explicitly-labelled estimate in estimated_cost.
    cost = getattr(product, "observed_cost", None) or product.estimated_cost
    unit: dict = {
        "selling_price": price,
        "product_cost": cost,
        "cost_is_estimate": product.cost_is_estimate,
        "currency": currency,
        "gross_profit_per_unit": None,
        "gross_margin_pct": None,
        "break_even_roas": None,
        "break_even_ad_spend_per_unit": None,
    }
    if price is None or cost is None:
        missing = [n for n, v in (("selling price", price), ("estimated cost", cost)) if v is None]
        warnings.append(
            f"Unit economics unavailable: missing {' and '.join(missing)} for '{product.title}'. "
            "No values were invented."
        )
    else:
        try:
            profit = calc.gross_profit_per_unit(price, cost)
            margin = calc.gross_margin_pct(price, cost)
            be = calc.break_even_roas(price, profit)
            unit["gross_profit_per_unit"] = profit
            unit["gross_margin_pct"] = margin
            unit["break_even_roas"] = be
            unit["break_even_ad_spend_per_unit"] = profit if profit > 0 else None
            if be is None:
                warnings.append(
                    "Break-even ROAS is undefined: the unit loses money before advertising "
                    f"(profit {_fmt_currency(profit, currency)} per unit)."
                )
            if margin is not None and margin < 40:
                warnings.append(
                    f"Gross margin is {margin:.1f}%. After fulfilment and payment fees this "
                    "product may not sustain paid acquisition."
                )
        except calc.CalculationError as exc:
            errors.append(f"Invalid product economics: {exc}")

    # ---- 1b. Contribution economics (with per-unit overheads) ------------- #
    overheads: CostOverheadInputs = request.overheads or CostOverheadInputs()
    extra_per_unit = sum(
        v or 0.0
        for v in (
            overheads.shipping_cost_per_unit,
            overheads.packaging_cost_per_unit,
            overheads.transaction_fee_per_unit,
        )
    )
    contribution: dict = {**overheads.model_dump(), "currency": currency,
                          "extra_unit_cost": round(extra_per_unit, 2) if extra_per_unit else None,
                          "contribution_per_unit": None, "markup_pct": None,
                          "break_even_units": None}
    if price and cost:
        try:
            contribution["markup_pct"] = calc.markup_pct(price, cost)
            if extra_per_unit:
                contribution["contribution_per_unit"] = calc.contribution_margin_per_unit(
                    price, cost, extra_per_unit
                )
                if overheads.fixed_costs:
                    contribution["break_even_units"] = calc.break_even_units(
                        price, cost, extra_per_unit, overheads.fixed_costs
                    )
                if contribution["contribution_per_unit"] is not None and contribution["contribution_per_unit"] <= 0:
                    warnings.append(
                        "With the entered shipping/packaging/transaction costs the unit "
                        "contribution is negative - no volume makes this profitable."
                    )
        except calc.CalculationError as exc:
            errors.append(f"Invalid overhead input: {exc}")

    # The campaign budget is what is actually being spent against (it can differ
    # from the brief budget after the user edits the plan); fall back to the brief.
    budget = (campaign.budget if campaign and campaign.budget else None) or brief.budget or None
    allocations = campaign.allocations if campaign else []
    spend_planned = sum(a.amount for a in allocations) if allocations else 0.0

    reserve = sum(a.amount for a in allocations if "reserve" in a.label.lower())
    budget_summary: dict = {"budget": budget, "planned_spend": None, "remaining": None, "utilization_pct": None}
    if budget:
        try:
            budget_summary = {
                "budget": budget,
                "planned_spend": round(spend_planned, 2),
                "reserve_held": round(reserve, 2),
                "expected_spend": round(spend_planned - reserve, 2),
                "remaining": round(budget - spend_planned, 2),
                "utilization_pct": round(spend_planned / budget * 100, 1) if budget else None,
                "currency": currency,
            }
            if spend_planned > budget:
                warnings.append(
                    f"Planned allocation ({_fmt_currency(spend_planned, currency)}) exceeds the "
                    f"campaign budget ({_fmt_currency(budget, currency)})."
                )
        except calc.CalculationError as exc:
            errors.append(str(exc))

    # ---- 2. Measured KPIs (only when real numbers exist) ------------------ #
    actuals = request.actuals
    kpis: dict = {"cpa": None, "conversion_rate_pct": None, "roas": None, "source": "no data"}
    if actuals and any(v is not None for v in (actuals.ad_spend, actuals.clicks, actuals.conversions, actuals.customers)):
        try:
            if actuals.ad_spend is not None and actuals.customers is not None:
                kpis["cpa"] = calc.cost_per_acquisition(actuals.ad_spend, actuals.customers)
            if actuals.conversions is not None and actuals.clicks is not None:
                kpis["conversion_rate_pct"] = calc.conversion_rate(actuals.conversions, actuals.clicks)
            if actuals.ad_spend is not None and actuals.clicks is not None:
                kpis["clicks"] = actuals.clicks
            if actuals.revenue is not None and actuals.ad_spend is not None:
                kpis["roas"] = round(actuals.revenue / actuals.ad_spend, 2) if actuals.ad_spend > 0 else None
            kpis["source"] = "measured input (you supplied these numbers)"
            if kpis["cpa"] is None:
                warnings.append("CPA not computed: zero acquired customers so far.")
            if kpis["conversion_rate_pct"] is None:
                warnings.append("Conversion rate not computed: zero clicks so far.")
        except calc.CalculationError as exc:
            errors.append(f"Invalid campaign actuals: {exc}")
    else:
        warnings.append(
            "No measured campaign data yet - KPIs reported as 'no data' rather than estimated."
        )

    # ---- 3. Scenario projections (assumptions explicit & editable) -------- #
    default_spend = spend_planned if spend_planned > 0 else (budget or 10000)
    scenarios: dict = {}
    assumptions_used: dict = {}
    for name, base in DEFAULT_SCENARIOS.items():
        supplied = getattr(request, name, None) or base
        cpc = supplied.cpc if supplied.cpc > 0 else DEFAULT_CPC
        clicks = supplied.clicks if supplied.clicks and supplied.clicks > 0 else max(1.0, default_spend / cpc)
        assumptions = ScenarioAssumptions(clicks=clicks, conversion_rate_pct=supplied.conversion_rate_pct, cpc=cpc)
        assumptions_used[name] = assumptions.model_dump()
        if price is None or cost is None:
            scenarios[name] = {"available": False, "reason": "missing product price/cost"}
            continue
        try:
            projection = calc.scenario_projection(
                price, cost, clicks, assumptions.conversion_rate_pct, cpc
            )
            projection["available"] = True
            projection["label"] = name
            scenarios[name] = projection
        except calc.CalculationError as exc:
            scenarios[name] = {"available": False, "reason": str(exc)}
            errors.append(f"{name} scenario: {exc}")
    if any(s.get("available") for s in scenarios.values()):
        warnings.append(
            "Scenario numbers are ILLUSTRATIVE projections from your editable assumptions "
            "(clicks, conversion rate, CPC) - not forecasts or guarantees."
        )

    # ---- 4. Evidence-based recommendations -------------------------------- #
    recommendations: list[str] = []
    if unit.get("gross_margin_pct") is not None and unit["break_even_roas"] is not None:
        be = unit["break_even_roas"]
        if be <= 1.5:
            recommendations.append(
                f"Break-even ROAS of {be:.2f} is healthy: sales above {be:.2f} ROAS are grossly profitable."
            )
        elif be <= 2.5:
            recommendations.append(
                f"Break-even ROAS is {be:.2f}: there is limited room for inefficient targeting - "
                "start narrow and scale only winning creatives."
            )
        else:
            recommendations.append(
                f"Break-even ROAS is {be:.2f}: paid acquisition will be tight. Improve product cost "
                "or raise average order value (bundles) before scaling spend."
            )
    if budget and spend_planned and spend_planned < budget:
        recommendations.append(
            f"Only {_fmt_currency(spend_planned, currency)} of {_fmt_currency(budget, currency)} is allocated. "
            "Keep the reserve until a creative beats break-even ROAS in testing."
        )
    base = scenarios.get("base") or {}
    if base.get("available"):
        if (base.get("net_profit") or 0) > 0:
            recommendations.append(
                f"Base case is profitable (net {_fmt_currency(base['net_profit'], currency)}) on your "
                "assumptions - validate with a small live test before committing the full budget."
            )
        else:
            recommendations.append(
                "Base case is unprofitable on current assumptions: negotiate cost down, raise price, "
                "or improve conversion rate assumptions with real evidence."
            )
    if product.is_sample_data:
        recommendations.append(
            "Product economics come from SAMPLE data - validate supplier cost and market price "
            "before spending real money."
        )

    return {
        "currency": currency,
        "product": {"id": product.id, "title": product.title, "is_sample_data": product.is_sample_data},
        "unit_economics": unit,
        "contribution_economics": contribution,
        "budget_summary": budget_summary,
        "kpis": kpis,
        "scenarios": scenarios,
        "assumptions": assumptions_used,
        "recommendations": recommendations,
        "warnings": warnings,
        "errors": errors,
        "formula_notes": {
            "gross_profit_per_unit": "selling price - product cost",
            "gross_margin_pct": "(selling price - product cost) / selling price x 100",
            "break_even_roas": "selling price / gross profit per unit",
            "break_even_caveat": (
                "Break-even ROAS uses GROSS profit only. It excludes shipping, payment gateways, "
                "returns, taxes and overheads unless you model them into the product cost."
            ),
            "markup_pct": "markup % = (selling price - product cost) / product cost x 100 (undefined when cost is 0)",
            "contribution_per_unit": "contribution per unit = price - product cost - (shipping + packaging + transaction fees)",
            "break_even_units": "fixed costs / contribution per unit, rounded UP to whole units (None when contribution <= 0)",
            "cpa": "advertising spend / acquired customers",
            "conversion_rate": "conversions / clicks x 100",
        },
        "generated_at": utcnow(),
        "analysis_mode": llm.mode(),
    }
