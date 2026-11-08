"""Misconfigured deployments explain setup without exposing merchant data."""
from fastapi.testclient import TestClient

from commercepilot import api, config


def test_missing_session_secret_keeps_setup_visible_and_workspace_closed(monkeypatch):
    monkeypatch.setattr(config, 'validate_runtime', lambda: None)
    monkeypatch.setattr(config, 'AUTH_ENABLED', True)
    monkeypatch.setattr(config, 'SESSION_SECRET', '')
    with TestClient(api.app) as client:
        response = client.get('/api/auth/session')
        assert response.status_code == 200
        assert response.json()['authenticated'] is False
        assert 'SESSION_SECRET' in response.json()['setup_error']
        assert client.get('/api/projects').status_code == 503
        assert client.get('/api/auth/login').status_code == 503
        assert client.get('/api/auth/callback').status_code == 503
        assert client.get('/api/health').status_code == 503


def test_database_failure_does_not_leak_connection_details(monkeypatch):
    monkeypatch.setattr(config, 'validate_runtime', lambda: None)
    monkeypatch.setattr(config, 'AUTH_ENABLED', False)
    def unavailable():
        raise RuntimeError('postgres://private-user:private-password@private-host')
    monkeypatch.setattr(api, '_store', unavailable)
    with TestClient(api.app) as client:
        body = client.get('/api/auth/session').json()
        assert body['required'] is True
        assert body['authenticated'] is False
        assert 'DATABASE_URL' in body['setup_error']
        assert 'private-password' not in str(body)
        assert client.get('/api/projects').status_code == 503
