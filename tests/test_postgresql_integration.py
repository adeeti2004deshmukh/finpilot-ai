"""Real server only: skipped unless FINPILOT_TEST_DATABASE_URL is explicitly set."""
from datetime import date
from decimal import Decimal

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.orm import sessionmaker

import seed as demo_seed
from app.config import settings
from app.database.session import get_db
from app.main import app
from app.models.entities import Budget, Category, Goal, Transaction, User


def test_postgresql_migrations_seed_and_phase4_apis(postgresql_engine, monkeypatch):
    engine = postgresql_engine  # Unique schema created and cleaned by the fixture.
    with engine.connect() as connection:
        assert "PostgreSQL" in connection.scalar(text("select version()"))
    monkeypatch.setattr(settings, "database_url", engine.url.render_as_string(hide_password=False))
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    command.check(config)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(demo_seed, "SessionLocal", factory)
    user_id = demo_seed.seed()

    def counts():
        with factory() as db:
            return tuple(db.scalar(select(func.count()).select_from(model))
                         for model in (User, Category, Goal, Transaction, Budget))

    before = counts()
    assert demo_seed.seed() == user_id
    assert counts() == before

    with factory() as db:
        def override_db():
            yield db

        previous_override = app.dependency_overrides.get(get_db)
        app.dependency_overrides[get_db] = override_db
        try:
            with TestClient(app, headers={"X-FinPilot-Request": "1"}) as client:
                assert client.post("/api/auth/demo").status_code == 200
                def get(path):
                    response = client.get(path)
                    assert response.status_code == 200, (path, response.status_code)
                    return response.json()

                plan = get(f"/api/investment/plan/{user_id}")
                assert Decimal(plan["monthly_income"]) - Decimal(plan["monthly_expenses"]) - Decimal(plan["monthly_debt_payment"]) == Decimal(plan["monthly_surplus"])
                assert sum(Decimal(line["amount"]) for line in plan["funding_ledger"]) == Decimal(plan["allocation_total"]) <= max(Decimal("0"), Decimal(plan["monthly_surplus"]))
                dashboard = get(f"/api/dashboard/{user_id}")
                health = get(f"/api/financial-health/{user_id}")
                assert sum(item["points"] for item in health["components"]) == health["score"] == dashboard["financial_health_score"]
                assert get(f"/api/financial-plan/monthly/{user_id}")["allocations"] == plan["funding_ledger"]
                get(f"/api/financial-priorities/{user_id}")
                get(f"/api/financial-insights/{user_id}")
                get(f"/api/investment/available/{user_id}")
                get("/api/investment/categories")
                goals = get(f"/api/goals?user_id={user_id}")
                for goal in goals:
                    comparison = get(f"/api/investment/compare/{user_id}?goal_id={goal['id']}")
                    assert comparison["goal"] == get(f"/api/goals/{goal['id']}/analysis?user_id={user_id}")
                    assert all(0 <= item["relevance_score"] <= 100 for item in comparison["categories_to_explore"])
                payload = {"user_id": user_id, "item_name": "PostgreSQL verification", "price": "60000",
                           "payment_method": "CASH", "purchase_date": date.today().isoformat()}
                for purchase in (payload, dict(payload, payment_method="EMI", down_payment="0", monthly_emi="5000", tenure_months=12)):
                    response = client.post("/api/affordability/analyze", json=purchase)
                    assert response.status_code == 200
                    result = response.json()
                    assert sum(result["score_components"].values()) == result["affordability_score"]
                    assert {"Wait 3 months", "Wait 6 months"} <= {item["name"] for item in result["alternative_scenarios"]}
                for kind in ("INCOME_INCREASE", "RENT_INCREASE", "FOOD_SPENDING_REDUCTION", "SAVINGS_INCREASE", "GOAL_DELAY"):
                    scenario = {"scenario_type": kind, "amount": "1000"}
                    if kind == "GOAL_DELAY":
                        scenario = {"scenario_type": kind, "goal_id": goals[0]["id"], "delay_months": 6}
                    assert client.post(f"/api/financial-plan/what-if/{user_id}", json=scenario).status_code == 200
                assert get(f"/api/investment/plan/{user_id}") == plan
        finally:
            if previous_override is None:
                app.dependency_overrides.pop(get_db, None)
            else:
                app.dependency_overrides[get_db] = previous_override
    assert counts() == before
