"""Small SQL boundary shared by SQLite and pooled PostgreSQL storage."""
from __future__ import annotations

import sqlite3
import sys
import threading
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=4)
def _pool(url: str):
    from psycopg.rows import dict_row
    from psycopg_pool import ConnectionPool

    return ConnectionPool(url, min_size=0, max_size=4, timeout=10,
                          kwargs={"autocommit": True, "row_factory": dict_row, "connect_timeout": 10})


class Result:
    def __init__(self, cursor):
        self.rowcount = cursor.rowcount
        self.rows = [dict(row) for row in cursor.fetchall()] if cursor.description else []

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


class Database:
    def __init__(self, target):
        self.target = str(target)
        self.postgres = self.target.startswith(("postgres://", "postgresql://"))
        self._local = threading.local()
        if not self.postgres:
            Path(self.target).parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connection(self):
        active = getattr(self._local, "connection", None)
        if active is not None:
            yield active
        elif self.postgres:
            with _pool(self.target).connection() as conn:
                yield conn
        else:
            conn = sqlite3.connect(self.target, timeout=15, isolation_level=None)
            conn.row_factory = sqlite3.Row
            try:
                yield conn
            finally:
                conn.close()

    def __enter__(self):
        self._local.manager = self.connection()
        conn = self._local.manager.__enter__()
        self._local.connection = conn
        try:
            conn.execute("BEGIN" if self.postgres else "BEGIN IMMEDIATE")
        except Exception:
            self._local.connection = None
            self._local.manager.__exit__(*sys.exc_info())
            raise
        return self

    def __exit__(self, kind, value, tb):
        conn = self._local.connection
        try:
            conn.execute("ROLLBACK" if kind else "COMMIT")
        finally:
            self._local.connection = None
            self._local.manager.__exit__(kind, value, tb)

    def execute(self, sql, params=()):
        if sql == "BEGIN IMMEDIATE":
            return None  # __enter__ already started the write transaction.
        if self.postgres:
            sql = sql.replace("%", "%%").replace("?", "%s")
        with self.connection() as conn:
            return Result(conn.execute(sql, params))

    def executescript(self, schema):
        if self.postgres:
            schema = schema.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "BIGSERIAL PRIMARY KEY")
            schema = schema.replace("REAL NOT NULL", "DOUBLE PRECISION NOT NULL")
        with self:
            self.lock_project("commercepilot-schema")
            for statement in schema.split(";"):
                if statement.strip():
                    self.execute(statement)

    def commit(self):
        pass  # Standalone statements autocommit; context blocks own transactions.

    def lock_project(self, project_id):
        if self.postgres:
            self.execute("SELECT pg_advisory_xact_lock(hashtextextended(?, 0))", (project_id,))
