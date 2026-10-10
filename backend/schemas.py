"""Pydantic schemas: request/response contracts and shared typed data structures.

Every API route validates its payload against these models, and every agent
reads/writes these structures through the shared project context.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


ColorStr = str
HEX_RE = r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$"


# --------------------------------------------------------------------------- #
# Shared primitives
# --------------------------------------------------------------------------- #
class DemandSignal(BaseModel):
    label: str
    value: str
    evidence: str = Field(description="Where this signal came from (URL or 'sample dataset entry').")


class ScoreFactor(BaseModel):
    factor: str
    weight: float = Field(description="Weight actually used for this product (renormalised).")
    raw_score: Optional[float] = Field(None, description="0-100 score for this factor, None = unknown")
    contribution: Optional[float] = None
    note: str = ""


class Product(BaseModel):
    id: str
    title: str
    description: str = ""
    category: str = "uncategorised"
    source: Literal["sample", "live", "merged"] = "sample"
    source_url: Optional[str] = None
    observed_price: Optional[float] = Field(None, ge=0)
    currency: Optional[str] = None
    estimated_cost: Optional[float] = Field(
        None, ge=0, description="ESTIMATE only - never a verified supplier quote."
    )
    cost_is_estimate: bool = True
    demand_level: Optional[Literal["low", "medium", "high"]] = None
    demand_signals: list[DemandSignal] = Field(default_factory=list)
    competition: Literal["low", "medium", "high", "unknown"] = "unknown"
    audience_fit: Optional[int] = Field(None, ge=0, le=100)
    price_suitability: Optional[int] = Field(None, ge=0, le=100)
    audience_tags: list[str] = Field(default_factory=list)
    score: Optional[float] = Field(None, ge=0, le=100, description="Coverage-adjusted ranking score.")
    evidence_score: Optional[float] = Field(
        None, ge=0, le=100, description="0-100 score computed on evidenced factors only."
    )
    evidence_coverage: Optional[float] = Field(
        None, ge=0, le=1, description="Share of total weighting that had real evidence."
    )
    score_breakdown: list[ScoreFactor] = Field(default_factory=list)
    confidence: Literal["low", "medium", "high"] = "low"
    ranking_reason: str = ""
    is_sample_data: bool = True
    margin_pct: Optional[float] = None
    gross_profit: Optional[float] = None


class ResearchRequest(BaseModel):
    niche: Optional[str] = Field(None, max_length=200)
    market: Optional[str] = Field("Pakistan", max_length=100)
    audience: Optional[str] = Field(None, max_length=400)
    budget: Optional[float] = Field(None, ge=0)
    price_min: Optional[float] = Field(None, ge=0)
    price_max: Optional[float] = Field(None, ge=0)
    constraints: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    mode: Literal["sample", "live", "both"] = "both"
    limit: int = Field(12, ge=1, le=50)
    weights: Optional[dict[str, float]] = Field(
        None, description="Optional override of scoring weights."
    )


class ResearchResult(BaseModel):
    mode: Literal["sample", "live", "both"]
    query: str = ""
    products: list[Product]
    is_sample_data: bool = True
    contains_live_results: bool = False
    sources: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    generated_at: str = Field(default_factory=utcnow)
    elapsed_ms: int = 0


# --------------------------------------------------------------------------- #
# Business brief & project
# --------------------------------------------------------------------------- #
class BusinessBrief(BaseModel):
    business_name: str = Field("", max_length=120)
    industry: str = Field("", max_length=120)
    niche: str = Field("", max_length=200)
    target_market: str = Field("Pakistan", max_length=100)
    target_audience: str = Field("", max_length=600)
    currency: str = Field("PKR", max_length=8)
    budget: float = Field(0, ge=0)
    brand_personality: str = Field("", max_length=400)
    preferred_price_min: Optional[float] = Field(None, ge=0)
    preferred_price_max: Optional[float] = Field(None, ge=0)
    constraints: list[str] = Field(default_factory=list)
    notes: str = Field("", max_length=2000)

    @field_validator("currency")
    @classmethod
    def _upper(cls, v: str) -> str:
        v = v.strip().upper()
        if not v or len(v) > 8:
            raise ValueError("currency must be a short code such as PKR or USD")
        return v

    @model_validator(mode="after")
    def _range(self):
        if (
            self.preferred_price_min is not None
            and self.preferred_price_max is not None
            and self.preferred_price_max < self.preferred_price_min
        ):
            raise ValueError("preferred_price_max must be >= preferred_price_min")
        return self


class ProjectCreate(BaseModel):
    name: Optional[str] = Field(None, max_length=160)
    example: bool = Field(False, description="Seed the illustrative Pakistani skincare demo brief.")
    brief: Optional[BusinessBrief] = None


class BriefUpdate(BaseModel):
    brief: BusinessBrief


# --------------------------------------------------------------------------- #
# Store Architect: structured website specification
# --------------------------------------------------------------------------- #
class NavItem(BaseModel):
    label: str
    href: str = "#"


class HeaderSection(BaseModel):
    type: Literal["header"] = "header"
    visible: bool = True
    logo_text: str = ""
    nav: list[NavItem] = Field(default_factory=list)
    cta_label: str = "Shop now"
    show_search: bool = True


class HeroSection(BaseModel):
    type: Literal["hero"] = "hero"
    visible: bool = True
    style: Literal["centered", "split", "editorial_split", "boxed", "minimal"] = "split"
    badge: str = ""
    headline: str = ""
    subheadline: str = ""
    cta_label: str = "Shop the collection"
    secondary_cta_label: str = "Learn more"
    image_style: str = "product"


class FeaturedSection(BaseModel):
    type: Literal["featured"] = "featured"
    visible: bool = True
    title: str = "Featured product"
    show_catalog: bool = True
    catalog_filter: bool = True


class ProductDetailSection(BaseModel):
    type: Literal["product_detail"] = "product_detail"
    visible: bool = True
    title: str = "Product details"
    description: str = ""
    bullets: list[str] = Field(default_factory=list)


class BenefitsSection(BaseModel):
    type: Literal["benefits"] = "benefits"
    visible: bool = True
    title: str = "Why you will love it"
    items: list[dict[str, str]] = Field(default_factory=list)  # {title,text,icon}


class ReviewItem(BaseModel):
    name: str
    rating: int = Field(5, ge=1, le=5)
    text: str


class ReviewsSection(BaseModel):
    type: Literal["reviews"] = "reviews"
    visible: bool = True
    title: str = "What customers say"
    sample_label: str = "SAMPLE REVIEWS - illustrative content, not real customer feedback."
    items: list[ReviewItem] = Field(default_factory=list)


class FaqItem(BaseModel):
    q: str
    a: str


class FaqSection(BaseModel):
    type: Literal["faq"] = "faq"
    visible: bool = True
    title: str = "Frequently asked questions"
    items: list[FaqItem] = Field(default_factory=list)


class FooterSection(BaseModel):
    type: Literal["footer"] = "footer"
    visible: bool = True
    columns: list[dict[str, Any]] = Field(default_factory=list)
    note: str = "Demo storefront generated by CommercePilot AI."


Section = (
    HeaderSection
    | HeroSection
    | FeaturedSection
    | ProductDetailSection
    | BenefitsSection
    | ReviewsSection
    | FaqSection
    | FooterSection
)


class StoreDesign(BaseModel):
    primary_color: str = "#0F3D2E"
    accent_color: str = "#2ECC71"
    background: str = "#FFFFFF"
    surface: str = "#F5F6F5"
    text_color: str = "#0B0B0B"
    radius: int = Field(14, ge=0, le=32)
    density: Literal["compact", "comfortable", "airy"] = "comfortable"
    font_heading: Literal["serif", "sans", "display"] = "serif"
    font_body: Literal["sans", "serif", "system"] = "sans"
    hero_style: Literal["centered", "split", "editorial_split", "boxed", "minimal"] = "split"
    card_style: Literal["minimal", "bordered", "elevated"] = "bordered"
    animation: Literal["none", "subtle", "moderate"] = "subtle"

    @field_validator(
        "primary_color", "accent_color", "background", "surface", "text_color"
    )
    @classmethod
    def _hex(cls, v: str) -> str:
        import re

        v = v.strip()
        if not re.match(HEX_RE, v):
            raise ValueError(f"'{v}' is not a valid hex colour")
        return v


class WebsiteSpec(BaseModel):
    version: int = 1
    brand_name: str = ""
    tagline: str = ""
    personality: str = ""
    industry: str = ""
    design: StoreDesign = Field(default_factory=StoreDesign)
    sections: list[Section] = Field(default_factory=list)
    product: Optional[Product] = None
    currency: str = "PKR"
    sample_catalog: list[Product] = Field(default_factory=list)
    generation_mode: Literal["template", "llm"] = "template"
    edit_history: list[dict[str, str]] = Field(default_factory=list)


class StoreGenerateRequest(BaseModel):
    brief: Optional[BusinessBrief] = None
    design: Optional[StoreDesign] = None
    extra_instructions: str = Field("", max_length=1000)


class StoreEditRequest(BaseModel):
    prompt: str = Field(..., min_length=2, max_length=500)


class StoreEditResponse(BaseModel):
    spec: WebsiteSpec
    applied_changes: list[str]
    unmatched: bool = False
    message: str = ""


# --------------------------------------------------------------------------- #
# Marketing Strategist
# --------------------------------------------------------------------------- #
class Allocation(BaseModel):
    label: str = Field(..., min_length=1, max_length=60)
    amount: float = Field(..., ge=0)
    purpose: str = ""


class CreativeConcept(BaseModel):
    name: str
    angle: str
    headline: str
    primary_text: str
    cta: str


class CampaignRequest(BaseModel):
    objective: Literal["traffic", "leads", "sales", "retargeting"] = "sales"
    budget: Optional[float] = Field(None, ge=0)
    duration_days: int = Field(14, ge=1, le=180)
    allocations: Optional[list[Allocation]] = None
    notes: str = Field("", max_length=1000)


class CampaignPlan(BaseModel):
    objective: str
    objective_detail: str = ""
    duration_days: int = 14
    budget: float = 0
    currency: str = "PKR"
    allocations: list[Allocation] = Field(default_factory=list)
    allocation_valid: bool = False
    audience_hypotheses: list[str] = Field(default_factory=list)
    creatives: list[CreativeConcept] = Field(default_factory=list)
    testing_strategy: list[str] = Field(default_factory=list)
    kpis: list[str] = Field(default_factory=list)
    risks_and_assumptions: list[str] = Field(default_factory=list)
    estimates_are_illustrative: bool = True
    status: Literal["draft", "demo_simulated"] = "draft"
    publication: str = "DEMO — NOT PUBLISHED"
    meta_connection: str = "not_connected"
    generation_mode: Literal["template", "llm"] = "template"
    created_at: str = Field(default_factory=utcnow)


class CampaignDraftUpdate(BaseModel):
    objective: Optional[Literal["traffic", "leads", "sales", "retargeting"]] = None
    budget: Optional[float] = Field(None, ge=0)
    duration_days: Optional[int] = Field(None, ge=1, le=180)
    allocations: Optional[list[Allocation]] = None
    status: Optional[Literal["draft", "demo_simulated"]] = None


# --------------------------------------------------------------------------- #
# Business Analyst
# --------------------------------------------------------------------------- #
class ScenarioAssumptions(BaseModel):
    clicks: float = Field(1000, ge=0)
    conversion_rate_pct: float = Field(2.0, ge=0, le=100)
    cpc: float = Field(50, ge=0)


class CampaignActuals(BaseModel):
    """Real measured campaign numbers. When absent, the analyst reports KPIs
    as 'no data' instead of inventing them."""

    ad_spend: Optional[float] = Field(None, ge=0)
    clicks: Optional[float] = Field(None, ge=0)
    conversions: Optional[float] = Field(None, ge=0)
    customers: Optional[float] = Field(None, ge=0)
    revenue: Optional[float] = Field(None, ge=0)


class AnalyzeRequest(BaseModel):
    actuals: Optional[CampaignActuals] = None
    best: Optional[ScenarioAssumptions] = None
    base: Optional[ScenarioAssumptions] = None
    conservative: Optional[ScenarioAssumptions] = None


# --------------------------------------------------------------------------- #
# Orchestrator
# --------------------------------------------------------------------------- #
class AgentExecution(BaseModel):
    id: str
    agent: str
    status: Literal["running", "success", "error", "skipped"] = "running"
    started_at: str = Field(default_factory=utcnow)
    finished_at: Optional[str] = None
    input_summary: str = ""
    output_summary: str = ""
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class WorkflowRequest(BaseModel):
    auto_select: bool = Field(
        True,
        description="When no product is selected yet, automatically select the top-ranked product "
        "(needed for the one-click demo run).",
    )
    mode: Literal["sample", "live", "both"] = "both"
    force: bool = Field(False, description="Re-run steps that already succeeded.")


class StepState(BaseModel):
    id: str
    title: str
    status: Literal["pending", "running", "success", "error", "skipped", "waiting"] = "pending"
    message: str = ""
    updated_at: str = Field(default_factory=utcnow)


WORKFLOW_STEPS: list[dict[str, str]] = [
    {"id": "brief", "title": "Validate business brief"},
    {"id": "research", "title": "Product Hunter research"},
    {"id": "select", "title": "Select product"},
    {"id": "store", "title": "Store Architect storefront"},
    {"id": "campaign", "title": "Marketing Strategist campaign"},
    {"id": "analyze", "title": "Business Analyst analysis"},
    {"id": "report", "title": "Consolidated project report"},
]


# --------------------------------------------------------------------------- #
# Integrations
# --------------------------------------------------------------------------- #
class MetaCredentials(BaseModel):
    access_token: str = Field(..., min_length=8, max_length=4096)
    ad_account_id: str = Field(..., min_length=3, max_length=64)
    app_id: str = Field("", max_length=64)
    app_secret: str = Field("", max_length=256)

    model_config = {"protected_namespaces": ()}


class ShopifyCredentials(BaseModel):
    shop_domain: str = Field(..., min_length=4, max_length=255)
    admin_token: str = Field(..., min_length=8, max_length=4096)

    model_config = {"protected_namespaces": ()}
