"""Real PostgreSQL checks; CI supplies a disposable database service."""
import os
import uuid
from urllib.parse import urlencode

import pytest

from commercepilot import config, credentials
from commercepilot.ai.usage import UsageLog
from commercepilot.database import _pool
from commercepilot.storage import ConcurrentUpdate, ProjectStore


@pytest.fixture
def target():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is not configured")
    import psycopg
    from psycopg import sql
    name = "test_" + uuid.uuid4().hex
    with psycopg.connect(url, autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(name)))
    target = url + ("&" if "?" in url else "?") + urlencode({"options": "-csearch_path=" + name})
    try:
        yield target
    finally:
        _pool(target).close()
        with psycopg.connect(url, autocommit=True) as connection:
            connection.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(name)))


def test_postgres_persistence_and_revision_conflict(target):
    first = ProjectStore(target)
    project = first.save({"id": "project", "name": "Client", "created_at": "2026-10-23", "updated_at": "2026-10-23"})
    second = ProjectStore(target)
    stale = second.get(project["id"])
    project["name"] = "Updated"
    first.save(project)
    with pytest.raises(ConcurrentUpdate):
        second.save(stale)
    assert second.get(project["id"])["name"] == "Updated"
    assert second.count() == 1
    assert len(second.list()) == 1
    assert second.delete(project["id"])


def test_postgres_usage_log_and_percent_sql(target):
    log = UsageLog(target)
    log.record(provider="test", model="test", prompt="intent", est_cost_usd=0.125, status="failed_transport")
    assert log.month_cost() == pytest.approx(0.125)
    assert log.summary()["failures"] == 1


def test_postgres_credentials_encrypted_and_durable(target, monkeypatch):
    from cryptography.fernet import Fernet
    monkeypatch.setattr(config, "DATABASE_URL", target)
    monkeypatch.setattr(config, "CREDENTIAL_ENCRYPTION_KEY", Fernet.generate_key().decode())
    credentials.save("shopify", {"admin_token": "test-secret", "shop_domain": "test.myshopify.com"})
    assert credentials.read("shopify")["admin_token"] == "test-secret"
    row = credentials._db().execute("SELECT ciphertext FROM integration_credentials WHERE provider=?", ("shopify",)).fetchone()
    assert "test-secret" not in row["ciphertext"]
    monkeypatch.setattr(config, "CREDENTIAL_ENCRYPTION_KEY", Fernet.generate_key().decode())
    with pytest.raises(credentials.CredentialError):
        credentials.read("shopify")


def test_postgres_support_snapshot_filters_and_sessions(target, monkeypatch):
    from commercepilot.database import Database
    from commercepilot.support import service, shopify
    from commercepilot.support.models import QueryPlan, Settings
    from commercepilot.support.store import SupportStore
    from tests.test_support import DOMAIN, seed, transport_data

    monkeypatch.setattr(config, "SHOPIFY_SHOP_DOMAIN", DOMAIN)
    monkeypatch.setattr(config, "SHOPIFY_ADMIN_TOKEN", "test-shopify-secret")
    monkeypatch.setattr(shopify, "graphql", transport_data)
    first = SupportStore(Database(target))
    seed(first)
    first.save_settings(Settings(enabled=True))
    second = SupportStore(Database(target))
    state = second.state()
    assert service.status(second)["ready"]
    assert service.status(second)["counts"] == {"policy": 1, "product": 2}
    products = second.products(state["active"], QueryPlan(intent="products", terms=["lamp"], max_price=25))
    assert len(products) == 1 and products[0]["price"] == "20"
    assert not second.products(state["active"], QueryPlan(intent="products", terms=["%_"]))
    token = first.new_session(state)
    assert second.reserve_session(state, token) == []
    second.finish_session(token, [{"role": "user", "content": "A lamp"}])
    assert first.reserve_session(state, token)[0]["content"] == "A lamp"
    first.finish_session(token)


def test_postgres_support_limit_concurrent_requests(target):
    from concurrent.futures import ThreadPoolExecutor

    from fastapi import HTTPException

    from commercepilot.database import Database
    from commercepilot.support.store import SupportStore

    store = SupportStore(Database(target))
    def attempt(_):
        try:
            store.limit("concurrent-test", 3, 3600)
            return 200
        except HTTPException as exc:
            return exc.status_code
    with ThreadPoolExecutor(max_workers=5) as workers:
        outcomes = list(workers.map(attempt, range(5)))
    assert outcomes.count(200) == 3 and outcomes.count(429) == 2


def test_postgres_advisor_conversation_is_durable_and_isolated(target):
    from commercepilot.advisor.store import AdvisorStore
    from commercepilot.database import Database

    first, second = AdvisorStore(Database(target)), AdvisorStore(Database(target))
    token = first.create("project-a")
    row, data = second.reserve(token)
    assert row["project_id"] == "project-a" and data["messages"] == []
    data["overrides"] = {"budget": 50000, "currency": "PKR", "location": "Lahore"}
    data["messages"] = [{"role": "user", "text": "Help plan my business"}]
    second.finish(token, data)
    assert first.read(token, "project-a", check_project=True)[1]["overrides"]["budget"] == 50000
    other = first.create("project-b")
    assert second.read(other)[1]["messages"] == []


def test_postgres_advisor_daily_budget_is_replica_safe(target, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor

    from fastapi import HTTPException

    from commercepilot.advisor.store import AdvisorStore
    from commercepilot.database import Database

    store = AdvisorStore(Database(target))
    monkeypatch.setattr(config, "ADVISOR_DAILY_MESSAGES", 3)
    tokens = [store.create() for _ in range(5)]
    def reserve(token):
        try:
            store.reserve(token)
            store.finish(token)
            return 200
        except HTTPException as exc:
            return exc.status_code
    with ThreadPoolExecutor(max_workers=5) as workers:
        results = list(workers.map(reserve, tokens))
    assert results.count(200) == 3 and results.count(429) == 2
