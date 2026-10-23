"""Client workflow regressions against the real HTTP and persistence layers."""
import pytest
from fastapi.testclient import TestClient

from commercepilot import api, config, integrations, runtime
from commercepilot.schemas import ProjectCreate
from commercepilot.storage import ProjectStore
from commercepilot.tools.web_search import SearchOutcome, SearchResult
from commercepilot.workflows import commerce_workflow as wf


@pytest.fixture
def client(tmp_path):
    runtime.set_store(ProjectStore(tmp_path / "client.sqlite3"))
    yield TestClient(api.app)
    runtime.reset_store()


def test_project_research_uses_and_saves_exact_query(client, monkeypatch):
    seen = []
    def search(query, **kwargs):
        seen.append(query)
        return SearchOutcome(results=[SearchResult("Desk lamp PKR 2000", "https://shop.example/lamp", "A desk lamp")])
    monkeypatch.setattr(api.product_hunter, "search", search)
    pid = client.post("/api/projects", json={"brief": {"business_name": "Store", "niche": "home", "budget": 1000}}).json()["id"]
    result = client.post(f"/api/projects/{pid}/research", json={"mode": "live", "niche": "desk lamps", "constraints": ["no batteries"]})
    assert result.status_code == 200
    assert len(seen) == 1 and "desk lamps" in seen[0]
    project = client.get(f"/api/projects/{pid}").json()
    assert project["research"]["products"][0]["title"] == "Desk lamp PKR 2000"
    assert project["selected_product"] is None
    assert project["campaign"] is None


def test_economics_updates_selected_product_and_invalidates(client):
    pid = client.post("/api/projects", json={"brief": {"business_name": "Store"}}).json()["id"]
    client.post(f"/api/projects/{pid}/products/manual", json={"title": "Notebook", "observed_price": 200, "observed_cost": 50})
    response = client.put(f"/api/projects/{pid}/product-economics", json={"observed_price": 250, "observed_cost": 0, "currency": "PKR"})
    assert response.status_code == 200
    project = response.json()
    assert project["selected_product"]["gross_profit"] == 250
    assert project["saved_products"][0]["observed_cost"] == 0
    assert project["store_spec"] is None
    assert client.put(f"/api/projects/{pid}/product-economics", json={"observed_price": 250, "observed_cost": 50, "currency": "USD"}).status_code == 422


def test_analytics_inputs_survive_scenario_update(client):
    pid = client.post("/api/projects", json={"brief": {"business_name": "Store"}}).json()["id"]
    client.post(f"/api/projects/{pid}/products/manual", json={"title": "Notebook", "observed_price": 200, "observed_cost": 50})
    first = client.post(f"/api/projects/{pid}/analyze", json={"actuals": {"ad_spend": 100, "customers": 2, "revenue": 400}, "overheads": {"shipping_cost_per_unit": 10}})
    assert first.json()["kpis"]["cpa"] == 50
    second = client.post(f"/api/projects/{pid}/analyze", json={"base": {"clicks": 100, "conversion_rate_pct": 2, "cpc": 1}})
    assert second.json()["kpis"]["cpa"] == 50
    assert second.json()["contribution_economics"]["shipping_cost_per_unit"] == 10


def test_verified_state_matches_credentials(client, monkeypatch):
    monkeypatch.setattr(integrations, "_saved", lambda provider: {})
    monkeypatch.setattr(config, "META_ACCESS_TOKEN", "test-token")
    monkeypatch.setattr(config, "META_AD_ACCOUNT_ID", "act_123")
    integrations.mark_verified("meta", ["test-token", "act_123"])
    assert integrations.meta_status()["status"] == "connected"
    monkeypatch.setattr(config, "META_ACCESS_TOKEN", "rotated-token")
    assert integrations.meta_status()["status"] == "configured_unverified"


def test_shopify_import_checks_currency_and_uses_server_catalog(client, monkeypatch):
    pid = client.post("/api/projects", json={"brief": {"business_name": "Store"}}).json()["id"]
    monkeypatch.setattr(integrations, "shopify_fetch_products", lambda limit: {"ok": True, "currency": "PKR", "products": [{"id": "gid://shopify/Product/1", "title": "Notebook", "price": "250", "description": "Paper"}]})
    response = client.post(f"/api/projects/{pid}/shopify/import", json={"product_id": "gid://shopify/Product/1", "price": 0.01})
    assert response.status_code == 200
    assert response.json()["selected_product"]["observed_price"] == 250
    assert not response.json()["selected_product"]["is_sample_data"]


def test_new_store_persists_across_instances(tmp_path):
    target = tmp_path / "durable.sqlite3"
    first = ProjectStore(target)
    project = wf.create_project(first, ProjectCreate(name="Real store"))
    second = ProjectStore(target)
    assert second.get(project["id"])["name"] == "Real store"
