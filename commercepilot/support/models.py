"""Bounded merchant, customer and model input contracts."""
from __future__ import annotations

import re
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def origin(value: str) -> str:
    if len(value) > 300 or any(char.isspace() for char in value.strip()):
        raise ValueError("Enter a valid store origin under 300 characters")
    parsed = urlsplit(value.strip().rstrip("/"))
    if not parsed.hostname or (parsed.port is not None and not 1 <= parsed.port <= 65535):
        raise ValueError("Enter a valid store host and port")
    local = parsed.hostname in {"localhost", "127.0.0.1"}
    if (parsed.scheme != "https" and not (local and parsed.scheme == "http")) or not parsed.netloc:
        raise ValueError("Use an HTTPS store origin, for example https://your-store.com")
    if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in {"", "/"}:
        raise ValueError("Enter an origin only, without a path, credentials or query")
    return f"{parsed.scheme}://{parsed.netloc.lower()}"


class FAQ(BaseModel):
    question: str = Field(min_length=3, max_length=200)
    answer: str = Field(min_length=3, max_length=2000)


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    enabled: bool = False
    assistant_name: str = Field(default="Shop assistant", min_length=2, max_length=60)
    welcome: str = Field(default="Hi! How can I help you find a product or answer a store question?", min_length=2, max_length=300)
    accent: str = Field(default="#174A38", pattern=r"^#[0-9a-fA-F]{6}$")
    support_email: str = Field(default="", max_length=200)
    allowed_origins: list[str] = Field(default_factory=list, max_length=10)
    faqs: list[FAQ] = Field(default_factory=list, max_length=20)

    @field_validator("support_email")
    @classmethod
    def email(cls, value):
        if value and not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", value):
            raise ValueError("Enter a valid customer support email")
        return value

    @field_validator("allowed_origins")
    @classmethod
    def origins(cls, values):
        return list(dict.fromkeys(origin(value) for value in values))


class HistoryTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=3000)


class PreviewRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    history: list[HistoryTurn] = Field(default_factory=list, max_length=8)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    session_token: str = Field(min_length=30, max_length=100)


class NextPage(BaseModel):
    sync_id: str = Field(pattern=r"^[a-f0-9]{32}$")


class QueryPlan(BaseModel):
    intent: Literal["products", "policies", "general", "handoff"]
    terms: list[str] = Field(default_factory=list, max_length=6)
    min_price: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    max_price: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    sort: Literal["relevance", "price_asc", "price_desc"] = "relevance"

    @field_validator("terms")
    @classmethod
    def short_terms(cls, values):
        return [value.strip()[:60] for value in values if value.strip()]

    @model_validator(mode="after")
    def prices(self):
        if self.min_price is not None and self.max_price is not None and self.min_price > self.max_price:
            raise ValueError("Minimum price exceeds maximum")
        return self


class GroundedAnswer(BaseModel):
    answer: str = Field(min_length=1, max_length=2500)
    product_ids: list[str] = Field(default_factory=list, max_length=4)
    source_ids: list[str] = Field(default_factory=list, max_length=6)
    needs_human: bool = False
