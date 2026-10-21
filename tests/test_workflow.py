"""Orchestrator tests: agent handoffs, persistence, retry, execution log."""
import pytest

from commercepilot.schemas import AnalyzeRequest, CampaignRequest, ProjectCreate, ResearchRequest
from commercepilot.storage import ProjectStore
from commercepilot.workflows import commerce_workflow as wf


@pytest.fixture()
def store(tmp_path):
    return ProjectStore(tmp_path / "test.sqlite3")


@pytest.fixture()
def project(store):
    return wf.create_project(store, ProjectCreate(example=True))


def _run_sample(store, project_id):
    return wf.run_full_workflow(store, project_id, auto_select=True, mode="sample")


class TestProjectCreation:
    def test_example_project_has_valid_brief_and_steps(self, project):
        assert project["brief"]["business_name"] == "Noor Glow"
        assert project["brief"]["budget"] == 30000
        assert project["brief"]["currency"] == "PKR"
        assert set(project["steps"]) == {"brief", "research", "select", "store", "campaign", "analyze", "report"}
        assert all(s["status"] == "pending" for s in project["steps"].values())

    def test_custom_project(self, store):
        p = wf.create_project(store, ProjectCreate(name="My shop"))
        assert p["name"] == "My shop"
        assert store.get(p["id"]) is not None


class TestFullWorkflow:
    def test_all_steps_succeed(self, store, project):
        out = _run_sample(store, project["id"])
        assert out["error"] is None
        assert [s["status"] for s in out["steps"]] == ["success"] * 7

    def test_product_flows_into_storefront(self, store, project):
        out = _run_sample(store, project["id"])
        saved = out["project"]
        assert saved["store_spec"]["product"]["id"] == saved["selected_product"]["id"]
        assert saved["store_spec"]["product"]["title"] == saved["selected_product"]["title"]

    def test_same_product_flows_into_campaign_and_analysis(self, store, project):
        out = _run_sample(store, project["id"])
        saved = out["project"]
        product = saved["selected_product"]
        # Analyst uses the stored values, not re-derived or fabricated ones
        unit = saved["analysis"]["unit_economics"]
        assert unit["selling_price"] == product["observed_price"]
        assert unit["product_cost"] == product["estimated_cost"]
        assert unit["gross_profit_per_unit"] == round(product["observed_price"] - product["estimated_cost"], 2)
        # Campaign uses the same budget as the brief
        assert saved["campaign"]["budget"] == saved["brief"]["budget"]
        assert abs(sum(a["amount"] for a in saved["campaign"]["allocations"]) - saved["campaign"]["budget"]) < 0.005

    def test_execution_log_records_agents(self, store, project):
        out = _run_sample(store, project["id"])
        agents = [e["agent"] for e in out["project"]["executions"]]
        for expected in ("Product Hunter", "Store Architect", "Marketing Strategist", "Business Analyst"):
            assert expected in agents
        for e in out["project"]["executions"]:
            assert e["status"] in ("success", "error", "skipped", "running")
            assert e["started_at"]

    def test_report_is_consolidated(self, store, project):
        out = _run_sample(store, project["id"])
        report = out["project"]["report"]
        titles = [s["title"] for s in report["sections"]]
        assert titles == ["Business brief", "Selected product", "Storefront", "Marketing campaign", "Business analysis"]
        assert any("SAMPLE" in p.upper() for p in report["data_provenance"])

    def test_rerun_without_force_is_idempotent(self, store, project):
        _run_sample(store, project["id"])
        executions_before = len(store.get(project["id"])["executions"])
        out = _run_sample(store, project["id"])
        assert out["error"] is None
        # steps are not re-executed when already successful
        assert len(store.get(project["id"])["executions"]) == executions_before


class TestProductChange:
    def test_changing_product_updates_downstream(self, store, project):
        _run_sample(store, project["id"])
        p = store.get(project["id"])
        wf.step_select_product(store, p, "sample-011", auto_select=True)  # fitness product
        p = store.get(project["id"])
        wf.step_generate_store(store, p)
        p = store.get(project["id"])
        wf.step_generate_campaign(store, p, CampaignRequest(objective="sales", budget=30000))
        p = store.get(project["id"])
        analysis = wf.step_analyze(store, p, AnalyzeRequest())
        assert p["selected_product"]["id"] == "sample-011"
        assert p["store_spec"]["product"]["id"] == "sample-011"
        assert analysis["product"]["id"] == "sample-011"
        # re-report
        wf.step_report(store, store.get(project["id"]))
        assert "Selected product" in str(store.get(project["id"])["report"]["sections"])


class TestFailureAndRetry:
    def test_incomplete_brief_fails_then_recovers(self, store, project):
        p = store.get(project["id"])
        p["brief"]["business_name"] = ""
        p["brief"]["niche"] = ""
        store.save(p)
        out = wf.run_full_workflow(store, project["id"], mode="sample")
        assert out["error"]["step"] == "brief"
        assert store.get(project["id"])["steps"]["brief"]["status"] == "error"
        # fix the brief and retry - no restart needed
        fixed = store.get(project["id"])
        fixed["brief"]["business_name"] = "Fixed Brand"
        fixed["brief"]["niche"] = "serum"
        store.save(fixed)
        out2 = wf.run_full_workflow(store, project["id"], mode="sample")
        assert out2["error"] is None
        assert store.get(project["id"])["steps"]["brief"]["status"] == "success"

    def test_research_with_no_products_fails_cleanly(self, store, project, monkeypatch):
        from commercepilot.agents import product_hunter as ph
        from commercepilot.schemas import ResearchResult

        monkeypatch.setattr(ph, "run", lambda req: ResearchResult(mode="sample", products=[]))
        p = store.get(project["id"])
        with pytest.raises(wf.StepFailed) as exc:
            wf.step_research(store, p, ResearchRequest(niche="x", mode="sample"))
        assert exc.value.step == "research"
        assert store.get(project["id"])["steps"]["research"]["status"] == "error"

    def test_store_edit_without_store_fails_cleanly(self, store, project):
        with pytest.raises(wf.StepFailed) as exc:
            wf.step_edit_store(store, project, "make it luxurious")
        assert exc.value.step == "store"


class TestPersistence:
    def test_projects_survive_store_reload(self, tmp_path):
        db = tmp_path / "persist.sqlite3"
        store1 = ProjectStore(db)
        project = wf.create_project(store1, ProjectCreate(example=True))
        _run_sample(store1, project["id"])
        store2 = ProjectStore(db)  # simulates a backend restart
        reloaded = store2.get(project["id"])
        assert reloaded is not None
        assert reloaded["selected_product"] is not None
        assert reloaded["report"] is not None
        assert store2.count() == 1

    def test_delete(self, store, project):
        assert store.delete(project["id"]) is True
        assert store.get(project["id"]) is None
        assert store.delete(project["id"]) is False
