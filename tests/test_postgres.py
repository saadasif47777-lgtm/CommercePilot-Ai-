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
