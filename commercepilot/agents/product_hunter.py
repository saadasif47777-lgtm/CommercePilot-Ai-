"""AGENT A - Product Hunter.

Discovers, scores and ranks product candidates for a niche.

Input  (ResearchRequest): niche, market, audience, budget, price range, constraints.
Output (ResearchResult): ranked products with evidence, source URLs, transparent
score breakdowns, confidence levels and ranking reasons.

Two research modes:
  * live  - real web search via commercepilot/tools/web_search.py (source URLs kept)
  * sample- local demonstration dataset (clearly labelled, not real demand)
  * both  - merged, de-duplicated, per-record source preserved.

Scoring is a configurable weighted heuristic, NEVER a market prediction.
Missing evidence is reported as "unknown" instead of being invented: unknown
factors are excluded and the remaining weights are renormalised.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional

from .. import config
from ..schemas import (
    DemandSignal,
    Product,
    ResearchRequest,
    ResearchResult,
    ScoreFactor,
    utcnow,
)
from ..tools import calculations as calc
from ..tools.product_pages import PageFacts, inspect_pages, is_collection_url
from ..tools.web_search import SearchResult, search

DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "sample_products.json"

DEFAULT_WEIGHTS: dict[str, float] = {
    "margin": 0.30,
    "demand": 0.25,
    "competition": 0.20,
    "audience_fit": 0.15,
    "price_suitability": 0.10,
}

DEMAND_SCORE = {"high": 90.0, "medium": 60.0, "low": 30.0}
COMPETITION_SCORE = {"low": 90.0, "medium": 55.0, "high": 25.0}
MARGIN_FULL_SCORE_PCT = 70.0  # a 70%+ gross margin scores 100 on the margin factor

CATEGORY_KEYWORDS = {
    "skincare": ["serum", "skin", "moistur", "lip mask", "facial", "acne", "niacinamide", "vitamin c", "ceramide"],
    "home accessories": ["vase", "home", "decor", "basket", "lamp", "living room", "storage", "sunset"],
    "fashion accessories": ["necklace", "bag", "tote", "jewelry", "jewellery", "scrunchie", "hair", "accessor", "watch"],
    "fitness": ["fitness", "yoga", "workout", "resistance", "gym", "exercise", "bottle"],
    "electronics accessories": ["charger", "power bank", "cable", "earbuds", "electronic", "headphone", "adapter", "usb"],
}

CURRENCY_HINTS = [
    (r"(?:pkr|rs\.?|₨)\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)", "PKR"),
    (r"([0-9][0-9,]*(?:\.[0-9]{1,2})?)\s*(?:pkr|rs\.?|₨)", "PKR"),
    (r"\$\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)", "USD"),
]


# --------------------------------------------------------------------------- #
# Sample dataset
# --------------------------------------------------------------------------- #
def load_sample_products() -> list[Product]:
    if config.production():
        raise ValueError("Sample catalogue is disabled in production")
    raw = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    products: list[Product] = []
    for row in raw["products"]:
        signals = [
            DemandSignal(label=s["label"], value=s["value"], evidence=s.get("evidence", "sample dataset (demo)"))
            for s in row.get("signals", [])
        ]
        signals.insert(
            0,
            DemandSignal(
                label="Data provenance",
                value="SAMPLE DATASET",
                evidence="data/sample_products.json - illustrative demo data, not live market data",
            ),
        )
        price = row.get("observed_price")
        cost = row.get("estimated_cost")
        margin = gross = None
        if price and cost is not None:
            try:
                gross = calc.gross_profit_per_unit(price, cost)
                margin = calc.gross_margin_pct(price, cost)
            except calc.CalculationError:
                pass
        products.append(
            Product(
                id=row["id"],
                title=row["title"],
                description=row.get("description", ""),
                category=row.get("category", "uncategorised"),
                source="sample",
                source_url=None,
                observed_price=price,
                currency=raw["meta"].get("currency", "PKR"),
                estimated_cost=cost,
                cost_is_estimate=True,
                demand_level=row.get("demand_level"),
                demand_signals=signals,
                competition=row.get("competition", "unknown"),
                audience_fit=row.get("audience_fit"),
                price_suitability=row.get("price_suitability"),
                audience_tags=row.get("audience_tags", []),
                is_sample_data=True,
                margin_pct=margin,
                gross_profit=gross,
            )
        )
    return products


# --------------------------------------------------------------------------- #
# Live search results -> products
# --------------------------------------------------------------------------- #
def parse_price(text: str) -> tuple[Optional[float], Optional[str]]:
    """Extract the first detectable price and its currency. None when absent."""
    if not text:
        return None, None
    for pattern, currency in CURRENCY_HINTS:
        m = re.search(pattern, text, flags=re.IGNORECASE)
        if m:
            try:
                value = float(m.group(1).replace(",", ""))
            except ValueError:
                continue
            if 0 < value < 1_000_000_000:
                return value, currency
    return None, None


def guess_category(text: str) -> str:
    lowered = text.lower()
    for category, words in CATEGORY_KEYWORDS.items():
        if any(w in lowered for w in words):
            return category
    return "uncategorised"


def _domain(url: str) -> str:
    m = re.search(r"https?://(?:www\.)?([^/]+)", url or "")
    return m.group(1) if m else ""


def _live_product(result: SearchResult, index: int) -> Product:
    price, currency = parse_price(f"{result.title} {result.snippet}")
    text = f"{result.title} {result.snippet}"
    category = guess_category(text)
    collection = is_collection_url(result.url)
    signals = [
        DemandSignal(
            label="Live search result",
            value=result.title[:90],
            evidence=result.url,
        )
    ]
    return Product(
        id="live-" + hashlib.sha256(result.url.encode()).hexdigest()[:20],
        title=result.title or result.url,
        description=result.snippet[:400],
        category=category,
        source="live",
        source_url=result.url,
        observed_price=None if collection else price,
        price_source="collection has no single product price" if collection else "search snippet — confirm on source" if price else "not provided",
        page_kind="collection" if collection else "not_checked",
        currency=None if collection else currency,
        estimated_cost=None,  # unknown - never invented
        demand_level=None,  # unknown - a search hit is not demand evidence
        demand_signals=signals,
        competition="unknown",
        audience_fit=None,
        price_suitability=None,
        is_sample_data=False,
    )


def enrich_product(product: Product, facts: PageFacts) -> Product:
    product.page_kind = "collection" if product.page_kind == "collection" and facts.kind == "needs_review" else facts.kind
    product.page_checked_at = utcnow()
    product.extraction_note = facts.note
    product.availability = facts.availability
    if facts.kind == "product":
        product.title = facts.title or product.title
        product.description = facts.description or product.description
        product.observed_price = facts.price
        product.currency = facts.currency
        product.price_source = facts.price_basis
        product.source_url = facts.url
        product.category = guess_category(product.title + " " + product.description)
        product.demand_signals.append(DemandSignal(label="Product page inspected", value=facts.price_basis, evidence=facts.url))
    elif product.page_kind == "collection":
        product.observed_price, product.currency = None, None
        product.price_source = "collection has no single product price"
    return product


# --------------------------------------------------------------------------- #
# Scoring
# --------------------------------------------------------------------------- #
def _margin_score(product: Product) -> Optional[float]:
    margin = product.margin_pct
    if margin is None and product.observed_price and product.estimated_cost is not None:
        # Derive margin from the stored price and estimated cost when present.
        try:
            margin = calc.gross_margin_pct(product.observed_price, product.estimated_cost)
            product.margin_pct = margin
            if product.gross_profit is None:
                product.gross_profit = calc.gross_profit_per_unit(product.observed_price, product.estimated_cost)
        except calc.CalculationError:
            return None
    if margin is None:
        return None
    return max(0.0, min(100.0, margin / MARGIN_FULL_SCORE_PCT * 100.0))


def _demand_score(product: Product) -> Optional[float]:
    if product.demand_level is None:
        return None
    return DEMAND_SCORE.get(product.demand_level)


def _competition_score(product: Product) -> Optional[float]:
    if product.competition == "unknown":
        return None
    return COMPETITION_SCORE.get(product.competition)


def _audience_score(product: Product, audience_keywords: list[str]) -> Optional[float]:
    if product.audience_fit is not None:
        return float(product.audience_fit)
    if not audience_keywords:
        return None
    # Evidence = the record's own text (dataset tags for sample rows, the live
    # search title/snippet for live rows). No match found -> unknown, not zero.
    haystack = f"{' '.join(product.audience_tags)} {product.title} {product.description}".lower()
    hits = sum(1 for k in audience_keywords if k and k in haystack)
    if hits == 0:
        return None
    return round(hits / len(audience_keywords) * 100.0, 1)


def _price_score(product: Product, price_min: Optional[float], price_max: Optional[float]) -> Optional[float]:
    if product.price_suitability is not None:
        return float(product.price_suitability)
    if product.observed_price is None:
        return None
    if price_min is None and price_max is None:
        return None  # no preference expressed -> unknown, not guessed
    p = product.observed_price
    if price_min is not None and p < price_min:
        return max(0.0, 100.0 - (price_min - p) / max(price_min, 1) * 100.0)
    if price_max is not None and p > price_max:
        return max(0.0, 100.0 - (p - price_max) / max(price_max, 1) * 100.0)
    return 95.0


def score_product(
    product: Product,
    audience_keywords: list[str],
    price_min: Optional[float],
    price_max: Optional[float],
    weights: Optional[dict[str, float]] = None,
) -> Product:
    """Attach a 0-100 weighted score, breakdown and confidence to one product."""
    raw_scores: dict[str, Optional[float]] = {
        "margin": _margin_score(product),
        "demand": _demand_score(product),
        "competition": _competition_score(product),
        "audience_fit": _audience_score(product, audience_keywords),
        "price_suitability": _price_score(product, price_min, price_max),
    }
    if product.page_kind == "collection":
        raw_scores = dict.fromkeys(raw_scores)

    w = dict(DEFAULT_WEIGHTS)
    if weights:
        for key, value in weights.items():
            if key in w and isinstance(value, (int, float)) and value >= 0:
                w[key] = float(value)
    total_w = sum(w.values())
    if total_w <= 0:
        w, total_w = dict(DEFAULT_WEIGHTS), sum(DEFAULT_WEIGHTS.values())
    w = {k: v / total_w for k, v in w.items()}  # normalise so weights sum to 1

    known = {k: v for k, v in raw_scores.items() if v is not None}
    breakdown: list[ScoreFactor] = []
    if known and sum(w[k] for k in known) > 0:
        known_weight_sum = sum(w[k] for k in known)
        score = 0.0
        for factor in ("margin", "demand", "competition", "audience_fit", "price_suitability"):
            raw = raw_scores[factor]
            if raw is None:
                breakdown.append(
                    ScoreFactor(
                        factor=factor,
                        weight=round(w[factor], 3),
                        raw_score=None,
                        contribution=None,
                        note="unknown - no evidence available; excluded and remaining weights renormalised",
                    )
                )
                continue
            effective_w = w[factor] / known_weight_sum
            contribution = effective_w * raw
            score += contribution
            breakdown.append(
                ScoreFactor(
                    factor=factor,
                    weight=round(effective_w, 3),
                    raw_score=round(raw, 1),
                    contribution=round(contribution, 2),
                    note=_factor_note(factor, product),
                )
            )
        evidence_score = max(0.0, min(100.0, score))
        product.evidence_score = round(evidence_score, 1)
        product.evidence_coverage = round(known_weight_sum, 2)
        # Ranking score: evidence score scaled by how much of the weighting
        # actually had evidence. Fully evidenced products are not penalised;
        # thin evidence cannot outrank well-evidenced candidates.
        product.score = round(evidence_score * known_weight_sum, 1)
    else:
        product.score = None
        product.evidence_score = None
        product.evidence_coverage = 0.0
        for factor in w:
            breakdown.append(
                ScoreFactor(factor=factor, weight=round(w[factor], 3), note="unknown - no evidence available")
            )

    known_ratio = len(known) / len(raw_scores)
    if known_ratio >= 0.8:
        confidence = "high"
    elif known_ratio >= 0.5:
        confidence = "medium"
    else:
        confidence = "low"
    product.confidence = confidence  # type: ignore[assignment]
    product.score_breakdown = breakdown
    product.ranking_reason = _ranking_reason(product, known, known_ratio, confidence)
    return product


def _factor_note(factor: str, product: Product) -> str:
    if factor == "margin":
        return (
            f"estimated margin {product.margin_pct:.1f}% (price {product.observed_price} - "
            f"estimated cost {product.estimated_cost}; cost is an ESTIMATE)"
            if product.margin_pct is not None and product.observed_price and product.estimated_cost is not None
            else "margin from dataset estimates"
        )
    if factor == "demand":
        return f"demand level '{product.demand_level}' (sample evidence)" if product.is_sample_data else f"demand level '{product.demand_level}'"
    if factor == "competition":
        return f"competition assessed as {product.competition}"
    if factor == "audience_fit":
        return "audience fit from dataset rating" if product.audience_fit is not None else "audience fit computed from tag overlap"
    return "price fit vs your preferred range" if product.price_suitability is None else "price suitability from dataset rating"


def _ranking_reason(product: Product, known: dict, known_ratio: float, confidence: str) -> str:
    if not known or product.evidence_score is None:
        return "No scoring evidence available - listed for manual review only."
    top = sorted(known.items(), key=lambda kv: kv[1], reverse=True)[:2]
    parts = [f"{k.replace('_', ' ')} ({v:.0f}/100)" for k, v in top]
    unknown = [k for k, v in known.items() if v is None]
    unknown = [k for k in DEFAULT_WEIGHTS if k not in known]
    reason = f"Evidence score {product.evidence_score:.1f}/100 on {', '.join(parts)}."
    if unknown:
        reason += f" Unknown (not estimated): {', '.join(u.replace('_', ' ') for u in unknown)}."
    cov = f"{product.evidence_coverage * 100:.0f}%" if product.evidence_coverage is not None else "?"
    reason += (
        f" Coverage {cov} of weighting -> ranking score {product.score:.1f}. "
        f"Confidence {confidence} ({len(known)}/{len(DEFAULT_WEIGHTS)} factors evidenced)."
    )
    if product.source == "live" and product.source_url:
        reason += f" Source: {product.source_url}"
    elif product.is_sample_data:
        reason += " Source: sample dataset (demo)."
    return reason


# --------------------------------------------------------------------------- #
# Filters / merge / orchestration of the agent
# --------------------------------------------------------------------------- #
def _normalise_title(title: str) -> str:
    t = re.sub(r"[^a-z0-9 ]", " ", (title or "").lower())
    return re.sub(r"\s+", " ", t).strip()


def _dedupe(products: list[Product]) -> list[Product]:
    """Merge duplicate listings (same URL or near-identical title).

    The record already in the list is updated in place so the richer merged
    data is never lost, and both sources stay attached (source="merged").
    """
    merged: list[Product] = []
    carry_fields = (
        "observed_price",
        "currency",
        "estimated_cost",
        "margin_pct",
        "gross_profit",
        "audience_fit",
        "price_suitability",
        "demand_level",
    )
    for product in products:
        best: Optional[Product] = None
        for existing in merged:
            ratio = SequenceMatcher(
                None, _normalise_title(product.title), _normalise_title(existing.title)
            ).ratio()
            if ratio > 0.86 or (product.source_url and product.source_url == existing.source_url):
                best = existing
                break
        if best is None:
            merged.append(product)
            continue
        for field in carry_fields:
            if getattr(best, field) is None and getattr(product, field) is not None:
                setattr(best, field, getattr(product, field))
        if best.category in ("uncategorised", "") and product.category not in ("uncategorised", ""):
            best.category = product.category
        if product.source_url and not best.source_url:
            best.source_url = product.source_url
        for tag in product.audience_tags:
            if tag not in best.audience_tags:
                best.audience_tags.append(tag)
        known_signals = {s.evidence for s in best.demand_signals}
        best.demand_signals.extend(s for s in product.demand_signals if s.evidence not in known_signals)
        if product.source != best.source:
            best.source = "merged"
            # merged rows still contain sample records, so keep the demo label
            best.is_sample_data = best.is_sample_data or product.is_sample_data
    return merged


def _matches_constraints(product: Product, constraints: list[str]) -> bool:
    """Exclude products that violate an explicit user constraint (best effort)."""
    if not constraints:
        return True
    haystack = f"{product.category} {' '.join(product.audience_tags)} {product.title}".lower()
    for constraint in constraints:
        c = constraint.lower().strip()
        if not c:
            continue
        if c.startswith("no ") and c[3:] in haystack:
            return False
        if "avoid" in c and c.split("avoid", 1)[1].strip() in haystack:
            return False
        if c == "lightweight only" and any(t in haystack for t in ("bulky", "heavy")):
            return False
    return True


def _build_query(req: ResearchRequest) -> str:
    parts = [req.niche or "product", "product price"]
    if req.market:
        parts.append(req.market)
    if req.price_min is not None and req.price_max is not None:
        parts.append(f"price {int(req.price_min)}-{int(req.price_max)}")
    return " ".join(str(p) for p in parts if p)


def _audience_keywords(audience: str) -> list[str]:
    if not audience:
        return []
    words = re.findall(r"[a-z0-9]+", audience.lower())
    stop = {"and", "the", "for", "with", "who", "are", "aged", "years", "old", "in", "of", "to"}
    return [w for w in words if len(w) > 2 and w not in stop][:8]


def run(req: ResearchRequest) -> ResearchResult:
    """Execute Product Hunter. Never raises: failures become warnings."""
    if config.production():
        if req.mode == "sample":
            raise ValueError("Sample research is disabled in production")
        req = req.model_copy(update={"mode": "live"})
    started = time.time()
    warnings: list[str] = []
    sources: list[str] = []
    query = _build_query(req)
    audience_kw = _audience_keywords(req.audience or "")

    sample_products: list[Product] = []
    if req.mode in ("sample", "both"):
        sample_products = load_sample_products()
        if not sample_products:
            warnings.append("Sample dataset is empty or unreadable.")

    live_products: list[Product] = []
    contains_live = False
    if req.mode in ("live", "both"):
        outcome = search(f"{query} buy online", limit=max(req.limit, 6))
        if outcome.warning:
            warnings.append(outcome.warning)
        if outcome.results:
            contains_live = True
            live_products = [_live_product(r, i + 1) for i, r in enumerate(outcome.results)]
            # Inspect four sources, then up to four same-site product links
            # discovered on collections. This is bounded, not a recursive crawl.
            facts = inspect_pages([p.source_url for p in live_products[:4]])
            for product, page in zip(live_products, facts, strict=False):
                enrich_product(product, page)
            niche_words = [w.rstrip("s") for w in re.findall(r"[a-z]+", (req.niche or "").lower()) if len(w) > 3 and w not in {"ceramic", "handmade", "decorative", "products"}]
            children = list(dict.fromkeys(link for page in facts if page.kind == "collection"
                                          for link in sorted(page.links, key=lambda link: not any(w in link.lower() for w in niche_words))[:2]))[:4]
            existing_urls = {p.source_url for p in live_products}
            for page in inspect_pages([link for link in children if link not in existing_urls]):
                if page.kind == "product" and (not niche_words or any(w in page.title.lower() for w in niche_words)):
                    live_products.append(enrich_product(_live_product(SearchResult(page.title, page.url, page.description), 0), page))
            domains = sorted({_domain(r.url) for r in outcome.results if _domain(r.url)})
            sources.extend(domains)
            # A real, verifiable observation about the result set (not a demand score).
            landscape = DemandSignal(
                label="Search landscape (live)",
                value=f"{len(domains)} distinct retailer domains returned for this query",
                evidence=f"{outcome.provider} search API, {outcome.elapsed_ms}ms",
            )
            for product in live_products:
                product.demand_signals.append(landscape)
        elif req.mode == "live":
            warnings.append(
                "Live search returned no usable results. Try a more specific niche, check the search connection, or import your own product."
            )

    candidates = sample_products + live_products
    if req.categories:
        wanted = {c.lower() for c in req.categories}
        candidates = [p for p in candidates if p.category.lower() in wanted]

    filtered: list[Product] = []
    dropped_price = 0
    for product in candidates:
        if not _matches_constraints(product, req.constraints):
            continue
        compatible = not req.currency or product.currency == req.currency
        if (compatible
            and product.observed_price is not None
            and req.price_min is not None
            and product.observed_price < req.price_min
        ):
            dropped_price += 1
            continue
        if (compatible
            and product.observed_price is not None
            and req.price_max is not None
            and product.observed_price > req.price_max
        ):
            dropped_price += 1
            continue
        filtered.append(product)
    if dropped_price:
        warnings.append(f"{dropped_price} candidate(s) excluded by your preferred price range.")

    merged = _dedupe(filtered)
    scored = [
        score_product(p, audience_kw,
                      req.price_min if not req.currency or p.currency == req.currency else None,
                      req.price_max if not req.currency or p.currency == req.currency else None,
                      req.weights) for p in merged
    ]
    scored.sort(key=lambda p: (p.page_kind == "collection", p.page_kind != "product", p.score is None, -(p.score or 0)))

    if req.mode == "both":
        # Keep live web results visible in the merged ranking. Score order is
        # preserved: unscored (evidence-only) rows sort last, and we simply
        # reserve a few slots so sample rows cannot crowd live sources out.
        live_rows = [p for p in scored if p.source in ("live", "merged")]
        if live_rows:
            reserve = min(len(live_rows), max(3, req.limit // 4))
            chosen_live = live_rows[:reserve]
            chosen_ids = {id(p) for p in chosen_live}
            headroom = max(0, req.limit - len(chosen_live))
            chosen_rest = [p for p in scored if id(p) not in chosen_ids][:headroom]
            scored = sorted(
                chosen_live + chosen_rest, key=lambda p: (p.score is None, -(p.score or 0))
            )
    scored = scored[: req.limit]

    unknown_priced = sum(1 for p in scored if p.observed_price is None and p.page_kind != "collection")
    if unknown_priced:
        warnings.append(
            f"{unknown_priced} result(s) need price confirmation. Open an individual product link or import your catalog."
        )
    # "Sample" means no live evidence reached the final result set.
    is_sample = (req.mode != "live" and all(p.is_sample_data for p in scored)) or not contains_live
    if contains_live:
        warnings.append(
            "Product pages are inspected where permitted. Collection pages are discovery sources, not products. "
            "Prices are source observations, not supplier quotes. Enter your own cost to calculate margin; sales demand remains unverified."
        )
        checked = sum(p.page_kind == "product" for p in scored)
        warnings.append(f"{checked} individual product page(s) identified. Up to eight pages are checked per run; blocked and dynamic pages need manual review.")
        if req.currency and any(p.observed_price is not None and p.currency != req.currency for p in scored):
            warnings.append(f"Some prices have another or unconfirmed currency. The {req.currency} price filter and price-fit score were not applied to them; no FX conversion was assumed.")

    return ResearchResult(
        mode=req.mode,
        query=query,
        products=scored,
        is_sample_data=is_sample,
        contains_live_results=contains_live,
        sources=sources,
        warnings=warnings,
        elapsed_ms=int((time.time() - started) * 1000),
    )


def score_with_defaults(product: Product, req: ResearchRequest) -> Product:
    """Re-score a single product with the same rules (used on selection)."""
    return score_product(
        product,
        _audience_keywords(req.audience or ""),
        req.price_min,
        req.price_max,
        req.weights,
    )
