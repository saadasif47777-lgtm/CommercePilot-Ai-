"""Create downloadable files from generated project assets.

The exports are written to a per-process temporary directory (not into the
repository) and returned as paths, which is what Gradio's ``File`` component
expects. Each export is a normal artifact of the project, so nothing secret is
ever written here.
"""
from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path
from typing import Any, Optional

from ..store_export import render_standalone_html

EXPORT_DIR = Path(tempfile.mkdtemp(prefix="commercepilot-exports-"))
_SAFE = re.compile(r"[^a-z0-9]+")


def _slug(value: str) -> str:
    """Filesystem-safe slug, used only for download filenames."""
    cleaned = _SAFE.sub("-", (value or "project").lower()).strip("-")
    return cleaned[:48] or "project"


def _path(project: dict, suffix: str) -> Path:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    return EXPORT_DIR / f"{_slug(project.get('name', 'project'))}-{suffix}"


def export_storefront(project: Optional[dict]) -> Optional[str]:
    """Standalone HTML file of the generated storefront."""
    if not project or not project.get("store_spec"):
        return None
    path = _path(project, "storefront.html")
    path.write_text(render_standalone_html(project["store_spec"]), encoding="utf-8")
    return str(path)


def export_campaign(project: Optional[dict]) -> Optional[str]:
    """Campaign draft plus simulation (when present) as JSON."""
    if not project or not project.get("campaign"):
        return None
    path = _path(project, "campaign.json")
    path.write_text(
        json.dumps(
            {
                "project": project.get("name"),
                "currency": (project.get("campaign") or {}).get("currency"),
                "campaign": project["campaign"],
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return str(path)


def export_report(project: Optional[dict]) -> Optional[str]:
    """Consolidated report as JSON."""
    if not project or not project.get("report"):
        return None
    path = _path(project, "report.json")
    path.write_text(json.dumps(project["report"], indent=2, ensure_ascii=False), encoding="utf-8")
    return str(path)


def export_analysis(project: Optional[dict]) -> Optional[str]:
    """Business analysis as JSON."""
    if not project or not project.get("analysis"):
        return None
    path = _path(project, "analysis.json")
    path.write_text(json.dumps(project["analysis"], indent=2, ensure_ascii=False), encoding="utf-8")
    return str(path)


def export_payload(name: str, payload: Any) -> str:
    """Write an arbitrary JSON payload (used for integration diagnostics)."""
    path = EXPORT_DIR / f"{_slug(name)}.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return str(path)
