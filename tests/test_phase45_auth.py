from datetime import date, datetime, timezone, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, func

from app.main import app
from app.database.session import get_db
from app.config import settings
from app.models.entities import User, AuthSession, Transaction, Goal, Budget, FinancialProfile, Category, MerchantRule, InvestmentPreference, Alert, Subscription
from app.services.auth import hasher
from app.models.enums import AlertSeverity, AlertType

PASSWORD = "Correct-Horse-4567"


@pytest.fixture
def accounts(db_session):
    previous = dict(app.dependency_overrides)
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = lambda: db_session
    clients = []

    def make():
        client = TestClient(app, headers={"X-FinPilot-Request": "1"})
        clients.append(client)
        return client

    yield make
    for client in clients:
        client.close()
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous)


def register(client, email="alice@example.com", name="Alice"):
    response = client.post("/api/auth/register", json={"name": name, "email": email,
        "password": PASSWORD, "confirm_password": PASSWORD})
    assert response.status_code == 201, response.text
    return response.json()


def onboard(client, **changes):
    response = client.post("/api/auth/onboarding", json={"name": "Alice", "monthly_income": "65000",
        "typical_essential_expenses": "30000", "current_savings": "120000", "emergency_savings": "55000",
        "risk_tolerance": "MODERATE", "emergency_fund_target_months": 6, **changes})
    assert response.status_code == 200, response.text
    return response.json()


def test_registration_normalization_hashing_me_and_duplicate(accounts, db_session):
    a = accounts()
    user = register(a, " Alice@Example.COM ")
    assert user["email"] == "alice@example.com" and not user["onboarding_completed"]
    assert "password" not in str(user) and "hash" not in str(user)
    row = db_session.get(User, user["id"])
    assert row.password_hash != PASSWORD and row.password_hash.startswith("$argon2id$")
    assert hasher.verify(row.password_hash, PASSWORD)
    assert a.get("/api/auth/me").json() == user
    cookie = a.cookies.get(settings.session_cookie_name)
    assert db_session.scalar(select(AuthSession)).token_hash != cookie
    assert register_response(a, "ALICE@example.com").status_code == 409


def register_response(client, email, password=PASSWORD, confirm=None):
    return client.post("/api/auth/register", json={"name": "Test", "email": email,
        "password": password, "confirm_password": password if confirm is None else confirm})


@pytest.mark.parametrize("password,confirm", [("short1", None), ("abcdefghijkl", None), (PASSWORD, "Different-456789")])
def test_password_validation_does_not_echo_secrets(accounts, password, confirm):
    response = register_response(accounts(), "test@example.com", password, confirm)
    assert response.status_code == 422
    assert password not in response.text


def test_login_invalid_password_logout_rotation_and_expiry(accounts, db_session):
    a = accounts()
    register(a)
    first_token = a.cookies.get(settings.session_cookie_name)
    response = a.post("/api/auth/login", json={"email": "alice@example.com", "password": "wrong"})
    assert response.status_code == 401 and response.json()["detail"] == "Email or password is incorrect"
    unknown = accounts().post("/api/auth/login", json={"email": "unknown@example.com", "password": "wrong"})
    assert unknown.json() == response.json()
    success = a.post("/api/auth/login", json={"email": "ALICE@example.com", "password": PASSWORD})
    assert success.status_code == 200
    assert "httponly" in success.headers["set-cookie"].lower()
    assert "samesite=lax" in success.headers["set-cookie"].lower()
    replay = accounts()
    replay.cookies.set(settings.session_cookie_name, first_token)
    assert replay.get("/api/auth/me").status_code == 401
    assert a.post("/api/auth/logout").status_code == 204
    assert a.get("/api/auth/me").status_code == 401
    assert a.post("/api/auth/login", json={"email": "alice@example.com", "password": PASSWORD}).status_code == 200
    session = db_session.scalar(select(AuthSession))
    session.expires_at = datetime.now(timezone.utc) - timedelta(days=2)
    db_session.commit()
    assert a.get("/api/auth/me").status_code == 401


def test_csrf_and_throttling(accounts):
    client = accounts()
    client.headers.pop("X-FinPilot-Request")
    assert register_response(client, "alice@example.com").status_code == 403
    client.headers["X-FinPilot-Request"] = "1"
    client.headers["Origin"] = "https://attacker.example"
    assert register_response(client, "alice@example.com").status_code == 403
    client.headers.pop("Origin")
    for _ in range(10):
        assert client.post("/api/auth/login", json={"email": "unknown@example.com", "password": "wrong"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "unknown@example.com", "password": "wrong"}).status_code == 429


def test_all_private_financial_routes_require_session(accounts):
    client = accounts()
    checked = 0
    for path, operations in app.openapi()["paths"].items():
        if not path.startswith("/api/") or path.startswith(("/api/auth/", "/api/v1/", "/api/simulate/")):
            continue
        import re
        url = re.sub(r"\{[^}]+\}", "1", path)
        for method in {method.upper() for method in operations if method in {"get", "post", "put", "delete", "patch"}}:
            response = client.request(method, url, json={})
            assert response.status_code == 401, (method, url, response.status_code)
            checked += 1
    assert checked > 35


def test_onboarding_empty_dashboard_salary_and_expense_crud(accounts, db_session):
    a = accounts()
    user = register(a)
    assert onboard(a, emergency_fund_target_months=7)["onboarding_completed"]
    assert a.post("/api/auth/onboarding", json={"name": "X", "monthly_income": 0, "risk_tolerance": "LOW"}).status_code == 409
    dashboard = a.get("/api/me/dashboard").json()
    assert dashboard["monthly_expenses_excluding_debt"] == "0.00"
    assert dashboard["monthly_savings"] == "0.00" and dashboard["goals"] == []
    assert a.get("/api/me/budgets").json() == []
    assert a.get("/api/me/transactions").json()["items"] == []
    assert dashboard["emergency_fund"]["target_amount"] == "210000.00"
    categories = a.get("/api/categories").json()
    salary = next(c for c in categories if c["name"] == "Salary")
    housing = next(c for c in categories if c["name"] == "Housing")
    payload = {"date": date.today().isoformat(), "merchant": "Employer", "description": "Salary", "amount": "65000", "transaction_type": "INCOME", "category_id": salary["id"]}
    assert a.post("/api/transactions", json=payload).status_code == 201
    assert a.get("/api/me/dashboard").json()["monthly_income"] == "65000.00"
    expense = a.post("/api/transactions", json=dict(payload, merchant="Rent", description="Rent", amount="35000", transaction_type="EXPENSE", category_id=housing["id"]))
    assert expense.status_code == 201
    tid = expense.json()["id"]
    assert expense.json()["user_id"] == user["id"]
    dashboard = a.get("/api/me/dashboard").json()
    assert dashboard["monthly_expenses_excluding_debt"] == "35000.00" and dashboard["monthly_surplus"] == "30000.00"
    assert a.get("/api/me/transactions?merchant=Rent").json()["total"] == 1
    assert a.put(f"/api/transactions/{tid}", json={"amount": "34000"}).status_code == 200
    assert a.delete(f"/api/transactions/{tid}").status_code == 204
    assert a.get(f"/api/transactions/{tid}").status_code == 404
    assert a.post("/api/budgets", json={"category_id": housing["id"], "monthly_limit": "20000", "month": date.today().month, "year": date.today().year}).status_code == 201
    assert a.get("/api/me/budget-status", params={"month": date.today().month, "year": date.today().year}).json()[0]["amount_spent"] == "0.00"
    assert a.post("/api/goals", json={"name": "Home", "goal_type": "OTHER", "target_amount": "100000"}).status_code == 201
    assert len(a.get("/api/me/goals").json()) == 1


def test_two_user_data_isolation_all_legacy_and_personal_routes(accounts, db_session):
    a, b = accounts(), accounts()
    ua = register(a)
    ub = register(b, "bob@example.com", "Bob")
    onboard(a)
    onboard(b, name="Bob", monthly_income="0", typical_essential_expenses="0", current_savings="0", emergency_savings="0")
    category = next(c for c in a.get("/api/categories").json() if c["name"] == "Housing")
    t = a.post("/api/transactions", json={"date": date.today().isoformat(), "merchant": "Private", "description": "Alice secret", "amount": "100", "transaction_type": "EXPENSE", "category_id": category["id"]}).json()
    g = a.post("/api/goals", json={"name": "Alice private goal", "goal_type": "OTHER", "target_amount": "10000"}).json()
    budget = a.post("/api/budgets", json={"category_id": category["id"], "monthly_limit": "10000", "month": 10, "year": 2026}).json()
    rule = a.post("/api/merchant-rules", json={"merchant_pattern": "AlicePrivate", "category_id": category["id"]}).json()
    db_session.add(Alert(user_id=ua["id"], title="Alice alert", message="Private alert", severity=AlertSeverity.WARNING, alert_type=AlertType.SYSTEM))
    db_session.add(Subscription(user_id=ua["id"], merchant="Alice subscription", monthly_amount=Decimal("99"), estimated_annual_amount=Decimal("1188"), is_active=True))
    db_session.commit()
    assert a.get("/api/me/alerts").json()[0]["title"] == "Alice alert"
    assert a.get("/api/me/subscriptions").json()[0]["merchant"] == "Alice subscription"
    assert b.get("/api/me/alerts").json() == []
    assert b.get("/api/me/subscriptions").json() == []
    assert b.get("/api/me/preferences").status_code == 200
    for resource, rid in (("transactions", t["id"]), ("goals", g["id"]), ("budgets", budget["id"]), ("merchant-rules", rule["id"])):
        for method in (["GET", "PUT", "DELETE"] if resource in {"transactions", "goals"} else ["PUT", "DELETE"]):
            assert b.request(method, f"/api/{resource}/{rid}", json={}).status_code == 404
    for prefix in ("users", "profile", "dashboard", "investment/plan", "investment/available", "financial-health", "financial-priorities", "financial-insights", "financial-plan/monthly"):
        assert b.get(f"/api/{prefix}/{ua['id']}").status_code == 404
    for path in ("transactions", "goals", "budgets", "budgets/status"):
        assert b.get(f"/api/{path}", params={"user_id": ua["id"]}).status_code == 404
    for resource in ("transactions", "goals", "budgets", "profile"):
        assert b.post(f"/api/{resource}", json={"user_id": ua["id"]}).status_code == 404
    purchase = {"item_name": "Phone", "price": "80000", "purchase_date": date.today().isoformat(), "payment_method": "CASH"}
    assert b.post("/api/affordability/analyze", json={**purchase, "user_id": ua["id"]}).status_code == 404
    assert b.post("/api/affordability/analyze", json=purchase).json()["user_id"] == ub["id"]
    assert b.get(f"/api/investment/compare/{ub['id']}", params={"goal_id": g["id"]}).status_code == 404
    assert b.post("/api/me/what-if", json={"scenario_type": "GOAL_DELAY", "goal_id": g["id"], "delay_months": 6}).status_code == 404
    for path in ("dashboard", "investment-plan", "financial-health", "insights", "monthly-plan", "priorities"):
        response = b.get(f"/api/me/{path}")
        assert response.status_code == 200
        assert "Alice" not in response.text
    assert b.get("/api/me/goals").json() == []
    assert b.get("/api/me/budgets").json() == []
    assert b.get("/api/me/transactions").json()["items"] == []
    assert "AlicePrivate" not in b.get("/api/merchant-rules").text
    assert a.get("/api/me/category-suggestion", params={"merchant": "AlicePrivate"}).json()["category_id"] == category["id"]
    assert b.get("/api/me/category-suggestion", params={"merchant": "AlicePrivate"}).json()["category_id"] is None


def test_first_goal_and_demo_are_separate_and_read_only(accounts, db_session, monkeypatch):
    import seed
    from sqlalchemy.orm import sessionmaker
    monkeypatch.setattr(seed, "SessionLocal", sessionmaker(bind=db_session.get_bind(), expire_on_commit=False))
    demo_id = seed.seed()
    demo = accounts()
    response = demo.post("/api/auth/demo")
    assert response.status_code == 200 and response.json()["is_demo"]
    assert demo.get("/api/me/dashboard").json()["user_id"] == demo_id
    assert demo.post("/api/goals", json={"name": "Do not save"}).status_code == 403
    assert demo.put(f"/api/users/{demo_id}", json={"name": "Changed"}).status_code == 403
    assert db_session.get(User, demo_id).name == "Aarav Sharma"
    a = accounts()
    user = register(a)
    onboard(a, first_goal={"name": "Education", "goal_type": "OTHER", "target_amount": "100000", "current_amount": "0"})
    assert a.get("/api/me/transactions").json()["total"] == 0
    assert [g["name"] for g in a.get("/api/me/goals").json()] == ["Education"]
    assert user["id"] != demo_id
    assert a.get(f"/api/dashboard/{demo_id}").status_code == 404


def test_secure_production_cookie(accounts, monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    response = register_response(accounts(), "secure@example.com")
    assert response.status_code == 201
    assert "; secure" in response.headers["set-cookie"].lower()
