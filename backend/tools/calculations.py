"""Exact business calculations for the Business Analyst agent.

Pure Python. No LLM involved: these are deterministic arithmetic functions
that must behave correctly for invalid, missing and edge-case inputs.

Definitions (as required by the specification):
  gross profit per unit = selling price - product cost
  gross margin %        = gross profit per unit / selling price * 100
  break-even ROAS       = selling price / gross profit per unit
  CPA                   = advertising spend / acquired customers
  conversion rate       = conversions / clicks * 100
"""
from __future__ import annotations

from typing import Any, Optional

__all__ = [
    "CalculationError",
    "validate_money",
    "gross_profit_per_unit",
    "gross_margin_pct",
    "break_even_roas",
    "cost_per_acquisition",
    "conversion_rate",
    "ad_spend_summary",
    "scenario_projection",
    "allocate_budget",
    "validate_allocation",
    "pct_of_budget",
]


class CalculationError(ValueError):
    """Raised when an input cannot be used for a calculation."""


def validate_money(value: Any, name: str, allow_zero: bool = True) -> float:
    """Validate a monetary input.

    Rejects non-numeric values, negatives (unless the caller opts in via
    allow_zero=False semantics for credits) and NaN/inf.
    """
    if value is None:
        raise CalculationError(f"{name} is required but missing")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CalculationError(f"{name} must be a number, got {type(value).__name__}")
    f = float(value)
    if f != f or f in (float("inf"), float("-inf")):  # NaN / inf
        raise CalculationError(f"{name} must be a finite number")
    if f < 0:
        raise CalculationError(f"{name} must not be negative (got {f})")
    if f == 0 and not allow_zero:
        raise CalculationError(f"{name} must be greater than zero")
    return f


def _r(value: float, places: int = 2) -> float:
    return round(float(value), places)


def gross_profit_per_unit(selling_price: Any, product_cost: Any) -> float:
    """Selling price - product cost. Validates both inputs."""
    price = validate_money(selling_price, "selling_price", allow_zero=False)
    cost = validate_money(product_cost, "product_cost")
    return _r(price - cost)


def gross_margin_pct(selling_price: Any, product_cost: Any) -> float:
    """(price - cost) / price * 100. Zero price is rejected (undefined)."""
    price = validate_money(selling_price, "selling_price", allow_zero=False)
    cost = validate_money(product_cost, "product_cost")
    return _r((price - cost) / price * 100.0)


def break_even_roas(selling_price: Any, gross_profit_per_unit_value: Any) -> Optional[float]:
    """Selling price / gross profit per unit.

    Returns None when the break-even ROAS is undefined:
      * gross profit <= 0 (the product loses money before ad spend)
      * gross profit == 0 would divide by zero
    """
    price = validate_money(selling_price, "selling_price", allow_zero=False)
    profit = float(gross_profit_per_unit_value)
    if profit != profit:
        raise CalculationError("gross_profit_per_unit must be a number")
    if profit <= 0:
        return None  # undefined: no amount of ROAS makes a loss-making unit break even
    return _r(price / profit)


def cost_per_acquisition(ad_spend: Any, acquired_customers: Any) -> Optional[float]:
    """Advertising spend / acquired customers. None when customers == 0."""
    spend = validate_money(ad_spend, "ad_spend")
    if acquired_customers is None:
        return None
    if isinstance(acquired_customers, bool) or not isinstance(acquired_customers, (int, float)):
        raise CalculationError("acquired_customers must be a number")
    if acquired_customers < 0:
        raise CalculationError("acquired_customers must not be negative")
    if acquired_customers == 0:
        return None  # undefined, not zero
    return _r(spend / float(acquired_customers))


def conversion_rate(conversions: Any, clicks: Any) -> Optional[float]:
    """Conversions / clicks * 100. None when clicks == 0."""
    if conversions is None or clicks is None:
        return None
    for v, name in ((conversions, "conversions"), (clicks, "clicks")):
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise CalculationError(f"{name} must be a number")
        if v < 0:
            raise CalculationError(f"{name} must not be negative")
    if clicks == 0:
        return None  # undefined
    return _r(float(conversions) / float(clicks) * 100.0)


def ad_spend_summary(budget: Any, spend: Any) -> dict:
    """Spend vs remaining budget with validation."""
    b = validate_money(budget, "budget", allow_zero=False)
    s = validate_money(spend, "ad_spend")
    if s > b + 1e-9:
        raise CalculationError(f"ad_spend ({s}) exceeds budget ({b})")
    return {
        "budget": _r(b),
        "spend": _r(s),
        "remaining": _r(b - s),
        "utilization_pct": _r(s / b * 100.0),
    }


def scenario_projection(
    selling_price: Any,
    product_cost: Any,
    clicks: Any,
    conversion_rate_pct: Any,
    cpc: Any,
) -> dict:
    """Project revenue/profit for one scenario.

    Assumptions are explicit inputs (clicks, conversion rate, CPC) and are
    returned alongside the outputs so the UI can display/edit them.
    """
    price = validate_money(selling_price, "selling_price", allow_zero=False)
    cost = validate_money(product_cost, "product_cost")
    ck = validate_money(clicks, "clicks")
    cvr = float(conversion_rate_pct)
    if cvr < 0 or cvr > 100:
        raise CalculationError("conversion_rate_pct must be between 0 and 100")
    cost_per_click = validate_money(cpc, "cpc")

    conversions = ck * cvr / 100.0
    revenue = conversions * price
    cogs = conversions * cost
    ad_cost = ck * cost_per_click
    gross_profit = revenue - cogs
    net_profit = gross_profit - ad_cost
    roas = (revenue / ad_cost) if ad_cost > 0 else None
    return {
        "assumptions": {
            "clicks": _r(ck, 0),
            "conversion_rate_pct": _r(cvr),
            "cpc": _r(cost_per_click),
        },
        "conversions": _r(conversions),
        "revenue": _r(revenue),
        "cogs": _r(cogs),
        "ad_cost": _r(ad_cost),
        "gross_profit": _r(gross_profit),
        "net_profit": _r(net_profit),
        "roas": _r(roas) if roas is not None else None,
        "cpa": _r(ad_cost / conversions) if conversions > 0 else None,
    }


def validate_allocation(total: Any, allocations: list) -> dict:
    """Validate that allocations are non-negative and sum exactly to total."""
    t = validate_money(total, "campaign budget", allow_zero=False)
    if not allocations:
        raise CalculationError("allocation list is empty")
    seen_labels = set()
    running = 0.0
    rows = []
    for a in allocations:
        label = str(a.get("label", "")).strip()
        if not label:
            raise CalculationError("every allocation needs a label")
        if label.lower() in seen_labels:
            raise CalculationError(f"duplicate allocation label: {label}")
        seen_labels.add(label.lower())
        amount = validate_money(a.get("amount"), f"allocation '{label}' amount")
        running += amount
        rows.append({"label": label, "amount": _r(amount), "purpose": str(a.get("purpose", ""))})
    if abs(running - t) > 0.005:
        raise CalculationError(
            f"allocations sum to {running:.2f} but campaign budget is {t:.2f} "
            f"(difference {running - t:+.2f})"
        )
    for row in rows:
        row["pct"] = _r(row["amount"] / t * 100.0, 1)
    return {"total": _r(t), "allocations": rows, "sum": _r(running)}


def allocate_budget(total: Any, split: dict) -> list:
    """Split a total budget by proportional weights, guaranteeing an exact sum.

    Remainder cents are assigned to the largest allocation so the rounded
    amounts always add up to the total.
    """
    t = validate_money(total, "campaign budget", allow_zero=False)
    if not split:
        raise CalculationError("split is empty")
    weights = {k: float(v) for k, v in split.items()}
    if any(w < 0 for w in weights.values()):
        raise CalculationError("split weights must not be negative")
    wsum = sum(weights.values())
    if wsum <= 0:
        raise CalculationError("split weights must sum to a positive number")
    amounts = {k: int(round(t * w / wsum)) for k, w in weights.items()}  # whole currency units
    drift = int(round(t)) - sum(amounts.values())
    if drift != 0:
        biggest = max(weights, key=lambda k: weights[k])
        amounts[biggest] += drift
    return [{"label": k, "amount": float(amounts[k])} for k in split]


def pct_of_budget(amount: Any, budget: Any) -> float:
    b = validate_money(budget, "budget", allow_zero=False)
    a = validate_money(amount, "amount")
    return _r(a / b * 100.0, 1)
