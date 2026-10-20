"""Read-only live API/page smoke verification; run with the backend venv Python.

Start backend/frontend first. Ports can be overridden with --api and --frontend.
Only calculation POSTs are made; no persisted records are created or changed.
"""
import argparse
from datetime import date
from decimal import Decimal as D
import json
from pathlib import Path

import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://127.0.0.1:8765")
    parser.add_argument("--frontend", default="http://127.0.0.1:3005")
    
    args = parser.parse_args()
    checks = []
    client = httpx.Client(headers={"Origin": "http://localhost:3000", "X-FinPilot-Request": "1"}, follow_redirects=True)

    def request(method, path, *, body=None, status=200, frontend=False):
        base = args.frontend if frontend else args.api
        response = client.request(method, base + path, json=body, timeout=20,
                                 headers={"Origin": "http://localhost:3000"})
        assert response.status_code == status, f"{method} {path}: {response.status_code}, expected {status}"
        checks.append({"method": method, "path": path, "server": "frontend" if frontend else "backend", "status": response.status_code})
        return response

    uid = request("POST", "/api/auth/demo").json()["id"]
    request("GET", "/health")
    request("GET", "/openapi.json")
    for path in (f"/api/users/{uid}", f"/api/profile/{uid}", "/api/categories", f"/api/transactions?user_id={uid}",
                 f"/api/budgets/status?user_id={uid}&month={date.today().month}&year={date.today().year}",
                 "/api/investment/categories", f"/api/investment/available/{uid}", f"/api/financial-priorities/{uid}"):
        request("GET", path)
    plan = request("GET", f"/api/investment/plan/{uid}").json()
    assert D(plan["monthly_income"]) - D(plan["monthly_expenses"]) - D(plan["monthly_debt_payment"]) == D(plan["monthly_surplus"])
    assert sum(D(item["amount"]) for item in plan["funding_ledger"]) == D(plan["allocation_total"]) <= max(D(0), D(plan["monthly_surplus"]))
    monthly = request("GET", f"/api/financial-plan/monthly/{uid}").json()
    assert monthly["allocations"] == plan["funding_ledger"]
    dashboard = request("GET", f"/api/dashboard/{uid}").json()
    health = request("GET", f"/api/financial-health/{uid}").json()
    assert sum(item["points"] for item in health["components"]) == health["score"] == dashboard["financial_health_score"]
    assert dashboard["investable_surplus"] == plan["investable_surplus"]
    insights = request("GET", f"/api/financial-insights/{uid}").json()
    assert insights["coverage_note"] and all(item["reason_code"] for item in insights["insights"])
    goals = request("GET", f"/api/goals?user_id={uid}").json()
    for goal in goals:
        analysis = request("GET", f"/api/goals/{goal['id']}/analysis?user_id={uid}").json()
        comparison = request("GET", f"/api/investment/compare/{uid}?goal_id={goal['id']}").json()
        assert comparison["goal"] == analysis
        assert all(0 <= item["relevance_score"] <= 100 for item in comparison["categories_to_explore"])
    purchase = {"user_id": uid, "item_name": "Verification only", "price": "60000",
                "purchase_date": date.today().isoformat(), "payment_method": "CASH"}
    for body in (purchase, dict(purchase, payment_method="EMI", down_payment="0", monthly_emi="5000", tenure_months=12)):
        result = request("POST", "/api/affordability/analyze", body=body).json()
        assert sum(result["score_components"].values()) == result["affordability_score"]
        assert {"Wait 3 months", "Wait 6 months"} <= {item["name"] for item in result["alternative_scenarios"]}
        assert all(item["affordability_score"] == 0 for item in result["alternative_scenarios"] if D(item["monthly_saving_shortfall"]) > 0)
    for kind in ("INCOME_INCREASE", "RENT_INCREASE", "FOOD_SPENDING_REDUCTION", "SAVINGS_INCREASE"):
        request("POST", f"/api/financial-plan/what-if/{uid}", body={"scenario_type": kind, "amount": "1000"})
    dated_goal = next((goal for goal in goals if goal["target_date"]), None)
    if dated_goal:
        request("POST", f"/api/financial-plan/what-if/{uid}", body={"scenario_type": "GOAL_DELAY", "goal_id": dated_goal["id"], "delay_months": 6})
    # Repeat reads prove calculation requests left the stored planning inputs unchanged.
    assert request("GET", f"/api/investment/plan/{uid}").json() == plan
    request("GET", "/api/investment/plan/99999999", status=404)
    request("POST", "/api/affordability/analyze", body=dict(purchase, price="-1"), status=422)
    preflight = httpx.options(
        args.api + f"/api/investment/plan/{uid}", headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"})
    assert preflight.status_code == 200 and preflight.headers.get("access-control-allow-origin") == "http://localhost:3000"
    for path in ("/", "/investments", "/affordability", "/what-if", "/goals", "/transactions", "/budget", "/simulator", "/settings"):
        response = request("GET", path, frontend=True)
        assert "<html" in response.text
    output = {"result": "PASS", "checks": checks, "cors_preflight": "PASS", "financial_invariants": "PASS",
              "browser_interaction": "NOT_PERFORMED", "database": "Existing SQLite, read-only calculation checks"}
    Path("PHASE4_LIVE_RESULTS.json").write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(f"PASS: {len(checks)} HTTP checks, CORS, cash-flow/score consistency and non-persistence")


if __name__ == "__main__":
    main()
