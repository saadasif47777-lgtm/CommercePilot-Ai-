"""Business advisor, grounded profile extraction and cent-exact budget planning."""
from datetime import timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from commercepilot import ai, api, config, runtime
from commercepilot.advisor import service
from commercepilot.advisor.finance import calculate
from commercepilot.advisor.models import Advice, ConversationPlan, Profile
from commercepilot.advisor.store import AdvisorStore, digest, now
from commercepilot.storage import ProjectStore


@pytest.mark.parametrize("amount", [0, 0.01, 0.07, 1, 33.33, 9999.99])
@pytest.mark.parametrize("model", ["physical", "dropshipping", "digital", "service"])
def test_allocations_exactly_match_budget(amount, model):
    result = calculate(Profile(budget=amount, currency="PKR", budget_scope="business", business_model=model))
    assert sum(Decimal(str(row["amount"])) for row in result["allocations"]) == Decimal(str(amount))
    assert all(row["amount"] >= 0 for row in result["allocations"])
    assert result["scenario"] is None


def test_unknown_currency_scope_and_costs_stay_unknown():
    result = calculate(Profile(budget=5000))
    assert result["status"] == "needs_details" and result["allocations"] == []
    result = calculate(Profile(budget=5000, currency="PKR", budget_scope="business", selling_price=100, product_cost=40))
    assert result["unit_economics"]["gross_profit_per_order"] == 60
    assert result["unit_economics"]["contribution_per_order"] is None
    assert result["unit_economics"]["break_even_cpa"] is None
    assert result["scenario"] is None


def test_explicit_economics_and_scenario_are_calculated():
    result = calculate(Profile(budget=1000, currency="USD", budget_scope="advertising", timeframe_days=10,
                               fixed_costs=0, selling_price=50, product_cost=20, other_costs_per_order=10,
                               assumed_cpc=5, assumed_conversion_pct=10))
    assert result["ad_test_budget"] == 550 and result["daily_ad_test_average"] == 55
    assert result["unit_economics"]["contribution_per_order"] == 20
    assert result["unit_economics"]["break_even_cpa"] == 20
    assert result["unit_economics"]["break_even_roas"] == 2.5
    assert result["scenario"]["clicks"] == 110 and result["scenario"]["expected_orders"] == 11
    assert result["scenario"]["revenue"] == 550 and result["scenario"]["contribution_after_ads"] == -330
    assert "not a forecast" in result["scenario"]["label"]


@pytest.mark.parametrize("extra", [{"selling_price": 50, "product_cost": 50}, {"selling_price": 50, "product_cost": 20, "other_costs_per_order": 35}, {"selling_price": 0, "product_cost": 0}, {"store_ready": False}, {"tracking_ready": False}])
def test_bad_margins_or_readiness_hold_paid_ads(extra):
    result = calculate(Profile(budget=5000, currency="PKR", budget_scope="business", **extra))
    assert result["status"] == "hold_paid_ads" and result["ad_test_budget"] == 0
    assert sum(row["amount"] for row in result["allocations"]) == 5000


def test_committed_costs_and_overcommitment():
    result = calculate(Profile(budget=1000, fixed_costs=200, currency="USD", budget_scope="business", selling_price=50, product_cost=20, other_costs_per_order=10))
    assert result["allocations"][0]["amount"] == 200
    assert result["unit_economics"]["fixed_cost_break_even_orders"] == 10
    assert sum(row["amount"] for row in result["allocations"]) == 1000
    result = calculate(Profile(budget=1000, fixed_costs=1200, currency="USD", budget_scope="business"))
    assert result["status"] == "overcommitted" and result["shortfall"] == 200 and result["allocations"] == []


def test_model_extraction_requires_current_message_evidence_and_matching_amount():
    plan = ConversationPlan(updates=Profile(budget=50000, location="Lahore", currency="PKR"),
                            evidence={"budget": "50k", "location": "Lahore", "currency": "PKR"})
    assert service.evidenced_updates(plan, "I have PKR 50k in Lahore")["budget"] == 50000
    assert service.evidenced_updates(plan, "What should I do next?") == {}
    plan = ConversationPlan(updates=Profile(budget=99999), evidence={"budget": "50k"})
    assert service.evidenced_updates(plan, "50k") == {}
    plan = ConversationPlan(updates=Profile(budget=100, currency="USD"), evidence={"budget": "$100", "currency": "$"})
    assert service.evidenced_updates(plan, "$100") == {"budget": 100, "currency": None}


@pytest.fixture
def advisor(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "APP_MODE", "production")
    monkeypatch.setattr(config, "LLM_API_KEY", "test-key-not-real")
    monkeypatch.setattr(config, "ADVISOR_DAILY_MESSAGES", 200)
    runtime.set_store(ProjectStore(tmp_path / "advisor.sqlite3"))
    state = {"plan": ConversationPlan(intent="guidance"), "calls": [], "answer": Advice(reply="Welcome! Start with your business idea, then use Business information.", next_steps=[{"title": "Set up your business", "explanation": "Save your niche and market.", "route": "/business"}])}
    def complete(**kwargs):
        state["calls"].append(kwargs)
        return state["plan"] if kwargs["prompt_name"] == "advisor_plan" else state["answer"]
    monkeypatch.setattr(ai, "complete_json", complete)
    monkeypatch.setattr(service, "_connections", lambda: {"meta": {"status": "not_connected"}})
    state["client"] = TestClient(api.app)
    state["store"] = runtime.get_advisor_store()
    yield state
    runtime.reset_store()


def new_session(advisor, project_id=None):
    response = advisor["client"].post("/api/advisor/session", json={"project_id": project_id})
    assert response.status_code == 200
    return response.json()


def ask(advisor, session, message="Hello", **extra):
    return advisor["client"].post("/api/advisor/chat", json={"session_token": session["session_token"], "message": message, **extra})


def create_project(advisor):
    return advisor["client"].post("/api/projects", json={"brief": {"business_name": "Client", "niche": "Lighting", "budget": 10000, "currency": "PKR"}}).json()["id"]


def test_first_time_visitor_gets_guidance_without_project(advisor):
    session = new_session(advisor)
    assert session["messages"] == [] and "/marketing" in [guide["route"] for guide in session["guides"]]
    assert session["profile"]["budget"] is None
    response = ask(advisor, session, "How does this platform work?")
    assert response.status_code == 200
    assert "Welcome" in response.json()["messages"][-1]["text"]
    assert response.json()["messages"][-1]["response"]["next_steps"][0]["route"] == "/business"
    assert all(call["timeout"] == 10 and call["retries"] == 0 for call in advisor["calls"])


def test_memory_profile_edits_resume_and_no_unintended_project_writes(advisor):
    project_id = create_project(advisor)
    session = new_session(advisor, project_id)
    assert session["profile"]["budget_scope"] == "advertising"
    response = ask(advisor, session, "Review my idea", profile_updates={"budget": 5000, "budget_scope": "business", "location": "Lahore", "currency": "PKR"})
    assert response.status_code == 200
    assert response.json()["profile"]["budget"] == 5000
    assert runtime.get_store().get(project_id)["brief"]["budget"] == 10000
    response = ask(advisor, session, "What about returns?")
    assert response.status_code == 200 and "Lahore" in advisor["calls"][-1]["user"]
    assert "Review my idea" in advisor["calls"][-1]["user"]
    resumed = advisor["client"].post("/api/advisor/session", json={"project_id": project_id, "session_token": session["session_token"]}).json()
    assert resumed["profile"]["budget"] == 5000 and len(resumed["messages"]) == 4
    assert AdvisorStore(advisor["store"].db).read(session["session_token"])[1]["overrides"]["location"] == "Lahore"


def test_currency_change_invalidates_old_amounts(advisor):
    session = new_session(advisor, create_project(advisor))
    result = ask(advisor, session, "Use another currency", profile_updates={"currency": "USD"}).json()
    assert result["profile"]["budget"] is None and result["budget"]["status"] == "needs_details"


def test_idea_review_balanced_and_uses_fixed_platform_capabilities(advisor):
    advisor["plan"] = ConversationPlan(intent="idea_review")
    advisor["answer"] = Advice(reply="A focused niche could work, but validate demand before advertising.", strengths=["A clearly defined audience could help you test a focused offer."],
                               risks=[{"factor": "Returns and delivery", "explanation": "Returns can remove your margin.", "mitigation": "Get courier quotes and include a returns allowance."}],
                               next_steps=[{"title": "Review your campaign plan", "explanation": "Prepare a small draft after verifying costs.", "route": "/marketing"}])
    result = ask(advisor, new_session(advisor), "Should I run ads for my idea?").json()
    response = result["messages"][-1]["response"]
    assert response["strengths"] and response["risks"][0]["mitigation"] and result["pending_action"] is None
    assert "read-only reporting" in advisor["calls"][-1]["user"]


def test_actions_require_bound_confirmation_and_cannot_replay(advisor, monkeypatch):
    project_id = create_project(advisor)
    session = new_session(advisor, project_id)
    calls = []
    monkeypatch.setattr(service, "execute_command", lambda *args, **kw: calls.append(kw) or {"reply": "Saved report"})
    advisor["plan"] = ConversationPlan(intent="action", requested_action="report")
    offered = ask(advisor, session, "Show my report").json()
    assert offered["pending_action"]["action"] == "report" and calls == []
    assert ask(advisor, session, "", confirmed_action="campaign").status_code == 409
    completed = ask(advisor, session, "", confirmed_action="report")
    assert completed.status_code == 200 and calls == [{"intent_override": "report"}]
    assert completed.json()["pending_action"] is None
    assert ask(advisor, session, "", confirmed_action="report").status_code == 409


def test_campaign_confirmation_uses_calculated_test_share(advisor, monkeypatch):
    from commercepilot.schemas import CampaignPlan

    project_id = create_project(advisor)
    response = advisor["client"].post(f"/api/projects/{project_id}/products/manual", json={"title": "Lamp", "observed_price": 1000, "observed_cost": 400, "currency": "PKR"})
    assert response.status_code == 200
    session = new_session(advisor, project_id)
    ask(advisor, session, "Use my budget", profile_updates={"budget": 5000, "budget_scope": "business", "other_costs_per_order": 100})
    advisor["plan"] = ConversationPlan(intent="action", requested_action="campaign")
    ask(advisor, session, "Draft my campaign")
    calls = []
    def campaign(store, project, request):
        calls.append(request)
        return CampaignPlan(objective="sales", budget=request.budget, duration_days=request.duration_days, currency="PKR")
    monkeypatch.setattr(service.wf, "step_generate_campaign", campaign)
    result = ask(advisor, session, "", confirmed_action="campaign")
    assert result.status_code == 200 and calls[0].budget == 750 and calls[0].duration_days == 7
    assert "No ad was published" in result.json()["messages"][-1]["text"]


def test_expired_and_cross_project_sessions_do_not_leak(advisor):
    session = new_session(advisor)
    other = new_session(advisor)
    ask(advisor, session, "My private business idea")
    assert advisor["store"].read(other["session_token"])[1]["messages"] == []
    project_id = create_project(advisor)
    assert advisor["client"].post("/api/advisor/session", json={"project_id": project_id, "session_token": session["session_token"]}).status_code == 409
    advisor["store"].db.execute("UPDATE advisor_sessions SET expires=? WHERE id_hash=?", ((now() - timedelta(seconds=1)).isoformat(), digest(session["session_token"])))
    assert ask(advisor, session).status_code == 410


def test_limits_failures_release_reservations_and_origin_guard(advisor, monkeypatch):
    session = new_session(advisor)
    def failure(**kwargs):
        raise ai.AIRequestError("Provider unavailable")
    monkeypatch.setattr(ai, "complete_json", failure)
    assert ask(advisor, session).status_code == 503
    assert advisor["store"].read(session["session_token"])[0]["busy_until"] == ""
    monkeypatch.setattr(config, "ADVISOR_DAILY_MESSAGES", 1)
    assert ask(advisor, session).status_code == 429
    assert advisor["client"].post("/api/advisor/session", json={}, headers={"origin": "https://untrusted-store.example"}).status_code == 403


def test_concurrent_turn_and_stale_action_rejected(advisor):
    session = new_session(advisor)
    advisor["store"].reserve(session["session_token"])
    with pytest.raises(HTTPException) as error:
        advisor["store"].reserve(session["session_token"])
    assert error.value.status_code == 409
    advisor["store"].finish(session["session_token"])
    project_id = create_project(advisor)
    session = new_session(advisor, project_id)
    advisor["plan"] = ConversationPlan(intent="action", requested_action="report")
    ask(advisor, session, "Build report")
    project = runtime.get_store().get(project_id)
    project["name"] = "Changed"
    runtime.get_store().save(project)
    assert ask(advisor, session, "", confirmed_action="report").status_code == 409
