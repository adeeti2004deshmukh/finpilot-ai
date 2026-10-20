from app.services.auth import get_current_user
from app.models.entities import User
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select, or_
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.entities import Category, MerchantRule
from app.models.enums import CategoryType
from app.schemas.merchant_rules import MerchantRuleCreate, MerchantRuleResponse, MerchantRuleUpdate

router = APIRouter(prefix="/api/merchant-rules", tags=["Merchant Rules"])


def validate_rule_category(db: Session, category_id: int) -> None:
    category = db.get(Category, category_id)
    if category is None or category.type != CategoryType.EXPENSE:
        raise HTTPException(status_code=400, detail="Merchant rule category must be an existing expense category")


def ensure_unique_pattern(db: Session, merchant_pattern: str, exclude_id: int | None = None, user_id: int | None = None) -> None:
    query = select(MerchantRule).where(func.lower(MerchantRule.merchant_pattern) == merchant_pattern.casefold(), MerchantRule.user_id == user_id)
    if exclude_id is not None:
        query = query.where(MerchantRule.id != exclude_id)
    if db.scalar(query) is not None:
        raise HTTPException(status_code=409, detail="A merchant rule already exists for this pattern")


@router.get("", response_model=list[MerchantRuleResponse], summary="List merchant categorization rules")
def list_rules(db: Session = Depends(get_db), actor: User = Depends(get_current_user)) -> list[MerchantRule]:
    return db.scalars(select(MerchantRule).where(or_(MerchantRule.user_id.is_(None), MerchantRule.user_id == actor.id)).order_by(MerchantRule.merchant_pattern)).all()


@router.post("", response_model=MerchantRuleResponse, status_code=201, summary="Create a merchant rule")
def create_rule(payload: MerchantRuleCreate, db: Session = Depends(get_db), actor: User = Depends(get_current_user)) -> MerchantRule:
    validate_rule_category(db, payload.category_id)
    ensure_unique_pattern(db, payload.merchant_pattern, user_id=actor.id)
    rule = MerchantRule(**payload.model_dump(), user_id=actor.id)
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.put("/{rule_id}", response_model=MerchantRuleResponse, summary="Update a merchant rule")
def update_rule(rule_id: int, payload: MerchantRuleUpdate, db: Session = Depends(get_db)) -> MerchantRule:
    rule = db.get(MerchantRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Merchant rule not found")
    changes = payload.model_dump(exclude_unset=True)
    if "merchant_pattern" in changes:
        ensure_unique_pattern(db, changes["merchant_pattern"], exclude_id=rule_id, user_id=rule.user_id)
    if "category_id" in changes:
        validate_rule_category(db, changes["category_id"])
    for field, value in changes.items():
        if value is None:
            raise HTTPException(status_code=422, detail=f"{field} cannot be null")
        setattr(rule, field, value)
    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a merchant rule")
def delete_rule(rule_id: int, db: Session = Depends(get_db)) -> Response:
    rule = db.get(MerchantRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Merchant rule not found")
    db.delete(rule)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)