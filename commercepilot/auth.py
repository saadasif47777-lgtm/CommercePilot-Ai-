"""Storage namespace context retained for existing data and storefront widgets.

Merchant login is deferred. Normal requests use the original shared workspace;
existing namespaced tables are preserved without migration or deletion.
"""
from contextvars import ContextVar

workspace = ContextVar("workspace", default="")
