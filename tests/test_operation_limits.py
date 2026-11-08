"""Concurrency checks use independent database objects like separate replicas."""
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import HTTPException

from commercepilot.ai.usage import UsageLog
from commercepilot.database import Database
from commercepilot.operations import operation


def test_budget_reservation_cannot_oversubscribe(tmp_path):
    path = tmp_path / 'budget.sqlite3'
    logs = [UsageLog(path) for _ in range(8)]
    with ThreadPoolExecutor(max_workers=8) as pool:
        reservations = list(pool.map(lambda log: log.reserve(0.4, 1.0), logs))
    assert len([token for token in reservations if token]) == 2
    assert logs[0].reserved_cost() == pytest.approx(0.8)
    token = next(token for token in reservations if token)
    logs[0].record(provider='test', model='test', prompt='test', est_cost_usd=0.1, reservation=token)
    assert logs[0].reserved_cost() == pytest.approx(0.4)
    assert logs[1].reserve(0.4, 1.0)
    assert not logs[2].reserve(0.2, 1.0)


def test_project_operation_has_one_owner_and_recovers_after_failure(tmp_path):
    path = tmp_path / 'ownership.sqlite3'
    first, second = Database(path), Database(path)
    def other_replica():
        with operation(second, 'project:one'):
            pytest.fail('A concurrent owner was admitted')
    with operation(first, 'project:one'):
        with operation(first, 'project:one'):
            pass  # nested workflow steps share the request owner
        with ThreadPoolExecutor(max_workers=1) as pool:
            with pytest.raises(HTTPException) as exc:
                pool.submit(other_replica).result()
            assert exc.value.status_code == 409
    with pytest.raises(RuntimeError), operation(second, 'project:one'):
        raise RuntimeError('interrupted')
    with operation(first, 'project:one'):
        pass


def test_unknown_transport_cost_stays_reserved(tmp_path):
    log = UsageLog(tmp_path / 'uncertain.sqlite3')
    token = log.reserve(0.9, 1.0)
    assert token
    log.record(provider='test', model='test', prompt='test', status='failed_transport')
    assert not log.reserve(0.2, 1.0)


def test_namespaced_budget_tables_do_not_share_allowance(tmp_path):
    from commercepilot.auth import workspace
    logs = []
    for subject in ['a' * 64, 'b' * 64]:
        token = workspace.set(subject)
        try:
            logs.append(UsageLog(tmp_path / 'clients.sqlite3'))
        finally:
            workspace.reset(token)
    assert logs[0].reserve(1, 1)
    assert logs[1].reserve(1, 1)
    assert not logs[0].reserve(0.1, 1)


def test_provider_allowance_is_shared_across_authenticated_clients(tmp_path, monkeypatch):
    from commercepilot import config, runtime
    from commercepilot.ai.client import _billing_log
    from commercepilot.auth import workspace
    monkeypatch.setattr(config, 'DB_PATH', tmp_path / 'shared-billing.sqlite3')
    monkeypatch.setattr(config, 'DATABASE_URL', '')
    monkeypatch.setattr(runtime, '_workspaces', {})
    a = workspace.set('a' * 64)
    try:
        assert _billing_log().reserve(0.8, 1)
        b = workspace.set('b' * 64)
        try:
            assert not _billing_log().reserve(0.3, 1)
        finally:
            workspace.reset(b)
    finally:
        workspace.reset(a)
