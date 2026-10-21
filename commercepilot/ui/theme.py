"""Visual theme for the Gradio interface.

Kept in one module so the look can be adjusted without touching any tab logic.
The palette is a deep, calm green with warm neutrals: it reads as a business
tool rather than a demo, and keeps contrast high for readability on projectors.
"""
from __future__ import annotations

import gradio as gr

# Brand colours (also reused by the exported storefront as a neutral base).
BRAND = "#0F3D2E"
BRAND_LIGHT = "#E7F0EA"
ACCENT = "#2F855A"
SURFACE = "#FFFFFF"
PAGE = "#F7F7F5"
TEXT = "#1A1A1A"
MUTED = "#5B665F"

CSS = f"""
/* ---- Layout ------------------------------------------------------------ */
.gradio-container {{
    max-width: 1280px !important;
    margin: 0 auto !important;
    background: {PAGE};
}}
footer {{ display: none !important; }}

/* ---- Header ------------------------------------------------------------ */
#cp-header {{
    background: linear-gradient(120deg, {BRAND} 0%, #1B5E45 100%);
    color: #FFFFFF;
    border-radius: 18px;
    padding: 26px 30px;
    margin-bottom: 8px;
}}
#cp-header h1 {{
    font-size: 1.65rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    margin: 0 0 6px 0;
    color: #FFFFFF;
}}
#cp-header p {{
    margin: 0;
    opacity: 0.86;
    font-size: 0.95rem;
    line-height: 1.5;
    color: #FFFFFF;
}}
#cp-header .cp-pill {{
    display: inline-block;
    background: rgba(255,255,255,0.16);
    border: 1px solid rgba(255,255,255,0.28);
    border-radius: 999px;
    padding: 3px 10px;
    font-size: 0.76rem;
    margin: 10px 6px 0 0;
}}

/* ---- Status strip ------------------------------------------------------ */
#cp-status {{
    background: {BRAND_LIGHT};
    border-left: 4px solid {ACCENT};
    border-radius: 10px;
    padding: 10px 16px;
    margin-bottom: 6px;
}}
#cp-status p {{ margin: 0; color: {TEXT}; }}

/* ---- Cards / sections -------------------------------------------------- */
.cp-card {{
    background: {SURFACE};
    border: 1px solid #E3E7E4;
    border-radius: 14px;
    padding: 18px 20px;
}}
.cp-section-title {{
    font-size: 1.02rem;
    font-weight: 650;
    color: {BRAND};
    margin: 4px 0 2px 0;
}}
.cp-hint {{ color: {MUTED}; font-size: 0.86rem; }}

/* ---- Tables ------------------------------------------------------------ */
.cp-table table {{ font-size: 0.86rem; }}
.cp-table th {{ background: {BRAND_LIGHT} !important; color: {BRAND} !important; }}

/* ---- Buttons ----------------------------------------------------------- */
button.primary {{
    background: {BRAND} !important;
    border: none !important;
}}
button.primary:hover {{ background: {ACCENT} !important; }}

/* ---- Storefront preview ----------------------------------------------- */
#cp-preview iframe {{
    width: 100%;
    height: 640px;
    border: 1px solid #E3E7E4;
    border-radius: 12px;
    background: #FFFFFF;
}}

/* ---- Chat -------------------------------------------------------------- */
#cp-chat {{ border-radius: 12px; }}
"""


def theme() -> gr.themes.Base:
    """Return the shared Gradio theme (system fonts: no external requests)."""
    return gr.themes.Soft(
        primary_hue=gr.themes.colors.emerald,
        secondary_hue=gr.themes.colors.stone,
        neutral_hue=gr.themes.colors.stone,
        font=("Inter", "system-ui", "sans-serif"),
    ).set(
        body_background_fill=PAGE,
        block_background_fill=SURFACE,
        block_border_width="1px",
        block_shadow="none",
        button_primary_background_fill=BRAND,
        button_primary_background_fill_hover=ACCENT,
        button_primary_text_color="#FFFFFF",
        body_text_color=TEXT,
        border_color_primary="#E3E7E4",
    )
