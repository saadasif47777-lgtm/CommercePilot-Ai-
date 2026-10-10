"""Export a generated storefront as a standalone HTML file.

The storefront in the app is rendered by React components from the validated
spec; this module produces a static HTML/CSS rendition of the SAME spec so the
generated store can be downloaded and opened anywhere. No JavaScript framework
is required, and no arbitrary generated code is executed.
"""
from __future__ import annotations

import html
from typing import Any

FONT_STACKS = {
    "serif": "'Playfair Display', Georgia, 'Times New Roman', serif",
    "display": "'Poppins', 'Helvetica Neue', Arial, sans-serif",
    "sans": "'Inter', -apple-system, 'Segoe UI', Roboto, sans-serif",
    "system": "-apple-system, 'Segoe UI', Roboto, sans-serif",
}
GAP = {"compact": "28px", "comfortable": "56px", "airy": "96px"}
PAD = {"compact": "32px", "comfortable": "56px", "airy": "80px"}


def _esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""))


def render_standalone_html(spec: dict) -> str:
    d = spec.get("design", {})
    sections = spec.get("sections", [])
    product = spec.get("product") or {}
    currency = spec.get("currency", "PKR")
    price = product.get("observed_price")
    price_label = f"{currency} {price:,.0f}" if price else "Price on request"
    heading_font = FONT_STACKS.get(d.get("font_heading", "sans"), FONT_STACKS["sans"])
    body_font = FONT_STACKS.get(d.get("font_body", "sans"), FONT_STACKS["sans"])
    radius = d.get("radius", 12)
    gap = GAP.get(d.get("density", "comfortable"), GAP["comfortable"])
    pad = PAD.get(d.get("density", "comfortable"), PAD["comfortable"])
    card_style = d.get("card_style", "bordered")

    by_type = {s.get("type"): s for s in sections}

    header = by_type.get("header") or {}
    hero = by_type.get("hero") or {}
    detail = by_type.get("product_detail") or {}
    benefits = by_type.get("benefits") or {}
    reviews = by_type.get("reviews") or {}
    faq = by_type.get("faq") or {}
    footer = by_type.get("footer") or {}

    nav_html = "".join(
        f'<a href="{_esc(n.get("href", "#"))}">{_esc(n.get("label"))}</a>'
        for n in (header.get("nav") or [])
    )

    hero_style = hero.get("style", "split")
    hero_inner = f"""
      <div class="hero-copy">
        <span class="badge">{_esc(hero.get('badge'))}</span>
        <h1>{_esc(hero.get('headline'))}</h1>
        <p class="sub">{_esc(hero.get('subheadline'))}</p>
        <div class="cta-row">
          <a class="btn" href="#product">{_esc(hero.get('cta_label'))}</a>
          <a class="btn ghost" href="#benefits">{_esc(hero.get('secondary_cta_label'))}</a>
        </div>
      </div>
      <div class="hero-media" aria-hidden="true">
        <div class="product-tile">
          <span class="tile-label">{_esc(product.get('category', 'product')).title()}</span>
          <strong>{_esc(product.get('title'))}</strong>
          <em>{_esc(price_label)}</em>
        </div>
      </div>"""
    hero_class = f"hero hero-{_esc(hero_style)}"

    bullets = "".join(f"<li>{_esc(b)}</li>" for b in (detail.get("bullets") or []))
    benefit_cards = "".join(
        f'<div class="card"><h3>{_esc(b.get("title"))}</h3><p>{_esc(b.get("text"))}</p></div>'
        for b in (benefits.get("items") or [])
    )
    review_cards = "".join(
        f'<div class="card review"><div class="stars">{"★" * int(r.get("rating", 5))}</div>'
        f'<p>{_esc(r.get("text"))}</p><span class="who">{_esc(r.get("name"))}</span></div>'
        for r in (reviews.get("items") or [])
    )
    faq_items = "".join(
        f"<details><summary>{_esc(f.get('q'))}</summary><p>{_esc(f.get('a'))}</p></details>"
        for f in (faq.get("items") or [])
    )
    footer_cols = "".join(
        f'<div><h4>{_esc(c.get("title"))}</h4>{"".join(f"<a>{_esc(l)}</a>" for l in (c.get("links") or []))}</div>'
        for c in (footer.get("columns") or [])
    )

    def visible(section: dict) -> bool:
        return section.get("visible", True) if section else False

    blocks = [f"""<header class="site-header">
  <div class="wrap"><a class="logo" href="#top">{_esc(header.get('logo_text'))}</a>
  <nav>{nav_html}</nav><a class="btn small" href="#product">{_esc(header.get('cta_label'))}</a></div>
</header>"""]
    if visible(hero):
        blocks.append(f'<section id="top" class="{hero_class} wrap">{hero_inner}</section>')
    if visible(detail):
        blocks.append(f"""<section id="product" class="wrap section">
  <h2>{_esc(detail.get('title'))}</h2>
  <div class="detail-grid">
    <div class="product-tile big" aria-hidden="true"><span class="tile-label">{_esc(product.get('category','product')).title()}</span><strong>{_esc(product.get('title'))}</strong><em>{_esc(price_label)}</em></div>
    <div><p>{_esc(detail.get('description'))}</p><ul>{bullets}</ul>
    <p class="demo-note">Demo storefront - product data is sample/demo content.</p></div>
  </div>
</section>""")
    if visible(benefits):
        blocks.append(f'<section id="benefits" class="section band"><div class="wrap"><h2>{_esc(benefits.get("title"))}</h2><div class="grid">{benefit_cards}</div></div></section>')
    if visible(reviews):
        blocks.append(f'<section id="reviews" class="wrap section"><h2>{_esc(reviews.get("title"))}</h2><p class="demo-note">{_esc(reviews.get("sample_label"))}</p><div class="grid">{review_cards}</div></section>')
    if visible(faq):
        blocks.append(f'<section id="faq" class="wrap section"><h2>{_esc(faq.get("title"))}</h2><div class="faq">{faq_items}</div></section>')
    if visible(footer):
        blocks.append(f'<footer class="site-footer"><div class="wrap cols">{footer_cols}</div><p class="wrap note">{_esc(outer_note(footer))}</p></footer>')

    card_css = (
        "box-shadow: 0 10px 30px rgba(0,0,0,.08);" if card_style == "elevated"
        else "border:1px solid rgba(0,0,0,.08);" if card_style == "bordered"
        else "border:none;background:transparent;"
    )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{_esc(spec.get('brand_name'))} - {_esc(product.get('title', 'Store'))}</title>
<style>
  :root {{ --primary:{_esc(d.get('primary_color','#0F3D2E'))}; --accent:{_esc(d.get('accent_color','#2ECC71'))}; --bg:{_esc(d.get('background','#FFFFFF'))}; --surface:{_esc(d.get('surface','#F5F6F5'))}; --text:{_esc(d.get('text_color','#0B0B0B'))}; --radius:{int(radius)}px; }}
  * {{ box-sizing:border-box; margin:0; }}
  body {{ font-family:{body_font}; color:var(--text); background:var(--bg); line-height:1.6; }}
  h1,h2,h3,h4,.logo {{ font-family:{heading_font}; line-height:1.15; }}
  h1 {{ font-size:clamp(2rem,4.5vw,3.4rem); }}
  h2 {{ font-size:1.8rem; margin-bottom:18px; }}
  .wrap {{ max-width:1120px; margin:0 auto; padding:0 22px; }}
  .section {{ padding:{pad} 0; }}
  .band {{ background:var(--surface); }}
  .site-header {{ position:sticky; top:0; background:rgba(255,255,255,.94); border-bottom:1px solid rgba(0,0,0,.06); z-index:20; }}
  .site-header .wrap {{ display:flex; align-items:center; gap:24px; height:64px; }}
  .logo {{ font-size:1.25rem; font-weight:700; color:var(--primary); text-decoration:none; }}
  nav {{ display:flex; gap:18px; flex:1; }}
  nav a {{ color:var(--text); text-decoration:none; font-size:.95rem; opacity:.8; }}
  nav a:hover {{ opacity:1; color:var(--primary); }}
  .btn {{ display:inline-block; background:var(--accent); color:#06281a; padding:12px 22px; border-radius:var(--radius); text-decoration:none; font-weight:600; }}
  .btn.small {{ padding:8px 16px; font-size:.9rem; }}
  .btn.ghost {{ background:transparent; color:var(--primary); border:1px solid var(--primary); }}
  .hero {{ display:grid; grid-template-columns:1.1fr .9fr; gap:40px; align-items:center; padding:{pad} 0; }}
  .hero-centered, .hero-minimal {{ grid-template-columns:1fr; text-align:center; }}
  .hero-editorial_split {{ grid-template-columns:1fr 1fr; }}
  .hero .sub {{ font-size:1.08rem; opacity:.85; margin:16px 0 24px; }}
  .badge {{ display:inline-block; background:var(--surface); color:var(--primary); padding:5px 12px; border-radius:99px; font-size:.8rem; letter-spacing:.04em; margin-bottom:14px; }}
  .cta-row {{ display:flex; gap:12px; flex-wrap:wrap; }}
  .product-tile {{ background:var(--primary); color:#fff; border-radius:var(--radius); padding:40px 28px; min-height:240px; display:flex; flex-direction:column; justify-content:flex-end; gap:8px; }}
  .product-tile.big {{ min-height:320px; }}
  .product-tile .tile-label {{ opacity:.7; font-size:.78rem; text-transform:uppercase; letter-spacing:.08em; }}
  .product-tile em {{ font-style:normal; color:var(--accent); font-weight:600; }}
  .detail-grid {{ display:grid; grid-template-columns:1fr 1.2fr; gap:36px; align-items:start; }}
  .detail-grid ul {{ margin:14px 0 0 18px; }}
  .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(240px,1fr)); gap:22px; }}
  .card {{ background:var(--bg); border-radius:var(--radius); padding:24px; {card_css} }}
  .card h3 {{ margin-bottom:8px; font-size:1.1rem; }}
  .stars {{ color:var(--accent); letter-spacing:2px; margin-bottom:8px; }}
  .who {{ display:block; margin-top:10px; font-size:.85rem; opacity:.7; }}
  .faq details {{ border-bottom:1px solid rgba(0,0,0,.08); padding:14px 0; }}
  .faq summary {{ cursor:pointer; font-weight:600; }}
  .site-footer {{ background:var(--primary); color:#e8f3ee; margin-top:{gap}; padding:48px 0 26px; }}
  .site-footer .cols {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:26px; }}
  .site-footer h4 {{ margin-bottom:10px; }}
  .site-footer a {{ display:block; opacity:.8; text-decoration:none; color:inherit; font-size:.92rem; }}
  .site-footer .note {{ opacity:.65; font-size:.82rem; margin-top:26px; }}
  .demo-note {{ font-size:.8rem; opacity:.6; margin-top:10px; }}
  @media (max-width:820px) {{
    .hero, .detail-grid {{ grid-template-columns:1fr; }}
    nav {{ display:none; }}
  }}
</style>
</head>
<body>
{''.join(blocks)}
</body>
</html>"""


def outer_note(footer: dict) -> str:
    return footer.get("note") or "Demo storefront generated by CommercePilot AI."
