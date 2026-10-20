"""Inject authenticated identity and reuse deterministic services. Never commit."""
from dataclasses import asdict
from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select

from app import financial_engine
from app.models.entities import Budget
from app.services import financial_tools as finance
from app.services.ai.tool_registry import REGISTRY
from app.services.finance import budget_status
from app.services.planning_context import load_planning_context
from app.services.what_if_service import _snapshot, _date_after_months


def compact(value):
    """Serialize aggregate results without identity or raw transactions."""
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    if isinstance(value, dict):
        return {key: compact(item) for key, item in value.items() if key != "user_id"}
    if isinstance(value, (list, tuple)):
        return [compact(item) for item in value]
    if isinstance(value, Decimal):
        return str(value)
    return jsonable_encoder(value)


class ToolExecutor:
    def __init__(self, db, user_id, purchase=None):
        self.db, self.user_id, self.purchase = db, user_id, purchase
        self.cache = {}

    def execute(self, name, arguments):
        if name not in REGISTRY or not isinstance(arguments, dict) or "user_id" in arguments:
            raise ValueError("Unsupported tool or arguments")
        args = REGISTRY[name][0].model_validate(arguments)
        return compact(self._execute(name, args))

    def dashboard(self):
        if "dashboard" not in self.cache:
            self.cache["dashboard"] = finance.get_financial_summary(self.db, self.user_id)
        return self.cache["dashboard"]

    def _execute(self, name, args):
        db, uid = self.db, self.user_id
        if name == "get_financial_summary":
            summary = self.dashboard().model_dump(exclude={"expense_by_category", "income_vs_expenses", "monthly_savings_trend", "goals", "top_spending_categories"})
            summary["financial_health_score"] = finance.get_financial_health(db, uid).score
            return summary
        if name == "get_spending_analysis":
            d = self.dashboard()
            return {"month": d.month, "monthly_spending": d.monthly_expenses_excluding_debt,
                    "category_breakdown": d.expense_by_category, "top_categories": d.top_spending_categories,
                    "spending_trends": d.income_vs_expenses,
                    "coverage_note": "Recorded transactions only. A large category alone does not establish overspending; compare budgets. Current month may be incomplete."}
        if name == "get_category_spending":
            matches = [c for c in self.dashboard().expense_by_category if c.category.casefold() == args.category.casefold()]
            return {"category": args.category, "recorded": bool(matches), "spending": matches}
        if name == "get_budget_status":
            today = date.today()
            rows = db.scalars(select(Budget).where(Budget.user_id == uid, Budget.month == today.month, Budget.year == today.year)).all()
            statuses = [budget_status(db, row) for row in rows]
            return {"budgets": statuses, "over_budget_categories": [s["category"] for s in statuses if s["status"] == "OVER_BUDGET"]}
        if name == "get_emergency_fund_status":
            context = load_planning_context(db, uid)
            return {**self.dashboard().emergency_fund.model_dump(),
                    "months_covered": _snapshot(context).emergency_fund_months,
                    "priorities": finance.get_financial_priorities(db, uid)}
        if name == "get_goals":
            dashboard_goals = self.dashboard().goals
            return {"goals": dashboard_goals, "analysis": finance.get_investment_plan(db, uid).goal_analysis}
        if name in {"get_financial_health", "get_financial_priorities", "get_monthly_plan", "get_investment_plan"}:
            return getattr(finance, name)(db, uid)
        if name in {"analyze_goal", "compare_investment_categories"}:
            return getattr(finance, name)(db, uid, args.goal_id)
        if name in {"simulate_sip", "simulate_rd", "simulate_fd"}:
            parameters = args.model_dump()
            if name == "simulate_rd":
                parameters["monthly_deposit"] = parameters.pop("monthly_contribution")
            result = asdict(getattr(financial_engine, name)(**parameters))
            result["assumptions"] = args.model_dump()
            result["warning"] = "Illustrative projection at your assumed rate, not a forecast or promise; excludes tax and fees. SIP risk depends on underlying assets."
            return result
        if name == "analyze_affordability":
            purchase = args.model_copy(update={"user_id": uid})
            result = finance.analyze_affordability(db, uid, purchase)
            self.purchase = arguments = args.model_dump(exclude={"user_id"}, mode="json")
            return {"inputs": arguments, "analysis": result}
        if name == "delay_purchase":
            if self.purchase is None:
                raise ValueError("Please provide purchase price, date and payment details first")
            from app.services.ai.schemas import PurchaseArgs
            original = PurchaseArgs.model_validate(self.purchase)
            delayed = original.model_copy(update={"purchase_date": _date_after_months(original.purchase_date, args.delay_months), "user_id": uid})
            return {"delay_months": args.delay_months, "inputs": delayed.model_dump(exclude={"user_id"}),
                    "analysis": finance.analyze_affordability(db, uid, delayed)}
        if name == "run_what_if_scenario":
            return finance.run_what_if_scenario(db, uid, args)
        if name == "simulate_goal":
            from types import SimpleNamespace
            from app.models.enums import GoalType
            from app.services.goal_analysis_service import analyze_goal
            if args.target_date <= date.today() or args.current_amount > args.target_amount:
                raise ValueError("Goal needs a future deadline and current amount no larger than target")
            plan = finance.get_investment_plan(db, uid)
            goal = SimpleNamespace(id=0, name=args.name, goal_type=GoalType.OTHER, target_date=args.target_date,
                                   target_amount=args.target_amount, current_amount=args.current_amount, monthly_contribution=Decimal("0"))
            return {"scenario": analyze_goal(goal, date.today(), plan.investable_surplus),
                    "available_after_existing_plan": plan.investable_surplus, "existing_goals": plan.goal_analysis,
                    "warnings": ["Unsaved scenario with no assumed returns. Existing commitments retained."]}
        raise HTTPException(422, "Unsupported tool")
