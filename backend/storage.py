"""SQLite persistence for projects.

A single `projects` table stores each project as a JSON document keyed by id.
Connections are per-thread; writes are atomic (BEGIN IMMEDIATE + commit).
Projects therefore survive page refreshes and backend restarts.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any, Optional

_SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_projects_updated ON projects(updated_at DESC);
"""


class ProjectStore:
    def __init__(self, path: Path | str):
        self.path = str(path)
        self._local = threading.local()
        self._init_lock = threading.Lock()
        self._initialized = False
        self.init_db()

    # ---- connection handling ------------------------------------------- #
    def _conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self.path, timeout=15)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            self._local.conn = conn
        return conn

    def init_db(self) -> None:
        with self._init_lock:
            if self._initialized:
                return
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
            conn = self._conn()
            conn.executescript(_SCHEMA)
            conn.commit()
            self._initialized = True

    # ---- CRUD ------------------------------------------------------------ #
    def save(self, project: dict[str, Any]) -> dict[str, Any]:
        payload = json.dumps(project, ensure_ascii=False)
        conn = self._conn()
        with conn:
            conn.execute(
                "INSERT INTO projects (id, name, data, created_at, updated_at) VALUES (?,?,?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET name=excluded.name, data=excluded.data, "
                "updated_at=excluded.updated_at",
                (
                    project["id"],
                    project.get("name") or "Untitled project",
                    payload,
                    project.get("created_at", ""),
                    project.get("updated_at", ""),
                ),
            )
        return project

    def get(self, project_id: str) -> Optional[dict[str, Any]]:
        row = self._conn().execute(
            "SELECT data FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        return self._migrate(json.loads(row["data"])) if row else None

    # Legacy-document migration lives here so EVERY load (routes, workflow,
    # assistant) sees versioned fields without each caller remembering them.
    def _migrate(self, project: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
        if project is None:
            return None
        project.setdefault("saved_products", [])
        project.setdefault("rejected_product_ids", [])
        return project

    def list(self) -> list[dict[str, Any]]:
        rows = self._conn().execute(
            "SELECT data FROM projects ORDER BY updated_at DESC"
        ).fetchall()
        return [self._migrate(json.loads(r["data"])) for r in rows]

    def delete(self, project_id: str) -> bool:
        conn = self._conn()
        with conn:
            cur = conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        return cur.rowcount > 0

    def count(self) -> int:
        return self._conn().execute("SELECT COUNT(*) AS n FROM projects").fetchone()["n"]
