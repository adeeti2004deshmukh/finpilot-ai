"""Explicit allowlist: no identity arguments, arbitrary queries, or mutations."""
from copy import deepcopy

from app.services.ai import schemas as s

REGISTRY = {
    "get_financial_summary": (s.EmptyArgs, "Current income, expenses, actual savings, savings rate, surplus, investable surplus and health."),
    "get_spending_analysis": (s.EmptyArgs, "Current recorded category spending, top categories and six monthly trends. Use for overspending."),
    "get_category_spending": (s.CategoryArgs, "Recorded current-month spending for a category name; missing categories are reported explicitly."),
    "get_budget_status": (s.EmptyArgs, "Current month budgets, spending, remaining amounts, percentages and over-budget categories."),
    "get_financial_health": (s.EmptyArgs, "Verified overall health score, components, strengths, weaknesses and actions."),
    "get_emergency_fund_status": (s.EmptyArgs, "Current reserve, target, coverage months, gap and priority."),
    "get_goals": (s.EmptyArgs, "Saved goals, deadlines, required monthly contributions, progress and funding status."),
    "analyze_goal": (s.GoalArgs, "Deterministic analysis of a saved goal owned by the signed-in user."),
    "get_financial_priorities": (s.EmptyArgs, "Deterministic financial priorities. Use for prioritization questions."),
    "get_monthly_plan": (s.EmptyArgs, "Monthly action plan and allocations."),
    "get_investment_plan": (s.EmptyArgs, "Purpose allocations, safety buffer, available cash flow, category relevance and warnings."),
    "compare_investment_categories": (s.GoalArgs, "Educational category comparison for a saved goal; no named securities."),
    "simulate_sip": (s.ContributionArgs, "SIP projection. Rate must be explicitly supplied by user; SIP is a method, risk depends on underlying assets."),
    "simulate_rd": (s.ContributionArgs, "Recurring-deposit projection using a user-supplied assumed rate."),
    "simulate_fd": (s.DepositArgs, "Fixed-deposit projection using a user-supplied assumed rate and compounding frequency."),
    "analyze_affordability": (s.PurchaseArgs, "Analyze purchase. Ask for missing price, purchase date and CASH/EMI choice; EMI needs down payment, monthly EMI and tenure. Never guess."),
    "run_what_if_scenario": (s.ScenarioArgs, "Simulate income/rent/savings changes, spending reduction or saved-goal delay. Ask for missing inputs."),
    "simulate_goal": (s.GoalScenarioArgs, "Unsaved goal scenario: uses existing goal engine, no return assumptions. Ask for current amount if unknown; never saves a goal."),
    "delay_purchase": (s.PurchaseDelayArgs, "Rerun the most recently verified affordability scenario after waiting this many months. Requires prior affordability result in this conversation."),
}


def strict_schema(schema):
    """Responses strict schemas require all object fields, nullable for optional values."""
    schema = deepcopy(schema)
    def visit(node):
        if isinstance(node, dict):
            node.pop("default", None)
            if node.get("type") == "object":
                node["additionalProperties"] = False
                node["required"] = list(node.get("properties", {}))
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)
    visit(schema)
    return schema


def tools():
    result = []
    for name, (model, description) in REGISTRY.items():
        schema = model.model_json_schema()
        if name == "analyze_affordability":
            schema["properties"].pop("user_id")
        result.append({"type": "function", "name": name, "description": description,
                       "parameters": strict_schema(schema), "strict": True})
    return result
