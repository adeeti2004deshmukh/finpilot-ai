from app.schemas.planning import InvestmentPlanResponse


def test_current_plan_endpoint_exposes_required_frontend_contract(client, user):
    response = client.get(f"/api/investment/plan/{user.id}")
    assert response.status_code == 200
    plan = response.json()
    required = {name for name, field in InvestmentPlanResponse.model_fields.items() if field.is_required()}
    assert required <= plan.keys()
    for name in ("funding_ledger", "financial_priorities", "allocations", "goal_analysis", "warnings", "methodology"):
        assert isinstance(plan[name], list)
    for allocation in plan["allocations"]:
        assert isinstance(allocation["categories_to_explore"], list)
    schema = client.get("/openapi.json").json()["components"]["schemas"]["InvestmentPlanResponse"]
    assert "funding_ledger" in schema["required"]
    assert schema["properties"]["funding_ledger"]["type"] == "array"
