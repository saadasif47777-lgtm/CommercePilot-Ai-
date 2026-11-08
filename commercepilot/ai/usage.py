"""AI usage log and monthly spend accounting.

SQLite today (same database file as projects); moves to Postgres with the rest
of the data layer in Phase 3. Only the prompt NAME and token counts are stored —
never prompt contents — so the log cannot leak user data.
"""
from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from ..database import Database

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
CREATE TABLE IF NOT EXISTS ai_module_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL,
    prompt TEXT NOT NULL, provider TEXT NOT NULL, model TEXT NOT NULL,
    status TEXT NOT NULL, latency_ms INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS ai_reservations (
    id TEXT PRIMARY KEY, created_at TEXT NOT NULL, amount REAL NOT NULL
);
"""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class UsageLog:
    def __init__(self, path: Path | str, namespace=None):
        self.path = str(path)
        self._database = Database(path, namespace=namespace)
        self._init_lock = threading.Lock()
        self._initialized = False
        self._init_db()

    def _conn(self):
        return self._database

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
        reservation: Optional[str] = None,
    ) -> None:
        conn = self._conn()
        with conn:
            conn.lock_project("ai-month-budget")
            if reservation:
                conn.execute("DELETE FROM ai_reservations WHERE id=?", (reservation,))
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

    def reserve(self, amount, cap):
        """Atomically admit estimated spend, including other in-flight calls.

        Ambiguous transport outcomes retain their reservation for this month.
        Provider-side controls remain necessary for a hard billing limit.
        """
        start = _utcnow()[:7] + "-01"
        token = uuid.uuid4().hex
        with self._conn() as conn:
            conn.lock_project("ai-month-budget")
            conn.execute("DELETE FROM ai_reservations WHERE created_at<?", (start,))
            pending = conn.execute("SELECT COALESCE(SUM(amount),0) AS cost FROM ai_reservations").fetchone()["cost"]
            used = conn.execute("SELECT COALESCE(SUM(est_cost_usd),0) AS cost FROM ai_usage WHERE created_at>=?", (start,)).fetchone()["cost"]
            if cap > 0 and float(used) + float(pending) + amount > cap:
                return None
            conn.execute("INSERT INTO ai_reservations(id,created_at,amount) VALUES (?,?,?)", (token, _utcnow(), amount))
        return token

    def reserved_cost(self):
        row = self._conn().execute("SELECT COALESCE(SUM(amount),0) AS cost FROM ai_reservations WHERE created_at>=?", (_utcnow()[:7] + "-01",)).fetchone()
        return float(row["cost"])

    def record_module(self, prompt, provider, model, status, latency):
        self._conn().execute("INSERT INTO ai_module_events(created_at,prompt,provider,model,status,latency_ms) VALUES (?,?,?,?,?,?)", (_utcnow(), prompt, provider, model, status, latency))

    def module_status(self, prompt):
        rows = self._conn().execute("SELECT created_at,provider,model,status,latency_ms FROM ai_module_events WHERE prompt=? ORDER BY id DESC LIMIT 100", (prompt,)).fetchall()
        return {"last_success": next((row for row in rows if row["status"] == "ok"), None),
                "last_failure": next((row for row in rows if row["status"].startswith("failed")), None)}

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
