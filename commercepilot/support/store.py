"""Durable knowledge snapshots, short-lived sessions and distributed request limits."""
from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

from .models import Settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS support_state (id TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS support_documents (
    generation TEXT NOT NULL, id TEXT NOT NULL, kind TEXT NOT NULL,
    title TEXT NOT NULL, body TEXT NOT NULL, url TEXT NOT NULL,
    search_text TEXT NOT NULL, price REAL NOT NULL, currency TEXT NOT NULL,
    data TEXT NOT NULL, PRIMARY KEY(generation,id)
);
CREATE INDEX IF NOT EXISTS idx_support_docs ON support_documents(generation,kind,price);
CREATE TABLE IF NOT EXISTS support_sessions (
    id_hash TEXT PRIMARY KEY, widget_id TEXT NOT NULL, generation TEXT NOT NULL,
    expires TEXT NOT NULL, busy_until TEXT NOT NULL, data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS support_limits (
    id TEXT PRIMARY KEY, used INTEGER NOT NULL, expires TEXT NOT NULL
);
"""


def now():
    return datetime.now(timezone.utc)


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


class SupportStore:
    def __init__(self, db):
        self.db = db
        db.executescript(SCHEMA)
        db.execute("INSERT INTO support_state(id,data) VALUES ('workspace',?) ON CONFLICT(id) DO NOTHING",
                   (json.dumps({"widget_id": secrets.token_hex(16), "settings": Settings().model_dump()}),))

    def state(self):
        return json.loads(self.db.execute("SELECT data FROM support_state WHERE id='workspace'").fetchone()["data"])

    def write_state(self, state):
        self.db.execute("UPDATE support_state SET data=? WHERE id='workspace'", (json.dumps(state),))

    def save_settings(self, settings):
        with self.db:
            self.db.lock_project("support-state")
            state = self.state()
            state["settings"] = settings.model_dump()
            self.write_state(state)
        return state

    def insert_documents(self, generation, docs):
        for doc in docs:
            self.db.execute("INSERT INTO support_documents(generation,id,kind,title,body,url,search_text,price,currency,data) "
                            "VALUES (?,?,?,?,?,?,?,?,?,?) ON CONFLICT(generation,id) DO UPDATE SET title=excluded.title,body=excluded.body,"
                            "url=excluded.url,search_text=excluded.search_text,price=excluded.price,currency=excluded.currency,data=excluded.data",
                            (generation, doc["id"], doc["kind"], doc["title"], doc["body"], doc["url"],
                             (doc["title"] + " " + doc["body"] + " " + doc.get("keywords", "")).casefold(),
                             float(doc.get("price") or 0), doc.get("currency", ""), json.dumps(doc)))

    def documents(self, generation, kind):
        rows = self.db.execute("SELECT data FROM support_documents WHERE generation=? AND kind=? ORDER BY id", (generation, kind)).fetchall()
        return [json.loads(row["data"]) for row in rows]

    def products(self, generation, plan):
        clauses, params = ["generation=?", "kind='product'"], [generation]
        if plan.terms:
            clauses.append("(" + " OR ".join("search_text LIKE ? ESCAPE '!'" for _ in plan.terms) + ")")
            params.extend("%" + term.casefold().replace("!", "!!").replace("%", "!%").replace("_", "!_") + "%" for term in plan.terms)
        if plan.min_price is not None:
            clauses.append("price>=?")
            params.append(plan.min_price)
        if plan.max_price is not None:
            clauses.append("price<=?")
            params.append(plan.max_price)
        if plan.currency:
            clauses.append("currency=?")
            params.append(plan.currency)
        order = "price DESC,id" if plan.sort == "price_desc" else "price ASC,id"
        if plan.sort == "relevance" and plan.terms:
            order = " + ".join("(CASE WHEN search_text LIKE ? ESCAPE '!' THEN 1 ELSE 0 END)" for _ in plan.terms) + " DESC,price ASC,id"
            params.extend("%" + term.casefold().replace("!", "!!").replace("%", "!%").replace("_", "!_") + "%" for term in plan.terms)
        rows = self.db.execute("SELECT data FROM support_documents WHERE " + " AND ".join(clauses) + " ORDER BY " + order + " LIMIT 6", params).fetchall()
        return [json.loads(row["data"]) for row in rows]

    def counts(self, generation):
        rows = self.db.execute("SELECT kind,COUNT(*) AS n FROM support_documents WHERE generation=? GROUP BY kind", (generation,)).fetchall()
        return {row["kind"]: row["n"] for row in rows}

    def limit(self, key, maximum, seconds):
        with self.db:
            self.db.lock_project("support-limit:" + key)
            self.db.execute("DELETE FROM support_limits WHERE expires<?", (now().isoformat(),))
            row = self.db.execute("SELECT used FROM support_limits WHERE id=?", (key,)).fetchone()
            if row and row["used"] >= maximum:
                raise HTTPException(429, "Chat limit reached. Please try later or contact the store.", headers={"Retry-After": str(seconds)})
            self.db.execute("INSERT INTO support_limits(id,used,expires) VALUES (?,1,?) "
                            "ON CONFLICT(id) DO UPDATE SET used=support_limits.used+1",
                            (key, (now() + timedelta(seconds=seconds)).isoformat()))

    def new_session(self, state):
        token = secrets.token_urlsafe(32)
        self.db.execute("DELETE FROM support_sessions WHERE expires<?", (now().isoformat(),))
        self.db.execute("INSERT INTO support_sessions(id_hash,widget_id,generation,expires,busy_until,data) VALUES (?,?,?,?,?,?)",
                        (digest(token), state["widget_id"], state["active"], (now() + timedelta(hours=24)).isoformat(), "", "[]"))
        return token

    def reserve_session(self, state, token):
        key = digest(token)
        with self.db:
            self.db.lock_project("support-session:" + key)
            row = self.db.execute("SELECT * FROM support_sessions WHERE id_hash=?", (key,)).fetchone()
            if not row or row["expires"] < now().isoformat() or row["widget_id"] != state["widget_id"] or row["generation"] != state["active"]:
                raise HTTPException(401, "Please start a new chat; this session has expired or the store was updated.")
            if row["busy_until"] > now().isoformat():
                raise HTTPException(409, "Your previous message is still being answered.")
            self.db.execute("UPDATE support_sessions SET busy_until=? WHERE id_hash=?", ((now() + timedelta(minutes=2)).isoformat(), key))
        return json.loads(row["data"])

    def finish_session(self, token, history=None):
        if history is None:
            self.db.execute("UPDATE support_sessions SET busy_until='' WHERE id_hash=?", (digest(token),))
        else:
            self.db.execute("UPDATE support_sessions SET busy_until='',data=? WHERE id_hash=?", (json.dumps(history[-8:]), digest(token)))
