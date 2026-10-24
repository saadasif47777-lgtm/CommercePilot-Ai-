"""Per-browser business conversations, expiring tokens and replica-safe quotas."""
import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

from .. import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS advisor_sessions (
    id_hash TEXT PRIMARY KEY, project_id TEXT NOT NULL, expires TEXT NOT NULL,
    busy_until TEXT NOT NULL, window_start TEXT NOT NULL, messages INTEGER NOT NULL, data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS advisor_limits (
    day TEXT PRIMARY KEY, messages INTEGER NOT NULL, sessions INTEGER NOT NULL
);
"""


def now():
    return datetime.now(timezone.utc)


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


class AdvisorStore:
    def __init__(self, db):
        self.db = db
        db.executescript(SCHEMA)

    def _daily(self, column, maximum):
        day = now().date().isoformat()
        self.db.lock_project("advisor-day:" + day)
        self.db.execute("INSERT INTO advisor_limits(day,messages,sessions) VALUES (?,0,0) ON CONFLICT(day) DO NOTHING", (day,))
        row = self.db.execute("SELECT messages,sessions FROM advisor_limits WHERE day=?", (day,)).fetchone()
        if row[column] >= maximum:
            raise HTTPException(429, "The assistant's daily limit has been reached. Please try again tomorrow.", headers={"Retry-After": "3600"})
        self.db.execute("UPDATE advisor_limits SET " + column + "=" + column + "+1 WHERE day=?", (day,))

    def create(self, project_id=None):
        token = secrets.token_urlsafe(32)
        data = {"overrides": {}, "messages": [], "pending": None}
        with self.db:
            self._daily("sessions", 300)
            self.db.execute("DELETE FROM advisor_sessions WHERE expires<?", (now().isoformat(),))
            self.db.execute("DELETE FROM advisor_limits WHERE day<?", ((now() - timedelta(days=2)).date().isoformat(),))
            self.db.execute("INSERT INTO advisor_sessions(id_hash,project_id,expires,busy_until,window_start,messages,data) VALUES (?,?,?,?,?,0,?)",
                            (digest(token), project_id or "", (now() + timedelta(hours=24)).isoformat(), "", now().isoformat(), json.dumps(data)))
        return token

    def read(self, token, project_id=None, check_project=False):
        row = self.db.execute("SELECT * FROM advisor_sessions WHERE id_hash=?", (digest(token),)).fetchone()
        if not row or row["expires"] < now().isoformat():
            raise HTTPException(410, "This conversation expired. Start a new conversation to continue.")
        if check_project and row["project_id"] != (project_id or ""):
            raise HTTPException(409, "This conversation belongs to a different workspace. Start a new conversation here.")
        return row, json.loads(row["data"])

    def reserve(self, token):
        with self.db:
            self.db.lock_project("advisor-session:" + digest(token))
            row, data = self.read(token)
            if row["busy_until"] > now().isoformat():
                raise HTTPException(409, "Your previous message is still being answered. Please wait.")
            reset = row["window_start"] < (now() - timedelta(hours=1)).isoformat()
            used = 0 if reset else row["messages"]
            if used >= 30:
                raise HTTPException(429, "This conversation reached its hourly limit. Please try later.", headers={"Retry-After": "3600"})
            self._daily("messages", config.ADVISOR_DAILY_MESSAGES)
            self.db.execute("UPDATE advisor_sessions SET busy_until=?,window_start=?,messages=? WHERE id_hash=?",
                            ((now() + timedelta(minutes=3)).isoformat(), now().isoformat() if reset else row["window_start"], used + 1, digest(token)))
        return row, data

    def finish(self, token, data=None):
        if data is None:
            self.db.execute("UPDATE advisor_sessions SET busy_until='' WHERE id_hash=?", (digest(token),))
        else:
            data["messages"] = data["messages"][-12:]
            self.db.execute("UPDATE advisor_sessions SET busy_until='',data=? WHERE id_hash=?", (json.dumps(data, allow_nan=False), digest(token)))
