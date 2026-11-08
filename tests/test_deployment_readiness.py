"""Misconfigured deployments explain setup without exposing merchant data."""
from fastapi.testclient import TestClient

from commercepilot import api, config


def test_auth_environment_variables_no_longer_gate_workspace(monkeypatch, tmp_path):
    from commercepilot.storage import ProjectStore
    monkeypatch.setattr(config, 'validate_runtime', lambda: None)
    monkeypatch.setenv('AUTH_ENABLED', 'true')
    monkeypatch.setenv('SESSION_SECRET', '')
    monkeypatch.setenv('GOOGLE_CLIENT_ID', '')
    monkeypatch.setenv('GOOGLE_CLIENT_SECRET', '')
    monkeypatch.setattr(api, '_store', lambda: ProjectStore(tmp_path / 'open.sqlite3'))
    with TestClient(api.app) as client:
        assert client.get('/api/projects').status_code == 200
        assert client.get('/api/health').status_code == 200
        for path in ['/api/auth/session', '/api/auth/login', '/api/auth/callback']:
            assert client.get(path).status_code == 404


def test_database_failure_does_not_leak_connection_details(monkeypatch):
    monkeypatch.setattr(config, 'validate_runtime', lambda: None)
    def unavailable():
        raise RuntimeError('postgres://private-user:private-password@private-host')
    monkeypatch.setattr(api, '_store', unavailable)
    with TestClient(api.app) as client:
        response = client.get('/api/projects')
        assert response.status_code == 503
        assert 'DATABASE_URL' in response.json()['detail']
        assert 'private-password' not in response.text
