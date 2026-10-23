"""API tests: status codes, validation, error handling, persistence."""
import pytest
from fastapi.testclient import TestClient

import commercepilot.api as api
from commercepilot import runtime
from commercepilot.storage import ProjectStore


@pytest.fixture(autouse=True)
def isolated_secrets(tmp_path, monkeypatch):
    """Keep integration credentials saved by tests inside a temp dir."""
    from commercepilot import config

    monkeypatch.setattr(config, "SECRETS_DIR", tmp_path / "secrets")
    monkeypatch.setattr(config, "integration_secrets_path", lambda provider: tmp_path / "secrets" / f"{provider}.json")


@pytest.fixture()
def client(tmp_path):
    """Point the shared runtime at a throwaway database for each test."""
    runtime.set_store(ProjectStore(tmp_path / "api.sqlite3"))
    yield TestClient(api.app)
    runtime.reset_store()


@pytest.fixture()
def project_id(client):
    resp = client.post("/api/projects", json={"example": True})
    assert resp.status_code == 201
    return resp.json()["id"]


class TestHealthAndData:
    def test_health(self, client):
        body = client.get("/api/health").json()
        assert body["status"] == "ok"
        assert body["llm_mode"] in ("llm", "fallback")

    def test_products_are_labelled_sample(self, client):
        body = client.get("/api/products").json()
        assert body["is_sample_data"] is True
        assert "DEMO" in body["disclaimer"]
        assert body["count"] >= 12
        assert all(p["is_sample_data"] for p in body["products"])

    def test_products_category_filter(self, client):
        body = client.get("/api/products", params={"category": "fitness"}).json()
        assert body["count"] >= 1
        assert all(p["category"] == "fitness" for p in body["products"])


class TestProjects:
    def test_create_requires_name(self, client):
        resp = client.post("/api/projects", json={})
        assert resp.status_code == 422

    def test_create_example(self, client):
        resp = client.post("/api/projects", json={"example": True})
        assert resp.status_code == 201
        body = resp.json()
        assert body["brief"]["budget"] == 30000

    def test_create_with_brief(self, client):
        resp = client.post("/api/projects", json={"brief": {"business_name": "Test Co", "niche": "serum", "budget": 5000}})
        assert resp.status_code == 201

    def test_create_rejects_negative_budget(self, client):
        resp = client.post("/api/projects", json={"brief": {"business_name": "X", "budget": -5}})
        assert resp.status_code == 422

    def test_get_missing_project_404(self, client):
        assert client.get("/api/projects/nope").status_code == 404

    def test_list_projects(self, client, project_id):
        body = client.get("/api/projects").json()
        assert body["count"] == 1
        assert body["projects"][0]["id"] == project_id

    def test_delete_project(self, client, project_id):
        assert client.delete(f"/api/projects/{project_id}").status_code == 200
        assert client.get(f"/api/projects/{project_id}").status_code == 404
        assert client.delete(f"/api/projects/{project_id}").status_code == 404

    def test_persistence_across_client_restarts(self, tmp_path):
        db = tmp_path / "p.sqlite3"
        runtime.set_store(ProjectStore(db))
        c1 = TestClient(api.app)
        pid = c1.post("/api/projects", json={"example": True}).json()["id"]
        c1.post(f"/api/projects/{pid}/run-workflow", json={"mode": "sample"})
        runtime.set_store(ProjectStore(db))  # simulated restart
        c2 = TestClient(api.app)
        body = c2.get(f"/api/projects/{pid}").json()
        assert body["selected_product"] is not None
        assert body["report"] is not None


class TestResearch:
    def test_sample_mode(self, client):
        resp = client.post("/api/research", json={"niche": "skincare", "mode": "sample", "limit": 5})
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["products"]) == 5
        assert body["is_sample_data"] is True

    def test_invalid_mode_rejected(self, client):
        assert client.post("/api/research", json={"niche": "x", "mode": "magic"}).status_code == 422

    def test_negative_price_rejected(self, client):
        assert client.post("/api/research", json={"niche": "x", "price_min": -10}).status_code == 422


class TestStore:
    def test_generate_store_requires_product(self, client, project_id):
        resp = client.post(f"/api/projects/{project_id}/generate-store", json={})
        assert resp.status_code == 422  # no product selected yet

    def test_select_then_generate(self, client, project_id):
        client.post("/api/research", json={"niche": "skincare", "mode": "sample", "limit": 8})
        client.post(f"/api/projects/{project_id}/run-workflow", json={"mode": "sample"})
        resp = client.post(f"/api/projects/{project_id}/generate-store", json={})
        assert resp.status_code == 200
        spec = resp.json()
        assert spec["product"]["title"]
        assert spec["design"]["primary_color"].startswith("#")

    def test_edit_store_unmatched_prompt(self, client, project_id):
        client.post(f"/api/projects/{project_id}/run-workflow", json={"mode": "sample"})
        resp = client.post(f"/api/projects/{project_id}/edit-store", json={"prompt": "zzzzz"})
        body = resp.json()
        assert body["unmatched"] is True
        assert body["applied_changes"] == []

    def test_edit_store_applies(self, client, project_id):
        client.post(f"/api/projects/{project_id}/run-workflow", json={"mode": "sample"})
        resp = client.post(f"/api/projects/{project_id}/edit-store", json={"prompt": "make it more luxurious"})
        assert resp.json()["applied_changes"]

    def test_edit_store_short_prompt_422(self, client, project_id):
        client.post(f"/api/projects/{project_id}/run-workflow", json={"mode": "sample"})
        assert client.post(f"/api/projects/{project_id}/edit-store", json={"prompt": ""}).status_code == 422

    def test_invalid_hex_colour_422(self, client, project_id):
        client.post(f"/api/projects/{project_id}/run-workflow", json={"mode": "sample"})
        resp = client.post(f"/api/projects/{project_id}/generate-store", json={"design": {"primary_color": "not-a-colour"}})
        assert resp.status_code == 422

    def test_export_html(self, client, project_id):
        client.post(f"/api/projects/{project_id}/run-workflow", json={"mode": "sample"})
        resp = client.get(f"/api/projects/{project_id}/store/export")
        assert resp.status_code == 200
        assert resp.text.lstrip().startswith("<!doctype html")


class TestCampaign:
    def test_generate_campaign(self, client, project_id):
        client.post(f"/api/projects/{project_id}/run-workflow", json={"mode": "sample"})
        resp = client.post(f"/api/projects/{project_id}/generate-campaign", json={"objective": "sales", "budget": 30000})
        assert resp.status_code == 200
        body = resp.json()
        assert body["allocation_valid"] is True
        assert sum(a["amount"] for a in body["allocations"]) == 30000
        assert body["meta_connection"] == "not_connected"
        assert "DEMO" in body["publication"]

    def test_invalid_allocation_422(self, client, project_id):
        client.post(f"/api/projects/{project_id}/run-workflow", json={"mode": "sample"})
        resp = client.put(
            f"/api/projects/{project_id}/campaign",
            json={"budget": 30000, "allocations": [{"label": "all", "amount": 100}]},
        )
        assert resp.status_code == 422
        assert "sum" in resp.json()["detail"]

    def test_valid_allocation_update(self, client, project_id):
        client.post(f"/api/projects/{project_id}/run-workflow", json={"mode": "sample"})
        resp = client.put(
            f"/api/projects/{project_id}/campaign",
            json={"budget": 30000, "allocations": [
                {"label": "Testing", "amount": 6000}, {"label": "Scaling", "amount": 21000}, {"label": "Reserve", "amount": 3000}]},
        )
        assert resp.status_code == 200
        assert resp.json()["allocation_valid"] is True

    def test_simulate_labelled_demo(self, client, project_id):
        client.post(f"/api/projects/{project_id}/run-workflow", json={"mode": "sample"})
        body = client.post(f"/api/projects/{project_id}/campaign/simulate").json()
        assert body["label"] == "DEMO - NOT PUBLISHED"
        assert "SAMPLE DATA" in body["metric_source"]
        assert body["assumptions"]["cpc"] == 45.0


class TestAnalysis:
    def test_analyze_uses_stored_product(self, client, project_id):
        client.post(f"/api/projects/{project_id}/run-workflow", json={"mode": "sample"})
        body = client.post(f"/api/projects/{project_id}/analyze", json={}).json()
        product = client.get(f"/api/projects/{project_id}").json()["selected_product"]
        unit = body["unit_economics"]
        assert unit["selling_price"] == product["observed_price"]
        assert unit["break_even_roas"] is not None

    def test_negative_actuals_422(self, client, project_id):
        client.post(f"/api/projects/{project_id}/run-workflow", json={"mode": "sample"})
        resp = client.post(f"/api/projects/{project_id}/analyze", json={"actuals": {"ad_spend": -5}})
        assert resp.status_code == 422

    def test_zero_clicks_actuals_handled(self, client, project_id):
        client.post(f"/api/projects/{project_id}/run-workflow", json={"mode": "sample"})
        body = client.post(f"/api/projects/{project_id}/analyze", json={"actuals": {"ad_spend": 0, "clicks": 0, "conversions": 0, "customers": 0}}).json()
        assert body["kpis"]["cpa"] is None
        assert body["kpis"]["conversion_rate_pct"] is None


class TestWorkflowAndReport:
    def test_full_workflow(self, client, project_id):
        body = client.post(f"/api/projects/{project_id}/run-workflow", json={"mode": "sample"}).json()
        assert body["error"] is None
        assert all(s["status"] == "success" for s in body["steps"])

    def test_report(self, client, project_id):
        client.post(f"/api/projects/{project_id}/run-workflow", json={"mode": "sample"})
        body = client.get(f"/api/projects/{project_id}/report").json()
        assert len(body["sections"]) == 5
        assert body["next_actions"]

    def test_report_missing_project_404(self, client):
        assert client.get("/api/projects/nope/report").status_code == 404


class TestAssistant:
    def test_requires_message(self, client, project_id):
        assert client.post(f"/api/projects/{project_id}/assistant", json={}).status_code == 422

    def test_unknown_intent_is_honest(self, client, project_id):
        body = client.post(f"/api/projects/{project_id}/assistant", json={"message": "tell me a joke"}).json()
        assert body["intent"] == "unknown"
        assert "research products" in body["reply"]

    def test_store_edit_intent(self, client, project_id):
        client.post(f"/api/projects/{project_id}/run-workflow", json={"mode": "sample"})
        body = client.post(f"/api/projects/{project_id}/assistant", json={"message": "make the store more luxurious"}).json()
        assert body["intent"] == "store_edit"
        assert body.get("applied")


class TestIntegrations:
    def test_status_shape(self, client):
        body = client.get("/api/integrations/status").json()
        assert body["meta"]["status"] == "not_connected"
        assert body["shopify"]["status"] == "not_connected"
        assert body["web_search"]["status"] == "configured_unverified"
        assert body["meta"]["missing_configuration"]

    def test_meta_credentials_never_echoed(self, client, monkeypatch):
        monkeypatch.setattr(api.integrations, "meta_verify", lambda: {"verified": False, "detail": "Rejected"})
        resp = client.post(
            "/api/integrations/meta/credentials",
            json={"access_token": "EAAGSuperSecretToken123", "ad_account_id": "act_123"},
        )
        body = resp.json()
        assert "EAAGSuperSecretToken123" not in str(body)
        assert body["saved"] is True
        assert body["verified"] is False  # fake token cannot verify against Meta
        # and the status view masks it too
        status = client.get("/api/integrations/status").json()
        assert "EAAGSuperSecretToken123" not in str(status)
        assert status["meta"]["status"] == "configured_unverified"

    def test_shopify_sync_not_configured(self, client):
        body = client.post("/api/integrations/shopify/sync").json()
        assert body["ok"] is False
