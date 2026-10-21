"""Unit tests for the exact business calculations (Business Analyst core)."""
import pytest

from commercepilot.tools import calculations as calc


class TestGrossProfit:
    def test_basic(self):
        assert calc.gross_profit_per_unit(2499, 820) == 1679.0

    def test_zero_cost(self):
        assert calc.gross_profit_per_unit(1000, 0) == 1000.0

    def test_loss_making(self):
        assert calc.gross_profit_per_unit(500, 700) == -200.0

    def test_rejects_negative_price(self):
        with pytest.raises(calc.CalculationError):
            calc.gross_profit_per_unit(-5, 1)

    def test_rejects_negative_cost(self):
        with pytest.raises(calc.CalculationError):
            calc.gross_profit_per_unit(100, -1)

    def test_rejects_zero_price(self):
        with pytest.raises(calc.CalculationError):
            calc.gross_profit_per_unit(0, 100)

    def test_rejects_non_numeric(self):
        with pytest.raises(calc.CalculationError):
            calc.gross_profit_per_unit("abc", 100)

    def test_rejects_none(self):
        with pytest.raises(calc.CalculationError):
            calc.gross_profit_per_unit(None, 100)

    def test_rejects_bool(self):
        with pytest.raises(calc.CalculationError):
            calc.gross_profit_per_unit(True, 100)


class TestMargin:
    def test_basic(self):
        assert calc.gross_margin_pct(2499, 820) == 67.19

    def test_full_margin(self):
        assert calc.gross_margin_pct(100, 0) == 100.0

    def test_negative_margin(self):
        assert calc.gross_margin_pct(100, 150) == -50.0

    def test_zero_price_undefined(self):
        with pytest.raises(calc.CalculationError):
            calc.gross_margin_pct(0, 50)


class TestBreakEvenRoas:
    def test_basic(self):
        # 2499 / 1679 = 1.4884 -> 1.49
        assert calc.break_even_roas(2499, 1679) == 1.49

    def test_zero_profit_is_undefined(self):
        assert calc.break_even_roas(100, 0) is None

    def test_negative_profit_is_undefined(self):
        assert calc.break_even_roas(100, -50) is None

    def test_invalid_price_raises(self):
        with pytest.raises(calc.CalculationError):
            calc.break_even_roas(-1, 10)


class TestCpa:
    def test_basic(self):
        assert calc.cost_per_acquisition(6000, 4) == 1500.0

    def test_zero_customers_is_none(self):
        assert calc.cost_per_acquisition(1000, 0) is None

    def test_zero_spend(self):
        assert calc.cost_per_acquisition(0, 3) == 0.0

    def test_negative_customers_raises(self):
        with pytest.raises(calc.CalculationError):
            calc.cost_per_acquisition(100, -1)


class TestConversionRate:
    def test_basic(self):
        assert calc.conversion_rate(4, 150) == 2.67

    def test_zero_clicks_is_none(self):
        assert calc.conversion_rate(3, 0) is None

    def test_zero_both_is_none(self):
        assert calc.conversion_rate(0, 0) is None

    def test_negative_raises(self):
        with pytest.raises(calc.CalculationError):
            calc.conversion_rate(-1, 10)


class TestBudget:
    def test_allocation_sum_must_match(self):
        ok = calc.validate_allocation(30000, [
            {"label": "Testing", "amount": 7500},
            {"label": "Scaling", "amount": 19500},
            {"label": "Reserve", "amount": 3000},
        ])
        assert ok["sum"] == 30000.0
        assert ok["allocations"][0]["pct"] == 25.0

    def test_allocation_mismatch_raises(self):
        with pytest.raises(calc.CalculationError) as exc:
            calc.validate_allocation(30000, [{"label": "all", "amount": 25000}])
        assert "25000" in str(exc.value)

    def test_negative_allocation_raises(self):
        with pytest.raises(calc.CalculationError):
            calc.validate_allocation(30000, [{"label": "x", "amount": -5}])

    def test_empty_allocation_raises(self):
        with pytest.raises(calc.CalculationError):
            calc.validate_allocation(30000, [])

    def test_duplicate_label_raises(self):
        with pytest.raises(calc.CalculationError):
            calc.validate_allocation(30000, [{"label": "a", "amount": 15000}, {"label": "a", "amount": 15000}])

    def test_allocate_budget_exact_sum(self):
        rows = calc.allocate_budget(30000, {"a": 25, "b": 65, "c": 10})
        assert sum(r["amount"] for r in rows) == 30000.0

    def test_allocate_budget_awkward_total(self):
        rows = calc.allocate_budget(33333, {"a": 1, "b": 1, "c": 1})
        assert sum(r["amount"] for r in rows) == 33333.0

    def test_allocate_budget_rejects_negative_weights(self):
        with pytest.raises(calc.CalculationError):
            calc.allocate_budget(100, {"a": -1, "b": 2})


class TestScenario:
    def test_projection_math(self):
        out = calc.scenario_projection(2499, 820, clicks=1000, conversion_rate_pct=2, cpc=45)
        assert out["conversions"] == 20.0
        assert out["revenue"] == 49980.0
        assert out["ad_cost"] == 45000.0
        assert out["net_profit"] == (49980 - 16400 - 45000)

    def test_zero_clicks(self):
        out = calc.scenario_projection(1000, 400, clicks=0, conversion_rate_pct=2, cpc=45)
        assert out["conversions"] == 0
        assert out["roas"] is None
        assert out["cpa"] is None

    def test_invalid_cvr_raises(self):
        with pytest.raises(calc.CalculationError):
            calc.scenario_projection(1000, 400, clicks=10, conversion_rate_pct=150, cpc=45)

    def test_budget_summary_rejects_overspend(self):
        with pytest.raises(calc.CalculationError):
            calc.ad_spend_summary(1000, 2000)
