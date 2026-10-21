"""AGENT B - Store Architect.

Turns the business brief + selected product into a STRUCTURED website
specification (Pydantic-validated WebsiteSpec). `store_export` renders that
spec as plain HTML/CSS, so no arbitrary generated code is ever executed and the
specification is validated before it is previewed or exported.

Natural-language edits ("make it more luxurious") update the structured spec
deterministically; an optional LLM can rewrite copy when configured. Every
edit reports exactly what changed.
"""
from __future__ import annotations

import re
from typing import Optional

from .. import ai
from ..ai.schemas import StoreCopy
from ..schemas import (
    BenefitsSection,
    BusinessBrief,
    FaqItem,
    FaqSection,
    FeaturedSection,
    FooterSection,
    HeaderSection,
    HeroSection,
    NavItem,
    Product,
    ProductDetailSection,
    ReviewItem,
    ReviewsSection,
    StoreDesign,
    StoreEditResponse,
    WebsiteSpec,
    utcnow,
)

PERSONALITY_DESIGNS = {
    "luxury": dict(font_heading="serif", density="airy", radius=4, primary_color="#0F3D2E", accent_color="#C9A227", card_style="elevated"),
    "premium": dict(font_heading="serif", density="airy", radius=8, primary_color="#10243E", accent_color="#C8A96A"),
    "playful": dict(font_heading="display", density="comfortable", radius=20, primary_color="#3D2E6B", accent_color="#F4A259", animation="moderate"),
    "natural": dict(font_heading="serif", density="comfortable", radius=16, primary_color="#3E5641", accent_color="#A6B77E"),
    "clinical": dict(font_heading="sans", density="compact", radius=6, primary_color="#0F3D2E", accent_color="#2ECC71"),
    "default": dict(font_heading="sans", density="comfortable", radius=14, primary_color="#0F3D2E", accent_color="#2ECC71"),
}

CATEGORY_BENEFITS = {
    "skincare": [
        {"title": "Gentle, daily-friendly formula", "text": "Designed for everyday use without overwhelming sensitive skin.", "icon": "sparkle"},
        {"title": "Visible glow routine", "text": "Fits a simple cleanse - treat - moisturise routine.", "icon": "sun"},
        {"title": "Clean, secure packaging", "text": "Shipped in protective packaging with batch and expiry details.", "icon": "shield"},
    ],
    "home accessories": [
        {"title": "Elevates any space", "text": "Neutral styling works with modern and traditional interiors.", "icon": "home"},
        {"title": "Durable materials", "text": "Made for daily use, not just photos.", "icon": "shield"},
        {"title": "Giftable presentation", "text": "Arrives ready to gift with minimal packaging waste.", "icon": "gift"},
    ],
    "fashion accessories": [
        {"title": "Everyday wearability", "text": "Pairs with casual and formal outfits.", "icon": "sparkle"},
        {"title": "Skin-friendly materials", "text": "Comfortable for all-day wear.", "icon": "shield"},
        {"title": "Gift-ready", "text": "Ships in a presentable box.", "icon": "gift"},
    ],
    "fitness": [
        {"title": "Beginner-friendly", "text": "Simple to start at home, no equipment experience needed.", "icon": "sparkle"},
        {"title": "Space-saving design", "text": "Folds or packs down for small spaces and travel.", "icon": "home"},
        {"title": "Built for repeat sessions", "text": "Materials chosen for frequent training.", "icon": "shield"},
    ],
    "electronics accessories": [
        {"title": "Reliable daily performance", "text": "Tested for consistent everyday use.", "icon": "shield"},
        {"title": "Compact and travel-ready", "text": "Fits bags and pockets without clutter.", "icon": "home"},
        {"title": "Warranty support", "text": "Local support for defects and replacement.", "icon": "gift"},
    ],
    "default": [
        {"title": "Quality checked", "text": "Every unit is inspected before dispatch.", "icon": "shield"},
        {"title": "Fast local delivery", "text": "Dispatch within 24-48 hours across Pakistan.", "icon": "home"},
        {"title": "Easy returns", "text": "7-day return window on unopened items.", "icon": "gift"},
    ],
}

DEFAULT_FAQ = {
    "delivery": ("How long does delivery take?", "Orders are dispatched within 24-48 hours and typically arrive in 3-5 working days across major cities."),
    "returns": ("What is the return policy?", "Unopened items can be returned within 7 days of delivery. Contact support with your order number to start a return."),
    "cod": ("Do you offer cash on delivery?", "Yes, cash on delivery is available for orders within Pakistan; rider charges may apply."),
    "authenticity": ("Is the product authentic?", "Every unit is sourced from an authorised supplier and ships with batch details on the packaging."),
}


def _pick_personality(brief: BusinessBrief) -> str:
    text = f"{brief.brand_personality} {brief.industry} {brief.niche}".lower()
    for key in ("luxury", "premium", "playful", "natural", "clinical"):
        if key in text:
            return key
    return "default"


def build_spec(
    brief: BusinessBrief,
    product: Product,
    design: Optional[StoreDesign] = None,
    extra_instructions: str = "",
    sample_catalog: Optional[list[Product]] = None,
) -> WebsiteSpec:
    """Generate a validated website specification from the brief + product."""
    personality_key = _pick_personality(brief)
    defaults = PERSONALITY_DESIGNS[personality_key]
    resolved = design or StoreDesign(**defaults)
    if design is None and personality_key != "default":
        # apply personality defaults that the user has not overridden
        for field, value in defaults.items():
            current = getattr(resolved, field)
            neutral = getattr(StoreDesign(), field)
            if current == neutral:
                setattr(resolved, field, value)

    brand = brief.business_name or f"{brief.niche.title()} Co."
    currency = brief.currency or product.currency or "PKR"

    copy_ = _generate_copy(brief, product, brand, personality_key)
    if extra_instructions:
        copy_["extra_instructions"] = extra_instructions

    nav = [
        NavItem(label="Home", href="#top"),
        NavItem(label="Product", href="#product"),
        NavItem(label="Benefits", href="#benefits"),
        NavItem(label="Reviews", href="#reviews"),
        NavItem(label="FAQ", href="#faq"),
    ]

    sections = [
        HeaderSection(logo_text=brand, nav=nav, cta_label=copy_["header_cta"], show_search=True),
        HeroSection(
            style=resolved.hero_style,
            badge=copy_["badge"],
            headline=copy_["headline"],
            subheadline=copy_["subheadline"],
            cta_label=copy_["cta"],
            image_style="product",
        ),
        FeaturedSection(title=copy_["featured_title"], show_catalog=bool(sample_catalog), catalog_filter=True),
        ProductDetailSection(
            title=copy_["detail_title"],
            description=product.description or copy_["detail_description"],
            bullets=copy_["detail_bullets"],
        ),
        BenefitsSection(title=copy_["benefits_title"], items=CATEGORY_BENEFITS.get(product.category, CATEGORY_BENEFITS["default"])),
        ReviewsSection(title="What customers say", items=_sample_reviews(product, brand)),
        FaqSection(items=_faq_items(product, copy_)),
        FooterSection(
            columns=[
                {"title": "Shop", "links": ["New arrivals", "Bestsellers", "Gift sets"]},
                {"title": "Help", "links": ["Shipping", "Returns", "Contact"]},
                {"title": brand, "links": ["Our story", "Ingredients", "Wholesale"]},
            ],
            note=f"Demo storefront generated by CommercePilot AI for {brand}. Reviews and copy marked as sample content.",
        ),
    ]

    return WebsiteSpec(
        brand_name=brand,
        tagline=copy_["tagline"],
        personality=personality_key,
        industry=brief.industry or product.category,
        design=resolved,
        sections=sections,
        product=product,
        currency=currency,
        sample_catalog=sample_catalog or [],
        generation_mode="template",
        edit_history=[{"at": utcnow(), "change": "Initial specification generated from business brief"}],
    )


# --------------------------------------------------------------------------- #
# Copy generation (LLM when configured, deterministic templates otherwise)
# --------------------------------------------------------------------------- #
def _generate_copy(brief: BusinessBrief, product: Product, brand: str, personality: str) -> dict:
    copy_out = _template_copy(brief, product, brand, personality)
    try:
        result = ai.complete_json(
            prompt_name="store_copy",
            schema=StoreCopy,
            quality=ai.QUALITY_STRONG,
            user=(
                f"Brand: {ai.wrap_untrusted('brand', brand)}\n"
                f"Industry: {ai.wrap_untrusted('industry', brief.industry)}\n"
                f"Niche: {ai.wrap_untrusted('niche', brief.niche)}\n"
                f"Audience: {ai.wrap_untrusted('audience', brief.target_audience)}\n"
                f"Personality: {ai.wrap_untrusted('personality', personality)}\n"
                f"Product: {ai.wrap_untrusted('product', product.title + ' - ' + product.description)}\n"
                "Write the storefront copy now."
            ),
        )
    except ai.AIError:
        # Budget hit, provider outage or invalid output: keep template copy and
        # leave generation_mode as "template" so the UI states the truth.
        return copy_out
    if result is None:
        return copy_out
    for key, value in result.model_dump(exclude_none=True).items():
        if (isinstance(value, str) and value.strip()) or (isinstance(value, list) and value):
            copy_out[key] = value
    copy_out["generation_mode"] = "llm"
    return copy_out


def _template_copy(brief: BusinessBrief, product: Product, brand: str, personality: str) -> dict:
    audience = brief.target_audience or "everyday customers"
    tone = {
        "luxury": "Refined craftsmanship, made to be noticed",
        "premium": "Thoughtful quality for people who notice details",
        "playful": "Bright, fun, and made for everyday moments",
        "natural": "Simple ingredients, honest everyday care",
        "clinical": "Straightforward, effective, dermatologist-minded",
        "default": "Everyday quality, delivered to your door",
    }[personality]
    bullets = [
        f"Designed for {audience.split(',')[0][:40]}",
        "Dispatch within 24-48 hours across Pakistan",
        "7-day return window on unopened items",
        "Cash on delivery available",
    ]
    return {
        "headline": product.title,
        "subheadline": tone + f". {product.description[:110]}".rstrip(".") + ".",
        "tagline": tone,
        "cta": "Add to cart",
        "header_cta": "Shop now",
        "badge": f"{product.category.title()} · {brand}",
        "featured_title": f"Meet the {product.title}",
        "detail_title": "Product details",
        "detail_description": product.description,
        "detail_bullets": bullets,
        "benefits_title": "Why customers choose it",
        "faq_intro": "Answers to the questions we hear most often.",
        "generation_mode": "template",
    }


def _sample_reviews(product: Product, brand: str) -> list[ReviewItem]:
    name = product.title.split()[0].title()
    return [
        ReviewItem(name="Ayesha K. (sample)", rating=5, text=f"Packaging felt premium and delivery was quick. {name} fits right into my routine. (sample review)"),
        ReviewItem(name="Hira M. (sample)", rating=4, text="Good value for the price point. Took a few days longer than expected. (sample review)"),
        ReviewItem(name="Sana R. (sample)", rating=5, text=f"Bought as a gift and it was well received. Would order from {brand} again. (sample review)"),
    ]


def _faq_items(product: Product, copy_out: dict) -> list[FaqItem]:
    items = [FaqItem(q=DEFAULT_FAQ["delivery"][0], a=DEFAULT_FAQ["delivery"][1]),
             FaqItem(q=DEFAULT_FAQ["returns"][0], a=DEFAULT_FAQ["returns"][1]),
             FaqItem(q=DEFAULT_FAQ["cod"][0], a=DEFAULT_FAQ["cod"][1])]
    if product.category == "skincare":
        items.insert(0, FaqItem(q="How do I use it?", a="Apply to clean skin morning or evening, then follow with moisturiser. Patch test first."))
    return items


# --------------------------------------------------------------------------- #
# Natural-language design editing
# --------------------------------------------------------------------------- #
def apply_edit(spec: WebsiteSpec, prompt: str) -> StoreEditResponse:
    """Apply deterministic structured edits from a natural-language prompt."""
    p = prompt.lower().strip()
    design = spec.design
    applied: list[str] = []

    def setd(field: str, value, label: str) -> None:
        if getattr(design, field) != value:
            setattr(design, field, value)
            applied.append(label)

    # Palette intents
    palettes = {
        "luxury": dict(primary_color="#0B0B0B", accent_color="#C9A227", background="#FBFAF7", surface="#F2EFE8"),
        "luxurious": dict(primary_color="#0B0B0B", accent_color="#C9A227", background="#FBFAF7", surface="#F2EFE8"),
        "premium": dict(primary_color="#10243E", accent_color="#C8A96A", background="#FCFBF8", surface="#F3F1EC"),
        "emerald": dict(primary_color="#0F3D2E", accent_color="#2ECC71"),
        "green": dict(primary_color="#0F3D2E", accent_color="#2ECC71"),
        "navy": dict(primary_color="#10243E", accent_color="#4C7DF0"),
        "blue": dict(primary_color="#0E2A47", accent_color="#3B82F6"),
        "black and white": dict(primary_color="#0B0B0B", accent_color="#8A8A8A", background="#FFFFFF", surface="#F5F5F5"),
        "monochrome": dict(primary_color="#0B0B0B", accent_color="#8A8A8A", background="#FFFFFF", surface="#F5F5F5"),
        "beige": dict(primary_color="#4A3F35", accent_color="#B08968", background="#FAF6F0", surface="#F1E9DE"),
        "warm": dict(primary_color="#3E2C23", accent_color="#D08C60", background="#FBF7F2", surface="#F4EDE4"),
        "dark": dict(primary_color="#0B0B0B", accent_color="#2ECC71", background="#0F1110", surface="#171A18", text_color="#F4F5F4"),
        "minimalist black": dict(primary_color="#0B0B0B", accent_color="#6B6B6B"),
    }
    for key, palette in palettes.items():
        if key in p:
            for field, value in palette.items():
                setd(field, value, f"Palette set to {key} ({field}={value})")
            if key in ("luxury", "luxurious", "premium"):
                setd("font_heading", "serif", "Heading font switched to serif")
                setd("density", "airy", "Layout density set to airy")
                setd("radius", 4, "Corners sharpened to 4px")
                setd("card_style", "elevated", "Product cards set to elevated")
            break

    hexes = re.findall(r"#([0-9a-f]{6})\b", p)
    if hexes and not applied:
        if len(hexes) >= 2:
            setd("primary_color", f"#{hexes[0]}", f"Primary colour set to #{hexes[0]}")
            setd("accent_color", f"#{hexes[1]}", f"Accent colour set to #{hexes[1]}")
        else:
            setd("primary_color", f"#{hexes[0]}", f"Primary colour set to #{hexes[0]}")

    # Hero intents
    hero = next((s for s in spec.sections if s.type == "hero"), None)
    if any(k in p for k in ("editorial split", "split-screen hero", "split screen hero")):
        if hero:
            hero.style = "editorial_split"
            design.hero_style = "editorial_split"
            applied.append("Hero switched to editorial split-screen")
    elif "split" in p and "hero" in p:
        if hero:
            hero.style = "split"
            design.hero_style = "split"
            applied.append("Hero switched to split layout")
    elif hero and ("centered hero" in p or ("center" in p and "hero" in p)):
        hero.style = "centered"
        design.hero_style = "centered"
        applied.append("Hero switched to centered layout")
    elif hero and "minimal hero" in p:
        hero.style = "minimal"
        design.hero_style = "minimal"
        applied.append("Hero switched to minimal layout")

    # Card style
    if any(k in p for k in ("minimal card", "cards more minimal", "card more minimal", "more minimal", "simpler card", "cleaner card")):
        setd("card_style", "minimal", "Product cards set to minimal")
    elif "bordered card" in p:
        setd("card_style", "bordered", "Product cards set to bordered")
    elif "elevated card" in p or "shadow card" in p:
        setd("card_style", "elevated", "Product cards set to elevated")

    # Typography
    if any(k in p for k in ("typography hierarchy", "stronger typography", "bigger headings", "stronger type")):
        setd("font_heading", "display", "Heading font switched to display for stronger hierarchy")
    if "serif" in p and "sans" not in p:
        setd("font_heading", "serif", "Heading font switched to serif")
    if "sans-serif" in p or "sans serif" in p or ("clean font" in p):
        setd("font_heading", "sans", "Heading font switched to sans-serif")
        setd("font_body", "sans", "Body font set to sans-serif")

    # Density / spacing
    if any(k in p for k in ("more spacious", "spacious", "airy", "more whitespace", "breathing room")):
        setd("density", "airy", "Layout density set to airy")
    if any(k in p for k in ("compact", "tighter", "denser", "less whitespace")):
        setd("density", "compact", "Layout density set to compact")

    # Corners
    if any(k in p for k in ("sharp", "square", "less rounded")):
        setd("radius", 2, "Corner radius reduced to 2px")
    elif any(k in p for k in ("rounded", "softer corners", "friendly")):
        setd("radius", 20, "Corner radius increased to 20px")

    # Animation
    if "reveal" in p or "animation" in p or "animate" in p:
        setd("animation", "subtle" if design.animation == "none" else "moderate", "Animation intensity increased")
    if "no animation" in p or "disable animation" in p or "static" in p:
        setd("animation", "none", "Animation disabled")

    # Mobile layout
    if "mobile" in p:
        if hero and hero.style in ("editorial_split", "split"):
            hero.style = "centered"
            design.hero_style = "centered"
            applied.append("Hero switched to centered for mobile readability")
        setd("density", "comfortable" if design.density == "airy" else design.density, "Mobile spacing normalised") if design.density != "comfortable" else None
        header = next((s for s in spec.sections if s.type == "header"), None)
        if header:
            header.show_search = False
            applied.append("Header search hidden on mobile to reduce clutter")

    # Section visibility
    for section_type, verb in (("reviews", "reviews"), ("faq", "faq"), ("benefits", "benefits")):
        if re.search(rf"(hide|remove|drop|disable)\s+{verb}", p):
            for s in spec.sections:
                if s.type == section_type and s.visible:
                    s.visible = False
                    applied.append(f"{verb.title()} section hidden")
        elif re.search(rf"(show|add|enable|bring back)\s+{verb}", p):
            for s in spec.sections:
                if s.type == section_type and not s.visible:
                    s.visible = True
                    applied.append(f"{verb.title()} section shown")

    # Catalog toggle
    if re.search(r"(hide|remove)\s+(catalog|collection|other products|product list)", p):
        for s in spec.sections:
            if s.type == "featured":
                s.show_catalog = False
                applied.append("Product catalog hidden (featured product only)")
    elif re.search(r"(show|add)\s+(catalog|collection|product list)", p):
        for s in spec.sections:
            if s.type == "featured":
                s.show_catalog = True
                applied.append("Product catalog shown")

    # Copy rewrites
    if re.search(r"(stronger|punchier|shorter)\s+(headline|tagline)", p) and hero:
        hero.headline = hero.headline.split("|")[0][:60].strip()
        hero.subheadline = hero.subheadline[:90].strip() + "..."
        applied.append("Headline and subheadline tightened")

    if not applied:
        return StoreEditResponse(
            spec=spec,
            applied_changes=[],
            unmatched=True,
            message=(
                "No supported change detected. Try things like: 'make it look more luxurious', "
                "'use an editorial split-screen hero', 'make the product cards more minimal', "
                "'improve the mobile layout', 'add a subtle reveal animation', 'use a stronger "
                "typography hierarchy', or a hex colour like #123456."
            ),
        )

    spec.edit_history.append({"at": utcnow(), "change": "; ".join(applied), "prompt": prompt})
    return StoreEditResponse(spec=spec, applied_changes=applied, unmatched=False, message="Changes applied.")
