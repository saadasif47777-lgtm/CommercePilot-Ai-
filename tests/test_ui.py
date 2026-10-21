"""Tests for the Python interface (Gradio), its formatting and its exports.

The interface is deliberately thin, so these tests cover the three things that
could actually break: the layout building, the data -> markup translation, and
the downloadable artifacts. Business logic is covered by the agent/workflow
tests.
"""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from commercepilot import runtime
from commercepilot.schemas import ProjectCreate
from commercepilot.storage import ProjectStore
from commercepilot.ui import build_ui, downloads
from commercepilot.ui import formatting as fmt
from commercepilot.ui.context import UIContext
from commercepilot.ui.tabs.store_tab import preview_html
from commercepilot.workflows import commerce_workflow as wf


@pytest.fixture()
def store(tmp_path):
    """Isolated database shared by the API, UI and workflow under test."""
    instance = ProjectStore(tmp_path / "ui.sqlite3")
    runtime.set_store(instance)
    yield instance
    runtime.reset_store()


@pytest.fixture()
def project(store):
    """A fully generated example project (sample data only)."""
    created = wf.create_project(store, ProjectCreate(example=True))
    result = wf.run_full_workflow(store, created["id"], mode="sample")
    assert result["error"] is None
    return store.get(created["id"])


# --------------------------------------------------------------------------- #
# Layout
# --------------------------------------------------------------------------- #
class TestLayout:
    def test_builds_all_tabs(self, store):
        demo = build_ui()
        config = json.dumps(demo.get_config_file())
        for label in (
            "Dashboard", "Product Hunter", "Store Builder", "Marketing Studio",
            "Business Analytics", "Assistant", "Projects", "Settings",
        ):
            assert label in config, f"missing tab: {label}"

    def test_dashboard_payload(self, project):
        ctx = UIContext()
        status, overview, steps, report, product = ctx.dashboard(project["id"])

        assert "Noor Glow" in status
        assert "Business brief" in overview
        assert len(steps) == 7  # every workflow step is represented
        assert "Project report" in report
        assert project["selected_product"]["title"] in product

    def test_empty_selection_is_graceful(self, store):
        ctx = UIContext()
        status, overview, steps, report, product = ctx.dashboard(None)
        assert "No project selected" in status
        assert "Welcome" in overview
        assert steps == []
        assert "Run the workflow" in report
        assert product  # an explanatory message, never an exception


# --------------------------------------------------------------------------- #
# Formatting
# --------------------------------------------------------------------------- #
class TestFormatting:
    def test_research_and_product_rows(self, project):
        research = project["research"]
        rows = fmt.product_rows(research["products"])
        assert len(rows) == len(research["products"])
        assert all(len(row) == len(fmt.PRODUCT_HEADERS) for row in rows)
        assert "candidates" in fmt.research_markdown(research)

    def test_campaign_views(self, project):
        campaign = project["campaign"]
        markdown = fmt.campaign_markdown(campaign)
        assert "DEMO" in markdown
        assert len(fmt.allocation_rows(campaign)) == len(campaign["allocations"])
        assert len(fmt.creative_rows(campaign)) == len(campaign["creatives"])

    def test_analysis_views(self, project):
        analysis = project["analysis"]
        markdown = fmt.analysis_markdown(analysis)
        assert "Break-even ROAS" in markdown
        assert len(fmt.scenario_rows(analysis)) >= 1

    def test_report_and_usage(self, project):
        assert "Next actions" in fmt.report_markdown(project["report"])
        from commercepilot import ai

        assert "AI usage" in fmt.usage_markdown(ai.usage_summary())

    def test_missing_values_render_as_dash(self):
        assert fmt.money(None) == fmt.DASH
        assert fmt.percent(None) == fmt.DASH
        assert fmt.number(None) == fmt.DASH
        assert "No brief yet" in fmt.brief_markdown({})
        assert "not specified" in fmt.brief_markdown({"business_name": "Acme"})

    def test_preview_html(self, project):
        html = preview_html(project["id"])
        assert "iframe" in html
        assert f"/api/projects/{project['id']}/store/export" in html
        assert "Generate a storefront" in preview_html(None)


# --------------------------------------------------------------------------- #
# Downloads
# --------------------------------------------------------------------------- #
class TestDownloads:
    def test_storefront_export(self, project):
        path = downloads.export_storefront(project)
        assert path is not None
        content = Path(path).read_text(encoding="utf-8")
        assert content.lstrip().lower().startswith("<!doctype html")
        assert project["store_spec"]["brand_name"] in content

    def test_campaign_and_report_exports(self, project):
        campaign = json.loads(Path(downloads.export_campaign(project)).read_text(encoding="utf-8"))
        assert campaign["campaign"]["objective"]
        report = json.loads(Path(downloads.export_report(project)).read_text(encoding="utf-8"))
        assert report["sections"]
        analysis = json.loads(Path(downloads.export_analysis(project)).read_text(encoding="utf-8"))
        assert "unit_economics" in analysis

    def test_export_requires_generated_content(self, store):
        project = wf.create_project(store, ProjectCreate(example=True))
        assert downloads.export_storefront(project) is None
        assert downloads.export_campaign(project) is None
        assert downloads.export_report(project) is None


# --------------------------------------------------------------------------- #
# Served application
# --------------------------------------------------------------------------- #
class TestServedApp:
    def test_root_serves_ui_and_api_survives_mount(self, store):
        from commercepilot.webapp import app

        client = TestClient(app)
        page = client.get("/")
        assert page.status_code == 200
        assert "CommercePilot AI" in page.text
        assert client.get("/api/health").json()["status"] == "ok"
