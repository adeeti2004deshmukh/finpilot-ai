from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import FinancialProfile, Goal
from app.services.finance import get_profile, period_cash_flow


@dataclass(frozen=True)
class PlanningContext:
    user_id: int
    today: date
    profile: FinancialProfile
    cash_flow: dict
    goals: list[Goal]

    @property
    def summary(self):
        return self.cash_flow["summary"]

    @property
    def monthly_income(self) -> Decimal:
        return self.summary.monthly_income

    @property
    def actual_monthly_savings(self) -> Decimal:
        return self.cash_flow["savings"]


def load_planning_context(db: Session, user_id: int, today: date | None = None) -> PlanningContext:
    today = today or date.today()
    profile = get_profile(db, user_id)
    cash_flow = period_cash_flow(db, profile, today)
    goals = db.scalars(select(Goal).where(Goal.user_id == user_id).order_by(Goal.priority, Goal.id)).all()
    return PlanningContext(user_id, today, profile, cash_flow, goals)