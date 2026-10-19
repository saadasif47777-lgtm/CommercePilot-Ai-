"""Pydantic schemas for every structured model output.

Anything rendered as data by the UI must validate against one of these. A
model response that fails validation is repaired once (the validation error is
sent back) and otherwise rejected — the caller then continues without AI
output instead of showing malformed or invented fields.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from .guard import sanitize_text


class _Clean(BaseModel):
    """Shared sanitisation: strip control chars and collapse whitespace."""

    @field_validator("*", mode="before")
    @classmethod
    def _clean_strings(cls, value):  # noqa: ANN001, ANN206
        if isinstance(value, str):
            return sanitize_text(value, limit=1200)
        return value


class StoreCopy(_Clean):
    """Storefront copy. Every field is optional: missing keys keep templates."""

    headline: Optional[str] = Field(None, max_length=160)
    subheadline: Optional[str] = Field(None, max_length=320)
    tagline: Optional[str] = Field(None, max_length=160)
    cta: Optional[str] = Field(None, max_length=60)
    header_cta: Optional[str] = Field(None, max_length=60)
    badge: Optional[str] = Field(None, max_length=80)
    featured_title: Optional[str] = Field(None, max_length=160)
    detail_title: Optional[str] = Field(None, max_length=160)
    detail_bullets: Optional[list[str]] = Field(None, max_length=5)
    benefits_title: Optional[str] = Field(None, max_length=160)
    faq_intro: Optional[str] = Field(None, max_length=400)

    @field_validator("detail_bullets")
    @classmethod
    def _bullets(cls, value):  # noqa: ANN001, ANN206
        if value is None:
            return None
        return [sanitize_text(b, limit=120) for b in value if sanitize_text(b, limit=120)][:5]


class CampaignCreatives(_Clean):
    """Ad copy. No statistics or performance claims are accepted."""

    headlines: Optional[list[str]] = Field(None, max_length=5)
    primary_texts: Optional[list[str]] = Field(None, max_length=5)

    @field_validator("headlines", "primary_texts")
    @classmethod
    def _lists(cls, value):  # noqa: ANN001, ANN206
        if value is None:
            return None
        cleaned = [sanitize_text(v, limit=220) for v in value]
        return [v for v in cleaned if v][:5]


class AssistantIntent(_Clean):
    intent: Literal[
        "research",
        "select",
        "store",
        "store_edit",
        "campaign",
        "analyze",
        "report",
        "workflow",
        "unknown",
    ]
