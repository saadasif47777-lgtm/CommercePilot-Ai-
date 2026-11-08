"""Replica-safe ownership of expensive project and sync operations."""
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps

from fastapi import HTTPException

owned = ContextVar("owned_operations", default=frozenset())


@contextmanager
def operation(db, key):
    identity = (db.target, db.namespace, key)
    if identity in owned.get():
        yield
        return
    db.execute("CREATE TABLE IF NOT EXISTS operation_leases (id TEXT PRIMARY KEY, owner TEXT NOT NULL, expires REAL NOT NULL)")
    owner = uuid.uuid4().hex
    with db:
        db.lock_project("operation:" + key)
        row = db.execute("SELECT expires FROM operation_leases WHERE id=?", (key,)).fetchone()
        if row and row["expires"] > time.time():
            raise HTTPException(409, "An operation is already running here. Wait, then refresh to resume saved results.")
        db.execute("INSERT INTO operation_leases(id,owner,expires) VALUES (?,?,?) ON CONFLICT(id) DO UPDATE SET owner=excluded.owner,expires=excluded.expires", (key, owner, time.time() + 120))
    reset = owned.set(owned.get() | {identity})
    try:
        yield
    finally:
        owned.reset(reset)
        db.execute("DELETE FROM operation_leases WHERE id=? AND owner=?", (key, owner))


def project_operation(fn):
    @wraps(fn)
    def wrapped(store, project, *args, **kwargs):
        key = project["id"] if isinstance(project, dict) else project
        with operation(store._conn(), "project:" + key):
            return fn(store, project, *args, **kwargs)
    return wrapped


def sync_operation(fn):
    @wraps(fn)
    def wrapped(store, *args, **kwargs):
        with operation(store.db, "shopify-sync"):
            return fn(store, *args, **kwargs)
    return wrapped
