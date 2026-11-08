"""Regression coverage for the November audit; providers never receive real calls."""
import copy

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

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
    monkeypatch.setattr(config, 'PUBLIC_URL', 'https://workspace.example')
    monkeypatch.setattr(config, 'DB_PATH', tmp_path / 'merchants.sqlite3')
    monkeypatch.setattr(config, 'DATABASE_URL', '')
    monkeypatch.setattr(config, 'CREDENTIAL_ENCRYPTION_KEY', Fernet.generate_key().decode())
    monkeypatch.setattr(runtime, '_workspaces', {})
    yield
    workspace.set('')


def test_old_session_cookie_does_not_restrict_shared_workspace(tmp_path):
    store = ProjectStore(tmp_path / 'shared.sqlite3')
    runtime.set_store(store)
    try:
        project = wf.create_project(store, ProjectCreate(name='Existing project'))
        client = TestClient(app)
        client.cookies.set('commercepilot_session', 'obsolete-session')
        assert client.get(f"/api/projects/{project['id']}").status_code == 200
        assert client.get('/api/projects').json()['count'] == 1
    finally:
        runtime.reset_store()


def test_credentials_and_knowledge_are_partitioned(merchants):
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
    ids = []
    for subject in ['a' * 64, 'b' * 64]:
        reset = workspace.set(subject)
        try:
            ids.append(runtime.get_support_store().state()['widget_id'])
        finally:
            workspace.reset(reset)
    assert ids[0] != ids[1]


def test_rejected_credentials_preserve_connection(tmp_path, monkeypatch):
    from commercepilot import integrations
    monkeypatch.setattr(config, 'SECRETS_DIR', tmp_path)
    integrations.save_credentials('meta', {'access_token': 'previous', 'ad_account_id': 'act_123'})
    monkeypatch.setattr(integrations, 'meta_verify', lambda **kw: {'verified': False, 'detail': 'Rejected'})
    response = TestClient(app).post('/api/integrations/meta/credentials', json={'access_token': 'invalid-replacement', 'ad_account_id': 'act_123'})
    assert response.json()['saved'] is False
    assert integrations._saved('meta')['access_token'] == 'previous'


def test_existing_namespaced_widget_remains_origin_scoped_without_auth(merchants, monkeypatch):
    from commercepilot.support import service
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
    from commercepilot.support.routes import registry
    widget = state['widget_id']
    registry().execute('INSERT INTO widget_workspaces(widget_id,workspace) VALUES (?,?)', (widget, 'a' * 64))
    shopper = TestClient(app)
    path = f'/api/support/widget/{widget}/config'
    assert shopper.get(path, headers={'Origin': 'https://store.example'}).status_code == 200
    assert shopper.get(path, headers={'Origin': 'https://other.example'}).status_code == 403


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


def test_unavailable_review_preserves_previous_research(tmp_path, monkeypatch):
    store = ProjectStore(tmp_path / 'review.sqlite3')
    project = wf.create_project(store, ProjectCreate(example=True))
    wf.run_full_workflow(store, project['id'], mode='sample')
    project = store.get(project['id'])
    previous = copy.deepcopy(project['research'])
    attempt = ResearchResult(**dict(previous, ai_review_status='unavailable'))
    monkeypatch.setattr(wf.product_hunter, 'run', lambda req: attempt)
    wf.step_research(store, project, ResearchRequest(mode='sample'))
    stored = store.get(project['id'])
    assert stored['research'] == previous
    assert stored['research_attempt']['status'] == 'unreviewed'
    assert stored['research_attempt']['result']['products']
    assert stored['report'] == project['report']


def test_legacy_migration_is_explicit_non_destructive_and_preserves_revision(tmp_path):
    from scripts.migrate_legacy_projects import migrate
    target = tmp_path / 'migration.sqlite3'
    original = ProjectStore(target)
    project = wf.create_project(original, ProjectCreate(name='Legacy'))
    other = wf.create_project(original, ProjectCreate(name='Other client'))
    owner = 'a' * 64
    assert migrate(target, owner, [project['id']], apply=False) == 1
    reset = workspace.set(owner)
    try:
        destination = ProjectStore(target)
        assert destination.count() == 0
    finally:
        workspace.reset(reset)
    migrate(target, owner, [project['id']], apply=True)
    assert destination.get(project['id']) == original.get(project['id'])
    assert destination.get(other['id']) is None
    assert original.count() == 2
    with pytest.raises(ValueError):
        migrate(target, owner, [project['id']], apply=True)
