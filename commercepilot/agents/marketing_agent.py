"""AGENT C - Marketing Strategist.

Builds a campaign plan from the SAME selected product, brand, audience and
budget used by the other agents. All performance estimates are labelled
illustrative assumptions - no sales, ROAS or conversion rates are promised.

Meta Marketing API: NOT CONNECTED in this prototype. Campaign drafts are stored
locally; simulated execution is visibly labelled "DEMO - NOT PUBLISHED".
"""
from __future__ import annotations

from .. import ai, config
from ..ai.schemas import CampaignCreatives
from ..schemas import (
    Allocation,
    BusinessBrief,
    CampaignPlan,
    CampaignRequest,
    CreativeConcept,
    Product,
    utcnow,
)
from ..tools import calculations as calc

# Default allocation: 25% structured testing, 65% scaling proven creatives,
# 10% untouched reserve. Objective tweaks the mix.
DEFAULT_SPLIT = {
    "sales": {"Testing (broad + lookalike)": 0.25, "Scaling winning creatives": 0.65, "Reserve": 0.10},
    "traffic": {"Testing (broad audiences)": 0.35, "Scaling winning creatives": 0.55, "Reserve": 0.10},
    "leads": {"Testing (interest stacks)": 0.30, "Scaling winning creatives": 0.60, "Reserve": 0.10},
    "retargeting": {"Testing (warm audiences)": 0.20, "Retargeting (site + IG engagers)": 0.70, "Reserve": 0.10},
}

OBJECTIVE_DETAIL = {
    "sales": "Drive purchases at or below break-even ROAS, then scale spend on profitable days.",
    "traffic": "Maximise qualified store visits cheaply, then retarget engaged visitors.",
    "leads": "Collect interested contacts (WhatsApp/lead form) for follow-up selling.",
    "retargeting": "Re-engage people who visited the store or engaged with content but did not buy.",
}

KPI_SETS = {
    "sales": ["ROAS (revenue / ad spend)", "CPA vs gross profit per unit", "Conversion rate", "Cost per link click"],
    "traffic": ["Cost per link click", "Landing page views", "Bounce rate", "Cost per engaged visit"],
    "leads": ["Cost per lead", "Lead-to-buyer rate", "Form completion rate"],
    "retargeting": ["ROAS on retargeting spend", "Frequency", "CPA vs cold audience CPA"],
}


def default_allocations(total: float, objective: str) -> list[Allocation]:
    split = DEFAULT_SPLIT.get(objective, DEFAULT_SPLIT["sales"])
    rows = calc.allocate_budget(total, split)
    purposes = {
        "Reserve": "Untouched buffer until a creative beats break-even ROAS.",
        "Testing (broad + lookalike)": "Structured cold-start tests: 3 creatives x 2 audiences.",
        "Testing (broad audiences)": "Cold traffic tests across interest groups.",
        "Testing (interest stacks)": "Audience tests to find the cheapest qualified lead.",
        "Testing (warm audiences)": "Small warm-audience validation before scaling.",
        "Scaling winning creatives": "Concentrated spend on ads that beat break-even ROAS.",
        "Retargeting (site + IG engagers)": "Website visitors and Instagram engagers who did not purchase.",
    }
    return [
        Allocation(label=r["label"], amount=float(r["amount"]), purpose=purposes.get(r["label"], ""))
        for r in rows
    ]


def generate(brief: BusinessBrief, product: Product, request: CampaignRequest) -> CampaignPlan:
    currency = brief.currency or product.currency or "PKR"
    if product.currency and product.currency.upper() != currency.upper():
        raise ValueError("Product and project currencies must match; automatic FX conversion is not supported")
    total = request.budget if request.budget is not None else brief.budget
    warnings: list[str] = []

    if request.allocations:
        try:
            validated = calc.validate_allocation(
                total, [a.model_dump() for a in request.allocations]
            )
            allocations = [
                Allocation(label=a["label"], amount=a["amount"], purpose=a["purpose"])
                for a in validated["allocations"]
            ]
        except calc.CalculationError as exc:
            if config.production():
                raise
            warnings.append(f"Provided allocation rejected ({exc}); replaced with the default split.")
            allocations = default_allocations(total, request.objective)
    else:
        allocations = default_allocations(total, request.objective) if total else []

    audience = brief.target_audience or "broad adult audience"
    hypotheses = _audience_hypotheses(brief, product, audience)
    creatives = _generate_creatives(brief, product, request.objective)
    generation_mode = "template"

    try:
        llm_creatives = ai.complete_json(
            prompt_name="campaign_creatives",
            schema=CampaignCreatives,
            quality=ai.QUALITY_STRONG,
            user=_llm_prompt(brief, product, request),
        )
    except ai.AIError:
        if config.production():
            raise
        # Budget hit, outage or invalid output: deterministic creatives stay and
        # generation_mode remains "template" so nothing is misrepresented.
        llm_creatives = None
    if llm_creatives is not None and llm_creatives.headlines:
        generation_mode = "llm"
        _merge_llm_creatives(creatives, llm_creatives.model_dump(exclude_none=True))
        if config.production():
            creatives = creatives[:min(len(llm_creatives.headlines), len(llm_creatives.primary_texts or []))]

    unit_profit = None
    if product.observed_price and product.estimated_cost is not None:
        try:
            unit_profit = calc.gross_profit_per_unit(product.observed_price, product.estimated_cost)
        except calc.CalculationError:
            unit_profit = None

    risks = [
        "All performance figures here are ILLUSTRATIVE ASSUMPTIONS. No historical campaign data "
        "was available, so nothing is a forecast or guarantee.",
        "Meta Marketing API is NOT CONNECTED: this plan is a local draft, nothing is published to Meta.",
    ]
    if product.is_sample_data:
        risks.append("Product price/cost come from SAMPLE demo data - validate real supplier economics first.")
    if unit_profit is not None:
        be = None
        if product.observed_price and unit_profit > 0:
            be = product.observed_price / unit_profit
        if be and be > 2.5:
            risks.append(
                f"Break-even ROAS is {be:.2f}: there is little margin for inefficient targeting - keep testing budgets small."
            )
    if request.objective == "retargeting":
        risks.append("Retargeting needs sufficient site volume first; with a brand-new store this audience will be small.")

    testing_strategy = [
        "Week 1 - structured test: 3 creative concepts x 2 audiences, equal budget, one variable per test.",
        "Kill any ad set that spends 1.5x the target CPA with zero purchases.",
        "Move 60% of remaining budget into the best performing creative by day 5-7.",
        "Hold the reserve until a creative beats break-even ROAS on 3 consecutive days.",
        "Re-test monthly: fatigue shows up as rising frequency and falling CTR.",
    ]

    plan = CampaignPlan(
        targeting=request.targeting,
        publication="DRAFT - NOT PUBLISHED" if config.production() else "DEMO - NOT PUBLISHED",
        objective=request.objective,
        objective_detail=OBJECTIVE_DETAIL[request.objective],
        duration_days=request.duration_days,
        budget=total,
        currency=currency,
        allocations=allocations,
        allocation_valid=bool(allocations) and abs(sum(a.amount for a in allocations) - total) < 0.005,
        audience_hypotheses=hypotheses,
        creatives=creatives,
        testing_strategy=testing_strategy,
        kpis=KPI_SETS[request.objective],
        risks_and_assumptions=risks + warnings,
        estimates_are_illustrative=True,
        status="draft",
        meta_connection="not_connected",
        generation_mode=generation_mode,
        created_at=utcnow(),
    )
    return plan


def _audience_hypotheses(brief: BusinessBrief, product: Product, audience: str) -> list[str]:
    base = [
        f"Primary: {audience}",
        f"People engaging with {product.category} content on Instagram/Pinterest in {brief.target_market or 'the target market'}",
    ]
    for tag in product.audience_tags[:3]:
        base.append(f"Interest-based: audiences matching '{tag}'")
    base.append("Lookalike of purchasers once a first customer list exists (not yet available).")
    return base


def _generate_creatives(brief: BusinessBrief, product: Product, objective: str) -> list[CreativeConcept]:
    brand = brief.business_name or "the brand"
    name = product.title
    price = f"{brief.currency or 'PKR'} {product.observed_price:,.0f}" if product.observed_price else ""
    cta = {"sales": "Shop Now", "traffic": "Learn More", "leads": "Sign Up", "retargeting": "Complete Your Order"}[objective]
    hook = product.title.split("(")[0].strip()
    return [
        CreativeConcept(
            name="Problem - Solution",
            angle=f"Lead with the problem '{hook}' solves, show the product in use.",
            headline=f"{hook} - simple daily upgrade",
            primary_text=(
                f"Small routine, visible difference. {name} {('for ' + price) if price else ''}. "
                f"Dispatch in 24-48 hours, cash on delivery available. {brand}."
            ),
            cta=cta,
        ),
        CreativeConcept(
            name="Social proof / UGC style",
            angle="Native-looking customer routine content with a soft call to action.",
            headline=f"Why I switched to {hook}",
            primary_text=(
                f"'Three weeks in and it just fits my routine.' Real routines, honest expectations. "
                f"Free replacement on damaged deliveries. {brand}."
            ),
            cta=cta,
        ),
        CreativeConcept(
            name="Offer / urgency",
            angle="Launch offer with clear value and a deadline; only use if the offer is real.",
            headline=f"Launch offer: {hook}",
            primary_text=(
                f"Launch pricing on {name} {(' - ' + price) if price else ''}. Limited stock on the first batch. "
                f"Cash on delivery across Pakistan."
            ),
            cta=cta,
        ),
    ]


def _llm_prompt(brief: BusinessBrief, product: Product, request: CampaignRequest) -> str:
    product_text = f"{product.title} ({product.category}), {brief.currency} {product.observed_price}"
    brand_text = f"{brief.business_name}, personality: {brief.brand_personality}"
    audience_text = f"{brief.target_audience}, market: {brief.target_market}"
    return (
        f"Product: {ai.wrap_untrusted('product', product_text)}\n"
        f"Brand: {ai.wrap_untrusted('brand', brand_text)}\n"
        f"Audience: {ai.wrap_untrusted('audience', audience_text)}\n"
        f"Objective: {request.objective}, budget: {request.budget} {brief.currency}, "
        f"days: {request.duration_days}\n"
        f"Delivery brief: {ai.wrap_untrusted('targeting', request.targeting.model_dump_json())}\n"
        "Write 3 headlines and 3 primary texts now."
    )


def _merge_llm_creatives(creatives: list[CreativeConcept], data: dict) -> None:
    headlines = [str(h)[:80] for h in data.get("headlines", []) if str(h).strip()]
    texts = [str(t)[:220] for t in data.get("primary_texts", []) if str(t).strip()]
    for i, creative in enumerate(creatives):
        if i < len(headlines):
            creative.headline = headlines[i]
        if i < len(texts):
            creative.primary_text = texts[i]
