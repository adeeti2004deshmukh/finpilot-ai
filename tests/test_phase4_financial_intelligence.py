from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.models.entities import Category, Goal, Transaction
from app.models.enums import CategoryType, GoalType, TransactionType
from app.services.goal_analysis_service import analyze_goal, classify_horizon
from app.services.investment_category_service import score_category_relevance
from app.models.enums import RiskTolerance

D = Decimal


def add_expense(db_session, user_id: int, category_name: str, amount: str, essential: bool = False) -> Category:
    category = db_session.scalar(
        select(Category).where(Category.name == category_name, Category.type == CategoryType.EXPENSE)
    )
    if category is None:
        category = Category(name=category_name, type=CategoryType.EXPENSE, is_essential=essential)
        db_session.add(category)
        db_session.flush()
    db_session.add(
        Transaction(
            user_id=user_id,
            date=date.today(),
            description=f"{category_name} test expense",
            merchant=category_name,
            amount=D(amount),
            transaction_type=TransactionType.EXPENSE,
            category_id=category.id,
        )
    )
    db_session.commit()
    return category


def add_savings(db_session, user_id: int, amount: str) -> None:
    db_session.add(
        Transaction(
            user_id=user_id,
            date=date.today(),
            description="Actual monthly savings",
            merchant="Savings transfer",
            amount=D(amount),
            transaction_type=TransactionType.SAVINGS,
        )
    )
    db_session.commit()


def add_goal(db_session, user_id: int, *, name: str = "Travel", goal_type: GoalType = GoalType.TRAVEL,
             target: str = "100000", current: str = "0", monthly: str = "3000",
             target_date: date | None = None) -> Goal:
    goal = Goal(
        user_id=user_id,
        name=name,
        goal_type=goal_type,
        target_amount=D(target),
        current_amount=D(current),
        target_date=target_date or date.today() + timedelta(days=540),
        monthly_contribution=D(monthly),
        priority=2,
    )
    db_session.add(goal)
    db_session.commit()
    db_session.refresh(goal)
    return goal


def test_plan_separates_surplus_actual_savings_buffer_and_investable(client, db_session, user) -> None:
    add_expense(db_session, user.id, "Rent Phase4", "30000", essential=True)
    add_expense(db_session, user.id, "Dining Phase4", "5000")
    add_savings(db_session, user.id, "4000")

    response = client.get(f"/api/investment/plan/{user.id}")
    assert response.status_code == 200
    plan = response.json()
    assert plan["monthly_income"] == "65000.00"
    assert plan["monthly_expenses"] == "35000.00"
    assert plan["monthly_debt_payment"] == "5000.00"
    assert plan["monthly_surplus"] == "25000.00"
    assert Decimal(plan["monthly_surplus"]) == Decimal(plan["monthly_income"]) - Decimal(plan["monthly_expenses"]) - Decimal(plan["monthly_debt_payment"])
    assert plan["actual_monthly_savings"] == "4000.00"
    assert plan["cash_after_actual_savings"] == "21000.00"
    assert plan["safety_buffer_target"] == "5200.00"
    assert plan["safety_buffer"] == "5200.00"
    assert plan["investable_surplus"] == "0.00"
    assert sum(Decimal(item["amount"]) for item in plan["allocations"]) <= Decimal("21000.00")
    assert any(priority["reason_code"] == "LOW_EMERGENCY_RESERVE" for priority in plan["financial_priorities"])


def test_safety_buffer_can_be_configured_and_no_surplus_means_no_allocation(client, db_session, user) -> None:
    profile = user.financial_profile
    profile.monthly_income = D("0")
    profile.monthly_debt_payment = D("0")
    profile.emergency_savings = D("0")
    db_session.commit()
    response = client.get(f"/api/investment/plan/{user.id}")
    assert response.status_code == 200
    plan = response.json()
    assert plan["monthly_surplus"] == "0.00"
    assert plan["safety_buffer"] == "0.00"
    assert plan["investable_surplus"] == "0.00"
    assert plan["financial_priorities"][0]["priority_level"] == "CRITICAL"


def test_no_emergency_fund_and_high_debt_create_high_priorities(client, db_session, user) -> None:
    user.financial_profile.emergency_savings = D("0")
    user.financial_profile.monthly_debt_payment = D("20000")
    user.financial_profile.total_debt = D("500000")
    db_session.commit()
    add_expense(db_session, user.id, "Essentials No EF", "10000", essential=True)
    response = client.get(f"/api/investment/plan/{user.id}")
    assert response.status_code == 200
    plan = response.json()
    reason_codes = {item["reason_code"] for item in plan["financial_priorities"]}
    assert "LOW_EMERGENCY_RESERVE" in reason_codes
    assert "HIGH_DEBT_BURDEN" in reason_codes
    assert Decimal(plan["investable_surplus"]) >= 0


def test_expenses_greater_than_income_force_zero_new_allocation(client, db_session, user) -> None:
    user.financial_profile.monthly_debt_payment = D("5000")
    db_session.commit()
    add_expense(db_session, user.id, "Very High Rent", "70000", essential=True)
    response = client.get(f"/api/investment/plan/{user.id}")
    assert response.status_code == 200
    plan = response.json()
    assert Decimal(plan["monthly_surplus"]) < 0
    assert plan["investable_surplus"] == "0.00"
    assert plan["allocations"] == []
    assert any("meet or exceed" in warning for warning in plan["warnings"])


def test_goal_horizon_boundaries_and_past_deadline_feasibility(db_session, user) -> None:
    today = date.today()
    assert classify_horizon(12) == "VERY_SHORT_TERM"
    assert classify_horizon(13) == "SHORT_TERM"
    assert classify_horizon(36) == "SHORT_TERM"
    assert classify_horizon(37) == "MEDIUM_TERM"
    assert classify_horizon(60) == "MEDIUM_TERM"
    assert classify_horizon(61) == "LONG_TERM"
    past_goal = add_goal(db_session, user.id, target_date=today - timedelta(days=1), monthly="0")
    analysis = analyze_goal(past_goal, today, D("10000"))
    assert analysis.remaining_months == 0
    assert analysis.goal_horizon == "VERY_SHORT_TERM"
    assert analysis.funding_status == "NOT_FEASIBLE_WITH_CURRENT_SURPLUS"


def test_category_relevance_adjusts_for_horizon_risk_and_emergency_coverage(db_session, user) -> None:
    short = add_goal(db_session, user.id, target_date=date.today() + timedelta(days=500))
    short_analysis = analyze_goal(short, date.today(), D("20000"))
    low_reserve = score_category_relevance(short_analysis, RiskTolerance.LOW, D("20"))
    high_reserve = score_category_relevance(short_analysis, RiskTolerance.MODERATE, D("100"))
    low_map = {item.name: item for item in low_reserve}
    full_map = {item.name: item for item in high_reserve}
    assert low_map["Recurring Deposit (RD)"].relevance_score >= low_map["Index-oriented SIP category"].relevance_score
    assert full_map["Index-oriented SIP category"].relevance_score > low_map["Index-oriented SIP category"].relevance_score
    assert "method" in low_map["Mutual Fund SIP"].description.lower()


def test_goal_comparison_endpoint_returns_structured_relevance(client, db_session, user) -> None:
    goal = add_goal(db_session, user.id, target_date=date.today() + timedelta(days=500))
    response = client.get(f"/api/investment/compare/{user.id}", params={"goal_id": goal.id})
    assert response.status_code == 200
    body = response.json()
    assert body["goal"]["goal_horizon"] == "SHORT_TERM"
    assert len(body["categories_to_explore"]) == 8
    assert all(0 <= item["relevance_score"] <= 100 for item in body["categories_to_explore"])


def test_affordability_cash_analysis_protects_emergency_reserve(client, user) -> None:
    response = client.post(
        "/api/affordability/analyze",
        json={
            "user_id": user.id,
            "item_name": "Laptop",
            "price": "80000",
            "purchase_date": (date.today() + timedelta(days=1)).isoformat(),
            "payment_method": "CASH",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["emergency_fund_before"] == "55000.00"
    assert body["emergency_fund_after"] == "40000.00"
    assert body["monthly_surplus_after"] == body["monthly_surplus_before"]
    assert body["cash_flow_impact"] == "80000.00"
    assert body["affordability_status"] in {"COMFORTABLE", "MANAGEABLE", "CAUTION", "HIGH_RISK"}
    assert sum(body["score_components"].values()) == body["affordability_score"]
    assert len(body["alternative_scenarios"]) == 4
    assert body["alternative_scenarios"][0]["name"] == "Buy now"
    assert body["warnings"]


def test_affordability_emi_counts_debt_and_cashflow(client, user) -> None:
    response = client.post(
        "/api/affordability/analyze",
        json={
            "user_id": user.id,
            "item_name": "Phone",
            "price": "60000",
            "purchase_date": date.today().isoformat(),
            "payment_method": "EMI",
            "down_payment": "10000",
            "monthly_emi": "5000",
            "tenure_months": 12,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["monthly_surplus_after"] == str(Decimal(body["monthly_surplus_before"]) - D("5000.00"))
    assert body["total_emi_commitment"] == "10000.00"
    assert Decimal(body["debt_burden_after_percent"]) > Decimal(body["debt_burden_before_percent"])


def test_affordability_rejects_negative_price_and_invalid_emi(client, user) -> None:
    base = {
        "user_id": user.id,
        "item_name": "Device",
        "price": "10000",
        "purchase_date": (date.today() + timedelta(days=1)).isoformat(),
        "payment_method": "EMI",
        "down_payment": "10000",
        "monthly_emi": "1000",
        "tenure_months": 12,
    }
    assert client.post("/api/affordability/analyze", json=base).status_code == 422
    assert client.post("/api/affordability/analyze", json=dict(base, price="-1")).status_code == 422


def test_health_breakdown_sums_to_existing_phase1_score(client, user) -> None:
    response = client.get(f"/api/financial-health/{user.id}")
    assert response.status_code == 200
    body = response.json()
    assert sum(component["points"] for component in body["components"]) == body["score"]
    assert body["score"] == 70
    assert body["goal_progress_context"]
    assert body["deterministic_actions"]


def test_monthly_action_plan_does_not_overallocate_income(client, user) -> None:
    response = client.get(f"/api/financial-plan/monthly/{user.id}")
    assert response.status_code == 200
    body = response.json()
    assert Decimal(body["allocation_total"]) <= max(
        D("0"), D(body["monthly_income"]) - D(body["essential_expenses"]) - D(body["discretionary_expenses"]) - D(body["debt_obligations"])
    )
    assert body["total_income_commitment"] <= body["income_limit"]


def test_what_if_income_rent_savings_and_goal_delay(client, db_session, user) -> None:
    rent = add_expense(db_session, user.id, "Rent What If", "15000", essential=True)
    food = add_expense(db_session, user.id, "Food What If", "5000")
    goal = add_goal(db_session, user.id, target_date=date.today() + timedelta(days=900))

    income = client.post(f"/api/financial-plan/what-if/{user.id}", json={"scenario_type": "INCOME_INCREASE", "amount": "10000"})
    assert income.status_code == 200
    assert Decimal(income.json()["projected"]["monthly_income"]) == Decimal(income.json()["current"]["monthly_income"]) + D("10000")

    rent_scenario = client.post(f"/api/financial-plan/what-if/{user.id}", json={"scenario_type": "RENT_INCREASE", "amount": "3000"})
    assert rent_scenario.status_code == 200
    assert Decimal(rent_scenario.json()["projected"]["monthly_expenses"]) == Decimal(rent_scenario.json()["current"]["monthly_expenses"]) + D("3000")

    food_scenario = client.post(f"/api/financial-plan/what-if/{user.id}", json={"scenario_type": "FOOD_SPENDING_REDUCTION", "amount": "2000"})
    assert food_scenario.status_code == 200
    assert Decimal(food_scenario.json()["projected"]["monthly_expenses"]) < Decimal(food_scenario.json()["current"]["monthly_expenses"])

    savings = client.post(f"/api/financial-plan/what-if/{user.id}", json={"scenario_type": "SAVINGS_INCREASE", "amount": "1000"})
    assert savings.status_code == 200
    assert savings.json()["projected"]["monthly_surplus"] == savings.json()["current"]["monthly_surplus"]
    assert Decimal(savings.json()["projected"]["actual_monthly_savings"]) == Decimal(savings.json()["current"]["actual_monthly_savings"]) + D("1000")

    delay = client.post(f"/api/financial-plan/what-if/{user.id}", json={"scenario_type": "GOAL_DELAY", "goal_id": goal.id, "delay_months": 12})
    assert delay.status_code == 200
    assert delay.json()["projected"]["goal_feasibility"][0]["required_monthly_contribution"] <= delay.json()["current"]["goal_feasibility"][0]["required_monthly_contribution"]


def test_deterministic_insights_return_reason_codes(client, user) -> None:
    response = client.get(f"/api/financial-insights/{user.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["insights"]
    assert all(item["reason_code"] and item["type"] for item in body["insights"])


def test_overdue_goal_is_not_on_track_despite_large_planned_contribution(db_session, user):
    goal = add_goal(db_session, user.id, target="1000", monthly="2000",
                    target_date=date.today() - timedelta(days=1))
    assert analyze_goal(goal, date.today(), D("50000")).funding_status == "NOT_FEASIBLE_WITH_CURRENT_SURPLUS"


def test_unfunded_cash_purchase_is_high_risk_and_explains_shortfall(client, user):
    response = client.post("/api/affordability/analyze", json={
        "user_id": user.id, "item_name": "Unfunded purchase", "price": "200000",
        "purchase_date": date.today().isoformat(), "payment_method": "CASH",
    })
    assert response.status_code == 200
    result = response.json()
    assert result["upfront_funding_shortfall"] == "80000.00"
    assert result["affordability_status"] == "HIGH_RISK"
    assert result["affordability_score"] == sum(result["score_components"].values()) == 0
    assert any("not fully funded" in warning for warning in result["warnings"])


def test_cash_purchase_rejects_emi_fields_and_underfunded_emi(client, user):
    payload = {"user_id": user.id, "item_name": "Device", "price": "10000",
               "purchase_date": date.today().isoformat(), "payment_method": "CASH",
               "monthly_emi": "1"}
    assert client.post("/api/affordability/analyze", json=payload).status_code == 422
    payload.update(payment_method="EMI", down_payment="0", tenure_months=12)
    assert client.post("/api/affordability/analyze", json=payload).status_code == 422


def test_food_reduction_uses_essential_food_and_does_not_write_transactions(client, db_session, user):
    add_expense(db_session, user.id, "Food essentials regression", "5000", essential=True)
    add_expense(db_session, user.id, "Entertainment regression", "1000")
    response = client.post(f"/api/financial-plan/what-if/{user.id}",
                           json={"scenario_type": "FOOD_SPENDING_REDUCTION", "amount": "7000"})
    assert response.status_code == 200
    result = response.json()
    assert D(result["current"]["monthly_expenses"]) - D(result["projected"]["monthly_expenses"]) == D("5000")
    assert D(result["changes"]["essential_expense_reduction"]) == D("5000")
    assert D(result["changes"]["discretionary_expense_reduction"]) == 0
    # A fresh read still sees the original transaction totals.
    plan = client.get(f"/api/investment/plan/{user.id}").json()
    assert plan["monthly_expenses"] == "6000.00"


def test_food_reduction_does_not_reduce_unrelated_discretionary_spend(client, db_session, user):
    add_expense(db_session, user.id, "Cinema regression", "2000")
    result = client.post(f"/api/financial-plan/what-if/{user.id}",
                         json={"scenario_type": "FOOD_SPENDING_REDUCTION", "amount": "1000"}).json()
    assert result["current"]["monthly_expenses"] == result["projected"]["monthly_expenses"]


def test_paise_allocations_reconcile_without_rounding_overdraft(client, db_session, user):
    user.financial_profile.monthly_income = D("5000.05")
    user.financial_profile.monthly_debt_payment = D("0")
    user.financial_profile.total_debt = D("0")
    db_session.commit()
    plan = client.get(f"/api/investment/plan/{user.id}").json()
    assert D(plan["safety_buffer"]) == D("5000")
    assert D(plan["unallocated_buffer"]) == D("0.01")
    assert D(plan["investable_surplus"]) == D("0.04")
    assert sum(D(line["amount"]) for line in plan["allocations"]) == D("5000.05")
    response = client.get(f"/api/financial-plan/monthly/{user.id}")
    assert response.status_code == 200
    assert D(response.json()["total_income_commitment"]) == D("5000.05")


def test_available_endpoint_does_not_count_goal_topup_twice(client, db_session, user):
    add_goal(db_session, user.id, target="12000", monthly="0",
             target_date=date.today() + timedelta(days=180))
    plan = client.get(f"/api/investment/plan/{user.id}").json()
    available = client.get(f"/api/investment/available/{user.id}").json()
    assert D(plan["short_term_goal_reserve"]) > 0
    assert D(available["monthly_goal_contributions"]) == D(plan["goal_contributions"])
