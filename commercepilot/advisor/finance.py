"""Planning arithmetic. Model text never supplies totals, margins or forecasts."""
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal

from .models import Profile

POLICIES = {
    "physical": {"Product validation & inventory": 30, "Fulfilment & returns buffer": 15, "Store & tracking": 10, "Creative production": 10, "Controlled ad test": 15, "Cash reserve": 20},
    "dropshipping": {"Samples & supplier validation": 20, "Fulfilment & returns buffer": 15, "Store & tracking": 10, "Creative production": 10, "Controlled ad test": 25, "Cash reserve": 20},
    "digital": {"Offer validation": 20, "Store & tracking": 15, "Creative production": 15, "Controlled ad test": 25, "Cash reserve": 25},
    "service": {"Offer validation & delivery": 25, "Landing page & tracking": 15, "Creative production": 10, "Controlled ad test": 25, "Cash reserve": 25},
    "advertising": {"Creative testing": 15, "Landing page & tracking": 10, "Controlled ad test": 55, "Cash reserve": 20},
}


def dec(value):
    return Decimal(str(value))


def money(value):
    return float(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def split(amount, weights):
    """Largest-remainder cent allocation; rows always equal available funds."""
    cents = int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    total = sum(weights.values())
    exact = [Decimal(cents) * dec(weight) / dec(total) for weight in weights.values()]
    values = [int(value.to_integral_value(rounding=ROUND_FLOOR)) for value in exact]
    for index in sorted(range(len(values)), key=lambda i: exact[i] - values[i], reverse=True)[:cents - sum(values)]:
        values[index] += 1
    return [{"label": label, "amount": money(dec(value) / 100), "percent": weight} for (label, weight), value in zip(weights.items(), values, strict=True)]


def calculate(profile: Profile):
    p = profile
    missing = [label for label, value in (("budget", p.budget), ("currency", p.currency), ("budget scope (whole business or advertising)", p.budget_scope),
                                          ("niche", p.niche), ("location", p.location), ("target audience", p.audience)) if value is None or value == ""]
    assumptions, warnings = [], []
    unit = {"gross_profit_per_order": None, "contribution_per_order": None, "break_even_cpa": None,
            "break_even_roas": None, "fixed_cost_break_even_orders": None}
    if p.selling_price is not None and p.product_cost is not None:
        unit["gross_profit_per_order"] = money(dec(p.selling_price) - dec(p.product_cost))
    contribution = None
    if p.selling_price is not None and p.product_cost is not None and p.other_costs_per_order is not None:
        contribution = dec(p.selling_price) - dec(p.product_cost) - dec(p.other_costs_per_order)
        unit["contribution_per_order"] = money(contribution)
        if contribution > 0:
            unit["break_even_cpa"] = money(contribution)
            unit["break_even_roas"] = round(float(dec(p.selling_price) / contribution), 4)
            if p.fixed_costs is not None:
                unit["fixed_cost_break_even_orders"] = int((dec(p.fixed_costs) / contribution).to_integral_value(rounding="ROUND_CEILING"))
        else:
            warnings.append("The product does not cover its stated variable costs. Improve pricing/costs before paying for acquisition.")
    else:
        warnings.append("Contribution and affordable acquisition cost need a selling price, product cost and all other per-order costs. Unknown costs are not treated as zero.")
    result = {"currency": p.currency, "scope": p.budget_scope, "total_budget": p.budget, "allocations": [], "unit_economics": unit,
              "missing_information": missing, "assumptions": assumptions, "warnings": warnings, "daily_ad_test_average": None,
              "ad_test_budget": None, "timeframe_days": p.timeframe_days, "scenario": None, "status": "needs_details"}
    if p.budget is None or p.currency is None or p.budget_scope is None:
        return result
    budget = dec(p.budget).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    fixed = dec(p.fixed_costs or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if p.fixed_costs is None:
        assumptions.append("No committed fixed costs were provided; zero is included provisionally. Add actual commitments before adopting this allocation.")
    if fixed > budget:
        result.update(status="overcommitted", shortfall=money(fixed - budget))
        warnings.append("Committed fixed costs exceed the available budget. Reduce commitments or revise available funds before advertising.")
        return result
    policy = "advertising" if p.budget_scope == "advertising" else p.business_model or "physical"
    weights = dict(POLICIES[policy])
    assumptions.append(f"Starting allocation uses the {policy} planning template; these shares are adjustable planning assumptions, not market benchmarks.")
    if not p.business_model and p.budget_scope == "business":
        assumptions.append("Physical-product business assumed until you confirm your business model.")
    blocked = budget == 0 or (contribution is not None and contribution <= 0) or (unit["gross_profit_per_order"] is not None and unit["gross_profit_per_order"] <= 0)
    if p.store_ready is False or p.tracking_ready is False:
        blocked = True
        warnings.append("Finish the store/checkout and tracking setup before allocating money to a paid test.")
    if blocked:
        weights["Cash reserve"] += weights["Controlled ad test"]
        weights["Controlled ad test"] = 0
    elif contribution is None:
        reduction = weights["Controlled ad test"] // 2
        weights["Controlled ad test"] -= reduction
        weights["Cash reserve"] += reduction
        assumptions.append("The paid-test share is reduced while complete unit costs are unknown. Confirm contribution before spending.")
    rows = split(budget - fixed, weights)
    if fixed:
        rows.insert(0, {"label": "Committed fixed costs", "amount": money(fixed), "percent": None})
    ad_budget = next(row["amount"] for row in rows if row["label"] == "Controlled ad test")
    days = p.timeframe_days or 7
    if p.timeframe_days is None:
        assumptions.append("A 7-day planning period is assumed. Change it to your actual test window.")
    warnings.append("Daily figure is a planning average, not an enforced Meta spending limit. Review platform lifetime/account limits before publishing.")
    if p.location:
        assumptions.append(f"Location: {p.location}. Obtain local shipping, payment, tax and ad quotes; no local market rate or currency conversion is invented.")
    result.update(status="hold_paid_ads" if blocked else "provisional", allocations=rows, total_budget=money(budget),
                  ad_test_budget=ad_budget, daily_ad_test_average=money(dec(ad_budget) / days), timeframe_days=days)
    if p.assumed_cpc is not None and p.assumed_conversion_pct is not None:
        clicks = int((dec(ad_budget) / dec(p.assumed_cpc)).to_integral_value(rounding=ROUND_FLOOR))
        orders = dec(clicks) * dec(p.assumed_conversion_pct) / 100
        result["scenario"] = {"label": "Illustration using your CPC and conversion assumptions; not a forecast or guarantee", "clicks": clicks,
                              "expected_orders": float(orders.quantize(Decimal("0.01"))),
                              "revenue": money(orders * dec(p.selling_price)) if p.selling_price is not None else None,
                              "contribution_after_ads": money(orders * contribution - dec(ad_budget)) if contribution is not None else None}
    return result
