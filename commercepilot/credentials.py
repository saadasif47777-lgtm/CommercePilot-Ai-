"""Encrypted integration credentials for hosts without persistent filesystems."""
import json

from cryptography.fernet import Fernet, InvalidToken

from . import config
from .database import Database


class CredentialError(Exception):
    """Configuration error safe to show to the workspace operator."""


def _cipher():
    try:
        return Fernet(config.CREDENTIAL_ENCRYPTION_KEY.encode())
    except (ValueError, TypeError) as exc:
        raise CredentialError("Set CREDENTIAL_ENCRYPTION_KEY on the server before saving integrations. Generate it with Fernet.generate_key().") from exc


def _db():
    db = Database(config.DATABASE_URL)
    db.execute("CREATE TABLE IF NOT EXISTS integration_credentials (provider TEXT PRIMARY KEY, ciphertext TEXT NOT NULL)")
    return db


def read(provider):
    row = _db().execute("SELECT ciphertext FROM integration_credentials WHERE provider=?", (provider,)).fetchone()
    if not row:
        return {}
    try:
        return json.loads(_cipher().decrypt(row["ciphertext"].encode()))
    except InvalidToken as exc:
        raise CredentialError("Saved credentials cannot be decrypted. Restore the original encryption key or reconnect this integration.") from exc


def save(provider, data):
    ciphertext = _cipher().encrypt(json.dumps(data).encode()).decode()
    _db().execute("INSERT INTO integration_credentials(provider,ciphertext) VALUES (?,?) ON CONFLICT(provider) DO UPDATE SET ciphertext=excluded.ciphertext", (provider, ciphertext))
