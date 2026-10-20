from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.financial_engine import FinancialProfile, calculate_financial_summary, simulate_fd, simulate_rd, simulate_sip
from app.models.entities import Category, Goal, MerchantRule, Transaction, User
from app.models.enums import CategoryType, GoalType, RiskTolerance, TransactionType


def add_category(db_session, name: str, essential: bool = False) -> Category:
    category = Category(name=name, type=CategoryType.EXPENSE, is_essential=essential)
    db_session.add(category)
    db_session.commit()
    db_session.refresh(category)
    return category


def test_models_use_decimal_money_and_relationships(db_session, user) -> None:
    assert isinstance(user.financial_profile.monthly_income, Decimal)
    assert user.financial_profile.user_id == user.id
    assert "transactions" in user.__mapper__.relationships
    assert "goals" in user.__mapper__.relationships


def test_categories_and_demo_user_endpoints(client, db_session, user) -> None:
    food = add_category(db_session, "Food endpoint test")
    categories = client.get("/api/categories", params={"type": "EXPENSE"})
    assert categories.status_code == 200
    assert any(item["id"] == food.id for item in categories.json())

    user_response = client.get(f"/api/users/{user.id}")
    assert user_response.status_code == 200
    assert user_response.json()["name"] == "Test User"
    updated = client.put(f"/api/users/{user.id}", json={"name": "Updated Test User"})
    assert updated.status_code == 200
    assert updated.json()["name"] == "Updated Test User"


def test_transaction_crud_filters_and_case_insensitive_merchant_rule(client, db_session, user) -> None:
    food = add_category(db_session, "Food")
    rule = MerchantRule(merchant_pattern="Swiggy", category_id=food.id, confidence=Decimal("0.99"))
    db_session.add(rule)
    db_session.commit()

    created = client.post(
        "/api/transactions",
        json={
            "user_id": user.id,
            "date": date.today().isoformat(),
            "description": "Lunch order",
            "merchant": "SWIGGY Pune",
            "amount": "540.25",
            "transaction_type": "EXPENSE",
        },
    )
    assert created.status_code == 201
    transaction_id = created.json()["id"]
    assert created.json()["category_id"] == food.id

    filtered = client.get(
        "/api/transactions",
        params={
            "user_id": user.id,
            "month": date.today().month,
            "year": date.today().year,
            "category": food.id,
            "merchant": "swiggy",
            "transaction_type": "EXPENSE",
            "page": 1,
        },
    )
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 1
    assert filtered.json()["items"][0]["id"] == transaction_id

    updated = client.put(f"/api/transactions/{transaction_id}", json={"amount": "600.00"})
    assert updated.status_code == 200
    assert updated.json()["amount"] == "600.00"
    assert client.get(f"/api/transactions/{transaction_id}").status_code == 200
    assert client.delete(f"/api/transactions/{transaction_id}").status_code == 204
    assert client.get(f"/api/transactions/{transaction_id}").status_code == 404


def test_profile_create_update_and_validation(client, db_session, user) -> None:
    payload = {
        "user_id": user.id,
        "monthly_income": "65000",
        "other_income": "2500",
        "current_savings": "120000",
        "emergency_savings": "55000",
        "monthly_debt_payment": "5000",
        "total_debt": "120000",
        "dependents": 0,
        "risk_tolerance": "MODERATE",
        "emergency_fund_target_months": 6,
    }
    assert client.post("/api/profile", json=payload).status_code == 409
    second_user = User(name="Second User", email="second@example.com", age=31)
    db_session.add(second_user)
    db_session.commit()
    new_profile_payload = dict(payload, user_id=second_user.id)
    # Cross-user creation is now rejected; the owner can still create a profile.
    assert client.post("/api/profile", json=new_profile_payload).status_code == 404
    from app.main import app
    from app.services.auth import get_current_user
    previous_actor = app.dependency_overrides[get_current_user]
    app.dependency_overrides[get_current_user] = lambda: second_user
    assert client.post("/api/profile", json=new_profile_payload).status_code == 201
    app.dependency_overrides[get_current_user] = previous_actor
    updated = client.put(f"/api/profile/{user.id}", json={"monthly_income": "70000"})
    assert updated.status_code == 200
    assert updated.json()["monthly_income"] == "70000.00"
    invalid = dict(payload, user_id=9999, risk_tolerance="EXTREME")
    assert client.post("/api/profile", json=invalid).status_code == 404


def test_goal_crud_and_calculated_progress(client, user) -> None:
    target_date = (date.today() + timedelta(days=300)).isoformat()
    created = client.post(
        "/api/goals",
        json={
            "user_id": user.id,
            "name": "Travel",
            "goal_type": "TRAVEL",
            "target_amount": "100000",
            "current_amount": "25000",
            "target_date": target_date,
            "monthly_contribution": "5000",
            "priority": 2,
        },
    )
    assert created.status_code == 201
    goal_id = created.json()["id"]
    assert created.json()["remaining_amount"] == "75000.00"
    assert created.json()["progress_percentage"] == "25.00"
    assert Decimal(created.json()["required_monthly_contribution"]) > 0
    assert client.get("/api/goals", params={"user_id": user.id}).json()[0]["id"] == goal_id
    assert client.put(f"/api/goals/{goal_id}", json={"current_amount": "50000"}).json()["progress_percentage"] == "50.00"
    assert client.delete(f"/api/goals/{goal_id}").status_code == 204


def test_budget_status_and_crud(client, db_session, user) -> None:
    category = add_category(db_session, "Dining")
    now = date.today()
    created = client.post(
        "/api/budgets",
        json={
            "user_id": user.id,
            "category_id": category.id,
            "monthly_limit": "1000",
            "month": now.month,
            "year": now.year,
        },
    )
    assert created.status_code == 201
    db_session.add(
        Transaction(
            user_id=user.id,
            date=now,
            description="Dinner",
            merchant="Local Cafe",
            amount=Decimal("850"),
            transaction_type=TransactionType.EXPENSE,
            category_id=category.id,
        )
    )
    db_session.commit()
    status_response = client.get(
        "/api/budgets/status", params={"user_id": user.id, "month": now.month, "year": now.year}
    )
    assert status_response.status_code == 200
    assert status_response.json()[0]["status"] == "WARNING"
    assert status_response.json()[0]["remaining_budget"] == "150.00"
    transaction = db_session.scalar(select(Transaction).where(Transaction.category_id == category.id))
    transaction.amount = Decimal("1100")
    db_session.commit()
    over_budget = client.get(
        "/api/budgets/status", params={"user_id": user.id, "month": now.month, "year": now.year}
    )
    assert over_budget.json()[0]["status"] == "OVER_BUDGET"
    budget_id = created.json()["id"]
    assert client.put(f"/api/budgets/{budget_id}", json={"monthly_limit": "1200"}).status_code == 200
    assert client.delete(f"/api/budgets/{budget_id}").status_code == 204


def test_dashboard_matches_phase1_calculation_engine(client, db_session, user) -> None:
    essential = add_category(db_session, "Essentials", essential=True)
    discretionary = add_category(db_session, "Leisure")
    now = date.today()
    db_session.add_all(
        [
            Transaction(user_id=user.id, date=now, description="Groceries", merchant="Market", amount=Decimal("9000"), transaction_type=TransactionType.EXPENSE, category_id=essential.id),
            Transaction(user_id=user.id, date=now, description="Cinema", merchant="Cinema", amount=Decimal("2000"), transaction_type=TransactionType.EXPENSE, category_id=discretionary.id),
            Transaction(user_id=user.id, date=now, description="Savings", merchant="Transfer", amount=Decimal("8000"), transaction_type=TransactionType.SAVINGS),
        ]
    )
    db_session.commit()

    engine_summary = calculate_financial_summary(
        FinancialProfile(
            monthly_take_home_income=Decimal("65000"),
            monthly_other_income=Decimal("0"),
            essential_expenses=Decimal("9000"),
            discretionary_expenses=Decimal("2000"),
            debt_payments=Decimal("5000"),
            monthly_savings=Decimal("8000"),
            current_emergency_fund=Decimal("55000"),
            emergency_fund_target_months=6,
        )
    )
    response = client.get(f"/api/dashboard/{user.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["monthly_income"] == str(engine_summary.monthly_income)
    assert data["monthly_expenses"] == str(engine_summary.monthly_expenses)
    assert data["monthly_surplus"] == str(engine_summary.monthly_surplus)
    assert data["financial_health_score"] == engine_summary.financial_health_score
    assert len(data["income_vs_expenses"]) == 6
    assert data["expense_by_category"]


def test_investable_surplus_reserves_emergency_and_goals(client, db_session, user) -> None:
    today = date.today()
    essential = add_category(db_session, "Rent", essential=True)
    db_session.add(
        Transaction(user_id=user.id, date=today, description="Rent", merchant="Rent", amount=Decimal("30000"), transaction_type=TransactionType.EXPENSE, category_id=essential.id),
    )
    db_session.add(
        Transaction(user_id=user.id, date=today, description="Monthly savings", merchant="Transfer", amount=Decimal("5000"), transaction_type=TransactionType.SAVINGS)
    )
    db_session.add(
        Goal(
            user_id=user.id,
            name="Travel",
            goal_type=GoalType.TRAVEL,
            target_amount=Decimal("50000"),
            current_amount=Decimal("0"),
            monthly_contribution=Decimal("3000"),
            priority=2,
        )
    )
    db_session.commit()
    result = client.get(f"/api/investment/available/{user.id}")
    assert result.status_code == 200
    body = result.json()
    assert body["emergency_fund_gap"] == "125000.00"
    assert body["emergency_fund_monthly_reserve"] == "20833.33"
    assert body["monthly_goal_contributions"] == "3000.00"
    assert Decimal(body["available_investable_surplus"]) >= 0


def test_merchant_rule_crud_and_rule_match_precedence(client, db_session, user) -> None:
    food = add_category(db_session, "Rule Food")
    shopping = add_category(db_session, "Rule Shopping")
    created = client.post(
        "/api/merchant-rules",
        json={"merchant_pattern": "Swiggy", "category_id": food.id, "confidence": "0.99"},
    )
    assert created.status_code == 201
    rule_id = created.json()["id"]
    conflict = client.post(
        "/api/merchant-rules",
        json={"merchant_pattern": "SWIGGY", "category_id": food.id},
    )
    assert conflict.status_code == 409
    transaction = client.post(
        "/api/transactions",
        json={
            "user_id": user.id,
            "date": date.today().isoformat(),
            "description": "Food order",
            "merchant": "New Swiggy order",
            "amount": "200",
            "transaction_type": "EXPENSE",
            "category_id": shopping.id,
        },
    )
    assert transaction.json()["category_id"] == shopping.id  # An explicit user override wins.
    assert client.put(f"/api/merchant-rules/{rule_id}", json={"confidence": "0.90"}).status_code == 200
    assert client.delete(f"/api/merchant-rules/{rule_id}").status_code == 204


def test_simulation_endpoints_match_phase1_functions(client) -> None:
    sip_payload = {"monthly_contribution": "1000", "annual_rate_percent": "8", "months": 24}
    sip_response = client.post("/api/simulate/sip", json=sip_payload)
    sip_expected = simulate_sip(Decimal("1000"), Decimal("8"), 24)
    assert sip_response.status_code == 200
    assert sip_response.json()["maturity_value"] == str(sip_expected.maturity_value)
    assert "not guaranteed" in sip_response.json()["disclaimer"]

    rd_response = client.post("/api/simulate/rd", json=sip_payload)
    rd_expected = simulate_rd(Decimal("1000"), Decimal("8"), 24)
    assert rd_response.json()["maturity_value"] == str(rd_expected.maturity_value)

    fd_payload = {"principal": "100000", "annual_rate_percent": "7", "months": 18}
    fd_response = client.post("/api/simulate/fd", json=fd_payload)
    fd_expected = simulate_fd(Decimal("100000"), Decimal("7"), 18)
    assert fd_response.json()["maturity_value"] == str(fd_expected.maturity_value)
    compound_response = client.post("/api/simulate/compound-growth", json=fd_payload)
    assert compound_response.status_code == 200
    assert "not guaranteed" in compound_response.json()["disclaimer"]
