from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Action = Literal["research", "store", "campaign", "analyze", "report"]
Route = Literal["/business", "/products", "/store", "/marketing", "/analytics", "/settings", "/support", "/history"]


class Profile(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    budget: float | None = Field(None, ge=0, le=1e12, allow_inf_nan=False)
    budget_scope: Literal["business", "advertising"] | None = None
    currency: str | None = Field(None, pattern=r"^[A-Z]{3}$")
    niche: str | None = Field(None, max_length=200)
    location: str | None = Field(None, max_length=150)
    audience: str | None = Field(None, max_length=400)
    business_model: Literal["physical", "dropshipping", "digital", "service"] | None = None
    timeframe_days: int | None = Field(None, ge=1, le=365)
    fixed_costs: float | None = Field(None, ge=0, le=1e12, allow_inf_nan=False)
    selling_price: float | None = Field(None, ge=0, le=1e12, allow_inf_nan=False)
    product_cost: float | None = Field(None, ge=0, le=1e12, allow_inf_nan=False)
    other_costs_per_order: float | None = Field(None, ge=0, le=1e12, allow_inf_nan=False)
    assumed_cpc: float | None = Field(None, gt=0, le=1e9, allow_inf_nan=False)
    assumed_conversion_pct: float | None = Field(None, gt=0, le=100, allow_inf_nan=False)
    store_ready: bool | None = None
    tracking_ready: bool | None = None

    @field_validator("currency", mode="before")
    @classmethod
    def uppercase_currency(cls, value):
        return value.strip().upper() if isinstance(value, str) else value


class SessionRequest(BaseModel):
    project_id: str | None = Field(None, max_length=100)
    session_token: str | None = Field(None, min_length=30, max_length=100)


class ChatRequest(BaseModel):
    session_token: str = Field(min_length=30, max_length=100)
    message: str = Field(default="", max_length=2000)
    profile_updates: Profile | None = None
    confirmed_action: Action | None = None


class ConversationPlan(BaseModel):
    intent: Literal["guidance", "budget", "idea_review", "action", "general"] = "general"
    updates: Profile = Field(default_factory=Profile)
    evidence: dict[str, str] = Field(default_factory=dict, max_length=20)
    requested_action: Action | None = None


class Risk(BaseModel):
    factor: str = Field(min_length=1, max_length=100)
    explanation: str = Field(min_length=1, max_length=600)
    mitigation: str = Field(min_length=1, max_length=500)


class Step(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    explanation: str = Field(min_length=1, max_length=350)
    route: Route


class Advice(BaseModel):
    reply: str = Field(min_length=1, max_length=5000)
    strengths: list[str] = Field(default_factory=list, max_length=4)
    risks: list[Risk] = Field(default_factory=list, max_length=6)
    next_steps: list[Step] = Field(default_factory=list, max_length=4)
    questions: list[str] = Field(default_factory=list, max_length=3)
