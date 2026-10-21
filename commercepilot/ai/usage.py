"""AI usage log and monthly spend accounting.

SQLite today (same database file as projects); moves to Postgres with the rest
of the data layer in Phase 3. Only the prompt NAME and token counts are stored —
never prompt contents — so the log cannot leak user data.
"""
from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

_SCHEMA = """
CREATE TABLE IF NOT EXISTS ai_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    prompt TEXT NOT NULL,
    user_id TEXT,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    est_cost_usd REAL NOT NULL DEFAULT 0,
    latency_ms INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ai_usage_created ON ai_usage(created_at);
"""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class UsageLog:
    def __init__(self, path: Path | str):
        self.path = str(path)
        self._local = threading.local()
        self._init_lock = threading.Lock()
        self._initialized = False
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(self.path, timeout=15)
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
        return conn

    def _init_db(self) -> None:
        with self._init_lock:
            if self._initialized:
                return
            conn = self._conn()
            conn.executescript(_SCHEMA)
            conn.commit()
            self._initialized = True

    def record(
        self,
        *,
        provider: str,
        model: str,
        prompt: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        est_cost_usd: float = 0.0,
        latency_ms: int = 0,
        status: str = "ok",
        user_id: Optional[str] = None,
    ) -> None:
        conn = self._conn()
        with conn:
            conn.execute(
                "INSERT INTO ai_usage (created_at, provider, model, prompt, user_id, "
                "input_tokens, output_tokens, est_cost_usd, latency_ms, status) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    _utcnow(),
                    provider,
                    model,
                    prompt,
                    user_id,
                    int(input_tokens),
                    int(output_tokens),
                    float(est_cost_usd),
                    int(latency_ms),
                    status,
                ),
            )

    def month_cost(self) -> float:
        """Estimated spend since the first day of the current UTC month."""
        start = datetime.now(timezone.utc).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        ).isoformat()
        row = self._conn().execute(
            "SELECT COALESCE(SUM(est_cost_usd), 0) AS cost FROM ai_usage WHERE created_at >= ?",
            (start,),
        ).fetchone()
        return float(row["cost"] or 0.0)

    def summary(self) -> dict[str, Any]:
        start = datetime.now(timezone.utc).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        ).isoformat()
        row = self._conn().execute(
            "SELECT COUNT(*) AS calls, "
            "COALESCE(SUM(input_tokens),0) AS input_tokens, "
            "COALESCE(SUM(output_tokens),0) AS output_tokens, "
            "COALESCE(SUM(est_cost_usd),0) AS est_cost_usd, "
            "COALESCE(SUM(CASE WHEN status LIKE 'failed%' THEN 1 ELSE 0 END),0) AS failures "
            "FROM ai_usage WHERE created_at >= ?",
            (start,),
        ).fetchone()
        return {
            "month": start[:7],
            "calls": int(row["calls"] or 0),
            "input_tokens": int(row["input_tokens"] or 0),
            "output_tokens": int(row["output_tokens"] or 0),
            "est_cost_usd": round(float(row["est_cost_usd"] or 0.0), 6),
            "failures": int(row["failures"] or 0),
        }
