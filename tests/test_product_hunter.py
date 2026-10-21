"""Tests for Product Hunter: ranking, missing evidence, merging, filters."""
import pytest

from commercepilot.agents import product_hunter as ph
from commercepilot.schemas import Product, ResearchRequest

REQ = ResearchRequest(
    niche="skincare", market="Pakistan", audience="women 18-34 urban",
    budget=30000, mode="sample", limit=10,
)


class TestSampleDataset:
    def test_has_at_least_12_products(self):
        assert len(ph.load_sample_products()) >= 12

    def test_covers_five_categories(self):
        cats = {p.category for p in ph.load_sample_products()}
        assert {"skincare", "home accessories", "fashion accessories", "fitness", "electronics accessories"} <= cats

    def test_flagged_as_sample(self):
        assert all(p.is_sample_data for p in ph.load_sample_products())


class TestRanking:
    def test_sample_mode_returns_ranked_scored_products(self):
        result = ph.run(REQ)
        assert result.products
        assert all(p.score is not None for p in result.products)
        scores = [p.score for p in result.products]
        assert scores == sorted(scores, reverse=True)

    def test_every_product_has_explanation(self):
        for p in ph.run(REQ).products:
            assert p.ranking_reason
            assert p.confidence in ("low", "medium", "high")
            assert p.score_breakdown

    def test_margin_is_computed_from_stored_price_and_cost(self):
        result = ph.run(REQ)
        top = result.products[0]
        expected = round((top.observed_price - top.estimated_cost) / top.observed_price * 100, 2)
        assert top.margin_pct == expected

    def test_ranking_reason_references_sample_source(self):
        result = ph.run(REQ)
        assert "sample dataset" in result.products[0].ranking_reason.lower()

    def test_deterministic(self):
        a = [p.id for p in ph.run(REQ).products]
        b = [p.id for p in ph.run(REQ).products]
        assert a == b


class TestMissingEvidence:
    def test_product_with_no_data_is_unscored_not_invented(self):
        p = Product(id="x", title="Mystery item")
        out = ph.score_product(p, [], None, None)
        assert out.score is None
        assert out.confidence == "low"
        assert out.evidence_coverage == 0.0
        assert all(f.raw_score is None for f in out.score_breakdown)

    def test_partial_evidence_reduces_coverage_and_scales_score(self):
        p = Product(id="y", title="Serum", observed_price=2000, currency="PKR",
                    estimated_cost=600, demand_level="high", competition="medium",
                    audience_fit=90, price_suitability=None)
        out = ph.score_product(p, [], None, None)
        assert out.evidence_coverage == pytest.approx(0.9)  # only price_suitability unknown
        assert out.score < out.evidence_score  # thin evidence cannot beat full evidence
        assert out.confidence == "high"  # 4 of 5 factors evidenced (>= 0.8 coverage)

    def test_two_of_five_factors_is_medium_confidence(self):
        p = Product(id="y2", title="Lamp", observed_price=2500, currency="PKR",
                    estimated_cost=None, demand_level="medium", competition="high",
                    audience_fit=None, price_suitability=80)
        out = ph.score_product(p, [], None, None)
        assert out.confidence == "medium"  # 3 of 5 factors evidenced (0.6 coverage)

    def test_unknown_competition_is_excluded_not_zeroed(self):
        p = Product(id="z", title="Bag", observed_price=1000, currency="PKR", estimated_cost=300,
                    competition="unknown", demand_level="low", audience_fit=80, price_suitability=80)
        out = ph.score_product(p, [], None, None)
        comp = next(f for f in out.score_breakdown if f.factor == "competition")
        assert comp.raw_score is None and comp.contribution is None

    def test_weight_override_is_honoured(self):
        p = Product(id="w", title="Serum", observed_price=2000, currency="PKR", estimated_cost=200,
                    demand_level="high", competition="low", audience_fit=90, price_suitability=90)
        biased = ph.score_product(Product(**p.model_dump()), [], None, None, weights={"margin": 100})
        normal = ph.score_product(Product(**p.model_dump()), [], None, None)
        assert biased.score != normal.score
        margin = next(f for f in biased.score_breakdown if f.factor == "margin")
        assert margin.weight >= 0.9


class TestLiveParsing:
    def test_price_parser_pkr(self):
        assert ph.parse_price("Only Rs. 1,299 today") == (1299.0, "PKR")

    def test_price_parser_usd(self):
        assert ph.parse_price("was $19.99 now cheaper") == (19.99, "USD")

    def test_price_parser_none(self):
        assert ph.parse_price("great product, best price") == (None, None)

    def test_category_guess(self):
        assert ph.guess_category("best vitamin c serum") == "skincare"
        assert ph.guess_category("resistance bands kit") == "fitness"
        assert ph.guess_category("random words") == "uncategorised"

    def test_live_product_marks_unknowns(self):
        p = ph._live_product(ph.SearchResult(title="Buy Serum in Pakistan", url="https://x.com/a", snippet="Best price"), 1)
        assert p.estimated_cost is None and p.demand_level is None and p.competition == "unknown"
        assert p.is_sample_data is False


class TestMergeAndFilters:
    def test_dedupe_merges_same_url(self):
        a = Product(id="a", title="Serum One", source="sample", source_url=None,
                    observed_price=1000, currency="PKR", estimated_cost=300)
        b = Product(id="b", title="Serum One", source="live", source_url="https://shop.com/serum")
        merged = ph._dedupe([a, b])
        assert len(merged) == 1
        assert merged[0].source_url == "https://shop.com/serum"
        assert merged[0].estimated_cost == 300  # richer record preserved

    def test_dedupe_keeps_distinct(self):
        a = Product(id="a", title="Serum One")
        b = Product(id="b", title="Yoga Mat Pro")
        assert len(ph._dedupe([a, b])) == 2

    def test_price_range_filter(self):
        req = ResearchRequest(niche="skincare", mode="sample", price_min=3000, price_max=4000, limit=20)
        result = ph.run(req)
        for p in result.products:
            assert p.observed_price is None or 3000 <= p.observed_price <= 4000

    def test_category_filter(self):
        req = ResearchRequest(niche="x", mode="sample", categories=["fitness"], limit=20)
        result = ph.run(req)
        assert result.products and all(p.category == "fitness" for p in result.products)

    def test_constraint_filter(self):
        req = ResearchRequest(niche="x", mode="sample", constraints=["no electronics"], limit=20)
        result = ph.run(req)
        assert all(p.category != "electronics accessories" for p in result.products)
