"""Regression coverage for the November audit; providers never receive real calls."""
import base64
import copy
import json

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from itsdangerous import TimestampSigner

from commercepilot import config, credentials, runtime
from commercepilot.api import app
from commercepilot.auth import workspace
from commercepilot.schemas import ProjectCreate, ResearchRequest, ResearchResult
from commercepilot.storage import ProjectStore
from commercepilot.workflows import commerce_workflow as wf


@pytest.mark.parametrize('outcome', ['empty', 'exception', 'success'])
def test_research_attempt_preserves_saved_work(tmp_path, monkeypatch, outcome):
    store = ProjectStore(tmp_path / 'research.sqlite3')
    project = wf.create_project(store, ProjectCreate(example=True))
    wf.run_full_workflow(store, project['id'], mode='sample')
    project = store.get(project['id'])
    fields = ['selected_product', 'store_spec', 'campaign', 'analysis', 'report']
    before = {k: copy.deepcopy(project.get(k)) for k in fields}
    old_research = copy.deepcopy(project['research'])

    def research(_):
        if outcome == 'exception':
            raise RuntimeError('search unavailable')
        return ResearchResult(**old_research) if outcome == 'success' else ResearchResult(mode='sample', products=[])

    monkeypatch.setattr(wf.product_hunter, 'run', research)
    if outcome == 'success':
        wf.step_research(store, project, ResearchRequest(mode='sample'))
    else:
        with pytest.raises(wf.StepFailed):
            wf.step_research(store, project, ResearchRequest(mode='sample'))
    after = store.get(project['id'])
    assert {k: after.get(k) for k in fields} == before
    assert after['research'] == old_research or outcome == 'success'
    assert after['executions'][-1]['status'] == ('success' if outcome == 'success' else 'error')


def test_report_get_is_read_only(tmp_path):
    store = ProjectStore(tmp_path / 'report.sqlite3')
    runtime.set_store(store)
    project = wf.create_project(store, ProjectCreate(example=True))
    client = TestClient(app)
    revision = store.get(project['id'])['_revision']
    assert client.get(f"/api/projects/{project['id']}/report").status_code == 404
    assert store.get(project['id'])['_revision'] == revision
    wf.run_full_workflow(store, project['id'], mode='sample')
    revision = store.get(project['id'])['_revision']
    assert client.get(f"/api/projects/{project['id']}/report").status_code == 200
    assert client.get(f"/api/projects/{project['id']}/report?refresh=true").status_code == 405
    assert store.get(project['id'])['_revision'] == revision


@pytest.fixture
def merchants(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'AUTH_ENABLED', True)
    monkeypatch.setattr(config, 'SESSION_SECRET', 'x' * 40)
    monkeypatch.setattr(config, 'PUBLIC_URL', 'https://workspace.example')
    monkeypatch.setattr(config, 'DB_PATH', tmp_path / 'merchants.sqlite3')
    monkeypatch.setattr(config, 'DATABASE_URL', '')
    monkeypatch.setattr(config, 'CREDENTIAL_ENCRYPTION_KEY', Fernet.generate_key().decode())
    monkeypatch.setattr(runtime, '_workspaces', {})
    # The test app's middleware was constructed in demo mode at import.
    def merchant(subject):
        client = TestClient(app)
        cookie = TimestampSigner('local-development-only').sign(base64.b64encode(json.dumps({'subject': subject}).encode())).decode()
        client.cookies.set('commercepilot_session', cookie)
        return client
    yield merchant('a' * 64), merchant('b' * 64)
    workspace.set('')


def test_anonymous_and_cross_workspace_access(merchants):
    a, b = merchants
    anonymous = TestClient(app)
    for path in ['/api/projects', '/api/integrations/status', '/api/support/status', '/docs']:
        assert anonymous.get(path).status_code == 401
    assert anonymous.post('/api/research', json={}).status_code == 401
    p = a.post('/api/projects', json={'brief': {'business_name': 'Private', 'niche': 'lamps', 'budget': 1000}}).json()
    assert a.get('/api/projects').json()['count'] == 1
    assert b.get('/api/projects').json()['count'] == 0
    for method, path in [('get', ''), ('delete', ''), ('get', '/store/export'), ('post', '/analyze'), ('post', '/report'), ('post', '/run-workflow')]:
        assert getattr(b, method)(f"/api/projects/{p['id']}{path}").status_code == 404
    assert a.get(f"/api/projects/{p['id']}").status_code == 200


def test_credentials_and_knowledge_are_partitioned(merchants):
    a, b = merchants
    for subject, token in [('a' * 64, 'private-a'), ('b' * 64, 'private-b')]:
        reset = workspace.set(subject)
        try:
            credentials.save('shopify', {'admin_token': token})
        finally:
            workspace.reset(reset)
    for subject, expected in [('a' * 64, 'private-a'), ('b' * 64, 'private-b')]:
        reset = workspace.set(subject)
        try:
            assert credentials.read('shopify')['admin_token'] == expected
        finally:
            workspace.reset(reset)
    assert a.get('/api/support/status').json()['widget_id'] != b.get('/api/support/status').json()['widget_id']


def test_rejected_credentials_preserve_connection(tmp_path, monkeypatch):
    from commercepilot import integrations
    monkeypatch.setattr(config, 'SECRETS_DIR', tmp_path)
    integrations.save_credentials('meta', {'access_token': 'previous', 'ad_account_id': 'act_123'})
    monkeypatch.setattr(integrations, 'meta_verify', lambda **kw: {'verified': False, 'detail': 'Rejected'})
    response = TestClient(app).post('/api/integrations/meta/credentials', json={'access_token': 'invalid-replacement', 'ad_account_id': 'act_123'})
    assert response.json()['saved'] is False
    assert integrations._saved('meta')['access_token'] == 'previous'


def test_widget_remains_public_but_origin_scoped_with_auth(merchants, monkeypatch):
    from commercepilot.support import service
    a, _ = merchants
    reset = workspace.set('a' * 64)
    try:
        support = runtime.get_support_store()
        state = support.state()
        state['settings']['enabled'] = True
        state['settings']['allowed_origins'] = ['https://store.example']
        support.write_state(state)
    finally:
        workspace.reset(reset)
    monkeypatch.setattr(service, 'availability', lambda state: '')
    widget = a.get('/api/support/install').json()['widget_id']
    shopper = TestClient(app)
    path = f'/api/support/widget/{widget}/config'
    assert shopper.get(path, headers={'Origin': 'https://store.example'}).status_code == 200
    assert shopper.get(path, headers={'Origin': 'https://other.example'}).status_code == 403
    assert shopper.get('/api/support/status').status_code == 401


def test_late_widget_release_does_not_clear_new_reservation(tmp_path):
    from commercepilot.database import Database
    from commercepilot.support.store import SupportStore, digest
    support = SupportStore(Database(tmp_path / 'leases.sqlite3'))
    state = support.state()
    state['active'] = 'generation'
    token = support.new_session(state)
    _, old = support.reserve_session(state, token)
    support.db.execute("UPDATE support_sessions SET busy_until='2099-01-01' WHERE id_hash=?", (digest(token),))
    support.finish_session(token, old)
    assert support.db.execute('SELECT busy_until FROM support_sessions WHERE id_hash=?', (digest(token),)).fetchone()['busy_until'] == '2099-01-01'
