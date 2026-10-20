"""Cross-feature invariants for Phase 4, using disposable in-memory data."""
from datetime import date, timedelta
from decimal import Decimal as D

import pytest

from app.models.entities import Category, Goal, Transaction, User
from app.models.enums import CategoryType, GoalType, TransactionType, RiskTolerance
from app.services import financial_tools
from app.services.goal_analysis_service import analyze_goal
from app.services.investment_category_service import score_category_relevance
from app.services.planning_context import load_planning_context
from app.services.insights_service import build_financial_insights


def goal(db, user, *, months=24, monthly="0", target="24000", current="0", emergency=False):
    item = Goal(user_id=user.id, name=f"Goal {months}", goal_type=GoalType.EMERGENCY_FUND if emergency else GoalType.OTHER,
                target_amount=D(target), current_amount=D(current), monthly_contribution=D(monthly),
                target_date=date.today() + timedelta(days=months * 30), priority=2)
    db.add(item)
    db.commit()
    return item


def transaction(db, user, amount, kind=TransactionType.EXPENSE, *, name="Rent", essential=True, when=None):
    category = None
    if kind == TransactionType.EXPENSE:
        category = Category(name=name, type=CategoryType.EXPENSE, is_essential=essential)
        db.add(category)
        db.flush()
    db.add(Transaction(user_id=user.id, date=when or date.today(), amount=D(amount),
                       transaction_type=kind, description="Verification", merchant="Verification",
                       category_id=category.id if category else None))
    db.commit()
    return category


@pytest.mark.parametrize("income", ["0", "5000.05", "50000", "100000"])
@pytest.mark.parametrize("saved", ["0", "10000", "90000"])
@pytest.mark.parametrize("scheduled", ["0", "20000", "150000"])
def test_funding_ledger_never_exceeds_cash_flow(client, db_session, user, income, saved, scheduled):
    user.financial_profile.monthly_income = D(income)
    db_session.commit()
    transaction(db_session, user, "5000.03")
    if D(saved):
        transaction(db_session, user, saved, TransactionType.SAVINGS)
    goal(db_session, user, monthly=scheduled, target="10000000")
    response = client.get(f"/api/investment/plan/{user.id}")
    assert response.status_code == 200
    plan = response.json()
    surplus = D(income) - D("5000.03") - D("5000")
    assert D(plan["monthly_surplus"]) == surplus
    assert D(plan["actual_monthly_savings"]) == D(saved)
    assert D(plan["monthly_expenses"]) == D("5000.03")
    assert D(plan["monthly_debt_payment"]) == D("5000")
    assert sum(D(line["amount"]) for line in plan["funding_ledger"]) == D(plan["allocation_total"])
    assert D(plan["allocation_total"]) <= max(D(0), surplus)
    assert sum(D(line["amount"]) for line in plan["allocations"]) <= D(plan["cash_after_existing_commitments"])
    assert D(plan["funded_existing_goal_contributions"]) <= min(max(D(0), surplus), D(scheduled))
    assert all(D(line["amount"]) >= 0 for line in plan["funding_ledger"])
    monthly = client.get(f"/api/financial-plan/monthly/{user.id}")
    assert monthly.status_code == 200
    assert monthly.json()["allocations"] == plan["funding_ledger"]


def test_competing_goals_share_capacity_and_comparison_matches(client, db_session, user):
    user.financial_profile.monthly_income = D("15000")
    db_session.commit()
    first = goal(db_session, user, months=1, monthly="10000", target="10000")
    second = goal(db_session, user, months=2, monthly="10000", target="20000")
    plan = client.get(f"/api/investment/plan/{user.id}").json()
    analyses = {item["goal_id"]: item for item in plan["goal_analysis"]}
    assert D(analyses[first.id]["funded_monthly_contribution"]) == D("10000")
    assert D(analyses[second.id]["funded_monthly_contribution"]) == 0
    assert analyses[second.id]["funding_status"] != "ON_TRACK"
    for item in (first, second):
        comparison = client.get(f"/api/investment/compare/{user.id}", params={"goal_id": item.id}).json()
        analysis = client.get(f"/api/goals/{item.id}/analysis", params={"user_id": user.id}).json()
        assert comparison["goal"] == analysis == analyses[item.id]


def test_medium_and_long_term_goals_receive_attributed_funding(client, db_session, user):
    medium = goal(db_session, user, months=48)
    long = goal(db_session, user, months=120)
    plan = client.get(f"/api/investment/plan/{user.id}").json()
    allocations = {item["related_goal_id"]: item for item in plan["allocations"] if item["related_goal_id"]}
    assert allocations[medium.id]["reason_code"] == "MEDIUM_TERM_GOAL"
    assert allocations[long.id]["reason_code"] == "LONG_TERM_GOAL"
    assert all(item["funding_status"] == "ON_TRACK" for item in plan["goal_analysis"])


def test_undated_goal_does_not_claim_dated_feasibility(db_session, user):
    item = goal(db_session, user, monthly="5000")
    item.target_date = None
    db_session.commit()
    result = analyze_goal(item, date.today(), D("5000"))
    assert result.funding_status == "NEEDS_TARGET_DATE"
    assert result.required_monthly_contribution == 0


def test_emergency_topup_is_separate_and_reflected_in_goal(client, db_session, user):
    transaction(db_session, user, "10000")
    item = goal(db_session, user, months=6, target="60000", emergency=True)
    plan = client.get(f"/api/investment/plan/{user.id}").json()
    analysis = next(g for g in plan["goal_analysis"] if g["goal_id"] == item.id)
    assert D(plan["emergency_fund_contribution"]) > 0
    assert plan["goal_contributions"] == "0.00"
    assert analysis["funded_monthly_contribution"] == plan["emergency_fund_contribution"]


@pytest.mark.parametrize("risk", list(RiskTolerance))
@pytest.mark.parametrize("months", [6, 24, 48, 120])
def test_category_relevance_is_bounded_deterministic_and_explained(db_session, user, risk, months):
    analysis = analyze_goal(goal(db_session, user, months=months), date.today(), D("60000"))
    categories = score_category_relevance(analysis, risk, D("100"))
    assert categories == score_category_relevance(analysis, risk, D("100"))
    assert all(0 <= c.relevance_score <= 100 and c.relevance_reason for c in categories)
    assert [c.relevance_score for c in categories] == sorted((c.relevance_score for c in categories), reverse=True)
    by_name = {c.name: c for c in categories}
    if months <= 24:
        assert by_name["Recurring Deposit (RD)"].relevance_score > by_name["Mutual Fund SIP"].relevance_score
        assert by_name["Fixed Deposit (FD)"].relevance_score > by_name["Index-oriented SIP category"].relevance_score
    if months == 120 and risk == RiskTolerance.HIGH:
        assert by_name["Index-oriented SIP category"].relevance_score > by_name["Fixed Deposit (FD)"].relevance_score


@pytest.mark.parametrize("income,savings,expenses,debt", [
    ("0", "0", "1", "0"), ("65000", "13000", "29001", "5000"),
    ("12345.67", "2456.78", "6789.12", "1234.56"), ("100000", "50000", "1000", "0"),
])
def test_health_components_reconcile_and_match_dashboard(client, db_session, user, income, savings, expenses, debt):
    user.financial_profile.monthly_income = D(income)
    user.financial_profile.monthly_debt_payment = D(debt)
    db_session.commit()
    transaction(db_session, user, expenses)
    if D(savings):
        transaction(db_session, user, savings, TransactionType.SAVINGS)
    health = client.get(f"/api/financial-health/{user.id}").json()
    assert sum(item["points"] for item in health["components"]) == health["score"]
    assert all(0 <= item["points"] <= item["maximum_points"] for item in health["components"])
    dashboard = client.get(f"/api/dashboard/{user.id}").json()
    assert health["score"] == dashboard["financial_health_score"]


def purchase(client, user, price, **extra):
    return client.post("/api/affordability/analyze", json={"user_id": user.id, "item_name": "Device",
        "price": price, "purchase_date": date.today().isoformat(), "payment_method": "CASH", **extra})


def test_wait_three_and_six_months_are_evaluated_against_capacity(client, user):
    result = purchase(client, user, "125000").json()
    alternatives = {item["name"]: item for item in result["alternative_scenarios"]}
    three, six = alternatives["Wait 3 months"], alternatives["Wait 6 months"]
    assert D(three["required_monthly_saving"]) == D("20000")
    assert D(six["required_monthly_saving"]) == D("10000")
    assert three["monthly_saving_shortfall"] == six["monthly_saving_shortfall"] == "0.00"
    assert three["projected_emergency_fund"] == six["projected_emergency_fund"] == "55000.00"
    assert three["affordability_score"] > 0 and six["affordability_score"] > 0
    too_large = purchase(client, user, "10000000").json()["alternative_scenarios"][1]
    assert too_large["status"] == "HIGH_RISK"
    assert D(too_large["monthly_saving_shortfall"]) > 0


def test_wait_alternatives_preserve_buffers_in_controlled_month(client, db_session, user):
    user.financial_profile.current_savings = D("245000")
    user.financial_profile.emergency_savings = D("180000")
    db_session.commit()
    transaction(db_session, user, "30000")
    transaction(db_session, user, "5000", name="Dining", essential=False)
    transaction(db_session, user, "4000", TransactionType.SAVINGS)
    result = purchase(client, user, "125000").json()
    three, six = result["alternative_scenarios"][1:3]
    assert three["available_monthly_saving"] == six["available_monthly_saving"] == "15800.00"
    assert three["required_monthly_saving"] == "20000.00"
    assert three["monthly_saving_shortfall"] == "4200.00"
    assert three["status"] == "HIGH_RISK"
    assert six["required_monthly_saving"] == "10000.00"
    assert six["monthly_saving_shortfall"] == "0.00"
    assert six["projected_emergency_fund"] == "180000.00"
    assert six["affordability_score"] == 89


def test_purchase_protects_goal_capital_and_emi_priorities(client, db_session, user):
    goal(db_session, user, current="60000", target="120000", monthly="5000")
    result = purchase(client, user, "80000").json()
    assert result["upfront_funding_shortfall"] == "20000.00"
    assert result["affordability_status"] == "HIGH_RISK"
    assert any("protected" in warning for warning in result["warnings"])
    transaction(db_session, user, "40000")
    emi = purchase(client, user, "120000", payment_method="EMI", down_payment="0", monthly_emi="10000", tenure_months=12).json()
    assert emi["affordability_status"] == "HIGH_RISK"
    assert any("displace" in warning for warning in emi["warnings"])


def test_explicit_food_category_and_savings_overcommit_warn_without_persistence(client, db_session, user):
    groceries = transaction(db_session, user, "7000", name="Groceries")
    response = client.post(f"/api/financial-plan/what-if/{user.id}", json={
        "scenario_type": "FOOD_SPENDING_REDUCTION", "amount": "2000", "category_ids": [groceries.id]})
    assert response.status_code == 200
    result = response.json()
    assert D(result["current"]["monthly_expenses"]) - D(result["projected"]["monthly_expenses"]) == D("2000")
    assert client.get(f"/api/investment/plan/{user.id}").json()["monthly_expenses"] == "7000.00"
    invalid = client.post(f"/api/financial-plan/what-if/{user.id}", json={
        "scenario_type": "FOOD_SPENDING_REDUCTION", "amount": "2000", "category_ids": [99999]})
    assert invalid.status_code == 422
    savings = client.post(f"/api/financial-plan/what-if/{user.id}", json={
        "scenario_type": "SAVINGS_INCREASE", "amount": "100000"}).json()
    assert any("exceed" in warning for warning in savings["warnings"])


def test_insights_use_matched_days_and_exclude_future_rows(db_session, user):
    # Fixed as-of date keeps the comparison independent of the test run date.
    transaction(db_session, user, "1000", name="Food trend", when=date(2026, 9, 3))
    transaction(db_session, user, "9000", name="Late trend", when=date(2026, 10, 25))
    context = load_planning_context(db_session, user.id, date(2026, 10, 10))
    result = build_financial_insights(db_session, context)
    assert "1–10" in result.coverage_note
    assert "2026-09" in result.coverage_note
    assert not any(item.reason_code == "CATEGORY_SPENDING_INCREASED" for item in result.insights)
    assert result == build_financial_insights(db_session, context)


def test_structured_service_facade_and_user_scoping(client, db_session, user):
    item = goal(db_session, user)
    plan = financial_tools.get_investment_plan(db_session, user.id)
    assert financial_tools.analyze_goal(db_session, user.id, item.id).model_dump(mode="json") == plan.goal_analysis[0].model_dump(mode="json")
    assert financial_tools.get_monthly_plan(db_session, user.id).allocations == plan.funding_ledger
    assert financial_tools.get_financial_summary(db_session, user.id).monthly_surplus == plan.monthly_surplus
    other = User(name="Other", email="other@example.com", age=30)
    db_session.add(other)
    db_session.flush()
    item.user_id = other.id
    db_session.commit()
    assert client.get(f"/api/goals/{item.id}/analysis", params={"user_id": user.id}).status_code == 404
    assert client.get(f"/api/investment/compare/{user.id}", params={"goal_id": item.id}).status_code == 404
    for path in ("investment/plan", "financial-health", "financial-plan/monthly", "financial-insights", "financial-priorities"):
        assert client.get(f"/api/{path}/99999").status_code == 404
