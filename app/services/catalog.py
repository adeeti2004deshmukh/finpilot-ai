"""Shared public category/rule knowledge; never copy any user's financial records."""
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.entities import Category, MerchantRule
from app.models.enums import CategoryType

CATEGORIES = {
    "Housing": ("EXPENSE", True), "Food & Dining": ("EXPENSE", False), "Groceries": ("EXPENSE", True),
    "Transport": ("EXPENSE", False), "Shopping": ("EXPENSE", False), "Utilities": ("EXPENSE", True),
    "Entertainment": ("EXPENSE", False), "Healthcare": ("EXPENSE", True), "Insurance": ("EXPENSE", True),
    "Education": ("EXPENSE", False), "Travel": ("EXPENSE", False), "Subscriptions": ("EXPENSE", False),
    "Debt Payment": ("EXPENSE", False), "Other": ("EXPENSE", False), "Salary": ("INCOME", False),
    "Freelance": ("INCOME", False), "Bonus": ("INCOME", False), "Interest": ("INCOME", False),
    "Other Income": ("INCOME", False), "Savings": ("SAVINGS", False),
}


def ensure_catalog(db: Session):
    categories = {}
    for name, (kind, essential) in CATEGORIES.items():
        category = db.scalar(select(Category).where(Category.name == name, Category.type == CategoryType(kind)))
        if category is None:
            category = Category(name=name, type=CategoryType(kind), is_essential=essential)
            db.add(category)
            db.flush()
        categories[name] = category
    for merchant, name in {"Swiggy": "Food & Dining", "Zomato": "Food & Dining", "Uber": "Transport", "Netflix": "Subscriptions"}.items():
        if not db.scalar(select(MerchantRule).where(MerchantRule.user_id.is_(None), MerchantRule.merchant_pattern == merchant)):
            db.add(MerchantRule(user_id=None, merchant_pattern=merchant, category_id=categories[name].id, confidence=1))
