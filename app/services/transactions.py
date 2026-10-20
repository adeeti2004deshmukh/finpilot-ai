from fastapi import HTTPException, status
from sqlalchemy import select, or_
from sqlalchemy.orm import Session

from app.models.entities import Category, MerchantRule, Transaction, User
from app.models.enums import CategoryType, TransactionType


def matching_category_id(db: Session, merchant: str, user_id: int | None = None) -> int | None:
    normalized_merchant = merchant.casefold()
    rules = db.scalars(select(MerchantRule).where(or_(MerchantRule.user_id.is_(None), MerchantRule.user_id == user_id))).all()
    matches = [rule for rule in rules if rule.merchant_pattern.casefold() in normalized_merchant]
    if not matches:
        return None
    matches.sort(key=lambda rule: (rule.user_id is not None, len(rule.merchant_pattern), rule.confidence), reverse=True)
    return matches[0].category_id


def validate_category(
    db: Session,
    category_id: int | None,
    transaction_type: TransactionType,
) -> int | None:
    if category_id is None:
        return None
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Category not found")
    expected_type = CategoryType(transaction_type.value)
    if category.type != expected_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Category type must match transaction_type",
        )
    return category_id


def categorize_transaction(
    db: Session,
    merchant: str,
    transaction_type: TransactionType,
    supplied_category_id: int | None,
    user_id: int | None = None,
) -> int | None:
    rule_category_id = matching_category_id(db, merchant, user_id) if transaction_type == TransactionType.EXPENSE else None
    category_id = supplied_category_id if supplied_category_id is not None else rule_category_id
    return validate_category(db, category_id, transaction_type)


def require_user(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def require_transaction(db: Session, transaction_id: int) -> Transaction:
    transaction = db.get(Transaction, transaction_id)
    if transaction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    return transaction