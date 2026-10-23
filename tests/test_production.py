"""Production boundaries and regressions; no external service calls."""
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from commercepilot import api, config, integrations, runtime
from commercepilot.agents import business_analyst, product_hunter, store_architect
from commercepilot.ai import client as llm
from commercepilot.ai.schemas import CampaignCreatives, StoreCopy
from commercepilot.schemas import BusinessBrief, ManualProductInput, Product, ProjectCreate, ResearchRequest
from commercepilot.storage import ConcurrentUpdate, ProjectStore
from commercepilot.tools.calculations import allocate_budget
from commercepilot.tools.web_search import SearchResult
from commercepilot.workflows import commerce_workflow as wf


@pytest.fixture
def store(tmp_path):
    db = ProjectStore(tmp_path / "test.sqlite3")
    runtime.set_store(db)
    yield db
    runtime.reset_store()


@pytest.fixture
def production(monkeypatch):
    monkeypatch.setattr(config, "APP_MODE", "production")
    monkeypatch.setattr(config, "ADMIN_PASSWORD", "a-test-password-at-least-24-characters")
    monkeypatch.setattr(config, "LLM_API_KEY", "test-not-a-real-key")


def test_auth_and_csrf(production, store):
    client = TestClient(api.app)
    assert client.get("/api/health").status_code == 200
    for path in ("/api/projects", "/api/integrations/status", "/docs", "/"):
        assert client.get(path).status_code == 401
    client.auth = (config.ADMIN_USERNAME, config.ADMIN_PASSWORD)
    assert client.get("/api/projects").status_code == 200
    assert client.post("/api/projects", json={}, headers={"origin": "https://evil.example"}).status_code == 403
    assert client.post("/api/projects", json={"example": True}).status_code == 422
    assert client.get("/api/products").status_code == 404


def test_startup_requires_configuration(production, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_PASSWORD", "short")
    with pytest.raises(RuntimeError, match="ADMIN_PASSWORD"):
        config.validate_runtime()


def test_no_key_never_templates(production, monkeypatch):
    monkeypatch.setattr(config, "LLM_API_KEY", "")
    with pytest.raises(llm.AIConfigError):
        llm.complete_json(prompt_name="store_copy", user="test", schema=StoreCopy)


@pytest.mark.parametrize("schema", [StoreCopy, CampaignCreatives])
def test_empty_model_response_rejected(production, schema):
    with pytest.raises(ValidationError):
        schema.model_validate({})


def test_model_outage_not_swallowed(production, monkeypatch):
    def unavailable(**kwargs):
        raise llm.AIRequestError("Provider unavailable")
    monkeypatch.setattr(store_architect.ai, "complete_json", unavailable)
    with pytest.raises(llm.AIRequestError):
        store_architect.build_spec(BusinessBrief(business_name="Shop"), Product(id="p", title="Item"))


def test_live_store_has_no_fabricated_sections(production, monkeypatch):
    copy = StoreCopy(headline="Item", subheadline="Description", tagline="Shop", cta="View",
                     header_cta="View", detail_bullets=["User supplied detail"])
    monkeypatch.setattr(store_architect.ai, "complete_json", lambda **kwargs: copy)
    spec = store_architect.build_spec(BusinessBrief(business_name="Shop"), Product(id="p", title="Item", is_sample_data=False))
    assert spec.generation_mode == "llm"
    assert not {"reviews", "faq", "benefits"}.intersection(s.type for s in spec.sections)


def test_production_research_never_loads_sample(production, monkeypatch):
    from commercepilot.tools.web_search import SearchOutcome
    monkeypatch.setattr(product_hunter, "search", lambda *a, **kw: SearchOutcome())
    result = product_hunter.run(ResearchRequest(mode="both"))
    assert result.mode == "live" and result.products == []
    with pytest.raises(ValueError):
        product_hunter.load_sample_products()


def test_live_ids_stable_across_order():
    hit = SearchResult(title="Item", url="https://shop.example/item")
    assert product_hunter._live_product(hit, 1).id == product_hunter._live_product(hit, 20).id
    assert product_hunter._live_product(hit, 1).id != product_hunter._live_product(SearchResult(title="Item", url="https://other.example/item"), 1).id


def test_zero_weight_evidence():
    product = Product(id="p", title="Item", audience_fit=80)
    result = product_hunter.score_product(product, [], None, None, {"audience_fit": 0})
    assert result.score is None


def test_stale_write_rejected(store):
    project = wf.create_project(store, ProjectCreate(example=True))
    first, second = store.get(project["id"]), store.get(project["id"])
    first["name"] = "Updated"
    store.save(first)
    second["name"] = "Stale"
    with pytest.raises(ConcurrentUpdate):
        store.save(second)
    assert store.get(project["id"])["name"] == "Updated"
    store.delete(project["id"])
    with pytest.raises(ConcurrentUpdate):
        store.save(first)


def test_manual_cost_and_execution(store):
    project = wf.create_project(store, ProjectCreate(example=True))
    wf.step_manual_product(store, project, ManualProductInput(title="Item", observed_price=100, observed_cost=0))
    product = project["selected_product"]
    assert product["source"] == "manual" and product["margin_pct"] == 100
    assert product["cost_is_estimate"] is False
    assert project["executions"][-1]["status"] == "success"
    assert business_analyst.analyze(BusinessBrief(), Product(**product))["unit_economics"]["gross_profit_per_unit"] == 100


def test_brief_change_clears_outputs(store):
    project = wf.create_project(store, ProjectCreate(example=True))
    wf.run_full_workflow(store, project["id"], mode="sample")
    project = store.get(project["id"])
    wf.update_brief(store, project, BusinessBrief(business_name="Different"))
    assert all(project[k] is None for k in ("selected_product", "store_spec", "campaign", "analysis", "report"))


def test_campaign_budget_update_must_balance(store):
    project = wf.create_project(store, ProjectCreate(example=True))
    wf.run_full_workflow(store, project["id"], mode="sample")
    response = TestClient(api.app).put(f"/api/projects/{project['id']}/campaign", json={"budget": 99})
    assert response.status_code == 422


def test_no_default_scenarios_in_production(production):
    result = business_analyst.analyze(BusinessBrief(), Product(id="p", title="Item", observed_price=100, observed_cost=0))
    assert all(not s["available"] for s in result["scenarios"].values())


def test_cents_preserved():
    rows = allocate_budget(100.01, {"A": 70, "B": 30})
    assert sum(row["amount"] for row in rows) == pytest.approx(100.01)


@pytest.mark.parametrize("domain", ["127.0.0.1", "evil.example", "store.myshopify.com.evil.example", "store.myshopify.com@evil.example"])
def test_shopify_rejects_untrusted_host(monkeypatch, domain):
    monkeypatch.setattr(integrations, "_saved", lambda _: {})
    monkeypatch.setattr(config, "SHOPIFY_SHOP_DOMAIN", domain)
    monkeypatch.setattr(config, "SHOPIFY_ADMIN_TOKEN", "secret")
    assert not integrations.shopify_fetch_products()["ok"]


def test_shopify_graphql(monkeypatch):
    import httpx
    monkeypatch.setattr(integrations, "_saved", lambda _: {})
    monkeypatch.setattr(config, "SHOPIFY_SHOP_DOMAIN", "store.myshopify.com")
    monkeypatch.setattr(config, "SHOPIFY_ADMIN_TOKEN", "secret")
    def post(self, url, **kwargs):
        assert url.endswith("/graphql.json")
        assert kwargs["json"]["variables"] == {"first": 10}
        return httpx.Response(200, json={"data": {"products": {"nodes": [{"title": "Item", "handle": "item", "variants": {"nodes": [{"price": "10.50"}]}}], "pageInfo": {"hasNextPage": False, "endCursor": "end"}}}})
    monkeypatch.setattr(httpx.Client, "post", post)
    # Mock transport construction as well, so machine proxy configuration is irrelevant.
    original = httpx.Client
    monkeypatch.setattr(integrations.httpx, "Client", lambda **kw: original(trust_env=False, **kw))
    assert integrations.shopify_fetch_products()["products"][0]["price"] == "10.50"


def test_authenticated_real_product_workflow(production, store, monkeypatch):
    def generate(**kwargs):
        if kwargs["prompt_name"] == "store_copy":
            return StoreCopy(headline="Handmade notebook", subheadline="Paper notebook", tagline="Paper shop",
                             cta="View notebook", header_cta="View", detail_bullets=["Paper pages"])
        return CampaignCreatives(headlines=["Handmade notebook"] * 3, primary_texts=["Explore our paper notebook."] * 3)
    monkeypatch.setattr(store_architect.ai, "complete_json", generate)
    client = TestClient(api.app)
    client.auth = (config.ADMIN_USERNAME, config.ADMIN_PASSWORD)
    created = client.post("/api/projects", json={"brief": {"business_name": "Paper shop", "niche": "notebooks", "budget": 1000}})
    assert created.status_code == 201
    pid = created.json()["id"]
    manual = client.post(f"/api/projects/{pid}/products/manual", json={"title": "Handmade notebook", "observed_price": 200, "observed_cost": 80})
    assert manual.status_code == 200
    result = client.post(f"/api/projects/{pid}/run-workflow", json={}).json()
    assert result["error"] is None
    project = result["project"]
    assert project["store_spec"]["generation_mode"] == "llm"
    assert project["campaign"]["generation_mode"] == "llm"
    assert project["analysis"]["unit_economics"]["gross_profit_per_unit"] == 120
    assert project["report"]
    assert client.post(f"/api/projects/{pid}/campaign/simulate").status_code != 200


def test_currency_mismatch_rejected():
    with pytest.raises(ValueError, match="currencies"):
        business_analyst.analyze(BusinessBrief(currency="PKR"), Product(id="p", title="Item", currency="USD", observed_price=10, observed_cost=2))
