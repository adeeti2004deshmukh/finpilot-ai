from calendar import monthrange
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select

from app.database.session import SessionLocal
from app.models.entities import (
    Budget,
    Category,
    FinancialProfile,
    Goal,
    InvestmentPreference,
    MerchantRule,
    Transaction,
    User,
)
from app.models.enums import CategoryType, GoalType, RiskTolerance, TransactionType

DEMO_EMAIL = "aarav.sharma.demo@example.com"
DEMO_NAME = "Aarav Sharma"

CATEGORIES = {
    "Housing": (CategoryType.EXPENSE, True),
    "Food": (CategoryType.EXPENSE, False),
    "Transportation": (CategoryType.EXPENSE, False),
    "Entertainment": (CategoryType.EXPENSE, False),
    "Shopping": (CategoryType.EXPENSE, False),
    "Utilities": (CategoryType.EXPENSE, True),
    "Groceries": (CategoryType.EXPENSE, True),
    "Insurance": (CategoryType.EXPENSE, True),
    "Salary": (CategoryType.INCOME, False),
    "Savings": (CategoryType.SAVINGS, False),
}

RULES = {
    "Swiggy": "Food",
    "Zomato": "Food",
    "Uber": "Transportation",
    "Ola": "Transportation",
    "Netflix": "Entertainment",
    "Spotify": "Entertainment",
    "Amazon": "Shopping",
    "Rent": "Housing",
    "Electricity": "Utilities",
    "Internet": "Utilities",
    "Groceries": "Groceries",
    "Insurance": "Insurance",
}

MONTHLY_TRANSACTIONS = [
    ("Rent", "Apartment rent", Decimal("18500")),
    ("Electricity", "Electricity bill", Decimal("1450")),
    ("Internet", "Home internet", Decimal("899")),
    ("Groceries", "Weekly groceries", Decimal("6800")),
    ("Swiggy", "Dinner delivery", Decimal("850")),
    ("Zomato", "Weekend meal", Decimal("620")),
    ("Uber", "Ride to office", Decimal("760")),
    ("Ola", "Airport ride", Decimal("540")),
    ("Amazon", "Household purchase", Decimal("1450")),
    ("Netflix", "Monthly streaming plan", Decimal("199")),
    ("Spotify", "Music subscription", Decimal("119")),
    ("Insurance", "Health insurance premium", Decimal("1800")),
]


def shifted_month(today: date, months_back: int) -> tuple[int, int]:
    month_index = today.year * 12 + today.month - 1 - months_back
    year, month_zero_based = divmod(month_index, 12)
    return year, month_zero_based + 1


def date_after_months(today: date, months_ahead: int) -> date:
    year, month = shifted_month(today, -months_ahead)
    return date(year, month, min(today.day, monthrange(year, month)[1]))


def seed() -> int:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(func.lower(User.email) == DEMO_EMAIL))
        if user is not None and (not user.is_demo or user.password_hash):
            raise RuntimeError("Demo email belongs to a non-demo account; seeding refused without modifying it")
        if user is None:
            user = User(name=DEMO_NAME, email=DEMO_EMAIL, normalized_email=DEMO_EMAIL, age=26, is_demo=True, onboarding_completed=True)
            db.add(user)
            db.flush()
        else:
            user.name = DEMO_NAME
            user.age = 26

        user.is_demo = True
        user.onboarding_completed = True
        user.normalized_email = DEMO_EMAIL

        categories: dict[str, Category] = {}
        for name, (category_type, is_essential) in CATEGORIES.items():
            category = db.scalar(
                select(Category).where(Category.name == name, Category.type == category_type)
            )
            if category is None:
                category = Category(name=name, type=category_type, is_essential=is_essential)
                db.add(category)
                db.flush()
            categories[name] = category

        profile = db.scalar(select(FinancialProfile).where(FinancialProfile.user_id == user.id))
        profile_values = {
            "monthly_income": Decimal("65000"),
            "other_income": Decimal("0"),
            "current_savings": Decimal("120000"),
            "emergency_savings": Decimal("55000"),
            "monthly_debt_payment": Decimal("5000"),
            "total_debt": Decimal("120000"),
            "dependents": 0,
            "risk_tolerance": RiskTolerance.MODERATE,
            "emergency_fund_target_months": 6,
        }
        if profile is None:
            db.add(FinancialProfile(user_id=user.id, **profile_values))
        else:
            for field, value in profile_values.items():
                setattr(profile, field, value)

        preference = db.scalar(
            select(InvestmentPreference).where(InvestmentPreference.user_id == user.id)
        )
        preference_values = {
            "risk_tolerance": RiskTolerance.MODERATE,
            "liquidity_requirement": "MEDIUM",
            "preferred_time_horizon": 10,
        }
        if preference is None:
            db.add(InvestmentPreference(user_id=user.id, **preference_values))
        else:
            for field, value in preference_values.items():
                setattr(preference, field, value)

        for pattern, category_name in RULES.items():
            rule = db.scalar(
                select(MerchantRule).where(
                    func.lower(MerchantRule.merchant_pattern) == pattern.casefold(), MerchantRule.user_id.is_(None)
                )
            )
            if rule is None:
                db.add(
                    MerchantRule(
                        merchant_pattern=pattern,
                        category_id=categories[category_name].id,
                        confidence=Decimal("0.98"),
                    )
                )
            else:
                rule.category_id = categories[category_name].id

        today = date.today()
        for months_back in range(2, -1, -1):
            year, month = shifted_month(today, months_back)
            transaction_date = date(year, month, min(5, monthrange(year, month)[1]))
            for index, (merchant, description, amount) in enumerate(MONTHLY_TRANSACTIONS):
                seed_key = f"demo-seed:{year}-{month:02d}:{index}:{merchant}"
                existing = db.scalar(
                    select(Transaction).where(
                        Transaction.user_id == user.id,
                        Transaction.notes == seed_key,
                    )
                )
                if existing is None:
                    db.add(
                        Transaction(
                            user_id=user.id,
                            date=transaction_date,
                            description=description,
                            merchant=merchant,
                            amount=amount,
                            transaction_type=TransactionType.EXPENSE,
                            category_id=categories[RULES[merchant]].id,
                            notes=seed_key,
                        )
                    )

            savings_key = f"demo-seed:{year}-{month:02d}:savings"
            existing_savings = db.scalar(
                select(Transaction).where(
                    Transaction.user_id == user.id,
                    Transaction.notes == savings_key,
                )
            )
            if existing_savings is None:
                db.add(
                    Transaction(
                        user_id=user.id,
                        date=transaction_date,
                        description="Monthly savings transfer",
                        merchant="Savings Transfer",
                        amount=Decimal("5000"),
                        transaction_type=TransactionType.SAVINGS,
                        category_id=categories["Savings"].id,
                        notes=savings_key,
                    )
                )

        goal_values = [
            ("Emergency Fund", GoalType.EMERGENCY_FUND, Decimal("150000"), Decimal("55000"), Decimal("8000"), 1, 12),
            ("Japan Travel", GoalType.TRAVEL, Decimal("90000"), Decimal("18000"), Decimal("5000"), 2, 18),
            ("Long-Term Wealth", GoalType.LONG_TERM_WEALTH, Decimal("600000"), Decimal("120000"), Decimal("7000"), 3, 120),
        ]
        for name, goal_type, target, current, contribution, priority, target_months in goal_values:
            goal = db.scalar(
                select(Goal).where(
                    Goal.user_id == user.id,
                    Goal.name == name,
                    Goal.goal_type == goal_type,
                )
            )
            values = {
                "target_amount": target,
                "current_amount": current,
                "target_date": date_after_months(today, target_months),
                "monthly_contribution": contribution,
                "priority": priority,
            }
            if goal is None:
                db.add(Goal(user_id=user.id, name=name, goal_type=goal_type, **values))
            else:
                for field, value in values.items():
                    setattr(goal, field, value)

        for category_name, limit in (
            ("Housing", Decimal("20000")),
            ("Food", Decimal("4500")),
            ("Transportation", Decimal("4000")),
            ("Groceries", Decimal("8000")),
            ("Entertainment", Decimal("1000")),
        ):
            budget = db.scalar(
                select(Budget).where(
                    Budget.user_id == user.id,
                    Budget.category_id == categories[category_name].id,
                    Budget.month == today.month,
                    Budget.year == today.year,
                )
            )
            if budget is None:
                db.add(
                    Budget(
                        user_id=user.id,
                        category_id=categories[category_name].id,
                        monthly_limit=limit,
                        month=today.month,
                        year=today.year,
                    )
                )
            else:
                budget.monthly_limit = limit

        db.commit()
        print(f"Seeded synthetic demo user {DEMO_EMAIL} (id={user.id})")
        return user.id


if __name__ == "__main__":
    seed()
